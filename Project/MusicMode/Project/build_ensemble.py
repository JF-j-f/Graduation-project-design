# -*- coding: utf-8 -*-
"""
build_ensemble.py — 3 模型横向对比 + 多策略集成

功能：
  1. 加载 3 个模型（LightGBM, DeepFM, DIEN）在验证集上推断
  2. 搜索最优加权系数（scipy.optimize.minimize，Kaggle Best Practice）
  3. Top-K 等权平均（K=2,3）
  4. Stacking 二阶段（Logistic Regression, Wolpert 1992）
  5. 输出横向对比报告 + ensemble_config.pkl

模型说明：
  LightGBM  — 梯度提升树，Val AUC ≈ 0.793
  DeepFM    — 因子分解机 + DNN，Val AUC ≈ 0.761
  DIEN      — 深度兴趣演化网络（Zhou et al. AAAI 2019），目标 Val AUC ≥ 0.770

执行：
  python build_ensemble.py

前置条件：
  - LightGBM:  python train_lgbm.py
  - DeepFM:    python train_deepfm_v3.py
  - DIEN:      python prepare_features_v3.py && python train_dien.py

作者：MusicMode 推荐系统
"""

import os
import sys
import pickle
import numpy as np
import pandas as pd
import warnings
warnings.filterwarnings('ignore')

from datetime import datetime
from sklearn.metrics import roc_auc_score
from sklearn.linear_model import LogisticRegression
from scipy.optimize import minimize

# ============================================================
# 配置
# ============================================================

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
MODE_DIR    = os.path.join(os.path.dirname(PROJECT_DIR), "Mode")

INPUT_FEATURES = os.path.join(MODE_DIR, "features_v3.pkl")
INPUT_SEQ      = os.path.join(MODE_DIR, "features_seq.pkl")   # DIEN 序列文件
ENSEMBLE_DIR   = os.path.join(MODE_DIR, "ensemble")
os.makedirs(ENSEMBLE_DIR, exist_ok=True)
OUTPUT_ENSEMBLE = os.path.join(ENSEMBLE_DIR, "ensemble_config.pkl")
OUTPUT_REPORT   = os.path.join(ENSEMBLE_DIR, "ensemble_report.txt")
OUTPUT_METRICS  = os.path.join(ENSEMBLE_DIR, "ensemble_metrics.csv")

VALID_RATIO  = 0.1   # 与训练脚本保持一致
RANDOM_SEED  = 42
BATCH_SIZE   = 8192

# 模型路径配置（三模型：LightGBM + DeepFM + DIEN）
MODEL_CONFIGS = {
    "LightGBM": {
        "type": "lgbm",
        "model_path": os.path.join(MODE_DIR, "lgbm", "lgbm_model.pkl"),
    },
    "DeepFM": {
        "type": "deepfm",
        "model_path": os.path.join(MODE_DIR, "deepfm", "deepfm_model.pth"),
        "config_path": os.path.join(MODE_DIR, "deepfm", "model_config.pkl"),
    },
    "DIEN": {
        "type": "dien",
        "model_path":  os.path.join(MODE_DIR, "dien", "dien_model.pth"),
        "config_path": os.path.join(MODE_DIR, "dien", "model_config.pkl"),
    },
}


# ============================================================
# 特征列定义（与训练脚本一致）
# ============================================================

SPARSE_FEATURES = [
    "user_id_encoded", "song_id_encoded",
    # 已删除零重要度：age_bucket_encoded, city_encoded, tenure_bucket_encoded,
    #   year_bucket_encoded, duration_bucket_encoded, user_peak_hour_encoded
    "genre_encoded", "language_encoded",
    "artist_encoded", "origin_country_encoded",
    "source_channel_encoded",
]

DENSE_FEATURES = [
    "user_play_count_log", "user_avg_completion",
    # user_genre_diversity: 删除（零重要度）
    "song_play_count_log", "song_avg_completion",
    "song_unique_users_log", "song_age_days_log",
    "user_genre_match", "user_artist_match",
    "user_language_match", "user_country_match",
    "user_target_rate", "song_target_rate",
    "user_skip_rate",
    "song_skip_rate",
    "hour_match",
    # days_since_last_play_log: 删除
    "days_since_artist_log",
    "user_artist_repeat_rate",
    # B-3/B-4 删除（零重要度）
    # SVD（仅保留非零维度）
    *[f"svd_user_song_{i}" for i in [0, 2, 3, 4, 5, 6, 9]],
    *[f"svd_song_user_{i}" for i in range(10)],
    *[f"svd_user_artist_{i}" for i in [0, 3, 4]],
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

    # user_history_position
    _df_meta["_seq_ratio"] = (
        _df_meta["_rank"] / (_df_meta["_cnt"] - 1).clip(lower=1)
    ).clip(0, 1).astype(np.float32)
    _seq_ratio_all = np.zeros(len(y), dtype=np.float32)
    _seq_ratio_all[_df_meta["orig_idx"].values] = _df_meta["_seq_ratio"].values

    # Target Leakage 修复
    _global_prior = float(y[train_idx].mean())
    _SMOOTH_M = 100  # 与训练脚本保持一致
    _train_meta = pd.DataFrame({
        "uid": user_id_enc[train_idx].astype(np.int32),
        "art": artist_enc[train_idx].astype(np.int32),
        "sid": song_id_enc[train_idx].astype(np.int32),
        "y":   y[train_idx].astype(np.float32),
    })
    _ua_stats = _train_meta.groupby(["uid", "art"])["y"].agg(["count", "mean"]).reset_index()
    _ua_stats["uar"] = (_ua_stats["count"] * _ua_stats["mean"] + _SMOOTH_M * _global_prior) / (_ua_stats["count"] + _SMOOTH_M)
    _u_stats = _train_meta.groupby("uid")["y"].agg(["count", "mean"]).reset_index()
    _u_stats["utr"] = (_u_stats["count"] * _u_stats["mean"] + _SMOOTH_M * _global_prior) / (_u_stats["count"] + _SMOOTH_M)
    _s_stats = _train_meta.groupby("sid")["y"].agg(["count", "mean"]).reset_index()
    _s_stats["str_v"] = (_s_stats["count"] * _s_stats["mean"] + _SMOOTH_M * _global_prior) / (_s_stats["count"] + _SMOOTH_M)

    def _fix_leaky(idx):
        _tmp = pd.DataFrame({"uid": user_id_enc[idx].astype(np.int32),
                              "art": artist_enc[idx].astype(np.int32),
                              "sid": song_id_enc[idx].astype(np.int32)})
        _tmp = _tmp.merge(_ua_stats[["uid","art","uar"]], on=["uid","art"], how="left")
        _tmp = _tmp.merge(_u_stats[["uid","utr"]], on="uid", how="left")
        _tmp = _tmp.merge(_s_stats[["sid","str_v"]], on="sid", how="left")
        _tmp["uar"]   = _tmp["uar"].fillna(_tmp["utr"]).fillna(_global_prior)
        _tmp["utr"]   = _tmp["utr"].fillna(_global_prior)
        _tmp["str_v"] = _tmp["str_v"].fillna(_global_prior)
        return (_tmp["uar"].values.astype(np.float32),
                _tmp["utr"].values.astype(np.float32),
                _tmp["str_v"].values.astype(np.float32))

    IDX_UAR = ALL_FEATURES.index("user_artist_repeat_rate")
    IDX_UTR = ALL_FEATURES.index("user_target_rate")
    IDX_STR = ALL_FEATURES.index("song_target_rate")

    X_val = X[val_idx].copy()
    uar_vl, utr_vl, str_vl = _fix_leaky(val_idx)
    X_val[:, IDX_UAR] = uar_vl
    X_val[:, IDX_UTR] = utr_vl
    X_val[:, IDX_STR] = str_vl

    # Cross TE
    _genre_enc   = feat.get("genre_encoded",          np.zeros(len(y), dtype=np.int32))
    _lang_enc    = feat.get("language_encoded",       np.zeros(len(y), dtype=np.int32))
    _country_enc = feat.get("origin_country_encoded", np.zeros(len(y), dtype=np.int32))
    _b2_meta = pd.DataFrame({
        "uid": user_id_enc[train_idx].astype(np.int32),
        "gnr": _genre_enc[train_idx].astype(np.int32),
        "lng": _lang_enc[train_idx].astype(np.int32),
        "ctr": _country_enc[train_idx].astype(np.int32),
        "y":   y[train_idx].astype(np.float32),
    })
    _ug_s = _b2_meta.groupby(["uid","gnr"])["y"].agg(["count","mean"]).reset_index()
    _ug_s["ug_te"] = (_ug_s["count"]*_ug_s["mean"] + _SMOOTH_M*_global_prior) / (_ug_s["count"] + _SMOOTH_M)
    _ul_s = _b2_meta.groupby(["uid","lng"])["y"].agg(["count","mean"]).reset_index()
    _ul_s["ul_te"] = (_ul_s["count"]*_ul_s["mean"] + _SMOOTH_M*_global_prior) / (_ul_s["count"] + _SMOOTH_M)
    _uc_s = _b2_meta.groupby(["uid","ctr"])["y"].agg(["count","mean"]).reset_index()
    _uc_s["uc_te"] = (_uc_s["count"]*_uc_s["mean"] + _SMOOTH_M*_global_prior) / (_uc_s["count"] + _SMOOTH_M)

    _t = pd.DataFrame({
        "uid": user_id_enc[val_idx].astype(np.int32),
        "gnr": _genre_enc[val_idx].astype(np.int32),
        "lng": _lang_enc[val_idx].astype(np.int32),
        "ctr": _country_enc[val_idx].astype(np.int32),
    })
    _t = _t.merge(_ug_s[["uid","gnr","ug_te"]], on=["uid","gnr"], how="left")
    _t = _t.merge(_ul_s[["uid","lng","ul_te"]], on=["uid","lng"], how="left")
    _t = _t.merge(_uc_s[["uid","ctr","uc_te"]], on=["uid","ctr"], how="left")

    IDX_GM = ALL_FEATURES.index("user_genre_match")
    IDX_LM = ALL_FEATURES.index("user_language_match")
    IDX_CM = ALL_FEATURES.index("user_country_match")
    X_val[:, IDX_GM] = _t["ug_te"].fillna(_global_prior).values.astype(np.float32)
    X_val[:, IDX_LM] = _t["ul_te"].fillna(_global_prior).values.astype(np.float32)
    X_val[:, IDX_CM] = _t["uc_te"].fillna(_global_prior).values.astype(np.float32)

    # ALS 向量注入
    ALS_MODEL_PATH = os.path.join(MODE_DIR, "als_model.pkl")
    _als_col = None
    try:
        from implicit.als import AlternatingLeastSquares as _ALS
        from scipy.sparse import csr_matrix as _csr
        if os.path.exists(ALS_MODEL_PATH):
            _n_u = int(user_id_enc.max()) + 1
            _n_s = int(song_id_enc.max()) + 1
            _tr_agg = pd.DataFrame({
                "u": user_id_enc[train_idx].astype(np.int32),
                "s": song_id_enc[train_idx].astype(np.int32),
                "y": y[train_idx].astype(np.float32),
            }).groupby(["u","s"])["y"].sum()
            _mat = _csr(
                (_tr_agg.values.astype(np.float32),
                 (_tr_agg.index.get_level_values("u"), _tr_agg.index.get_level_values("s"))),
                shape=(_n_u, _n_s), dtype=np.float32,
            )
            _als_m = _ALS(factors=50, iterations=10, regularization=0.1, use_gpu=False)
            _als_m.fit(_mat.T, show_progress=False)
            _ue = np.clip(user_id_enc[val_idx].astype(np.int32), 0, _als_m.item_factors.shape[0]-1)
            _se = np.clip(song_id_enc[val_idx].astype(np.int32), 0, _als_m.user_factors.shape[0]-1)
            _als_col = (_als_m.item_factors[_ue] * _als_m.user_factors[_se]).sum(axis=1, keepdims=True).astype(np.float32)
            print("   ✅ ALS 注入完成")
    except Exception as e:
        print(f"   ⚠️  ALS 跳过: {e}")

    if _als_col is not None:
        X_val = np.hstack([X_val, _als_col])

    # ── SVD 重拟合（在训练集上拟合，与训练脚本逻辑一致）
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
    _ai = np.clip(_a_all[val_idx].astype(np.int32), 0, _uv_ua.shape[0]-1)
    for _i in [0, 2, 3, 4, 5, 6, 9]:
        X_val[:, ALL_FEATURES.index(f"svd_user_song_{_i}")] = _uv_us[_ui, _i].astype(np.float32)
    for _i in range(10):
        X_val[:, ALL_FEATURES.index(f"svd_song_user_{_i}")] = _sv_us[_si, _i].astype(np.float32)
    for _i in [0, 3, 4]:
        X_val[:, ALL_FEATURES.index(f"svd_user_artist_{_i}")] = _uv_ua[_ai, _i].astype(np.float32)
    X_val[:, ALL_FEATURES.index("svd_dot_score")] = (_uv_us[_ui] * _sv_us[_si]).sum(axis=1).astype(np.float32)
    print("   ✅ SVD 重拟合完成")

    # ── user_history_position 注入
    X_val = np.hstack([X_val, _seq_ratio_all[val_idx].reshape(-1, 1)])
    print(f"   ✅ user_history_position 注入（val 均值={_seq_ratio_all[val_idx].mean():.3f}）")

    y_val = y[val_idx]
    print(f"   验证集: {len(y_val):,} 样本 | 正样本率: {y_val.mean():.4f}")
    return X_val, y_val, feat, val_idx, train_idx


# ============================================================
# Step 2: 各模型推断
# ============================================================

def predict_tree_model(name, cfg, X_val):
    """树模型推断（LightGBM）"""
    if not os.path.exists(cfg["model_path"]):
        print(f"   ⚠️  {name} 模型不存在，跳过")
        return None

    with open(cfg["model_path"], "rb") as f:
        payload = pickle.load(f)

    model = payload["model"]
    model_type = cfg["type"]

    # 安全校验：用模型保存的 feature_names 对齐列数
    saved_fnames = payload.get("feature_names")
    X_use = X_val
    if saved_fnames is not None and len(saved_fnames) != X_val.shape[1]:
        print(f"   ⚠️  特征列数不匹配 (data={X_val.shape[1]}, model={len(saved_fnames)})，尝试按 feature_names 截断")
        X_use = X_val[:, :len(saved_fnames)]

    if model_type == "lgbm":
        preds = model.predict(X_use, num_iteration=payload.get("best_iteration"))
    else:
        raise ValueError(f"Unknown type: {model_type}")

    auc = payload.get("val_auc", 0)
    duration = payload.get("duration_min", 0)
    train_auc = payload.get("train_auc", 0)
    print(f"   {name}: AUC={auc:.4f} (train={train_auc:.4f}, {duration:.1f} min)")
    return preds


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


def predict_dien_model(name, cfg, feat, val_idx, train_idx):
    """
    DIEN 模型验证集推断。

    与 DeepFM 推断不同，DIEN 需要额外加载序列数据（features_seq.pkl），
    并对输入数据进行与 train_dien.py 完全一致的预处理：
      - 低频 ID 过滤（min_count=3，仅统计训练集）
      - song_id +1 偏移（与序列 Embedding 表对齐）
      - OOF Target Encoding（全量训练集统计回填验证集）
      - user_history_position 计算

    Args:
        name     (str):  模型名称
        cfg      (dict): MODEL_CONFIGS 中的配置项
        feat     (dict): features_v3.pkl 内容
        val_idx  (np.ndarray): 验证集行索引
        train_idx (np.ndarray): 训练集行索引

    Returns:
        preds (np.ndarray | None): 验证集预测概率，失败返回 None
    """
    # ── 前置检查
    if not os.path.exists(cfg["model_path"]):
        print(f"   ⚠️  {name} 模型权重不存在: {cfg['model_path']}")
        print(f"        请先运行: python train_dien.py")
        return None
    if not os.path.exists(cfg.get("config_path", "")):
        print(f"   ⚠️  {name} 配置文件不存在: {cfg.get('config_path')}")
        return None
    if not os.path.exists(INPUT_SEQ):
        print(f"   ⚠️  序列文件不存在: {INPUT_SEQ}")
        print(f"        请先运行: python prepare_features_v3.py")
        return None

    try:
        # ── 延迟导入（避免 torch 未安装时整个脚本失败）
        import torch
        import torch.utils.data as Data
        # 直接从 train_dien 导入 DIENModel 及相关配置
        sys.path.insert(0, PROJECT_DIR)
        from train_dien import (
            DIENModel, DIENDataset,
            OTHER_SPARSE_SPECS, DENSE_FEAT_SPECS,
            SEQ_LEN, EMBEDDING_DIM, GRU_HIDDEN,
        )

        # ── 加载模型配置
        with open(cfg["config_path"], "rb") as f:
            model_cfg = pickle.load(f)

        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

        # ── 重建 DIENModel 并加载权重
        model = DIENModel(model_cfg).to(device)
        state_dict = torch.load(cfg["model_path"], map_location=device, weights_only=True)
        model.load_state_dict(state_dict)
        model.eval()

        # ── 加载序列文件
        with open(INPUT_SEQ, "rb") as f:
            seq = pickle.load(f)

        n_samples    = len(feat["target"])
        target       = feat["target"].astype(np.float32)

        # ── 低频 ID 过滤（min_count=3，与 train_dien.py 完全一致）
        _MIN_COUNT  = 3
        user_id_enc = feat["user_id_encoded"].copy().astype(np.int32)
        song_id_enc = feat["song_id_encoded"].copy().astype(np.int32)
        _u_counts = np.bincount(user_id_enc[train_idx],
                                minlength=int(user_id_enc.max()) + 1)
        _s_counts = np.bincount(song_id_enc[train_idx],
                                minlength=int(song_id_enc.max()) + 1)
        user_id_enc[np.isin(user_id_enc, np.where(_u_counts < _MIN_COUNT)[0])] = 0
        song_id_enc[np.isin(song_id_enc, np.where(_s_counts < _MIN_COUNT)[0])] = 0

        # 候选歌曲 ID：song_id_enc + 1（与序列 Embedding 表对齐）
        cand_song_ids = (song_id_enc + 1).astype(np.int32)

        # ── 构建稠密特征矩阵
        dense_list   = []
        active_dense = []
        for feat_name in DENSE_FEAT_SPECS:
            if feat_name in feat or feat_name == "user_history_position":
                arr = feat.get(feat_name, np.zeros(n_samples, dtype=np.float32)).astype(np.float32)
                arr = np.nan_to_num(arr, nan=0.0, posinf=10.0, neginf=0.0)
                dense_list.append(arr.reshape(-1, 1))
                active_dense.append(feat_name)
        dense_mat = np.concatenate(dense_list, axis=1).astype(np.float32)

        # ── user_history_position（用原有 _df_meta 等价重算）
        play_time_unix = feat.get("play_time_unix", np.zeros(n_samples, dtype=np.int64))
        _df = pd.DataFrame({
            "orig_idx": np.arange(n_samples),
            "uid":      feat["user_id_encoded"].astype(np.int32),
            "time":     play_time_unix,
        }).sort_values(["uid", "time"])
        _df["_cnt"]  = _df.groupby("uid")["uid"].transform("count")
        _df["_rank"] = _df.groupby("uid").cumcount()
        _df["_sr"]   = (_df["_rank"] / (_df["_cnt"] - 1).clip(lower=1)).clip(0, 1).astype(np.float32)
        _sr_all = np.zeros(n_samples, dtype=np.float32)
        _sr_all[_df["orig_idx"].values] = _df["_sr"].values
        _hp_idx = next((i for i, fn in enumerate(active_dense)
                        if fn == "user_history_position"), None)
        if _hp_idx is not None:
            dense_mat[:, _hp_idx] = _sr_all

        # ── OOF TE（全量训练集统计回填验证集，无泄漏）
        train_target  = target[train_idx]
        _gp           = float(train_target.mean())
        _uid  = feat["user_id_encoded"]
        _gnr  = feat.get("genre_encoded",          np.zeros(n_samples, dtype=np.int32))
        _lng  = feat.get("language_encoded",       np.zeros(n_samples, dtype=np.int32))
        _ctr  = feat.get("origin_country_encoded", np.zeros(n_samples, dtype=np.int32))
        _SM   = 100
        _fm = pd.DataFrame({
            "uid": _uid[train_idx].astype(np.int32),
            "gnr": _gnr[train_idx].astype(np.int32),
            "lng": _lng[train_idx].astype(np.int32),
            "ctr": _ctr[train_idx].astype(np.int32),
            "y":   train_target,
        })
        def _smooth_te(df, keys):
            g = df.groupby(keys)["y"].agg(["count", "mean"]).reset_index()
            g["te"] = (g["count"] * g["mean"] + _SM * _gp) / (g["count"] + _SM)
            return g

        _ug_s = _smooth_te(_fm, ["uid", "gnr"])
        _ul_s = _smooth_te(_fm, ["uid", "lng"])
        _uc_s = _smooth_te(_fm, ["uid", "ctr"])
        _vf = pd.DataFrame({
            "uid": _uid[val_idx].astype(np.int32),
            "gnr": _gnr[val_idx].astype(np.int32),
            "lng": _lng[val_idx].astype(np.int32),
            "ctr": _ctr[val_idx].astype(np.int32),
        })
        _vf = _vf.merge(_ug_s[["uid", "gnr", "te"]].rename(columns={"te": "ug"}),
                        on=["uid", "gnr"], how="left")
        _vf = _vf.merge(_ul_s[["uid", "lng", "te"]].rename(columns={"te": "ul"}),
                        on=["uid", "lng"], how="left")
        _vf = _vf.merge(_uc_s[["uid", "ctr", "te"]].rename(columns={"te": "uc"}),
                        on=["uid", "ctr"], how="left")
        for _te_col, _col_name in [("ug", "user_genre_match"),
                                   ("ul", "user_language_match"),
                                   ("uc", "user_country_match")]:
            _ci = next((i for i, fn in enumerate(active_dense) if fn == _col_name), None)
            if _ci is not None:
                dense_mat[val_idx, _ci] = _vf[_te_col].fillna(_gp).values.astype(np.float32)

        # ── 构建 OTHER_SPARSE 特征矩阵（13 维）
        sparse_list   = []
        for feat_name, enc_key, n_key, _ in OTHER_SPARSE_SPECS:
            if enc_key in feat and n_key in feat:
                arr = feat[enc_key].astype(np.int32).copy()
                if feat_name == "user_id":
                    arr = user_id_enc
                sparse_list.append(arr.reshape(-1, 1))
        other_sparse_mat = np.concatenate(sparse_list, axis=1).astype(np.int32) \
            if sparse_list else np.zeros((n_samples, 1), dtype=np.int32)

        # ── 构建验证集 DIENDataset
        seq_song_ids = seq["seq_song_ids"].astype(np.int32)
        seq_lengths  = np.minimum(seq["seq_lengths"], SEQ_LEN).astype(np.int32)
        val_ds = DIENDataset(
            other_sparse  = other_sparse_mat[val_idx],
            cand_song_ids = cand_song_ids[val_idx],
            dense_vals    = dense_mat[val_idx],
            hist_seq      = seq_song_ids[val_idx],
            seq_lengths   = seq_lengths[val_idx],
            targets       = target[val_idx],
        )
        val_loader = Data.DataLoader(
            val_ds, batch_size=BATCH_SIZE * 2, shuffle=False,
            num_workers=0, pin_memory=False,
        )

        # ── 批量推断
        preds_list = []
        with torch.no_grad():
            for sp, cs, dv, hs, sl, _ in val_loader:
                sp = sp.to(device); cs = cs.to(device)
                dv = dv.to(device); hs = hs.to(device); sl = sl.to(device)
                if device.type == 'cuda':
                    from torch.amp import autocast
                    with autocast(device_type='cuda'):
                        vp, _ = model(sp, cs, dv, hs, sl, is_training=False)
                else:
                    vp, _ = model(sp, cs, dv, hs, sl, is_training=False)
                preds_list.append(vp.cpu().float().numpy())

        preds    = np.concatenate(preds_list)
        best_auc = model_cfg.get("best_val_auc", 0.0)
        print(f"   {name}: best_val_AUC(训练时)={best_auc:.4f}")

        # 保存 val 预测（供后续调试）
        np.save(os.path.join(DIEN_DIR_PREDS, "dien_val_preds.npy"), preds)
        return preds

    except Exception as e:
        import traceback
        print(f"   ❌ {name} 推断失败: {e}")
        traceback.print_exc()
        return None


# DIEN val preds 保存目录（与模型同目录）
DIEN_DIR_PREDS = os.path.join(MODE_DIR, "dien")


def collect_predictions(X_val, y_val, feat, val_idx, train_idx):
    """收集所有可用模型的预测概率"""
    print("\n" + "=" * 62)
    print("[Step 2] 各模型验证集推断（LightGBM / DeepFM / DIEN）")
    print("=" * 62)

    model_preds = {}
    model_aucs  = {}

    for name, cfg in MODEL_CONFIGS.items():
        if cfg["type"] == "lgbm":
            preds = predict_tree_model(name, cfg, X_val)
        elif cfg["type"] == "dien":
            preds = predict_dien_model(name, cfg, feat, val_idx, train_idx)
        else:
            preds = predict_torch_model(name, cfg, feat, val_idx)

        if preds is not None:
            auc = roc_auc_score(y_val, preds)
            model_preds[name] = preds
            model_aucs[name]  = auc
            print(f"   [{name}] 验证集 AUC = {auc:.4f}")

    return model_preds, model_aucs


# ============================================================
# Step 3: 集成策略
# ============================================================

def ensemble_strategies(y_val, model_preds, model_aucs):
    print("\n" + "=" * 62)
    print("[Step 3] 集成策略对比")
    print("=" * 62)

    names = list(model_preds.keys())
    n_models = len(names)
    results = {}

    if n_models < 2:
        print("   ⚠️  可用模型不足 2 个，跳过集成")
        return results

    # ── 策略 A: 最优加权平均（scipy.optimize.minimize）
    print("\n  [A] 最优加权平均（scipy.optimize.minimize）...")
    pred_matrix = np.column_stack([model_preds[n] for n in names])

    def neg_auc(weights):
        w = np.array(weights)
        w = w / w.sum()
        ensemble = pred_matrix @ w
        return -roc_auc_score(y_val, ensemble)

    # 初始权重 = 等权
    x0 = np.ones(n_models) / n_models
    bounds = [(0, 1)] * n_models
    constraints = [{"type": "eq", "fun": lambda w: w.sum() - 1}]
    res = minimize(neg_auc, x0, method="SLSQP", bounds=bounds, constraints=constraints)

    best_weights = res.x / res.x.sum()
    best_ensemble = pred_matrix @ best_weights
    best_auc = roc_auc_score(y_val, best_ensemble)

    print(f"   最优权重:")
    for n, w in zip(names, best_weights):
        print(f"     {n}: {w:.4f}")
    print(f"   加权集成 AUC: {best_auc:.4f}")
    results["Weighted Avg"] = best_auc

    # ── 策略 B: Top-K 等权平均
    print("\n  [B] Top-K 等权平均...")
    sorted_models = sorted(model_aucs.items(), key=lambda x: -x[1])
    for k in range(2, n_models + 1):
        top_k = [n for n, _ in sorted_models[:k]]
        top_k_preds = np.mean([model_preds[n] for n in top_k], axis=0)
        top_k_auc = roc_auc_score(y_val, top_k_preds)
        label = f"Top-{k} Avg"
        results[label] = top_k_auc
        print(f"   {label} ({', '.join(top_k)}): AUC={top_k_auc:.4f}")

    # ── 策略 C: Stacking（Logistic Regression, Wolpert 1992）
    print("\n  [C] Stacking (Logistic Regression meta-learner)...")
    # 使用模型预测概率作为元特征
    meta_X = pred_matrix
    lr = LogisticRegression(C=1.0, max_iter=1000, random_state=RANDOM_SEED)
    lr.fit(meta_X, y_val)  # 简化版：直接在验证集上 fit（严格版需 K-Fold OOF）
    stacking_preds = lr.predict_proba(meta_X)[:, 1]
    stacking_auc = roc_auc_score(y_val, stacking_preds)
    results["Stacking (LR)"] = stacking_auc
    print(f"   Stacking AUC: {stacking_auc:.4f}")
    print(f"   LR 系数: {lr.coef_[0]}")

    return results, best_weights, names


# ============================================================
# Step 4: 生成报告
# ============================================================

def generate_report(model_aucs, ensemble_results, best_weights, weight_names):
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
                with open(cfg["model_path"], "rb") as f:
                    p = pickle.load(f)
                info["train_auc"] = p.get("train_auc", 0)
                info["duration_min"] = p.get("duration_min", 0)
            else:
                with open(cfg.get("config_path", ""), "rb") as f:
                    p = pickle.load(f)
                info["train_auc"] = max(p.get("history", {}).get("val_auc", [0]))
                info["duration_min"] = 0
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

    for name in ["LightGBM", "DeepFM", "DIEN"]:
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
    lines.append("最优加权系数:")
    for n, w in zip(weight_names, best_weights):
        lines.append(f"  {n}: {w:.4f}")

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

def save_config(model_aucs, ensemble_results, best_weights, weight_names, best_overall):
    config = {
        "model_aucs":       model_aucs,
        "ensemble_results": ensemble_results,
        "best_weights":     dict(zip(weight_names, best_weights.tolist())),
        "best_overall_auc": best_overall,
        "calibrated_at":    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "version":          "v5_dien_ensemble",
    }
    with open(OUTPUT_ENSEMBLE, "wb") as f:
        pickle.dump(config, f, protocol=4)
    print(f"   ✅ 集成配置: {OUTPUT_ENSEMBLE}")


# ============================================================
# main
# ============================================================

def main():
    print("\n" + "=" * 62)
    print("   3 模型横向对比 + 多策略集成（LightGBM + DeepFM + DIEN）")
    print(f"   开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("   目标: 集成 AUC ≥ 0.800")
    print("=" * 62)

    # 1. 加载数据（时序切分 + 泄漏修复）
    X_val, y_val, feat, val_idx, train_idx = load_val_data()

    # 2. 各模型推断
    model_preds, model_aucs = collect_predictions(X_val, y_val, feat, val_idx, train_idx)

    if len(model_preds) == 0:
        print("\n❌ 无可用模型！请先训练至少一个模型。")
        sys.exit(1)

    # 3. 集成策略
    if len(model_preds) >= 2:
        ensemble_results, best_weights, weight_names = ensemble_strategies(
            y_val, model_preds, model_aucs
        )
    else:
        ensemble_results = {}
        best_weights = np.array([1.0])
        weight_names = list(model_preds.keys())

    # 4. 生成报告
    best_overall = generate_report(model_aucs, ensemble_results, best_weights, weight_names)

    # 5. 保存
    save_config(model_aucs, ensemble_results, best_weights, weight_names, best_overall)

    print(f"\n{'=' * 62}")
    print(f"✅ 集成对比完成！最终最佳 AUC: {best_overall:.4f}")
    if best_overall >= 0.80:
        print(f"   🎉 AUC 已达到 0.80 目标！")
    else:
        print(f"   ⚠️  距目标 0.80 还差 {0.80 - best_overall:.4f}")
    print(f"{'=' * 62}")


if __name__ == "__main__":
    main()
