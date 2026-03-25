# -*- coding: utf-8 -*-
"""
train_dien.py — DIEN 精排模型训练

模型：Deep Interest Evolution Network（Zhou et al. AAAI 2019）
  - 兴趣提取层（IEL）：GRU + 辅助损失（预测用户下一首歌）
  - 兴趣演化层（AUGRU）：注意力门控 GRU，候选歌曲作为查询向量
  - 预测 MLP：h_final + 候选嵌入 + 静态稀疏/稠密特征 → 二分类

输入文件：
  Mode/features_v3.pkl   — 与 DeepFM/LightGBM 共用特征矩阵
  Mode/features_seq.pkl  — 用户行为序列（由 prepare_features_v3.py Step 6 生成）

输出文件：
  Mode/dien/dien_model.pth        — 最佳模型权重（state_dict）
  Mode/dien/model_config.pkl      — 模型架构配置（供 build_ensemble.py 重建模型）
  Mode/dien/training_progress.png — 训练曲线（Loss / AUC / LR）
  Mode/dien/dien_metrics.csv      — 逐 epoch 指标（论文附录用）

目标：单模型 Val AUC ≥ 0.770，集成后 ≥ 0.800

GPU 加速策略：
  - AMP FP16 混合精度（autocast + GradScaler）
  - DataLoader num_workers=4 CPU 预取 + pin_memory=True 锁页内存
  - 非阻塞 DMA：tensor.to(device, non_blocking=True)
  - Windows 跳过 torch.compile（Triton 不支持）

作者：MusicMode 推荐系统
"""

import os
import sys
import pickle
import time
import numpy as np
import pandas as pd
from tqdm import tqdm
from datetime import datetime
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import warnings
warnings.filterwarnings('ignore')

# 在 torch 导入前完成所有标准库导入，避免 CUDA 初始化影响 fork
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.utils.data as Data
from torch.amp import autocast, GradScaler
from torch.optim import Adam
from torch.optim.lr_scheduler import ReduceLROnPlateau
from sklearn.metrics import roc_auc_score, log_loss

# ============================================================
# 路径配置
# ============================================================

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
MODE_DIR    = os.path.join(os.path.dirname(PROJECT_DIR), "Mode")

INPUT_FEATURES = os.path.join(MODE_DIR, "features_v3.pkl")
INPUT_SEQ      = os.path.join(MODE_DIR, "features_seq.pkl")
DIEN_DIR       = os.path.join(MODE_DIR, "dien")
os.makedirs(DIEN_DIR, exist_ok=True)
OUTPUT_MODEL   = os.path.join(DIEN_DIR, "dien_model.pth")
OUTPUT_CONFIG  = os.path.join(DIEN_DIR, "model_config.pkl")
OUTPUT_PLOT    = os.path.join(DIEN_DIR, "training_progress.png")
OUTPUT_HISTORY = os.path.join(DIEN_DIR, "dien_metrics.csv")

# ============================================================
# 超参数配置（每项均附中文说明及取值依据）
# ============================================================

# ─── 序列与模型结构 ───
SEQ_LEN       = 50    # 用户历史序列长度；平均历史 217 条/用户，取最近 50 首捕捉近期兴趣，避免早期噪声
GRU_HIDDEN    = 64    # GRU 隐状态维度；32 表达力不足，128 过拟合风险升高，64 是经验最优
EMBEDDING_DIM = 32    # Embedding 向量维度；与 DeepFM 保持一致，确保特征空间可比性
LAMBDA_AUX    = 0.05  # 辅助损失权重；
L2_EMB        = 3e-4  # Embedding L2 正则系数；

# ─── 训练流程 ───
BATCH_SIZE          = 4096  # 每批样本数；
EPOCHS              = 40    # 最大训练轮数；
LR                  = 2e-4  # 初始学习率；GRU 对 LR 敏感，5e-4 过高易快速过拟合，2e-4 更稳定
LR_PATIENCE         = 3     # ReduceLROnPlateau 触发条件
LR_FACTOR           = 0.5   # LR 衰减因子；每次触发后 LR × 0.5，温和下降避免跌入局部最优
LR_MIN              = 1e-5  # LR 下限；
EARLY_STOP_PATIENCE = 20    # 早停耐心；增大至 20 给模型更多时间走出局部平台
VALID_RATIO         = 0.1   # 验证集比例；与 LightGBM/DeepFM 保持一致，确保评估口径统一
MIN_INTERACTIONS    = 5     # 最少交互数过滤；用户历史 <5 条则不进入验证集，与 DeepFM 一致
NUM_WORKERS         = 2     # DataLoader 工作进程；
RANDOM_SEED         = 42    # 随机种子；保证实验在相同环境下可复现

# ─── MLP Dropout ───
DROPOUT1 = 0.5  # MLP 第一层 Dropout；

DROPOUT2 = 0.3  # MLP 第二层 Dropout；保持 0.3，渐进式衰减，靠近输出层正则化强度适度降低

# ============================================================
# 特征列定义（与 train_deepfm_v3.py 完全一致，保证数据对齐）
# ============================================================

# 格式：(特征名, pkl编码键, pkl基数键, embedding维度)
# 注：song_id 由 seq_song_emb 表单独处理（序列 + 候选共享），仍保留在此供 n_key 读取
SPARSE_FEAT_SPECS = [
    ("user_id",         "user_id_encoded",         "n_users",        EMBEDDING_DIM),
    ("song_id",         "song_id_encoded",          "n_songs",        EMBEDDING_DIM),
    ("genre",           "genre_encoded",            "n_genres",       EMBEDDING_DIM),
    ("language",        "language_encoded",         "n_languages",    EMBEDDING_DIM),
    ("artist",          "artist_encoded",           "n_artists",      EMBEDDING_DIM),
    ("origin_country",  "origin_country_encoded",   "n_countries",    EMBEDDING_DIM),
    ("year_bucket",     "year_bucket_encoded",      "n_year_buckets", EMBEDDING_DIM),
    ("source_channel",  "source_channel_encoded",   "n_sources",      EMBEDDING_DIM),
    ("city",            "city_encoded",             "n_cities",       EMBEDDING_DIM),
    ("gender",          "gender_encoded",           "n_genders",      EMBEDDING_DIM),
    ("age_bucket",      "age_bucket_encoded",       "n_age_buckets",  EMBEDDING_DIM),
    ("tenure_bucket",   "tenure_bucket_encoded",    "n_tenures",      EMBEDDING_DIM),
    ("duration_bucket", "duration_bucket_encoded",  "n_dur_buckets",  EMBEDDING_DIM),
    ("user_peak_hour",  "user_peak_hour_encoded",   "n_peak_hours",   EMBEDDING_DIM),
]

# 其他 13 个稀疏特征（排除 song_id，song_id 由 seq_song_emb 覆盖）
OTHER_SPARSE_SPECS = [s for s in SPARSE_FEAT_SPECS if s[0] != "song_id"]

# 稠密特征列表（与 train_deepfm_v3.py 完全一致）
DENSE_FEAT_SPECS = [
    "user_play_count_log",
    "user_avg_completion",
    "song_play_count_log",
    "song_avg_completion",
    "song_unique_users_log",
    "song_age_days_log",
    "user_genre_match",
    "user_artist_match",
    "user_language_match",
    "user_country_match",
    "user_skip_rate",
    "song_skip_rate",
    "hour_match",
    "days_since_artist_log",
    *[f"svd_user_song_{i}" for i in [0, 2, 3, 4, 5, 6, 9]],
    *[f"svd_song_user_{i}" for i in range(10)],
    *[f"svd_user_artist_{i}" for i in [0, 3, 4]],
    "svd_dot_score",
    "user_history_position",
]


# ============================================================
# 工具函数（复用 train_deepfm_v3.py 模式）
# ============================================================

def set_seed(seed: int = RANDOM_SEED) -> None:
    """固定所有随机种子，保证实验可复现"""
    import random
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark     = False


def check_gpu() -> torch.device:
    """
    检测 GPU 可用性，打印设备信息，返回 torch.device。

    Returns:
        device: cuda 或 cpu
    """
    if torch.cuda.is_available():
        name = torch.cuda.get_device_name(0)
        vram = torch.cuda.get_device_properties(0).total_memory / 1024 ** 3
        print(f"\n✅ GPU: {name}  ({vram:.1f} GB VRAM)")
        print(f"   PyTorch {torch.__version__}  CUDA {torch.version.cuda}")
        print(f"   AMP (FP16 混合精度) 已启用")
        return torch.device('cuda')
    else:
        print("⚠️  CUDA 不可用，回退 CPU（训练会较慢）")
        return torch.device('cpu')


# ============================================================
# Step 1: 加载数据
# ============================================================

def load_data():
    """
    加载特征矩阵（features_v3.pkl）和用户行为序列（features_seq.pkl）。

    Returns:
        feat (dict): 特征字典，包含 target / 各编码特征 / n_xxx 基数 等
        seq  (dict): 序列字典，含 seq_song_ids(N,50) / seq_lengths(N,) / seq_len

    Raises:
        SystemExit: 文件不存在或行数不一致时直接退出并提示用户
    """
    print("\n" + "=" * 62)
    print("📂 [Step 1/4] 加载特征数据与序列数据")
    print("=" * 62)

    for path, hint in [
        (INPUT_FEATURES, "python prepare_features_v3.py"),
        (INPUT_SEQ,      "python prepare_features_v3.py（会自动执行 Step 6）"),
    ]:
        if not os.path.exists(path):
            print(f"❌ 文件不存在: {path}")
            print(f"   请先运行: {hint}")
            sys.exit(1)

    with open(INPUT_FEATURES, "rb") as f:
        feat = pickle.load(f)
    with open(INPUT_SEQ, "rb") as f:
        seq = pickle.load(f)

    n_feat = len(feat["target"])
    n_seq  = len(seq["seq_song_ids"])
    if n_feat != n_seq:
        print(f"❌ 特征行数({n_feat:,}) 与序列行数({n_seq:,}) 不一致！")
        print("   请重新运行 prepare_features_v3.py 重新生成两个文件")
        sys.exit(1)

    print(f"   ✅ features_v3.pkl：{n_feat:,} 条样本，正样本率={feat['target'].mean():.4f}")
    print(f"   ✅ features_seq.pkl：seq_len={seq['seq_len']}")
    for _, _, n_key, _ in SPARSE_FEAT_SPECS:
        if n_key in feat:
            print(f"   {n_key:<20} = {feat[n_key]:,}")

    return feat, seq


# ============================================================
# Step 2: 数据集 & DataLoader
# ============================================================

class DIENDataset(Data.Dataset):
    """
    DIEN 专用 PyTorch Dataset，返回 6 元组供 DataLoader 批量加载。

    元组结构：
      other_sparse : (13,)  int32  — 除 song_id 外的 13 个稀疏特征 ID
      cand_song_id : ()     int32  — 候选歌曲 ID（已 +1 偏移，与序列 Embedding 表对齐）
      dense_vals   : (D,)   float32 — 稠密特征向量（D 个维度，D≈36）
      hist_seq     : (T,)   int32  — 用户历史序列（0=padding，有效 ID≥1）
      seq_length   : ()     int32  — 真实有效历史长度（上限 SEQ_LEN）
      target       : ()     float32 — 收听标签（1=30天内重播，0=否）

    Args:
        other_sparse  (np.ndarray): (N, 13) int32
        cand_song_ids (np.ndarray): (N,)    int32
        dense_vals    (np.ndarray): (N, D)  float32
        hist_seq      (np.ndarray): (N, T)  int32
        seq_lengths   (np.ndarray): (N,)    int32
        targets       (np.ndarray): (N,)    float32
    """

    def __init__(self, other_sparse, cand_song_ids, dense_vals,
                 hist_seq, seq_lengths, targets):
        self.other_sparse  = torch.from_numpy(other_sparse.astype(np.int32))
        self.cand_song_ids = torch.from_numpy(cand_song_ids.astype(np.int32))
        self.dense_vals    = torch.from_numpy(dense_vals.astype(np.float32))
        self.hist_seq      = torch.from_numpy(hist_seq.astype(np.int32))
        self.seq_lengths   = torch.from_numpy(seq_lengths.astype(np.int32))
        self.targets       = torch.from_numpy(targets.astype(np.float32))

    def __len__(self) -> int:
        return len(self.targets)

    def __getitem__(self, idx):
        return (
            self.other_sparse[idx],
            self.cand_song_ids[idx],
            self.dense_vals[idx],
            self.hist_seq[idx],
            self.seq_lengths[idx],
            self.targets[idx],
        )


def prepare_dien_data(feat: dict, seq: dict):
    """
    数据预处理：时序切分 + 低频过滤 + user_history_position + OOF TE + 构建 DataLoader。

    时序切分（无泄漏）：与 train_deepfm_v3.py L249-265 完全相同的逻辑，
    保证三个模型在同一验证集上评估，确保 AUC 指标可横向对比。

    Args:
        feat (dict): features_v3.pkl 内容
        seq  (dict): features_seq.pkl 内容

    Returns:
        train_loader (DataLoader): 训练 DataLoader
        val_loader   (DataLoader): 验证 DataLoader
        feat_config  (dict): 模型初始化所需的配置信息
    """
    print("\n" + "=" * 62)
    print("⚙️  [Step 2/4] 数据预处理 & 构建 DataLoader")
    print("=" * 62)

    n_samples = len(feat["target"])
    target    = feat["target"].astype(np.float32)

    # ── 用户级时序切分（与 DeepFM 完全一致）
    # 无泄漏：按 (uid, time) 升序，每用户最后 10% 为验证集
    play_time_unix = feat.get("play_time_unix", np.zeros(n_samples, dtype=np.int64))
    _uid_arr       = feat["user_id_encoded"].astype(np.int32)
    _df_meta = pd.DataFrame({
        "orig_idx": np.arange(n_samples),
        "uid":      _uid_arr,
        "time":     play_time_unix,
    }).sort_values(["uid", "time"])
    _df_meta["_cnt"]  = _df_meta.groupby("uid")["uid"].transform("count")
    _df_meta["_rank"] = _df_meta.groupby("uid").cumcount()
    _n_val_vec = (_df_meta["_cnt"] * VALID_RATIO).astype(int).clip(lower=1)
    _is_val    = (
        (_df_meta["_cnt"] >= MIN_INTERACTIONS) &
        (_df_meta["_rank"] >= _df_meta["_cnt"] - _n_val_vec)
    )
    train_idx = _df_meta.loc[~_is_val, "orig_idx"].values
    val_idx   = _df_meta.loc[ _is_val, "orig_idx"].values
    print(f"   时序切分：训练 {len(train_idx):,} / 验证 {len(val_idx):,}")

    # ── 低频 ID 过滤（min_count=3，仅统计训练集，与 DeepFM 一致）
    _MIN_COUNT  = 3
    user_id_enc = feat["user_id_encoded"].copy().astype(np.int32)
    song_id_enc = feat["song_id_encoded"].copy().astype(np.int32)
    _u_counts = np.bincount(user_id_enc[train_idx],
                            minlength=int(user_id_enc.max()) + 1)
    _s_counts = np.bincount(song_id_enc[train_idx],
                            minlength=int(song_id_enc.max()) + 1)
    user_id_enc[np.isin(user_id_enc, np.where(_u_counts < _MIN_COUNT)[0])] = 0
    song_id_enc[np.isin(song_id_enc, np.where(_s_counts < _MIN_COUNT)[0])] = 0
    print(f"   低频过滤：用户 {int((_u_counts < _MIN_COUNT).sum())} 个 → UNK，"
          f"歌曲 {int((_s_counts < _MIN_COUNT).sum())} 首 → UNK")

    # ── 候选歌曲 ID（+1 偏移）：song_id_enc 中 UNK=0 → 映射为索引 1（UNK 槽）
    # 序列文件中 seq_song_ids 同样为 +1 偏移，保证两者使用相同 Embedding 表
    cand_song_ids = (song_id_enc + 1).astype(np.int32)

    # ── 构建稠密特征矩阵
    dense_list   = []
    active_dense = []
    for feat_name in DENSE_FEAT_SPECS:
        if feat_name in feat or feat_name == "user_history_position":
            # user_history_position 稍后单独填充
            arr = feat.get(feat_name, np.zeros(n_samples, dtype=np.float32)).astype(np.float32)
            arr = np.nan_to_num(arr, nan=0.0, posinf=10.0, neginf=0.0)
            dense_list.append(arr.reshape(-1, 1))
            active_dense.append(feat_name)
    dense_mat = np.concatenate(dense_list, axis=1).astype(np.float32)
    n_dense   = dense_mat.shape[1]
    print(f"   稠密特征: {n_dense} 维")

    # ── 计算 user_history_position（与 DeepFM L285-291 完全相同）
    _df_meta["_seq_ratio"] = (
        _df_meta["_rank"] / (_df_meta["_cnt"] - 1).clip(lower=1)
    ).clip(0, 1).astype(np.float32)
    _seq_ratio_all = np.zeros(n_samples, dtype=np.float32)
    _seq_ratio_all[_df_meta["orig_idx"].values] = _df_meta["_seq_ratio"].values
    _hp_idx = next((i for i, fn in enumerate(active_dense)
                    if fn == "user_history_position"), None)
    if _hp_idx is not None:
        dense_mat[:, _hp_idx] = _seq_ratio_all

    # ── 构建 OTHER_SPARSE 特征矩阵（13 维，不含 song_id）
    sparse_list   = []
    active_sparse = []
    for feat_name, enc_key, n_key, _ in OTHER_SPARSE_SPECS:
        if enc_key in feat and n_key in feat:
            arr = feat[enc_key].astype(np.int32)
            sparse_list.append(arr.reshape(-1, 1))
            active_sparse.append((feat_name, enc_key, n_key))
    other_sparse_mat = np.concatenate(sparse_list, axis=1).astype(np.int32) \
        if sparse_list else np.zeros((n_samples, 1), dtype=np.int32)
    # 将低频过滤后的 user_id 写回 other_sparse_mat
    _uid_col = next((i for i, (fn, _, _) in enumerate(active_sparse)
                     if fn == "user_id"), None)
    if _uid_col is not None:
        other_sparse_mat[:, _uid_col] = user_id_enc
    print(f"   其他稀疏特征: {len(active_sparse)} 维（song_id 由 seq_song_emb 处理）")

    # ── 5 折 OOF Target Encoding（user×genre/language/country_match，防 target leakage）
    # 完全复用 train_deepfm_v3.py L298-378 逻辑
    train_target  = target[train_idx]
    _global_prior = float(train_target.mean())
    _uid  = feat["user_id_encoded"]
    _gnr  = feat.get("genre_encoded",          np.zeros(n_samples, dtype=np.int32))
    _lng  = feat.get("language_encoded",       np.zeros(n_samples, dtype=np.int32))
    _ctr  = feat.get("origin_country_encoded", np.zeros(n_samples, dtype=np.int32))
    _SM   = 100  # 贝叶斯平滑强度 M；值越大越向全局先验收缩，抑制稀疏组合的噪声
    _NOOF = 5    # OOF 折数；5 折在样本量 660 万下计算成本可接受

    print(f"   🎯 5折 OOF Target Encoding（global_prior={_global_prior:.4f}）...")
    _fold_edges = np.linspace(0, len(train_idx), _NOOF + 1, dtype=int)
    _ug_oof = np.full(n_samples, _global_prior, dtype=np.float32)
    _ul_oof = np.full(n_samples, _global_prior, dtype=np.float32)
    _uc_oof = np.full(n_samples, _global_prior, dtype=np.float32)

    for _k in range(_NOOF):
        _fold_mask  = np.zeros(len(train_idx), dtype=bool)
        _fold_mask[_fold_edges[_k]:_fold_edges[_k + 1]] = True
        _other_idx  = train_idx[~_fold_mask]
        _this_idx   = train_idx[_fold_mask]

        _om = pd.DataFrame({
            "uid": _uid[_other_idx].astype(np.int32),
            "gnr": _gnr[_other_idx].astype(np.int32),
            "lng": _lng[_other_idx].astype(np.int32),
            "ctr": _ctr[_other_idx].astype(np.int32),
            "y":   target[_other_idx],
        })
        def _smooth(df, keys, col_name):
            g = df.groupby(keys)["y"].agg(["count", "mean"]).reset_index()
            g[col_name] = (g["count"] * g["mean"] + _SM * _global_prior) / (g["count"] + _SM)
            return g

        _ug_o = _smooth(_om, ["uid", "gnr"], "te")
        _ul_o = _smooth(_om, ["uid", "lng"], "te")
        _uc_o = _smooth(_om, ["uid", "ctr"], "te")

        _tf = pd.DataFrame({
            "uid": _uid[_this_idx].astype(np.int32),
            "gnr": _gnr[_this_idx].astype(np.int32),
            "lng": _lng[_this_idx].astype(np.int32),
            "ctr": _ctr[_this_idx].astype(np.int32),
        })
        _tf = _tf.merge(_ug_o[["uid", "gnr", "te"]].rename(columns={"te": "ug_te"}),
                        on=["uid", "gnr"], how="left")
        _tf = _tf.merge(_ul_o[["uid", "lng", "te"]].rename(columns={"te": "ul_te"}),
                        on=["uid", "lng"], how="left")
        _tf = _tf.merge(_uc_o[["uid", "ctr", "te"]].rename(columns={"te": "uc_te"}),
                        on=["uid", "ctr"], how="left")
        _ug_oof[_this_idx] = _tf["ug_te"].fillna(_global_prior).values.astype(np.float32)
        _ul_oof[_this_idx] = _tf["ul_te"].fillna(_global_prior).values.astype(np.float32)
        _uc_oof[_this_idx] = _tf["uc_te"].fillna(_global_prior).values.astype(np.float32)

    # 验证集：全量训练统计回填（无泄漏：验证集不参与统计）
    _fm = pd.DataFrame({
        "uid": _uid[train_idx].astype(np.int32),
        "gnr": _gnr[train_idx].astype(np.int32),
        "lng": _lng[train_idx].astype(np.int32),
        "ctr": _ctr[train_idx].astype(np.int32),
        "y":   train_target,
    })
    _ug_s = _smooth(_fm, ["uid", "gnr"], "te")
    _ul_s = _smooth(_fm, ["uid", "lng"], "te")
    _uc_s = _smooth(_fm, ["uid", "ctr"], "te")
    _vf = pd.DataFrame({
        "uid": _uid[val_idx].astype(np.int32),
        "gnr": _gnr[val_idx].astype(np.int32),
        "lng": _lng[val_idx].astype(np.int32),
        "ctr": _ctr[val_idx].astype(np.int32),
    })
    _vf = _vf.merge(_ug_s[["uid", "gnr", "te"]].rename(columns={"te": "ug_te"}),
                    on=["uid", "gnr"], how="left")
    _vf = _vf.merge(_ul_s[["uid", "lng", "te"]].rename(columns={"te": "ul_te"}),
                    on=["uid", "lng"], how="left")
    _vf = _vf.merge(_uc_s[["uid", "ctr", "te"]].rename(columns={"te": "uc_te"}),
                    on=["uid", "ctr"], how="left")

    # 将 OOF TE 结果写入 dense_mat 对应列
    for _arr_train, _arr_val_col, _col_name in [
        (_ug_oof, "ug_te", "user_genre_match"),
        (_ul_oof, "ul_te", "user_language_match"),
        (_uc_oof, "uc_te", "user_country_match"),
    ]:
        _ci = next((i for i, fn in enumerate(active_dense) if fn == _col_name), None)
        if _ci is not None:
            dense_mat[train_idx, _ci] = _arr_train[train_idx]
            dense_mat[val_idx,   _ci] = _vf[_arr_val_col].fillna(_global_prior).values.astype(np.float32)
    print(f"   ✅ OOF TE 完成")

    # ── 提取序列数据
    seq_song_ids = seq["seq_song_ids"].astype(np.int32)                        # (N, T)
    seq_lengths  = np.minimum(seq["seq_lengths"], SEQ_LEN).astype(np.int32)   # (N,)

    # ── 构建 Dataset
    def _make_ds(idx):
        return DIENDataset(
            other_sparse  = other_sparse_mat[idx],
            cand_song_ids = cand_song_ids[idx],
            dense_vals    = dense_mat[idx],
            hist_seq      = seq_song_ids[idx],
            seq_lengths   = seq_lengths[idx],
            targets       = target[idx],
        )

    train_loader = Data.DataLoader(
        _make_ds(train_idx),
        batch_size=BATCH_SIZE,
        shuffle=True,
        num_workers=NUM_WORKERS,
        pin_memory=True,
        persistent_workers=(NUM_WORKERS > 0),
        prefetch_factor=2 if NUM_WORKERS > 0 else None,
    )
    val_loader = Data.DataLoader(
        _make_ds(val_idx),
        batch_size=BATCH_SIZE * 4,
        shuffle=False,
        num_workers=0,
        pin_memory=False,
    )
    print(f"\n   训练: {len(train_idx):,} 样本  |  验证: {len(val_idx):,} 样本")
    print(f"   训练正样本率: {train_target.mean():.4f}")

    # ── feat_config 供模型初始化使用
    feat_config = {
        "n_sparse":      len(active_sparse),
        "n_dense":       n_dense,
        "active_sparse": active_sparse,
        "active_dense":  active_dense,
        "seq_len":       SEQ_LEN,
    }
    for _, _, n_key, _ in SPARSE_FEAT_SPECS:
        if n_key in feat:
            feat_config[n_key] = int(feat[n_key])

    return train_loader, val_loader, feat_config


# ============================================================
# DIEN 模型定义
# ============================================================

class AUGRU(nn.Module):
    """
    Attention-based Update Gate RNN（AUGRU）—— DIEN 兴趣演化层。

    核心思想：将标准 GRU 的更新门乘以当前时刻对候选歌曲的注意力权重，
    使兴趣演化过程聚焦于与目标歌曲相关的历史行为，过滤无关噪声。

    公式（Zhou et al. AAAI 2019，公式 3-7）：
      a_t  = masked_softmax( h_t^IEL · e_proj_target / √hidden )  # 注意力权重
      r_t  = σ( W_r · [x_t, h_{t-1}] )                           # 重置门
      u_t  = σ( W_z · [x_t, h_{t-1}] )                           # 标准更新门
      ũ_t  = a_t · u_t                                            # 注意力门控更新门（AUGRU核心）
      h̃_t = tanh( W_h · [x_t, r_t ⊙ h_{t-1}] )                 # 候选新状态
      h_t  = (1 - ũ_t) ⊙ h_{t-1} + ũ_t ⊙ h̃_t                  # 最终状态

    Args:
        input_dim  (int): 输入维度（= EMBEDDING_DIM = 32）
        hidden_dim (int): 隐状态维度（= GRU_HIDDEN = 64）
    """

    def __init__(self, input_dim: int, hidden_dim: int):
        super().__init__()
        self.hidden_dim  = hidden_dim
        combined_dim     = input_dim + hidden_dim  # 拼接后的输入维度

        # GRU 三门线性变换（输入 = [x_t, h_{t-1}]）
        self.W_r = nn.Linear(combined_dim, hidden_dim, bias=True)   # 重置门权重
        self.W_z = nn.Linear(combined_dim, hidden_dim, bias=True)   # 更新门权重
        self.W_h = nn.Linear(combined_dim, hidden_dim, bias=True)   # 候选状态权重

    def forward(
        self,
        h_states:    torch.Tensor,   # (B, T, hidden_dim) — IEL-GRU 输出的所有隐状态
        e_proj:      torch.Tensor,   # (B, hidden_dim)    — 候选歌曲投影向量（用于注意力）
        hist_emb:    torch.Tensor,   # (B, T, input_dim)  — 历史序列 Embedding
        seq_lengths: torch.Tensor,   # (B,)               — 每条样本的真实序列长度
    ) -> torch.Tensor:
        """
        AUGRU 前向计算，返回最后有效时刻的隐状态。

        Returns:
            h_final (Tensor): (B, hidden_dim)
        """
        B, T, _ = h_states.shape

        # ─── Step 1: 计算注意力权重 a_t
        # e_proj: (B, hidden_dim) → unsqueeze → (B, 1, hidden_dim)
        # h_states: (B, T, hidden_dim) → 逐元素乘后求和 → (B, T)
        attn_scores = (h_states * e_proj.unsqueeze(1)).sum(dim=-1)   # (B, T)
        attn_scores = attn_scores / (self.hidden_dim ** 0.5)          # 缩放，防止梯度消失

        # ─── Step 2: Padding 掩码（将 padding 位置的注意力分数置为 -inf）
        # 无泄漏：seq_lengths 只反映当前样本已发生的历史，不含未来信息
        arange = torch.arange(T, device=h_states.device).unsqueeze(0)  # (1, T)
        pad_mask = arange >= seq_lengths.unsqueeze(1)                   # (B, T) True=padding
        attn_scores = attn_scores.masked_fill(pad_mask, float('-inf'))

        # 边界情况：若整条序列全为 padding（新用户），避免 softmax 产生 nan
        all_pad = (seq_lengths == 0)
        if all_pad.any():
            attn_scores[all_pad] = 0.0

        attn_weights = torch.softmax(attn_scores, dim=-1)  # (B, T) 归一化权重

        # ─── Step 3: AUGRU 顺序递推（T=50 步，每步一次前向矩阵乘法）
        # 初始隐状态为全 0（等效于"无历史记忆"）
        h = torch.zeros(B, self.hidden_dim,
                        device=h_states.device, dtype=h_states.dtype)

        for t in range(T):
            x_t = hist_emb[:, t, :]          # (B, input_dim) 当前时刻歌曲 Embedding
            a_t = attn_weights[:, t:t + 1]   # (B, 1) 当前时刻注意力权重（保持维度用于广播）

            xh  = torch.cat([x_t, h], dim=-1)          # (B, combined_dim) 拼接输入

            r_t = torch.sigmoid(self.W_r(xh))           # (B, hidden_dim) 重置门：遗忘旧状态的比例
            u_t = torch.sigmoid(self.W_z(xh))           # (B, hidden_dim) 标准更新门
            u_t_att = a_t * u_t                          # (B, hidden_dim) 注意力加权更新门（AUGRU 核心）

            # 候选新状态（重置门过滤旧状态后计算）
            xrh   = torch.cat([x_t, r_t * h], dim=-1)  # (B, combined_dim)
            h_hat = torch.tanh(self.W_h(xrh))           # (B, hidden_dim) 候选状态

            # 最终隐状态：attention-weighted 插值
            h = (1.0 - u_t_att) * h + u_t_att * h_hat  # (B, hidden_dim)

        # 循环结束后 h 即为最后有效时刻的隐状态
        # （padding 位置的 attn_weight ≈ 0，对状态的影响接近零）
        return h  # (B, hidden_dim)


class DIENModel(nn.Module):
    """
    完整 DIEN 模型，封装所有组件的前向传播。

    架构（从输入到输出）：
      1. seq_song_emb：Embedding(n_songs+1, 32, padding_idx=0)
         → 历史序列 hist_emb(B,T,32) + 候选歌曲 e_target(B,32)
      2. sparse_embs：13 个独立 Embedding（user_id / genre / ...）
         → sparse_concat(B, 13×32=416)
      3. dense_bn：BatchNorm1d(D) → dense_norm(B,D)
      4. gru_iel：GRU(32→64) → h_states(B,T,64) + 辅助损失
      5. target_proj：Linear(32→64) → e_proj(B,64)（注意力计算用）
      6. augru：AUGRU → h_final(B,64)
      7. MLP：[h_final|e_target|sparse_concat|dense_norm] → pred(B,)

    Args:
        feat_config (dict): prepare_dien_data 返回的配置字典
    """

    def __init__(self, feat_config: dict):
        super().__init__()

        n_songs = feat_config.get("n_songs", 50000)
        n_dense = feat_config.get("n_dense", 36)

        # ─── 序列 / 候选共享 Embedding 表（song_id 统一用此表）
        # vocab_size = n_songs + 1：0 保留为 padding token，有效 ID 范围 [1, n_songs]
        self.seq_song_emb = nn.Embedding(n_songs + 1, EMBEDDING_DIM, padding_idx=0)

        # ─── 其他 13 个稀疏特征的独立 Embedding 表
        self.sparse_embs       = nn.ModuleDict()
        self.sparse_feat_names = []
        for feat_name, _, n_key, emb_dim in OTHER_SPARSE_SPECS:
            vocab_size = feat_config.get(n_key, 1000)
            self.sparse_embs[feat_name] = nn.Embedding(vocab_size + 1, emb_dim)
            self.sparse_feat_names.append(feat_name)
        n_other_sparse = len(self.sparse_feat_names)

        # ─── 稠密特征 BatchNorm（统一量纲，加速收敛）
        self.dense_bn = nn.BatchNorm1d(n_dense)

        # ─── 兴趣提取层（IEL）：GRU
        self.gru_iel = nn.GRU(EMBEDDING_DIM, GRU_HIDDEN, batch_first=True)

        # ─── 辅助损失：将 GRU 隐状态映射回 Embedding 空间，与下一首歌做对比
        # 维度桥接：GRU_HIDDEN(64) → EMBEDDING_DIM(32)
        self.aux_proj = nn.Linear(GRU_HIDDEN, EMBEDDING_DIM, bias=False)

        # ─── 候选歌曲投影层：EMBEDDING_DIM(32) → GRU_HIDDEN(64)（AUGRU 注意力计算用）
        self.target_proj = nn.Linear(EMBEDDING_DIM, GRU_HIDDEN, bias=False)

        # ─── 兴趣演化层（IEL）：AUGRU
        self.augru = AUGRU(EMBEDDING_DIM, GRU_HIDDEN)

        # ─── 预测 MLP
        # 输入维度 = h_final(64) + e_target(32) + sparse(n_other×32) + dense(D)
        mlp_in = GRU_HIDDEN + EMBEDDING_DIM + n_other_sparse * EMBEDDING_DIM + n_dense
        self.mlp = nn.Sequential(
            nn.Linear(mlp_in, 256),
            nn.BatchNorm1d(256),
            nn.ReLU(),
            nn.Dropout(DROPOUT1),
            nn.Linear(256, 128),
            nn.BatchNorm1d(128),
            nn.ReLU(),
            nn.Dropout(DROPOUT2),
            nn.Linear(128, 1),
            # Sigmoid 移除：改用 BCEWithLogitsLoss（AMP 安全），推理时手动加 sigmoid
        )

        self._init_weights()

    def _init_weights(self):
        """Xavier 均匀初始化权重，加速初期收敛，减少随机性对实验的影响"""
        for module in self.modules():
            if isinstance(module, nn.Embedding):
                nn.init.xavier_uniform_(module.weight)
                if module.padding_idx is not None:
                    module.weight.data[module.padding_idx].zero_()
            elif isinstance(module, nn.Linear):
                nn.init.xavier_uniform_(module.weight)
                if module.bias is not None:
                    nn.init.zeros_(module.bias)

    def _compute_aux_loss(
        self,
        h_states:    torch.Tensor,   # (B, T, GRU_HIDDEN)
        hist_seq:    torch.Tensor,   # (B, T) 序列 ID（含 padding=0）
        seq_lengths: torch.Tensor,   # (B,)   真实长度
    ) -> torch.Tensor:
        """
        计算 DIEN 辅助损失（auxiliary loss）。

        辅助损失原理（DIEN 论文 Section 3.3）：
          GRU 隐状态 h_t 应能"预测"下一首歌 song_{t+1}（正样本），
          而不能预测批次中随机的歌曲（负样本）。
          这迫使 IEL 的 GRU 学习用户兴趣的演化轨迹，而非仅仅记忆历史 ID。

        实现：
          - 正样本 e_pos = seq_song_emb(hist_seq[:, t+1])
          - 负样本 e_neg = 同批次 e_pos 随机行置换
          - pos_score = sigmoid( aux_proj(h_t) · e_pos )
          - neg_score = sigmoid( aux_proj(h_t) · e_neg )
          - aux_loss  = BCE(pos_score, 1) + BCE(neg_score, 0)，仅计算有效位

        Returns:
            aux_loss (Tensor): 标量
        """
        B, T, _ = h_states.shape

        # 有效位置：t 和 t+1 均非 padding（即 t < seq_length - 1）
        arange    = torch.arange(T, device=h_states.device).unsqueeze(0)  # (1, T)
        valid_pos = arange < (seq_lengths.unsqueeze(1) - 1)               # (B, T) bool

        if not valid_pos.any():
            return torch.tensor(0.0, device=h_states.device)

        # 正样本：下一首歌的 Embedding（向左偏移 1 位，最后列用 padding 填充）
        next_ids         = torch.zeros_like(hist_seq)
        next_ids[:, :-1] = hist_seq[:, 1:]                     # 左移 1 位
        e_pos = self.seq_song_emb(next_ids.long())              # (B, T, EMBEDDING_DIM)

        # 负样本：同批次行乱序（保证与正样本维度完全一致，简单高效）
        neg_perm = torch.randperm(B, device=h_states.device)
        e_neg    = e_pos[neg_perm]                              # (B, T, EMBEDDING_DIM)

        # 将 GRU 隐状态投影回 Embedding 空间（64→32）后与 e_pos/e_neg 计算点积
        h_proj    = self.aux_proj(h_states)                     # (B, T, EMBEDDING_DIM)
        pos_score = (h_proj * e_pos).sum(dim=-1)                # (B, T)
        neg_score = (h_proj * e_neg).sum(dim=-1)                # (B, T)

        # 仅对有效位置计算损失
        pos_s = pos_score[valid_pos]
        neg_s = neg_score[valid_pos]
        aux_loss = (
            F.binary_cross_entropy_with_logits(pos_s, torch.ones_like(pos_s)) +
            F.binary_cross_entropy_with_logits(neg_s, torch.zeros_like(neg_s))
        ) * 0.5
        return aux_loss

    def forward(
        self,
        other_sparse: torch.Tensor,   # (B, 13) int32 — 其他稀疏特征 ID
        cand_song_id: torch.Tensor,   # (B,)    int32 — 候选歌曲 ID（+1 偏移）
        dense_vals:   torch.Tensor,   # (B, D)  float32 — 稠密特征
        hist_seq:     torch.Tensor,   # (B, T)  int32 — 历史序列（0=padding）
        seq_lengths:  torch.Tensor,   # (B,)    int32 — 真实历史长度
        is_training:  bool = True,
    ):
        """
        DIEN 完整前向传播。

        Returns:
            pred     (Tensor): (B,) 预测概率，Sigmoid 输出
            aux_loss (Tensor): 标量，训练时为辅助损失，推理时为 0
        """
        # ─── 1. 序列/候选 Embedding（共享同一 Embedding 表）
        hist_emb = self.seq_song_emb(hist_seq.long())      # (B, T, 32)
        e_target = self.seq_song_emb(cand_song_id.long())  # (B, 32)

        # ─── 2. 兴趣提取层 IEL：GRU
        h_states, _ = self.gru_iel(hist_emb)               # (B, T, 64)

        # ─── 3. 辅助损失（训练时计算，推理时跳过以节省时间）
        if is_training:
            aux_loss = self._compute_aux_loss(h_states, hist_seq, seq_lengths)
        else:
            aux_loss = torch.tensor(0.0, device=hist_emb.device)

        # ─── 4. 候选歌曲投影（32→64，为 AUGRU 注意力提供查询向量）
        e_proj = self.target_proj(e_target)  # (B, 64)

        # ─── 5. 兴趣演化层 IEL：AUGRU
        h_final = self.augru(h_states, e_proj, hist_emb, seq_lengths)  # (B, 64)

        # ─── 6. 其他稀疏特征 Embedding（13 × 32 = 416 维）
        sparse_list = [
            self.sparse_embs[fn](other_sparse[:, i].long())
            for i, fn in enumerate(self.sparse_feat_names)
        ]
        sparse_concat = torch.cat(sparse_list, dim=-1)  # (B, 416)

        # ─── 7. 稠密特征归一化
        dense_norm = self.dense_bn(dense_vals.float())   # (B, D)

        # ─── 8. 拼接 → MLP → 预测概率
        all_feats = torch.cat([h_final, e_target, sparse_concat, dense_norm], dim=-1)
        pred = self.mlp(all_feats).squeeze(-1)           # (B,)

        return pred, aux_loss


# ============================================================
# Step 3: 训练循环
# ============================================================

def train_dien(train_loader, val_loader, feat_config, device):
    """
    DIEN 训练主循环（AMP 混合精度 + ReduceLROnPlateau + 早停）。

    与 train_deepfm_v3.py 保持相同的训练框架，确保结果可比性：
      - 相同的优化器 Adam + weight_decay=1e-4
      - 相同的 AMP 策略（autocast + GradScaler）
      - 相同的早停与 LR 衰减逻辑
      - 额外：DIEN 辅助损失 LAMBDA_AUX × aux_loss 叠加到主损失

    Args:
        train_loader: 训练 DataLoader
        val_loader:   验证 DataLoader
        feat_config:  特征配置字典（含 n_songs 等）
        device:       torch.device

    Returns:
        model      (DIENModel): 加载了最佳权重的模型
        history    (dict):      训练历史（loss / val_loss / val_auc / lr）
        best_epoch (int):       最佳 epoch 编号
        best_auc   (float):     最佳验证集 AUC
    """
    print("\n" + "=" * 62)
    print("🚀 [Step 3/4] 训练 DIEN")
    print("=" * 62)

    model = DIENModel(feat_config).to(device)
    n_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"\n   模型参数量: {n_params:,}")
    print(f"   Batch Size: {BATCH_SIZE:,}  |  Max Epochs: {EPOCHS}")
    print(f"   LR: {LR}  |  LR_patience={LR_PATIENCE}  factor={LR_FACTOR}  min={LR_MIN}")
    print(f"   早停 patience: {EARLY_STOP_PATIENCE}  |  λ_aux={LAMBDA_AUX}")
    print(f"   Device: {device}")

    # Windows 下跳过 torch.compile（Triton 不支持）
    if sys.platform != 'win32':
        try:
            model = torch.compile(model, mode='default')
            print("   torch.compile ✅")
        except Exception:
            pass
    else:
        print("   torch.compile 跳过（Windows/Triton 不支持）")

    optimizer = Adam(model.parameters(), lr=LR, weight_decay=L2_EMB)
    scheduler = ReduceLROnPlateau(
        optimizer, mode='min', factor=LR_FACTOR,
        patience=LR_PATIENCE, min_lr=LR_MIN, verbose=True,
    )
    loss_fn = nn.BCEWithLogitsLoss(reduction='mean')  # AMP 安全：将 sigmoid+BCE 合并为数值稳定的单步计算
    use_amp = (device.type == 'cuda')
    scaler  = GradScaler(device=str(device)) if use_amp else None

    steps_per_epoch = len(train_loader)
    print(f"   Steps/epoch: {steps_per_epoch:,}\n")

    history = {'loss': [], 'val_loss': [], 'val_auc': [], 'lr': []}
    best_auc   = 0.0
    best_epoch = 0
    no_improve = 0
    best_state = None

    print(f"{'=' * 62}")
    print(f"  开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'=' * 62}\n")

    for epoch in range(EPOCHS):
        model.train()
        epoch_loss = 0.0
        t0 = time.time()

        pbar = tqdm(
            train_loader,
            total=steps_per_epoch,
            desc=f"Epoch {epoch + 1:2d}/{EPOCHS}",
            ncols=110,
            bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}] {postfix}",
        )

        for step, (sp, cs, dv, hs, sl, y) in enumerate(pbar):
            # 非阻塞 DMA 传输（CPU→GPU，DataLoader pin_memory 已锁页）
            sp = sp.to(device, non_blocking=True)
            cs = cs.to(device, non_blocking=True)
            dv = dv.to(device, non_blocking=True)
            hs = hs.to(device, non_blocking=True)
            sl = sl.to(device, non_blocking=True)
            y  = y.to(device, non_blocking=True)

            optimizer.zero_grad(set_to_none=True)

            if use_amp:
                with autocast(device_type='cuda'):
                    pred, aux_loss = model(sp, cs, dv, hs, sl, is_training=True)
                    main_loss = loss_fn(pred.float(), y.float())
                    loss      = main_loss + LAMBDA_AUX * aux_loss
                scaler.scale(loss).backward()
                scaler.unscale_(optimizer)
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                scaler.step(optimizer)
                scaler.update()
            else:
                pred, aux_loss = model(sp, cs, dv, hs, sl, is_training=True)
                main_loss = loss_fn(pred.float(), y.float())
                loss      = main_loss + LAMBDA_AUX * aux_loss
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()

            epoch_loss += main_loss.item()
            if (step + 1) % 100 == 0:
                pbar.set_postfix(loss=f"{epoch_loss / (step + 1):.4f}", refresh=False)

        avg_train_loss = epoch_loss / steps_per_epoch

        # ─── 验证集评估（不计算辅助损失，加快速度）
        model.eval()
        val_preds_list = []
        with torch.no_grad():
            for sp, cs, dv, hs, sl, _ in val_loader:
                sp = sp.to(device, non_blocking=True)
                cs = cs.to(device, non_blocking=True)
                dv = dv.to(device, non_blocking=True)
                hs = hs.to(device, non_blocking=True)
                sl = sl.to(device, non_blocking=True)
                if use_amp:
                    with autocast(device_type='cuda'):
                        vp, _ = model(sp, cs, dv, hs, sl, is_training=False)
                else:
                    vp, _ = model(sp, cs, dv, hs, sl, is_training=False)
                # 模型输出为 logit，需手动 sigmoid 转为概率（对应去掉 MLP 末尾 Sigmoid 的改动）
                val_preds_list.append(torch.sigmoid(vp).cpu().float().numpy())

        val_preds = np.concatenate(val_preds_list)
        val_true  = val_loader.dataset.targets.numpy()
        val_loss  = log_loss(val_true, val_preds)
        val_auc   = roc_auc_score(val_true, val_preds)
        cur_lr    = optimizer.param_groups[0]['lr']

        history['loss'].append(avg_train_loss)
        history['val_loss'].append(val_loss)
        history['val_auc'].append(val_auc)
        history['lr'].append(cur_lr)

        elapsed = time.time() - t0
        print(f"  → Epoch {epoch + 1:2d}/{EPOCHS}  "
              f"loss={avg_train_loss:.4f}  "
              f"val_loss={val_loss:.4f}  "
              f"val_AUC={val_auc:.4f}  "
              f"lr={cur_lr:.2e}  "
              f"({elapsed:.0f}s)")

        # ReduceLROnPlateau 调度（监控 val_loss）
        scheduler.step(val_loss)

        # 早停 & 最佳权重保存
        if val_auc > best_auc + 1e-5:
            best_auc   = val_auc
            best_epoch = epoch + 1
            no_improve = 0
            raw_model  = getattr(model, '_orig_mod', model)
            best_state = {k: v.cpu().clone() for k, v in raw_model.state_dict().items()}
            print(f"     ✅ 最佳 AUC 更新: {best_auc:.4f}（Epoch {best_epoch}）")
        else:
            no_improve += 1
            print(f"     ⏳ 无提升 {no_improve}/{EARLY_STOP_PATIENCE}")
            if no_improve >= EARLY_STOP_PATIENCE:
                print(f"\n⛔ 早停触发！最佳 Epoch={best_epoch}，val_AUC={best_auc:.4f}")
                break

    print(f"\n{'=' * 62}")
    print(f"  训练结束: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  最佳 Epoch: {best_epoch}  |  最佳 val_AUC: {best_auc:.4f}")
    print(f"{'=' * 62}")

    # 恢复最佳权重
    raw_model = getattr(model, '_orig_mod', model)
    if best_state is not None:
        raw_model.load_state_dict(best_state)

    return raw_model, history, best_epoch, best_auc


# ============================================================
# Step 4: 可视化 + 保存
# ============================================================

def plot_training_history(history: dict) -> None:
    """
    绘制训练曲线（Loss / AUC / LR），保存为 PNG 并输出逐 epoch CSV。

    Args:
        history (dict): {'loss', 'val_loss', 'val_auc', 'lr'} 各含列表
    """
    print("\n" + "=" * 62)
    print("📊 绘制训练曲线")
    print("=" * 62)

    plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Arial']
    plt.rcParams['axes.unicode_minus'] = False

    epochs = range(1, len(history['loss']) + 1)
    fig, axes = plt.subplots(1, 3, figsize=(18, 5))

    # 损失曲线
    ax = axes[0]
    ax.plot(epochs, history['loss'],     'b-o', label='Train Loss', lw=2, ms=5)
    ax.plot(epochs, history['val_loss'], 'r-s', label='Val Loss',   lw=2, ms=5)
    ax.set_xlabel('Epoch'); ax.set_ylabel('Loss')
    ax.set_title('DIEN Loss Curve', fontweight='bold')
    ax.legend(); ax.grid(alpha=0.3)

    # AUC 曲线
    ax = axes[1]
    ax.plot(epochs, history['val_auc'], 'g-o', label='Val AUC', lw=2, ms=5)
    ax.set_xlabel('Epoch'); ax.set_ylabel('AUC')
    ax.set_title('DIEN Validation AUC', fontweight='bold')
    ax.axhline(y=0.770, color='orange', linestyle='--', lw=1.5, label='目标 0.770')
    ax.legend(); ax.grid(alpha=0.3)
    ax.set_ylim([max(0.5, min(history['val_auc']) - 0.02), 1.0])

    # 学习率曲线
    ax = axes[2]
    ax.plot(epochs, history['lr'], 'm-^', label='Learning Rate', lw=2, ms=5)
    ax.set_xlabel('Epoch'); ax.set_ylabel('LR')
    ax.set_title('Learning Rate Schedule', fontweight='bold')
    ax.set_yscale('log'); ax.legend(); ax.grid(alpha=0.3)

    plt.tight_layout()
    plt.savefig(OUTPUT_PLOT, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"   ✅ 训练曲线: {OUTPUT_PLOT}")

    # 保存逐 epoch CSV（论文附录用）
    import csv
    with open(OUTPUT_HISTORY, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["epoch", "train_loss", "val_loss", "val_auc", "lr"])
        writer.writeheader()
        for i, (tl, vl, va, lr) in enumerate(zip(
                history["loss"], history["val_loss"],
                history["val_auc"], history["lr"]), 1):
            writer.writerow({
                "epoch": i, "train_loss": f"{tl:.6f}",
                "val_loss": f"{vl:.6f}", "val_auc": f"{va:.6f}",
                "lr": f"{lr:.2e}",
            })
    print(f"   ✅ 训练指标 CSV: {OUTPUT_HISTORY}")


def save_model(model: DIENModel, feat_config: dict,
               history: dict, best_epoch: int, best_auc: float) -> None:
    """
    保存模型权重和架构配置。

    保存内容：
      - dien_model.pth：state_dict（最佳权重）
      - model_config.pkl：完整架构参数（供 build_ensemble.py 重建模型时使用）

    Args:
        model:      加载了最佳权重的 DIENModel
        feat_config: 特征配置字典
        history:    训练历史
        best_epoch: 最佳 epoch 编号
        best_auc:   最佳验证集 AUC
    """
    print("\n" + "=" * 62)
    print("💾 [Step 4/4] 保存模型")
    print("=" * 62)

    torch.save(model.state_dict(), OUTPUT_MODEL)
    size_mb = os.path.getsize(OUTPUT_MODEL) / 1024 / 1024
    print(f"   模型权重: {OUTPUT_MODEL}  ({size_mb:.1f} MB)")

    config = {
        **feat_config,                          # n_songs / n_users / active_sparse 等
        "gru_hidden":    GRU_HIDDEN,
        "embedding_dim": EMBEDDING_DIM,
        "seq_len":       SEQ_LEN,
        "lambda_aux":    LAMBDA_AUX,
        "dropout1":      DROPOUT1,
        "dropout2":      DROPOUT2,
        "history":       history,
        "best_epoch":    best_epoch,
        "best_val_auc":  best_auc,
        "train_time":    datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "version":       "dien_v1",
    }
    with open(OUTPUT_CONFIG, "wb") as f:
        pickle.dump(config, f, protocol=4)
    print(f"   模型配置: {OUTPUT_CONFIG}")
    print(f"   ✅ 保存完成  最佳 val_AUC={best_auc:.4f}  Epoch={best_epoch}")


# ============================================================
# main
# ============================================================

def main():
    print("\n" + "🎵" * 31)
    print("   MusicMode DIEN v1 — 序列精排模型训练")
    print(f"   开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("   模型: Deep Interest Evolution Network (AAAI 2019)")
    print("   目标: Val AUC ≥ 0.770，集成后 ≥ 0.800")
    print("🎵" * 31)

    set_seed(RANDOM_SEED)
    device = check_gpu()

    # Step 1: 加载数据
    feat, seq = load_data()

    # Step 2: 预处理 & 构建 DataLoader
    train_loader, val_loader, feat_config = prepare_dien_data(feat, seq)

    # 释放原始数据节省内存（特征矩阵已切片进 Dataset）
    del feat, seq

    # Step 3: 训练
    model, history, best_epoch, best_auc = train_dien(
        train_loader, val_loader, feat_config, device)

    # Step 4: 保存结果
    plot_training_history(history)
    save_model(model, feat_config, history, best_epoch, best_auc)

    print(f"\n{'=' * 62}")
    print(f"✅ DIEN 训练完成！")
    print(f"   最佳 val_AUC = {best_auc:.4f}  (目标 ≥ 0.770)")
    if best_auc >= 0.770:
        print(f"   🎉 达到目标！可运行集成：python build_ensemble.py")
    else:
        print(f"   ⚠️  未达目标，建议检查序列文件是否正确生成后重试")
    print(f"{'=' * 62}\n")


if __name__ == "__main__":
    main()
