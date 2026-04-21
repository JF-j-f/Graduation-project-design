# -*- coding: utf-8 -*-
"""
build_ensemble.py — 精排集成（DeepFM + LightGBM → Meta-LR）

功能：
  1. 加载 DeepFM、LightGBM 在验证集上推断
  2. 元学习器（逻辑回归 Meta-LR）集成精排预测
  3. 输出对比报告 + ensemble_config.pkl

架构说明：
  DeepFM    — 精排层，捕捉特征同时性交互（FM+DNN），AUC=0.8202
  LightGBM  — 精排层（原粗排，移至此层），梯度提升树，AUC=0.8226
  BST       — 已移至粗排层（sync_recs_v3.py），负责 600→300 粗筛

执行：
  python build_ensemble.py

前置条件：
  - python train_deepfm_v3.py（产出 deepfm_model.pth + deepfm_oof.npy）
  - python train_lgbm.py      （产出 lgbm_model.pkl  + lgbm_oof.npy）

开发者：JunFu
"""

import os
import sys
import pickle
from pathlib import Path
import numpy as np
import pandas as pd
import warnings
warnings.filterwarnings('ignore')

from datetime import datetime
from sklearn.metrics import roc_auc_score

# ============================================================
# 配置
# ============================================================

MODE_DIR     = Path(__file__).resolve().parents[2] / "Mode"
FE_DIR       = MODE_DIR / "feature_engineering"
FR_DIR       = MODE_DIR / "fine_rank"
CR_DIR       = MODE_DIR / "coarse_rank"    # BST 粗排层模型所在目录
ENSEMBLE_DIR = FR_DIR / "ensemble"

# train_bst.py 已迁至 coarse_rank/，import 时需插入该目录到 sys.path
PROJECT_DIR    = str(Path(__file__).resolve().parent)                    # fine_rank/（本文件所在）
CR_PROJECT_DIR = str(Path(__file__).resolve().parent.parent / "coarse_rank")  # coarse_rank/（train_bst所在）
ENSEMBLE_DIR.mkdir(parents=True, exist_ok=True)

INPUT_FEATURES  = FE_DIR / "features_v3.pkl"
INPUT_SEQ       = FE_DIR / "features_seq.pkl"   # BST 序列特征
OUTPUT_ENSEMBLE = ENSEMBLE_DIR / "ensemble_config.pkl"
OUTPUT_REPORT   = ENSEMBLE_DIR / "ensemble_report.txt"
OUTPUT_METRICS  = ENSEMBLE_DIR / "ensemble_metrics.csv"

VALID_RATIO  = 0.1   # 与训练脚本保持一致
RANDOM_SEED  = 42
BATCH_SIZE   = 8192

# ── 模型路径配置（精排集成：DeepFM + LightGBM）
# 架构调整说明（原 DeepFM+BST → 现 DeepFM+LightGBM）：
#   DeepFM    — 精排层，归纳偏置=特征同时性交互（FM+DNN），AUC=0.8202
#   LightGBM  — 精排层，归纳偏置=树模型特征分裂（GBDT），AUC=0.8226
#   BST 已移至粗排层（sync_recs_v3.py），不再参与精排集成
#   DeepFM（神经网络）+ LightGBM（树模型）归纳偏置互补，集成多样性更强
MODEL_CONFIGS = {
    "DeepFM": {
        "type": "deepfm",
        "model_path":  FR_DIR / "deepfm" / "deepfm_model.pth",
        "config_path": FR_DIR / "deepfm" / "model_config.pkl",
    },
    "LightGBM": {
        "type": "lgbm",
        "model_path": FR_DIR / "lgbm" / "lgbm_model.pkl",
    },
}

# ============================================================
# 特征列定义（与训练脚本一致）
# ============================================================

SPARSE_FEATURES = [
    "user_id_encoded", "song_id_encoded",
    "genre_encoded", "language_encoded",
    "artist_encoded", "origin_country_encoded",
    "source_channel_encoded",
]

DENSE_FEATURES = [
    # 用户基础统计
    "user_play_count_log", "user_avg_completion",
    "user_genre_diversity", "user_30d_active_days",
    # 歌曲基础统计
    "song_play_count_log", "song_avg_completion",
    "song_popularity_norm", "song_age_days_log",
    "song_target_rate",
    # 交互特征
    "user_artist_match", "user_skip_rate", "song_skip_rate",
    # 时序匹配
    "hour_match", "dow_match",
    # 最近交互
    "days_since_artist_log", "days_since_last_play_log",
    # 歌单亲和力
    "user_has_in_playlist", "user_playlist_artist_count_log",
    # 记忆衰减：用户对同一首歌的历史播放行为
    "user_song_prev_play_days", "user_song_play_count_before",
    # 近期滚动窗口统计
    "user_7d_play_count_log", "user_30d_play_count_log",
    "user_7d_avg_completion",
    "song_7d_play_count_log", "song_30d_play_count_log",
    "song_trending_ratio",
    # SVD 协同过滤嵌入
    *[f"svd_user_song_{i}" for i in range(10)],
    *[f"svd_song_user_{i}" for i in range(10)],
    *[f"svd_user_artist_{i}" for i in range(5)],
    "svd_dot_score",
]

ALL_FEATURES = SPARSE_FEATURES + DENSE_FEATURES


# ============================================================
# Step 1: 加载数据 & 时序切分 & 泄漏修复
# ============================================================

def load_val_data():
    print("\n" + "=" * 62)
    print("[Step 1] 加载特征 & 时序切分 & 泄漏修复")
    print("=" * 62)

    with open(INPUT_FEATURES, "rb") as f:
        feat = pickle.load(f)

    arrays = {}
    for col in ALL_FEATURES:
        arrays[col] = feat[col] if col in feat else np.zeros(len(feat["target"]))

    X = np.column_stack([arrays[c] for c in ALL_FEATURES]).astype(np.float32)
    y = feat["target"].astype(np.int8)

    play_time_unix = feat.get("play_time_unix", np.zeros(len(y), dtype=np.int64))
    user_id_enc    = feat["user_id_encoded"]
    song_id_enc    = feat["song_id_encoded"]
    artist_enc     = feat["artist_encoded"]

    # 用户级时序切分（向量化，与训练脚本保持完全一致）
    MIN_INTERACTIONS = 5
    _df_meta = pd.DataFrame({
        "orig_idx": np.arange(len(play_time_unix)),
        "uid":      user_id_enc.astype(np.int32),
        "time":     play_time_unix,
    }).sort_values(["uid", "time"])
    _df_meta["_cnt"]  = _df_meta.groupby("uid")["uid"].transform("count")
    _df_meta["_rank"] = _df_meta.groupby("uid").cumcount()
    _n_val_vec        = (_df_meta["_cnt"] * VALID_RATIO).astype(int).clip(lower=1)
    _is_val           = ((_df_meta["_cnt"] >= MIN_INTERACTIONS) &
                         (_df_meta["_rank"] >= _df_meta["_cnt"] - _n_val_vec))
    train_idx = _df_meta.loc[~_is_val, "orig_idx"].values
    val_idx   = _df_meta.loc[ _is_val, "orig_idx"].values

    # song_target_rate 泄漏修复：用训练集的 OOF 平滑均值替换验证集的原始目标编码
    _global_prior = float(y[train_idx].mean())
    _SMOOTH_M = 100
    _s_stats = pd.DataFrame({
        "sid": song_id_enc[train_idx].astype(np.int32),
        "y":   y[train_idx].astype(np.float32),
    }).groupby("sid")["y"].agg(["count", "mean"]).reset_index()
    _s_stats["str_v"] = (
        (_s_stats["count"] * _s_stats["mean"] + _SMOOTH_M * _global_prior)
        / (_s_stats["count"] + _SMOOTH_M)
    )

    IDX_STR = ALL_FEATURES.index("song_target_rate")
    X_val = X[val_idx].copy()
    _sid_val = pd.DataFrame({"sid": song_id_enc[val_idx].astype(np.int32)})
    _sid_val = _sid_val.merge(_s_stats[["sid", "str_v"]], on="sid", how="left")
    X_val[:, IDX_STR] = _sid_val["str_v"].fillna(_global_prior).values.astype(np.float32)

    # SVD 重拟合：在训练集上拟合，避免验证集信息泄漏
    print("   🔧 SVD 重拟合（训练集拟合 → val 推断）...")
    from scipy.sparse import coo_matrix as _coo_svd
    from sklearn.decomposition import TruncatedSVD as _TruncSVD
    _u_all = feat["user_id_encoded"]
    _s_all = feat["song_id_encoded"]
    _a_all = feat["artist_encoded"]
    _n_u_s = int(_u_all.max()) + 1
    _n_s_s = int(_s_all.max()) + 1
    _n_a_s = int(_a_all.max()) + 1
    _us_mat = _coo_svd(
        (np.ones(len(train_idx), dtype=np.float32),
         (_u_all[train_idx].astype(np.int32), _s_all[train_idx].astype(np.int32))),
        shape=(_n_u_s, _n_s_s),
    ).tocsr()
    _svd_us = _TruncSVD(n_components=10, random_state=42)
    _uv_us  = _svd_us.fit_transform(_us_mat)
    _sv_us  = _svd_us.components_.T
    _ua_mat = _coo_svd(
        (np.ones(len(train_idx), dtype=np.float32),
         (_u_all[train_idx].astype(np.int32), _a_all[train_idx].astype(np.int32))),
        shape=(_n_u_s, _n_a_s),
    ).tocsr()
    _svd_ua = _TruncSVD(n_components=5, random_state=42)
    _uv_ua  = _svd_ua.fit_transform(_ua_mat)
    _ui = np.clip(_u_all[val_idx].astype(np.int32), 0, _uv_us.shape[0]-1)
    _si = np.clip(_s_all[val_idx].astype(np.int32), 0, _sv_us.shape[0]-1)
    # 注：_uv_ua 行索引为用户ID（_ui），与 train_lgbm.py 修复保持一致
    # 原代码误用 _ai（歌手ID）索引用户-歌手矩阵，导致 svd_user_artist 特征全部错乱
    for _i in range(10):
        X_val[:, ALL_FEATURES.index(f"svd_user_song_{_i}")] = _uv_us[_ui, _i].astype(np.float32)
    for _i in range(10):
        X_val[:, ALL_FEATURES.index(f"svd_song_user_{_i}")] = _sv_us[_si, _i].astype(np.float32)
    for _i in range(5):
        X_val[:, ALL_FEATURES.index(f"svd_user_artist_{_i}")] = _uv_ua[_ui, _i].astype(np.float32)
    X_val[:, ALL_FEATURES.index("svd_dot_score")] = (_uv_us[_ui] * _sv_us[_si]).sum(axis=1).astype(np.float32)
    print("   ✅ SVD 重拟合完成")

    y_val = y[val_idx]
    print(f"   验证集: {len(y_val):,} 样本 | 正样本率: {y_val.mean():.4f}")
    return X_val, y_val, feat, val_idx, train_idx


# ============================================================
# Step 2: 各模型推断
# ============================================================

def predict_torch_model(name, cfg, feat, val_idx):
    """DeepFM 推断（使用 deepctr-torch DeepFM 类加载权重）"""
    if not os.path.exists(cfg["model_path"]) or not os.path.exists(cfg.get("config_path", "")):
        print(f"   ⚠️  {name} 模型不存在，跳过")
        return None

    import torch
    from deepctr_torch.models import DeepFM
    from deepctr_torch.inputs import get_feature_names

    with open(cfg["config_path"], "rb") as f:
        model_cfg = pickle.load(f)

    feature_columns  = model_cfg["feature_columns"]
    dnn_hidden_units = model_cfg.get("dnn_hidden_units", (512, 256, 128, 64))
    dnn_dropout      = model_cfg.get("dnn_dropout", 0.2)
    sparse_specs     = model_cfg.get("sparse_feat_specs", [])
    dense_specs      = model_cfg.get("dense_feat_specs", [])

    model = DeepFM(
        linear_feature_columns=feature_columns,
        dnn_feature_columns=feature_columns,
        dnn_hidden_units=dnn_hidden_units,
        dnn_dropout=dnn_dropout,
        device='cpu',
    )
    state_dict = torch.load(cfg["model_path"], map_location='cpu', weights_only=True)
    model.load_state_dict(state_dict)
    model.eval()

    feature_names = get_feature_names(feature_columns)
    data_dict = {}
    for feat_name, enc_key, _, _ in sparse_specs:
        if enc_key in feat:
            data_dict[feat_name] = feat[enc_key][val_idx].astype(np.int32)
    for feat_name in dense_specs:
        if feat_name in feat:
            data_dict[feat_name] = np.nan_to_num(feat[feat_name][val_idx].astype(np.float32), nan=0.0)

    # Leakage 修复（简化版，用全局先验）
    _gp = float(feat["target"].mean())
    if "user_artist_repeat_rate" in data_dict: data_dict["user_artist_repeat_rate"][:] = _gp
    if "user_target_rate"        in data_dict: data_dict["user_target_rate"][:] = _gp
    if "song_target_rate"        in data_dict: data_dict["song_target_rate"][:] = _gp

    arrays = [data_dict[f].reshape(-1, 1) for f in feature_names]
    X_tensor = torch.from_numpy(np.concatenate(arrays, axis=1)).float()

    preds_list = []
    with torch.no_grad():
        for start in range(0, X_tensor.shape[0], BATCH_SIZE):
            batch = X_tensor[start:start+BATCH_SIZE]
            out = model(batch).squeeze().cpu().numpy()
            preds_list.append(out)

    preds = np.concatenate(preds_list)
    best_auc = model_cfg.get("best_val_auc", 0)
    print(f"   {name}: best_val_AUC={best_auc:.4f}")
    return preds


def predict_bst_model(name, cfg, feat, val_idx, train_idx):
    """
    BST 模型验证集推断。
    从 train_bst.py 导入模型类和特征规格，确保预处理与训练完全一致。
    """
    if not os.path.exists(cfg["model_path"]):
        print(f"   BST 模型权重不存在: {cfg['model_path']}")
        print(f"        请先运行: python train_bst.py")
        return None
    if not os.path.exists(cfg.get("config_path", "")):
        print(f"   BST 配置文件不存在: {cfg.get('config_path')}")
        return None
    if not os.path.exists(INPUT_SEQ):
        print(f"   序列文件不存在: {INPUT_SEQ}")
        return None

    try:
        import torch
        from torch.utils.data import DataLoader
        sys.path.insert(0, CR_PROJECT_DIR)   # train_bst.py 已迁至 coarse_rank/
        # 从 train_bst 导入模型类和特征规格（保证与训练完全对齐）
        from train_bst import BSTModel, BSTDataset, SPARSE_FEAT_SPECS, DENSE_FEAT_SPECS, SEQ_LEN

        # 加载模型配置并重建 BSTModel
        with open(cfg["config_path"], "rb") as f:
            model_cfg = pickle.load(f)

        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        model  = BSTModel(
            n_songs            = model_cfg["n_songs"],
            n_users            = model_cfg["n_users"],
            other_sparse_sizes = model_cfg["other_sparse_sizes"],
            dense_dim          = model_cfg["dense_dim"],
            embed_dim          = model_cfg.get("embed_dim", 32),
            seq_len            = model_cfg.get("seq_len",   50),
            n_heads            = model_cfg.get("n_heads",   4),
            d_model            = model_cfg.get("d_model",   64),
            ffn_dim            = model_cfg.get("ffn_dim",   128),
            dropout            = model_cfg.get("dropout",   0.4),
        ).to(device)
        sd = torch.load(cfg["model_path"], map_location=device, weights_only=True)
        model.load_state_dict(sd)
        model.eval()

        # 加载序列数据
        with open(INPUT_SEQ, "rb") as f:
            seq_data = pickle.load(f)

        n_samples = len(feat["target"])
        target    = feat["target"].astype(np.float32)

        # ── 构建稀疏特征矩阵 (N, 14)，顺序与 SPARSE_FEAT_SPECS 严格对齐
        sparse_parts = []
        for enc_key, _ in SPARSE_FEAT_SPECS:
            col = feat.get(enc_key)
            if col is None:
                col = np.zeros(n_samples, dtype=np.int32)
            else:
                if hasattr(col, "values"):
                    col = col.values
                col = np.asarray(col, dtype=np.int32)
            sparse_parts.append(col.reshape(-1, 1))
        sparse_arr = np.hstack(sparse_parts)   # (N, 14)

        # ── 构建稠密特征矩阵 (N, 35)，顺序与 DENSE_FEAT_SPECS 严格对齐
        dense_parts = []
        for feat_name in DENSE_FEAT_SPECS:
            col = feat.get(feat_name)
            if col is None:
                col = np.zeros(n_samples, dtype=np.float32)
            else:
                if hasattr(col, "values"):
                    col = col.values
                col = np.asarray(col, dtype=np.float32)
                col = np.nan_to_num(col, nan=0.0, posinf=10.0, neginf=-10.0)
            dense_parts.append(col.reshape(-1, 1))
        dense_arr = np.hstack(dense_parts)     # (N, 35)

        # ── 序列 (N, seq_len)
        seq_arr = seq_data["seq_song_ids"].astype(np.int32)   # (N, 50)

        # ── 构建验证集 Dataset（使用 train_bst.BSTDataset）
        val_ds = BSTDataset(
            seq_arr    = seq_arr[val_idx],
            sparse_arr = sparse_arr[val_idx],
            dense_arr  = dense_arr[val_idx],
            target_arr = target[val_idx],
        )
        val_loader = DataLoader(
            val_ds, batch_size=BATCH_SIZE * 2, shuffle=False,
            num_workers=0, pin_memory=(device.type == "cuda"),
        )

        # ── 批量推断（与 train_bst.eval_epoch 逻辑一致）
        preds_list = []
        with torch.no_grad():
            for seq_b, sparse_b, dense_b, _ in val_loader:
                seq_b    = seq_b.to(device)
                feat_b   = torch.cat(
                    [sparse_b.float().to(device), dense_b.to(device)], dim=-1
                )   # (B, 14+35=49)
                out = model(seq_b, feat_b).squeeze(-1)
                preds_list.append(out.cpu().float().numpy())

        preds    = np.concatenate(preds_list)
        best_auc = model_cfg.get("best_val_auc", 0.0)
        print(f"   {name}: best_val_AUC(训练时)={best_auc:.4f}")
        return preds

    except Exception as e:
        import traceback
        print(f"   BST 推断失败: {e}")
        traceback.print_exc()
        return None


def predict_lgbm_model(name, cfg, feat, val_idx):
    """
    LightGBM 验证集推断。
    按模型保存的 feature_names 顺序从 feat 字典逐列提取，
    确保特征顺序与 train_lgbm.py 训练时完全对齐。

    Args:
        name:    模型名称（用于日志输出）
        cfg:     MODEL_CONFIGS 中的配置字典
        feat:    features_v3.pkl 加载的完整特征字典
        val_idx: 验证集样本的原始行索引

    Returns:
        preds: shape (n_val,) 的预测概率数组，失败时返回 None
    """
    if not os.path.exists(cfg["model_path"]):
        print(f"   ⚠️  {name} 模型不存在，跳过: {cfg['model_path']}")
        return None
    try:
        with open(cfg["model_path"], "rb") as f:
            payload = pickle.load(f)
        lgbm_model     = payload["model"]
        feature_names  = payload["feature_names"]   # 59维，训练时保存的精确列名
        best_iteration = payload.get("best_iteration")
        val_auc_saved  = payload.get("val_auc", 0)

        # 按 feature_names 顺序逐列从 feat 字典提取验证集特征
        cols = []
        for fn in feature_names:
            col = feat.get(fn, np.zeros(len(feat["target"]), dtype=np.float32))
            col = np.nan_to_num(np.asarray(col, dtype=np.float32), nan=0.0)
            cols.append(col[val_idx].reshape(-1, 1))
        X_val_lgbm = np.hstack(cols)   # (n_val, 59)

        preds   = lgbm_model.predict(
            X_val_lgbm, num_iteration=best_iteration
        ).astype(np.float32)
        auc_now = roc_auc_score(feat["target"][val_idx], preds)
        print(f"   {name}: 训练时val_AUC={val_auc_saved:.4f}，"
              f"重推AUC={auc_now:.4f}，特征维度={len(feature_names)}")
        return preds

    except Exception as e:
        import traceback
        print(f"   {name} 推断失败: {e}")
        traceback.print_exc()
        return None


def _predict_lgbm_direct(name, cfg, X_val, y_val):
    """
    直接用 load_val_data() 已正确重算SVD的 X_val 进行LightGBM推断，
    避免从 feat 字典重建特征时引入 nan_to_num=0.0 导致的 Training-Serving Skew。

    train_lgbm.py 训练时：冷启动用户SVD特征设为 NaN（非0），LightGBM学会了NaN路由；
    若此处用 nan_to_num 填0，会破坏该路由，导致验证集AUC从0.82降至0.70左右。
    X_val 由 load_val_data() 按同一 SVD refit 流程计算，保证训练/推断特征口径一致。

    Args:
        name:  模型名称（日志用）
        cfg:   MODEL_CONFIGS 中对应条目
        X_val: load_val_data() 返回的验证集特征矩阵，已正确处理SVD和NaN
        y_val: 验证集标签，用于计算并打印AUC

    Returns:
        preds (np.float32 array) 或 None（模型文件不存在/加载失败）
    """
    if not os.path.exists(cfg["model_path"]):
        print(f"   ⚠️  {name} 模型不存在，跳过: {cfg['model_path']}")
        return None
    try:
        with open(cfg["model_path"], "rb") as f:
            payload = pickle.load(f)
        lgbm_model     = payload["model"]
        best_iteration = payload.get("best_iteration")
        val_auc_saved  = payload.get("val_auc", 0)

        # 直接用已重算SVD的 X_val，无需从 feat 逐列重建，保留 NaN 路由
        preds   = lgbm_model.predict(X_val, num_iteration=best_iteration).astype(np.float32)
        auc_now = roc_auc_score(y_val, preds)
        print(f"   {name}: 训练时val_AUC={val_auc_saved:.4f}，"
              f"重推AUC={auc_now:.4f}，特征维度={X_val.shape[1]}")
        return preds

    except Exception as e:
        import traceback
        print(f"   {name} 推断失败: {e}")
        traceback.print_exc()
        return None


def collect_predictions(X_val, y_val, feat, val_idx, train_idx):
    """收集 DeepFM 和 LightGBM 的预测概率"""
    print("\n" + "=" * 62)
    print("[Step 2] 各模型验证集推断（DeepFM / LightGBM）")
    print("=" * 62)

    model_preds = {}
    model_aucs  = {}

    for name, cfg in MODEL_CONFIGS.items():
        if cfg["type"] == "lgbm":
            # 使用 _predict_lgbm_direct 避免从 feat 重建特征时 nan_to_num 破坏NaN路由
            preds = _predict_lgbm_direct(name, cfg, X_val, y_val)
        elif cfg["type"] == "bst":
            preds = predict_bst_model(name, cfg, feat, val_idx, train_idx)
        else:
            preds = predict_torch_model(name, cfg, feat, val_idx)

        if preds is not None:
            auc = roc_auc_score(y_val, preds)
            model_preds[name] = preds
            model_aucs[name]  = auc
            print(f"   [{name}] 验证集 AUC = {auc:.4f}")

    return model_preds, model_aucs


# ============================================================
# Step 3: 元学习器训练（LightGBM，仅在OOF文件存在时执行）
# ============================================================

def meta_learner_training(y_val, model_preds, feat, val_idx):
    """
    加载 DeepFM + LightGBM 的OOF预测，训练逻辑回归元学习器（Meta-LR），
    并在验证集上评估其效果。

    两阶段Stacking框架：
    - 第一阶段：DeepFM/LightGBM通过K折OOF生成元特征（5折，保持一致）
    - 第二阶段：LogisticRegression拟合这两个元特征 → 输出最终集成分数

    架构调整：BST已移至粗排层，精排集成改为 DeepFM（神经网络）+ LightGBM（树模型）

    Returns:
        (meta_lr, meta_auc): 元学习器对象和验证集AUC，若OOF文件不存在则返回 (None, 0.0)
    """
    from sklearn.linear_model import LogisticRegression

    # OOF 文件路径：DeepFM 在 fine_rank/deepfm/，LightGBM 在 fine_rank/lgbm/
    deepfm_oof_path = os.path.join(FR_DIR, "deepfm", "deepfm_oof.npy")
    deepfm_idx_path = os.path.join(FR_DIR, "deepfm", "deepfm_oof_idx.npy")
    lgbm_oof_path   = os.path.join(FR_DIR, "lgbm",   "lgbm_oof.npy")
    lgbm_idx_path   = os.path.join(FR_DIR, "lgbm",   "lgbm_oof_idx.npy")

    for p in [deepfm_oof_path, deepfm_idx_path, lgbm_oof_path, lgbm_idx_path]:
        if not os.path.exists(p):
            print(f"\n   ⚠️  OOF文件不存在: {p}")
            print("      跳过元学习器训练")
            return None, 0.0

    print("\n" + "=" * 62)
    print("[Step 3] 元学习器训练（DeepFM + LightGBM OOF → LogisticRegression）")
    print("=" * 62)

    deepfm_oof = np.load(deepfm_oof_path)
    deepfm_idx = np.load(deepfm_idx_path)
    lgbm_oof   = np.load(lgbm_oof_path)
    lgbm_idx   = np.load(lgbm_idx_path)

    # 对齐两个OOF的原始索引（理论上完全相同，取交集作为保险）
    # OOF索引按时间排序，不是数值有序，需用字典映射避免searchsorted出错
    d_map = {int(idx): pos for pos, idx in enumerate(deepfm_idx)}
    l_map = {int(idx): pos for pos, idx in enumerate(lgbm_idx)}
    common_set = np.array(
        sorted(set(d_map.keys()) & set(l_map.keys())), dtype=np.int64
    )
    n_common = len(common_set)

    # 按 common_set 从各自OOF数组中取出对齐的预测值
    d_pos = np.array([d_map[int(i)] for i in common_set], dtype=np.int64)
    l_pos = np.array([l_map[int(i)] for i in common_set], dtype=np.int64)

    deepfm_oof_aligned = deepfm_oof[d_pos]
    lgbm_oof_aligned   = lgbm_oof[l_pos]
    y_oof = feat["target"][common_set].astype(np.int32)

    print(f"   OOF训练样本: {n_common:,} | 正样本率: {y_oof.mean():.4f}")

    X_meta_train = np.column_stack([deepfm_oof_aligned, lgbm_oof_aligned])
    meta_lr = LogisticRegression(C=1.0, max_iter=1000, random_state=42)
    meta_lr.fit(X_meta_train, y_oof)
    print(f"   逻辑回归元学习器训练完成（C=1.0, max_iter=1000）")

    # 在验证集上评估（使用 collect_predictions 已生成的验证集预测）
    meta_auc = 0.0
    if "DeepFM" in model_preds and "LightGBM" in model_preds:
        X_val_meta     = np.column_stack(
            [model_preds["DeepFM"], model_preds["LightGBM"]]
        )
        meta_val_preds = meta_lr.predict_proba(X_val_meta)[:, 1]
        meta_auc       = roc_auc_score(y_val, meta_val_preds)
        print(f"   元学习器验证集 AUC: {meta_auc:.4f}")
    else:
        print("   ⚠️  验证集预测不可用，跳过AUC评估")

    # 保存元学习器到 ensemble 目录
    meta_path = os.path.join(ENSEMBLE_DIR, "meta_learner.pkl")
    with open(meta_path, "wb") as f:
        pickle.dump(meta_lr, f, protocol=4)
    print(f"   ✅ 元学习器已保存: {meta_path}")

    return meta_lr, meta_auc


# ============================================================
# Step 4: 生成报告
# ============================================================

def generate_report(model_aucs, ensemble_results):
    print("\n" + "=" * 62)
    print("[Step 4] 生成横向对比报告")
    print("=" * 62)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 读取各模型训练信息
    model_info = {}
    for name, cfg in MODEL_CONFIGS.items():
        if name not in model_aucs:
            continue
        info = {"val_auc": model_aucs[name], "train_auc": 0, "duration_min": 0}
        try:
            if cfg["type"] == "lgbm":
                # LightGBM pkl payload 直接存有 train_auc 字段
                with open(cfg["model_path"], "rb") as f:
                    p = pickle.load(f)
                info["train_auc"] = p.get("train_auc", 0)
            else:
                # DeepFM/BST 通过 config_path 读取训练历史
                with open(cfg.get("config_path", ""), "rb") as f:
                    p = pickle.load(f)
                info["train_auc"] = max(p.get("history", {}).get("val_auc", [0]))
        except Exception:
            pass
        model_info[name] = info

    # 构建报告文本
    lines = []
    lines.append("=" * 62)
    lines.append(f"  模型横向对比报告 ({now})")
    lines.append("=" * 62)
    lines.append("")
    lines.append(f"{'模型':<16} {'Train AUC':>10} {'Val AUC':>10} {'耗时(min)':>10}")
    lines.append("-" * 50)

    for name in ["DeepFM", "LightGBM"]:
        if name in model_info:
            info = model_info[name]
            lines.append(f"{name:<16} {info['train_auc']:>10.4f} {info['val_auc']:>10.4f} {info['duration_min']:>10.1f}")

    lines.append("-" * 50)

    best_single = max(model_aucs.values()) if model_aucs else 0
    best_single_name = max(model_aucs, key=model_aucs.get) if model_aucs else "N/A"
    lines.append(f"{'Best Single':<16} {'':>10} {best_single:>10.4f} ({best_single_name})")

    for label, auc in ensemble_results.items():
        lines.append(f"{label:<16} {'':>10} {auc:>10.4f}")

    lines.append("")
    best_overall = max(list(ensemble_results.values()) + list(model_aucs.values()))
    lines.append(f"最终最佳 AUC: {best_overall:.4f}")
    if best_overall >= 0.80:
        lines.append(">>> 已达到 0.80 目标! <<<")
    else:
        lines.append(f">>> 距目标 0.80 还差 {0.80 - best_overall:.4f} <<<")

    lines.append("=" * 62)

    report_text = "\n".join(lines)
    print("\n" + report_text)

    with open(OUTPUT_REPORT, "w", encoding="utf-8") as f:
        f.write(report_text)
    print(f"\n   ✅ 报告已保存: {OUTPUT_REPORT}")

    # 保存 CSV
    rows = []
    for name, auc in model_aucs.items():
        rows.append({"model": name, "type": "single", "val_auc": auc})
    for label, auc in ensemble_results.items():
        rows.append({"model": label, "type": "ensemble", "val_auc": auc})
    pd.DataFrame(rows).to_csv(OUTPUT_METRICS, index=False, encoding="utf-8-sig")
    print(f"   ✅ 指标 CSV: {OUTPUT_METRICS}")

    return best_overall


# ============================================================
# 保存集成配置
# ============================================================

def save_config(model_aucs, ensemble_results, best_overall, meta_lr=None, meta_auc=0.0):
    """
    保存集成配置到 ensemble_config.pkl。
    使用逻辑回归元学习器（Meta-LR）作为集成推断方案。
    sync_recs_v3.py 加载时优先使用元学习器。
    """
    config = {
        "model_aucs":             model_aucs,
        "ensemble_results":       ensemble_results,
        "best_overall_auc":       best_overall,
        "calibrated_at":          datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "version":                "v9_logistic_meta_learner",
        # 元学习器可用标志（sync_recs_v3.py 据此决定推断路径）
        "meta_learner_available": meta_lr is not None,
        "meta_auc":               meta_auc,
    }
    with open(OUTPUT_ENSEMBLE, "wb") as f:
        pickle.dump(config, f, protocol=4)
    print(f"   ✅ 集成配置: {OUTPUT_ENSEMBLE}")


# ============================================================
# main
# ============================================================

def main():
    # 脚本级计时：在任何工作开始前记录，覆盖数据加载、推断、元学习器训练全程
    _start = datetime.now()
    print("\n" + "=" * 62)
    print("   精排集成（DeepFM + LightGBM Meta-LR）")
    print(f"   开始时间: {_start.strftime('%Y-%m-%d %H:%M:%S')}")
    print("   目标: 集成 AUC ≥ 0.800")
    print("=" * 62)

    # 1. 加载数据（时序切分 + 泄漏修复）
    X_val, y_val, feat, val_idx, train_idx = load_val_data()

    # 2. 各模型推断
    model_preds, model_aucs = collect_predictions(X_val, y_val, feat, val_idx, train_idx)

    if len(model_preds) == 0:
        print("\n❌ 无可用模型！请先训练至少一个模型。")
        sys.exit(1)

    ensemble_results = {}

    # 3. 元学习器训练（LightGBM，需要OOF文件）
    meta_lr, meta_auc = meta_learner_training(y_val, model_preds, feat, val_idx)
    if meta_lr is not None:
        ensemble_results["Meta-LR (OOF)"] = meta_auc

    # 4. 生成报告
    best_overall = generate_report(model_aucs, ensemble_results)

    # 5. 保存
    save_config(model_aucs, ensemble_results, best_overall, meta_lr=meta_lr, meta_auc=meta_auc)

    _elapsed = str(datetime.now() - _start).split(".")[0]
    print(f"\n{'=' * 62}")
    print(f"✅ 集成对比完成！最终最佳 AUC: {best_overall:.4f}")
    if best_overall >= 0.80:
        print(f"   🎉 AUC 已达到 0.80 目标！")
    else:
        print(f"   ⚠️  距目标 0.80 还差 {0.80 - best_overall:.4f}")
    print(f"   结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   总耗时:   {_elapsed}")
    print(f"{'=' * 62}")


if __name__ == "__main__":
    main()
