# -*- coding: utf-8 -*-
"""
train_deepfm_v3.py — DeepFM 精排模型训练 v3

特点：
  - 输入: features_v3.pkl（来自 prepare_features_v3.py）
  - 特征: 14 个稀疏特征（SparseFeat）+ 36 个稠密特征（DenseFeat）
  - 目标: 预测"30天内重复收听"概率（二分类）
  - 模型: DeepFM（DNN=(256,256,128)）
  - 优化: GPU AMP（FP16 混合精度）+ ReduceLROnPlateau + 早停
  - 输出: deepfm_model.pth + model_config.pkl + training_progress.png

预计时间：约 30 分钟（7.37M 样本，GPU RTX 4060）
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

# ============================================================
# 配置
# ============================================================

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
MODE_DIR    = os.path.join(os.path.dirname(PROJECT_DIR), "Mode")

INPUT_FEATURES   = os.path.join(MODE_DIR, "features_v3.pkl")
DEEPFM_DIR       = os.path.join(MODE_DIR, "deepfm")
os.makedirs(DEEPFM_DIR, exist_ok=True)
OUTPUT_MODEL     = os.path.join(DEEPFM_DIR, "deepfm_model.pth")
OUTPUT_CONFIG    = os.path.join(DEEPFM_DIR, "model_config.pkl")
OUTPUT_PLOT      = os.path.join(DEEPFM_DIR, "training_progress.png")
OUTPUT_HISTORY   = os.path.join(DEEPFM_DIR, "deepfm_metrics.csv")  # 论文用：逐 epoch 指标

# 训练超参数
BATCH_SIZE       = 8192        # 样本数
EPOCHS           = 60           # 最大训练轮数
LEARNING_RATE    = 0.002        #初始学习率（Adam 默认值，通常适合 DeepFM）
DNN_HIDDEN_UNITS = (512, 256, 128, 64)
DROPOUT          = 0.35        # 丢弃率
NUM_WORKERS      = 5            # DataLoader 线程数
RANDOM_SEED      = 42

# ReduceLROnPlateau 学习率衰减参数
LR_PATIENCE      = 3          # 在验证指标不提升多少个 epoch 后触发学习率衰减
LR_FACTOR        = 0.35         # 学习率衰减因子（new_lr = old_lr * factor）
LR_MIN           = 1e-6         # 学习率下限，避免过度衰减导致训练停滞

# 早停参数
EARLY_STOP_PATIENCE = 10      

# 验证集比例
VALID_RATIO = 0.1              # 10%，与 BST 一致


# ============================================================
# 特征列定义
# ============================================================

# (deepctr特征名, pkl编码键, pkl基数键, embedding维度)
# ⚠️ DeepCTR-Torch 要求所有 SparseFeat embedding_dim 一致
# ⚠️ n_key 须与 prepare_features_v3.py save_outputs() 中的 key 名完全一致
SPARSE_FEAT_SPECS = [
    ("user_id",         "user_id_encoded",          "n_users",         32),
    ("song_id",         "song_id_encoded",           "n_songs",         32),
    ("genre",           "genre_encoded",             "n_genres",        32),
    ("language",        "language_encoded",          "n_languages",     32),
    ("artist",          "artist_encoded",            "n_artists",       32),
    ("origin_country",  "origin_country_encoded",    "n_countries",     32),
    ("year_bucket",     "year_bucket_encoded",       "n_year_buckets",  32),
    ("source_channel",  "source_channel_encoded",    "n_sources",       32),
    ("city",            "city_encoded",              "n_cities",        32),
    ("gender",          "gender_encoded",            "n_genders",       32),
    ("age_bucket",      "age_bucket_encoded",        "n_age_buckets",   32),
    ("tenure_bucket",   "tenure_bucket_encoded",     "n_tenures",       32),
    ("duration_bucket", "duration_bucket_encoded",   "n_dur_buckets",   32),
    ("user_peak_hour",  "user_peak_hour_encoded",    "n_peak_hours",    32),
]

# 稠密特征名（与 features_v3.pkl 中的 key 对应）
DENSE_FEAT_SPECS = [
    # 用户基础统计
    "user_play_count_log",
    "user_avg_completion",
    "user_genre_diversity",            
    "user_30d_active_days",             
    # 歌曲基础统计
    "song_play_count_log",
    "song_avg_completion",
    "song_popularity_norm",
    "song_age_days_log",
    "song_target_rate",
    # 交互特征（保留有信号的）
    "user_artist_match",
    "user_skip_rate",
    "song_skip_rate",
    # 时序匹配
    "hour_match",
    "dow_match",                       
    # 最近交互
    "days_since_artist_log",
    "days_since_last_play_log",         
    # 歌单亲和力
    "user_has_in_playlist",            
    "user_playlist_artist_count_log",
    # B-3 记忆衰减
    "user_song_prev_play_days",
    "user_song_play_count_before",
    # B-4 滚动窗口
    "user_7d_play_count_log",
    "user_30d_play_count_log",
    "user_7d_avg_completion",
    "song_7d_play_count_log",
    "song_30d_play_count_log",
    "song_trending_ratio",
    # SVD 嵌入（全维度）
    *[f"svd_user_song_{i}" for i in range(10)],
    *[f"svd_song_user_{i}" for i in range(10)],
    *[f"svd_user_artist_{i}" for i in range(5)],
    "svd_dot_score",
]


# ============================================================
# 工具函数
# ============================================================

def set_seed(seed=RANDOM_SEED):
    import random, torch
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark     = False


def check_gpu():
    import torch
    if torch.cuda.is_available():
        name = torch.cuda.get_device_name(0)
        vram = torch.cuda.get_device_properties(0).total_memory / 1024**3
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
    print("\n" + "=" * 62)
    print("📂 [Step 1/4] 加载特征数据")
    print("=" * 62)

    if not os.path.exists(INPUT_FEATURES):
        print(f"❌ 特征文件不存在：{INPUT_FEATURES}")
        print("   请先运行 prepare_features_v3.py")
        sys.exit(1)

    with open(INPUT_FEATURES, "rb") as f:
        feat = pickle.load(f)

    # ── pkl 字段完整性验证
    _req_dense   = [f for f in DENSE_FEAT_SPECS]
    _req_enc     = [enc for _, enc, _,   _ in SPARSE_FEAT_SPECS]
    _req_n       = [nk  for _, _,   nk,  _ in SPARSE_FEAT_SPECS]
    _req_meta    = ["target", "play_time_unix", "artist_encoded",
                    "genre_encoded", "language_encoded", "origin_country_encoded"]
    _all_required = _req_dense + _req_enc + _req_n + _req_meta
    _missing = [k for k in _all_required if k not in feat]
    if _missing:
        print(f"\n❌ pkl 缺少以下字段（共 {len(_missing)} 个），请重新运行 prepare_features_v3.py：")
        for k in _missing:
            print(f"   - {k}")
        sys.exit(1)
    print(f"   ✅ pkl 字段验证通过（{len(_all_required)} 个必要字段均存在）")

    n = len(feat["target"])
    print(f"\n   样本数: {n:,}")
    print(f"   正样本率: {feat['target'].mean():.4f}")

    for spec in SPARSE_FEAT_SPECS:
        n_key = spec[2]
        if n_key in feat:
            print(f"   {spec[0]:<18} n={feat[n_key]:,}")

    return feat


# ============================================================
# Step 2: 构建特征列 & 分割数据集
# ============================================================

def prepare_deepfm_data(feat):
    print("\n" + "=" * 62)
    print("⚙️  [Step 2/4] 构建特征列 & 分割数据集")
    print("=" * 62)

    from deepctr_torch.inputs import SparseFeat, DenseFeat, get_feature_names
    from sklearn.model_selection import train_test_split

    # ── 构建特征列
    feature_columns = []

    active_sparse_specs = []
    skipped_sparse = []
    for feat_name, enc_key, n_key, embed_dim in SPARSE_FEAT_SPECS:
        if enc_key in feat and n_key in feat:
            vocab_size = int(feat[n_key]) + 1
            feature_columns.append(
                SparseFeat(feat_name, vocabulary_size=vocab_size,
                           embedding_dim=embed_dim)
            )
            active_sparse_specs.append((feat_name, enc_key, n_key, embed_dim))
        else:
            skipped_sparse.append(feat_name)

    active_dense_specs = []
    skipped_dense = []
    for feat_name in DENSE_FEAT_SPECS:
        if feat_name in feat:
            feature_columns.append(DenseFeat(feat_name, dimension=1))
            active_dense_specs.append(feat_name)
        else:
            skipped_dense.append(feat_name)

    if skipped_sparse:
        print(f"\n   ⚠️  跳过稀疏特征 ({len(skipped_sparse)} 个): {skipped_sparse}")
    if skipped_dense:
        print(f"   ⚠️  跳过稠密特征 ({len(skipped_dense)} 个): {skipped_dense}")

    print(f"\n   已加载稀疏特征: {len(active_sparse_specs)} 个 SparseFeat")
    print(f"   已加载稠密特征: {len(active_dense_specs)} 个 DenseFeat")
    print(f"   特征总数: {len(feature_columns)} 个")

    # ── 构建数据字典（键名 = deepctr feature_name）
    n_samples = len(feat["target"])
    data_dict = {}

    for feat_name, enc_key, _, _ in active_sparse_specs:
        arr = feat[enc_key].astype(np.int32)
        data_dict[feat_name] = arr

    for feat_name in active_dense_specs:
        arr = feat[feat_name].astype(np.float32)
        arr = np.nan_to_num(arr, nan=0.0, posinf=10.0, neginf=0.0)
        data_dict[feat_name] = arr

    target = feat["target"].astype(np.float32)

    # ── 用户级时序切分（向量化版）
    feature_names  = get_feature_names(feature_columns)
    play_time_unix = feat.get("play_time_unix", np.zeros(n_samples, dtype=np.int64))
    _uid_arr = feat["user_id_encoded"].astype(np.int32)
    MIN_INTERACTIONS = 5
    _df_meta = pd.DataFrame({
        "orig_idx": np.arange(n_samples),
        "uid":      _uid_arr,
        "time":     play_time_unix,
    }).sort_values(["uid", "time"])
    _df_meta["_cnt"]  = _df_meta.groupby("uid")["uid"].transform("count")
    _df_meta["_rank"] = _df_meta.groupby("uid").cumcount()
    _n_val_vec        = (_df_meta["_cnt"] * VALID_RATIO).astype(int).clip(lower=1)
    _is_val           = ((_df_meta["_cnt"] >= MIN_INTERACTIONS) &
                         (_df_meta["_rank"] >= _df_meta["_cnt"] - _n_val_vec))
    train_idx = _df_meta.loc[~_is_val, "orig_idx"].values
    val_idx   = _df_meta.loc[ _is_val, "orig_idx"].values

    # ── 低频 ID 过滤（min_count=3，只统计训练集，防 Embedding 死记硬背长尾 ID）
    print("  🔧 低频 ID 过滤（min_count=3）...")
    _MIN_COUNT = 3
    user_id_enc = feat["user_id_encoded"].copy()
    song_id_enc = feat["song_id_encoded"].copy()
    _u_counts = np.bincount(user_id_enc[train_idx].astype(np.int32),
                            minlength=int(user_id_enc.max()) + 1)
    _s_counts = np.bincount(song_id_enc[train_idx].astype(np.int32),
                            minlength=int(song_id_enc.max()) + 1)
    user_id_enc[np.isin(user_id_enc, np.where(_u_counts < _MIN_COUNT)[0])] = 0
    song_id_enc[np.isin(song_id_enc, np.where(_s_counts < _MIN_COUNT)[0])] = 0
    # 同步更新 data_dict 中的 ID 特征
    data_dict["user_id"] = user_id_enc
    data_dict["song_id"] = song_id_enc
    _n_rare_u = int((_u_counts < _MIN_COUNT).sum())
    _n_rare_s = int((_s_counts < _MIN_COUNT).sum())
    print(f"   ✅ 稀疏用户 {_n_rare_u} 个 → UNK，稀疏歌曲 {_n_rare_s} 首 → UNK")

    train_data   = {k: v[train_idx] for k, v in data_dict.items()}
    val_data     = {k: v[val_idx]   for k, v in data_dict.items()}
    train_target = target[train_idx]
    val_target   = target[val_idx]

    # ── 5折 OOF Target Encoding（训练集无泄漏，训练/验证分布一致）
    _global_prior = float(train_target.mean())
    _uid  = feat["user_id_encoded"]
    _gnr  = feat.get("genre_encoded",          np.zeros(n_samples, dtype=np.int32))
    _lng  = feat.get("language_encoded",       np.zeros(n_samples, dtype=np.int32))
    _ctr  = feat.get("origin_country_encoded", np.zeros(n_samples, dtype=np.int32))
    _SMOOTH_M = 100
    _N_OOF    = 5

    print(f"  🎯 5折 OOF Target Encoding（user×genre/language/country_match）...")
    _fold_edges = np.linspace(0, len(train_idx), _N_OOF + 1, dtype=int)
    _ug_oof = np.full(n_samples, _global_prior, dtype=np.float32)
    _ul_oof = np.full(n_samples, _global_prior, dtype=np.float32)
    _uc_oof = np.full(n_samples, _global_prior, dtype=np.float32)

    for _k in range(_N_OOF):
        _fold_mask  = np.zeros(len(train_idx), dtype=bool)
        _fold_mask[_fold_edges[_k]:_fold_edges[_k+1]] = True
        _other_orig = train_idx[~_fold_mask]
        _this_orig  = train_idx[_fold_mask]

        _om = pd.DataFrame({
            "uid": _uid[_other_orig].astype(np.int32),
            "gnr": _gnr[_other_orig].astype(np.int32),
            "lng": _lng[_other_orig].astype(np.int32),
            "ctr": _ctr[_other_orig].astype(np.int32),
            "y":   target[_other_orig].astype(np.float32),
        })
        _ug_o = _om.groupby(["uid","gnr"])["y"].agg(["count","mean"]).reset_index()
        _ug_o["ug_te"] = (_ug_o["count"]*_ug_o["mean"] + _SMOOTH_M*_global_prior) / (_ug_o["count"] + _SMOOTH_M)
        _ul_o = _om.groupby(["uid","lng"])["y"].agg(["count","mean"]).reset_index()
        _ul_o["ul_te"] = (_ul_o["count"]*_ul_o["mean"] + _SMOOTH_M*_global_prior) / (_ul_o["count"] + _SMOOTH_M)
        _uc_o = _om.groupby(["uid","ctr"])["y"].agg(["count","mean"]).reset_index()
        _uc_o["uc_te"] = (_uc_o["count"]*_uc_o["mean"] + _SMOOTH_M*_global_prior) / (_uc_o["count"] + _SMOOTH_M)

        _tf = pd.DataFrame({
            "uid": _uid[_this_orig].astype(np.int32),
            "gnr": _gnr[_this_orig].astype(np.int32),
            "lng": _lng[_this_orig].astype(np.int32),
            "ctr": _ctr[_this_orig].astype(np.int32),
        })
        _tf = _tf.merge(_ug_o[["uid","gnr","ug_te"]], on=["uid","gnr"], how="left")
        _tf = _tf.merge(_ul_o[["uid","lng","ul_te"]], on=["uid","lng"], how="left")
        _tf = _tf.merge(_uc_o[["uid","ctr","uc_te"]], on=["uid","ctr"], how="left")
        _ug_oof[_this_orig] = _tf["ug_te"].fillna(_global_prior).values.astype(np.float32)
        _ul_oof[_this_orig] = _tf["ul_te"].fillna(_global_prior).values.astype(np.float32)
        _uc_oof[_this_orig] = _tf["uc_te"].fillna(_global_prior).values.astype(np.float32)

    # 训练集：应用 OOF TE（无自我泄漏）
    if "user_genre_match"    in train_data: train_data["user_genre_match"]    = _ug_oof[train_idx]
    if "user_language_match" in train_data: train_data["user_language_match"] = _ul_oof[train_idx]
    if "user_country_match"  in train_data: train_data["user_country_match"]  = _uc_oof[train_idx]
    print(f"   ✅ 训练集 OOF TE 完成（5折，global_prior={_global_prior:.4f}）")

    # 验证集：用全量训练集统计回填（与 OOF 同分布，无泄漏）
    _full_meta = pd.DataFrame({
        "uid": _uid[train_idx].astype(np.int32),
        "gnr": _gnr[train_idx].astype(np.int32),
        "lng": _lng[train_idx].astype(np.int32),
        "ctr": _ctr[train_idx].astype(np.int32),
        "y":   train_target.astype(np.float32),
    })
    _ug_s = _full_meta.groupby(["uid","gnr"])["y"].agg(["count","mean"]).reset_index()
    _ug_s["ug_te"] = (_ug_s["count"]*_ug_s["mean"] + _SMOOTH_M*_global_prior) / (_ug_s["count"] + _SMOOTH_M)
    _ul_s = _full_meta.groupby(["uid","lng"])["y"].agg(["count","mean"]).reset_index()
    _ul_s["ul_te"] = (_ul_s["count"]*_ul_s["mean"] + _SMOOTH_M*_global_prior) / (_ul_s["count"] + _SMOOTH_M)
    _uc_s = _full_meta.groupby(["uid","ctr"])["y"].agg(["count","mean"]).reset_index()
    _uc_s["uc_te"] = (_uc_s["count"]*_uc_s["mean"] + _SMOOTH_M*_global_prior) / (_uc_s["count"] + _SMOOTH_M)
    _vf = pd.DataFrame({
        "uid": _uid[val_idx].astype(np.int32),
        "gnr": _gnr[val_idx].astype(np.int32),
        "lng": _lng[val_idx].astype(np.int32),
        "ctr": _ctr[val_idx].astype(np.int32),
    })
    _vf = _vf.merge(_ug_s[["uid","gnr","ug_te"]], on=["uid","gnr"], how="left")
    _vf = _vf.merge(_ul_s[["uid","lng","ul_te"]], on=["uid","lng"], how="left")
    _vf = _vf.merge(_uc_s[["uid","ctr","uc_te"]], on=["uid","ctr"], how="left")
    if "user_genre_match"    in val_data: val_data["user_genre_match"]    = _vf["ug_te"].fillna(_global_prior).values.astype(np.float32)
    if "user_language_match" in val_data: val_data["user_language_match"] = _vf["ul_te"].fillna(_global_prior).values.astype(np.float32)
    if "user_country_match"  in val_data: val_data["user_country_match"]  = _vf["uc_te"].fillna(_global_prior).values.astype(np.float32)
    print(f"   ✅ 验证集 TE 完成（全量训练集统计回填）")

    print(f"\n   训练集: {len(train_idx):,} 样本")
    print(f"   验证集: {len(val_idx):,} 样本")
    print(f"   训练集正样本率: {train_target.mean():.4f}")

    return (feature_columns, feature_names,
            train_data, val_data, train_target, val_target)


# ============================================================
# Step 3: 训练（AMP + ReduceLROnPlateau + 早停）
# ============================================================

def train_deepfm(feature_columns, feature_names,
                 train_data, val_data, train_target, val_target, device):
    import torch
    import torch.nn.functional as F
    import torch.utils.data as Data
    from torch.amp import autocast, GradScaler
    from torch.optim import Adam
    from torch.optim.lr_scheduler import ReduceLROnPlateau
    from deepctr_torch.models import DeepFM
    from sklearn.metrics import roc_auc_score, log_loss

    print("\n" + "=" * 62)
    print("🚀 [Step 3/4] 训练 DeepFM v3")
    print("=" * 62)
    print(f"\n   DNN 隐藏层: {DNN_HIDDEN_UNITS}")
    print(f"   Dropout:    {DROPOUT}")
    print(f"   Batch Size: {BATCH_SIZE:,}")
    print(f"   Max Epochs: {EPOCHS}")
    print(f"   LR 初始值: {LEARNING_RATE}  |  patience={LR_PATIENCE}  factor={LR_FACTOR}  min={LR_MIN}")
    print(f"   早停 patience: {EARLY_STOP_PATIENCE} epochs")
    print(f"   Device:     {device}")

    # ── 构建模型
    model = DeepFM(
        linear_feature_columns=feature_columns,
        dnn_feature_columns=feature_columns,
        dnn_hidden_units=DNN_HIDDEN_UNITS,
        dnn_dropout=DROPOUT,
        l2_reg_embedding=1e-4,
        device=str(device),
    )

    # torch.compile 仅 Linux 支持（Windows 跳过）
    if sys.platform != 'win32':
        try:
            model = torch.compile(model, mode='default')
            print("   torch.compile ✅")
        except Exception:
            print("   torch.compile 不可用，跳过")
    else:
        print("   torch.compile 跳过（Windows / Triton 不支持）")

    model = model.to(device)

    optimizer = Adam(model.parameters(), lr=LEARNING_RATE, weight_decay=1e-4)
    scheduler = ReduceLROnPlateau(
        optimizer, mode='min', factor=LR_FACTOR,
        patience=LR_PATIENCE, min_lr=LR_MIN, verbose=True
    )
    loss_fn = torch.nn.BCELoss(reduction='mean')
    use_amp = (device.type == 'cuda')
    scaler  = GradScaler(device=str(device)) if use_amp else None

    # ── 构建 Tensor 数据
    def make_tensor(data_dict):
        """按 feature_names 顺序拼接，稀疏用 int32、稠密用 float32"""
        arrays = []
        for f in feature_names:
            arr = data_dict[f].reshape(-1, 1)
            arrays.append(arr)
        return torch.from_numpy(np.concatenate(arrays, axis=1))

    X_train = make_tensor(train_data)       # shape: (N_train, n_features)
    y_train = torch.from_numpy(train_target)
    X_val   = make_tensor(val_data).to(device).float()
    y_val   = torch.from_numpy(val_target)

    train_dataset = Data.TensorDataset(X_train, y_train)
    train_loader  = Data.DataLoader(
        train_dataset,
        batch_size=BATCH_SIZE,
        shuffle=True,
        num_workers=NUM_WORKERS,
        pin_memory=(device.type == 'cuda'),
        persistent_workers=(NUM_WORKERS > 0),
        prefetch_factor=2 if NUM_WORKERS > 0 else None,
    )
    steps_per_epoch = len(train_loader)
    print(f"\n   Steps/epoch: {steps_per_epoch:,}")

    # val_loader 在循环外构建一次（避免每 epoch 重建，节省 1-2 分钟）
    # X_val 已在 GPU 上，不能再 pin_memory（只能 pin CPU tensor）
    val_loader = Data.DataLoader(
        Data.TensorDataset(X_val, torch.zeros(len(y_val))),
        batch_size=BATCH_SIZE * 4, shuffle=False,
        pin_memory=False,
    )

    # ── 训练循环
    history = {
        'loss': [], 'val_loss': [], 'val_auc': [], 'lr': []
    }
    best_val_auc   = 0.0
    best_epoch     = 0
    no_improve     = 0
    best_state     = None

    print(f"\n{'='*62}")
    print(f"  开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*62}\n")

    for epoch in range(EPOCHS):
        model.train()
        epoch_loss = 0.0
        t_epoch = time.time()

        pbar = tqdm(
            train_loader,
            total=steps_per_epoch,
            desc=f"Epoch {epoch+1:2d}/{EPOCHS}",
            ncols=100,
            bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}] {postfix}",
        )

        for step, (x_batch, y_batch) in enumerate(pbar):
            x_batch = x_batch.to(device, non_blocking=True).float()
            y_batch = y_batch.to(device, non_blocking=True).float()

            optimizer.zero_grad(set_to_none=True)

            if use_amp:
                with autocast(device_type='cuda'):
                    y_pred = model(x_batch).squeeze()
                loss = loss_fn(y_pred.float(), y_batch)
                scaler.scale(loss).backward()
                scaler.unscale_(optimizer)
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                scaler.step(optimizer)
                scaler.update()
            else:
                y_pred = model(x_batch).squeeze()
                loss = loss_fn(y_pred, y_batch)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()

            epoch_loss += loss.item()
            if (step + 1) % 100 == 0 or step == 0:
                pbar.set_postfix(
                    loss=f"{epoch_loss/(step+1):.4f}",
                    refresh=False
                )

        avg_train_loss = epoch_loss / steps_per_epoch

        # ── 验证集评估
        model.eval()
        val_preds_list = []
        with torch.no_grad():
            for xv, _ in val_loader:
                if use_amp:
                    with autocast(device_type='cuda'):
                        vp = model(xv).squeeze()
                else:
                    vp = model(xv).squeeze()
                val_preds_list.append(vp.cpu().float().numpy())

        val_preds = np.concatenate(val_preds_list)
        val_true  = y_val.numpy()

        val_loss = log_loss(val_true, val_preds)
        val_auc  = roc_auc_score(val_true, val_preds)
        cur_lr   = optimizer.param_groups[0]['lr']

        history['loss'].append(avg_train_loss)
        history['val_loss'].append(val_loss)
        history['val_auc'].append(val_auc)
        history['lr'].append(cur_lr)

        elapsed = time.time() - t_epoch
        print(f"  → Epoch {epoch+1:2d}/{EPOCHS}  "
              f"loss={avg_train_loss:.4f}  "
              f"val_loss={val_loss:.4f}  "
              f"val_AUC={val_auc:.4f}  "
              f"lr={cur_lr:.2e}  "
              f"({elapsed:.0f}s)")

        # ReduceLROnPlateau 更新（监控 val_loss）
        scheduler.step(val_loss)

        # 早停 & 最佳权重保存
        if val_auc > best_val_auc + 1e-5:
            best_val_auc = val_auc
            best_epoch   = epoch + 1
            no_improve   = 0
            # 拷贝当前最佳权重（避免 compile 包装层）
            raw_model = model._orig_mod if hasattr(model, '_orig_mod') else model
            best_state = {k: v.cpu().clone() for k, v in raw_model.state_dict().items()}
            print(f"     ✅ 最佳 AUC 更新: {best_val_auc:.4f}（Epoch {best_epoch}）")
        else:
            no_improve += 1
            print(f"     ⏳ 无提升 {no_improve}/{EARLY_STOP_PATIENCE}")
            if no_improve >= EARLY_STOP_PATIENCE:
                print(f"\n⛔ 早停触发！最佳 Epoch={best_epoch}，val_AUC={best_val_auc:.4f}")
                break

    print(f"\n{'='*62}")
    print(f"  训练结束: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  最佳 Epoch: {best_epoch}  |  最佳 val_AUC: {best_val_auc:.4f}")
    print(f"{'='*62}")

    # 恢复最佳权重到模型
    raw_model = model._orig_mod if hasattr(model, '_orig_mod') else model
    if best_state is not None:
        raw_model.load_state_dict(best_state)

    return raw_model, history, best_epoch, best_val_auc


# ============================================================
# Step 4: 可视化 + 保存
# ============================================================

def plot_training_history(history):
    print("\n" + "=" * 62)
    print("📊 绘制训练曲线")
    print("=" * 62)

    plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Arial']
    plt.rcParams['axes.unicode_minus'] = False

    epochs = range(1, len(history['loss']) + 1)
    fig, axes = plt.subplots(1, 3, figsize=(18, 5))

    # Loss
    ax = axes[0]
    ax.plot(epochs, history['loss'],     'b-o', label='Train Loss', lw=2, ms=6)
    ax.plot(epochs, history['val_loss'], 'r-s', label='Val Loss',   lw=2, ms=6)
    ax.set_xlabel('Epoch'); ax.set_ylabel('Loss')
    ax.set_title('Loss Curve', fontweight='bold')
    ax.legend(); ax.grid(alpha=0.3); ax.set_xticks(list(epochs))

    # AUC
    ax = axes[1]
    ax.plot(epochs, history['val_auc'], 'g-o', label='Val AUC', lw=2, ms=6)
    ax.set_xlabel('Epoch'); ax.set_ylabel('AUC')
    ax.set_title('Validation AUC', fontweight='bold')
    ax.legend(); ax.grid(alpha=0.3); ax.set_xticks(list(epochs))
    ax.set_ylim([max(0.5, min(history['val_auc']) - 0.02), 1.0])

    # Learning Rate
    ax = axes[2]
    ax.plot(epochs, history['lr'], 'm-^', label='Learning Rate', lw=2, ms=6)
    ax.set_xlabel('Epoch'); ax.set_ylabel('LR')
    ax.set_title('Learning Rate Schedule', fontweight='bold')
    ax.set_yscale('log'); ax.legend(); ax.grid(alpha=0.3)
    ax.set_xticks(list(epochs))

    plt.tight_layout()
    plt.savefig(OUTPUT_PLOT, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"   ✅ 训练曲线已保存: {OUTPUT_PLOT}")

    # 保存逐 epoch CSV（论文用）
    import csv
    with open(OUTPUT_HISTORY, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["epoch", "train_loss", "val_loss", "val_auc", "lr"])
        writer.writeheader()
        for i, (tl, vl, va, lr) in enumerate(zip(
                history["loss"], history["val_loss"], history["val_auc"], history["lr"]), 1):
            writer.writerow({"epoch": i, "train_loss": f"{tl:.6f}", "val_loss": f"{vl:.6f}",
                             "val_auc": f"{va:.6f}", "lr": f"{lr:.2e}"})
    print(f"   ✅ 训练指标 CSV: {OUTPUT_HISTORY}")


def save_model(model, feature_columns, feature_names, history, best_epoch, best_val_auc):
    import torch

    print("\n" + "=" * 62)
    print("💾 保存模型")
    print("=" * 62)

    # 保存模型权重（最佳）
    torch.save(model.state_dict(), OUTPUT_MODEL)
    size_mb = os.path.getsize(OUTPUT_MODEL) / 1024 / 1024
    print(f"   模型权重: {OUTPUT_MODEL}  ({size_mb:.1f} MB)")

    # 保存特征配置（供 build_faiss_index.py 和 sync_recs_v3.py 重建模型）
    config = {
        'feature_columns':  feature_columns,
        'feature_names':    feature_names,
        'dnn_hidden_units': DNN_HIDDEN_UNITS,
        'dnn_dropout':      DROPOUT,
        'sparse_feat_specs': SPARSE_FEAT_SPECS,
        'dense_feat_specs':  DENSE_FEAT_SPECS,
        'history':          history,
        'best_epoch':       best_epoch,
        'best_val_auc':     best_val_auc,
        'train_time':       datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'version':          'v3',
    }
    with open(OUTPUT_CONFIG, 'wb') as f:
        pickle.dump(config, f, protocol=4)
    print(f"   模型配置: {OUTPUT_CONFIG}")
    print("   ✅ 保存完成")


# ============================================================
# main
# ============================================================

def main():
    print("\n" + "🎵" * 31)
    print("   MusicMode DeepFM v3 — 精排模型训练")
    print(f"   开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("🎵" * 31)

    set_seed(RANDOM_SEED)
    device = check_gpu()

    # 1. 加载数据
    feat = load_data()

    # 2. 构建特征列 & 分割数据
    (feature_columns, feature_names,
     train_data, val_data,
     train_target, val_target) = prepare_deepfm_data(feat)

    # 3. 训练
    model, history, best_epoch, best_val_auc = train_deepfm(
        feature_columns, feature_names,
        train_data, val_data, train_target, val_target, device
    )

    # 4. 可视化 + 保存
    plot_training_history(history)
    save_model(model, feature_columns, feature_names,
               history, best_epoch, best_val_auc)

    print(f"\n" + "=" * 62)
    print(f"✅ DeepFM v3 训练完成！")
    print(f"   最佳 val_AUC: {best_val_auc:.4f}（Epoch {best_epoch}）")
    print(f"   完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 62)
    print(f"\n🚀 下一步:")
    print(f"   python build_faiss_index.py   # 构建 FAISS 向量索引")
    print(f"   python build_ensemble.py      # 校准集成系数 α")


if __name__ == "__main__":
    main()
