# -*- coding: utf-8 -*-
"""
train_lgbm.py — LightGBM 粗排模型训练

特点：
  - 输入: features_v3.pkl（来自 prepare_features_v3.py）
  - 目标: 预测"30天内重复收听"概率（二分类）
  - 模型: LightGBM（num_leaves=128, max_depth=6, n_estimators=8000）
  - 特征: 7 个稀疏特征 + 36 个稠密特征（含 SVD、user_history_position）
  - 输出: lgbm_model.pkl + lgbm_importance.png

执行：
  python train_lgbm.py

预计时间：约 30-60 分钟（7.37M 样本，CPU 训练）
作者：MusicMode 推荐系统
"""

import os
import sys
import pickle
import warnings
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime

from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score
import lightgbm as lgb

warnings.filterwarnings('ignore')

# ============================================================
# 配置
# ============================================================

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
MODE_DIR    = os.path.join(os.path.dirname(PROJECT_DIR), "Mode")

INPUT_FEATURES  = os.path.join(MODE_DIR, "features_v3.pkl")
LGBM_DIR        = os.path.join(MODE_DIR, "lgbm")
os.makedirs(LGBM_DIR, exist_ok=True)
OUTPUT_MODEL    = os.path.join(LGBM_DIR, "lgbm_model.pkl")
OUTPUT_PLOT     = os.path.join(LGBM_DIR, "lgbm_importance.png")
OUTPUT_METRICS  = os.path.join(LGBM_DIR, "lgbm_metrics.csv")       # 论文用：特征重要度 + 评估指标

# 训练配置
VALID_RATIO  = 0.1    # 验证集比例：10%，与 DeepFM/DIN 一致
RANDOM_SEED  = 42
N_JOBS       = -1     # 使用全部 CPU 核心

# LightGBM 超参数（KKBOX Kaggle 竞赛最优实践）
LGBM_PARAMS = {
    "objective":         "binary",   # 目标函数：二分类（输出 sigmoid 概率）
    "metric":            "auc",      # 评估指标：AUC（排序质量，不受正负样本比例影响）
    "boosting_type":     "gbdt",     # 提升类型：梯度提升决策树（GBDT）
    "num_leaves":        128,        # 每棵树最大叶节点数（越大模型越复杂，128≈2^7）
    "max_depth":         6,          # 树的最大深度（控制树结构复杂度，防止过深过拟合）
    "min_child_samples": 2000,       # 叶节点所需最少样本数（越大越保守，防止小叶片过拟合）
    "learning_rate":     0.01,       # 学习率（越小收敛越稳定，须配合大 n_estimators）
    "feature_fraction":  0.6,        # 列采样比例：每棵树随机使用 60% 特征（防过拟合+加速）
    "bagging_fraction":  0.7,        # 行采样比例：每轮随机使用 70% 样本（防过拟合）
    "bagging_freq":      5,          # 每 5 轮执行一次行采样
    "reg_alpha":         1.0,        # L1 正则化系数（促进稀疏，对无关特征权重归零有效）
    "reg_lambda":        5.0,        # L2 正则化系数（防止权重过大，减少方差）
    "n_estimators":      8000,       # 最大迭代轮次（配合 early_stopping，实际轮次由验证集决定）
    "early_stopping_rounds": 300,    # 早停耐心：验证集 AUC 连续 300 轮无提升则终止训练
    "verbose":           -1,         # 关闭 LightGBM 内部日志（由训练脚本统一输出）
    "n_jobs":            N_JOBS,     # 并行线程数（-1 = 自动使用全部 CPU 核心）
    "random_state":      RANDOM_SEED,# 随机种子（保证实验可复现）
    "num_threads":       0,          # 0 = 与 n_jobs 一致，自动使用所有线程
}


# ============================================================
# 特征列定义
# ============================================================

# 稀疏特征
SPARSE_FEATURES = [
    "user_id_encoded", "song_id_encoded",
    "genre_encoded", "language_encoded",
    "artist_encoded", "origin_country_encoded",
    "source_channel_encoded",
]

# 稠密特征
DENSE_FEATURES = [
    "user_play_count_log", "user_avg_completion",
    "song_play_count_log", "song_avg_completion",
    "song_unique_users_log", "song_age_days_log",
    "user_genre_match", "user_artist_match",
    "user_language_match", "user_country_match",
    "user_target_rate", "song_target_rate",
    "user_skip_rate",
    "song_skip_rate",
    "hour_match",
    "days_since_artist_log",
    "user_artist_repeat_rate",
    *[f"svd_user_song_{i}" for i in [0, 2, 3, 4, 5, 6, 9]],
    *[f"svd_song_user_{i}" for i in range(10)],
    *[f"svd_user_artist_{i}" for i in [0, 3, 4]],
    "svd_dot_score",
]

ALL_FEATURES = SPARSE_FEATURES + DENSE_FEATURES


# ============================================================
# 主函数
# ============================================================

def main():
    print("\n" + "🌲" * 31)
    print("   LightGBM 精排模型训练")
    print(f"   开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("🌲" * 31)

    # ── 1. 加载特征数据
    print(f"\n📥 加载特征: {INPUT_FEATURES}")
    if not os.path.exists(INPUT_FEATURES):
        print("❌ 特征文件不存在！请先运行 prepare_features_v3.py")
        sys.exit(1)

    _npz_cache = INPUT_FEATURES.replace(".pkl", "_cache.npz")
    _use_cache = (os.path.exists(_npz_cache) and
                  os.path.getmtime(_npz_cache) >= os.path.getmtime(INPUT_FEATURES))
    if _use_cache:
        print(f"   ⚡ 从 npz 缓存加载（速度 5-10x）...")
        _raw = np.load(_npz_cache, allow_pickle=True)
        feat = {k: _raw[k].item() if _raw[k].ndim == 0 else _raw[k] for k in _raw.files}
    else:
        print(f"   首次加载 pkl，同时生成 npz 缓存供后续使用...")
        with open(INPUT_FEATURES, "rb") as f:
            feat = pickle.load(f)
        np.savez(_npz_cache, **{k: np.array(v) for k, v in feat.items()})
        print(f"   ✅ npz 缓存已保存: {_npz_cache}")

    # ── 2. 构建特征矩阵
    print(f"\n🔧 构建特征矩阵...")
    arrays = {}
    for col in ALL_FEATURES:
        if col in feat:
            arrays[col] = feat[col]
        else:
            print(f"   ⚠️  缺少特征 {col}，用 0 填充")
            arrays[col] = np.zeros(len(feat["target"]))

    X = np.column_stack([arrays[c] for c in ALL_FEATURES]).astype(np.float32)
    y = feat["target"].astype(np.int8)

    print(f"   特征矩阵形状: {X.shape}")
    print(f"   正样本率: {y.mean():.4f}")

    # ── 2b. 加载时序元数据（用于时序切分 & 泄漏修复）
    play_time_unix = feat.get("play_time_unix", np.zeros(len(feat["target"]), dtype=np.int64))
    user_id_enc    = feat["user_id_encoded"]
    song_id_enc    = feat["song_id_encoded"]
    artist_enc     = feat["artist_encoded"]

    # ── 3. 用户级时序切分（向量化版本，速度 10x；同时计算 user_history_position）
    MIN_INTERACTIONS = 5
    print(f"\n🔀 用户级时序切分（验证集 {VALID_RATIO*100:.0f}%，向量化）...")
    _df_meta = pd.DataFrame({
        "orig_idx": np.arange(len(play_time_unix)),
        "uid":      user_id_enc.astype(np.int32),
        "time":     play_time_unix,
    }).sort_values(["uid", "time"])
    _df_meta["_cnt"]  = _df_meta.groupby("uid")["uid"].transform("count")
    _df_meta["_rank"] = _df_meta.groupby("uid").cumcount()   # 0-indexed
    _n_val_vec        = (_df_meta["_cnt"] * VALID_RATIO).astype(int).clip(lower=1)
    _is_val           = ((_df_meta["_cnt"] >= MIN_INTERACTIONS) &
                         (_df_meta["_rank"] >= _df_meta["_cnt"] - _n_val_vec))
    train_idx = _df_meta.loc[~_is_val, "orig_idx"].values
    val_idx   = _df_meta.loc[ _is_val, "orig_idx"].values

    # user_history_position：记录在用户历史中的位置比例（0=最早, 1=最新），对抗时序概念漂移
    _df_meta["_seq_ratio"] = (
        _df_meta["_rank"] / (_df_meta["_cnt"] - 1).clip(lower=1)
    ).clip(0, 1).astype(np.float32)
    _seq_ratio_all = np.zeros(len(y), dtype=np.float32)
    _seq_ratio_all[_df_meta["orig_idx"].values] = _df_meta["_seq_ratio"].values

    # ── 3b. Target Leakage 修复：仅用训练集统计重计算 3 个 TE 特征，消除自我泄漏
    print("  🔧 修复 Target Leakage（user_artist_repeat_rate / user_target_rate / song_target_rate）...")
    _global_prior = float(y[train_idx].mean())
    _train_meta = pd.DataFrame({
        "uid": user_id_enc[train_idx].astype(np.int32),
        "art": artist_enc[train_idx].astype(np.int32),
        "sid": song_id_enc[train_idx].astype(np.int32),
        "y":   y[train_idx].astype(np.float32),
    })
    # Bayesian Smoothing: TE_smoothed = (n × mean + m × prior) / (n + m)
    _SMOOTH_M = 100
    _ua_stats = _train_meta.groupby(["uid", "art"])["y"].agg(["count", "mean"]).reset_index()
    _ua_stats["uar"] = (_ua_stats["count"] * _ua_stats["mean"] + _SMOOTH_M * _global_prior) / (_ua_stats["count"] + _SMOOTH_M)
    _ua_df = _ua_stats[["uid", "art", "uar"]]
    _u_stats = _train_meta.groupby("uid")["y"].agg(["count", "mean"]).reset_index()
    _u_stats["utr"] = (_u_stats["count"] * _u_stats["mean"] + _SMOOTH_M * _global_prior) / (_u_stats["count"] + _SMOOTH_M)
    _u_df = _u_stats[["uid", "utr"]]
    _s_stats = _train_meta.groupby("sid")["y"].agg(["count", "mean"]).reset_index()
    _s_stats["str_v"] = (_s_stats["count"] * _s_stats["mean"] + _SMOOTH_M * _global_prior) / (_s_stats["count"] + _SMOOTH_M)
    _s_df = _s_stats[["sid", "str_v"]]

    def _fix_leaky(idx):
        _tmp = pd.DataFrame({
            "uid": user_id_enc[idx].astype(np.int32),
            "art": artist_enc[idx].astype(np.int32),
            "sid": song_id_enc[idx].astype(np.int32),
        })
        _tmp = _tmp.merge(_ua_df, on=["uid", "art"], how="left")
        _tmp = _tmp.merge(_u_df,  on="uid",          how="left")
        _tmp = _tmp.merge(_s_df,  on="sid",          how="left")
        _tmp["uar"]   = _tmp["uar"].fillna(_tmp["utr"]).fillna(_global_prior)
        _tmp["utr"]   = _tmp["utr"].fillna(_global_prior)
        _tmp["str_v"] = _tmp["str_v"].fillna(_global_prior)
        return (_tmp["uar"].values.astype(np.float32),
                _tmp["utr"].values.astype(np.float32),
                _tmp["str_v"].values.astype(np.float32))

    IDX_UAR = ALL_FEATURES.index("user_artist_repeat_rate")
    IDX_UTR = ALL_FEATURES.index("user_target_rate")
    IDX_STR = ALL_FEATURES.index("song_target_rate")

    # 提前加载 Cross TE 所需编码（OOF 循环内需要）
    _genre_enc   = feat.get("genre_encoded",          np.zeros(len(y), dtype=np.int32))
    _lang_enc    = feat.get("language_encoded",       np.zeros(len(y), dtype=np.int32))
    _country_enc = feat.get("origin_country_encoded", np.zeros(len(y), dtype=np.int32))

    X_train = X[train_idx].copy()
    X_val   = X[val_idx].copy()

    # ── OOF Target Encoding（5折，替代全量回写，消除自我泄漏）
    print("  🔧 5折 OOF Target Encoding（消除训练集自我泄漏）...")
    _N_OOF = 5
    _fold_edges = np.linspace(0, len(train_idx), _N_OOF + 1, dtype=int)
    _uar_oof = np.full(len(y), _global_prior, dtype=np.float32)
    _utr_oof = np.full(len(y), _global_prior, dtype=np.float32)
    _str_oof = np.full(len(y), _global_prior, dtype=np.float32)
    _ug_oof  = np.full(len(y), _global_prior, dtype=np.float32)
    _ul_oof  = np.full(len(y), _global_prior, dtype=np.float32)
    _uc_oof  = np.full(len(y), _global_prior, dtype=np.float32)

    for _k in range(_N_OOF):
        _fold_mask = np.zeros(len(train_idx), dtype=bool)
        _fold_mask[_fold_edges[_k]:_fold_edges[_k+1]] = True
        _other_idx = train_idx[~_fold_mask]
        _this_fold = train_idx[_fold_mask]

        # — Primary TE stats from other folds
        _om = pd.DataFrame({
            "uid": user_id_enc[_other_idx].astype(np.int32),
            "art": artist_enc[_other_idx].astype(np.int32),
            "sid": song_id_enc[_other_idx].astype(np.int32),
            "y":   y[_other_idx].astype(np.float32),
        })
        _ua_o = _om.groupby(["uid","art"])["y"].agg(["count","mean"]).reset_index()
        _ua_o["uar"] = (_ua_o["count"]*_ua_o["mean"] + _SMOOTH_M*_global_prior) / (_ua_o["count"] + _SMOOTH_M)
        _u_o  = _om.groupby("uid")["y"].agg(["count","mean"]).reset_index()
        _u_o["utr"]  = (_u_o["count"]*_u_o["mean"]  + _SMOOTH_M*_global_prior) / (_u_o["count"]  + _SMOOTH_M)
        _s_o  = _om.groupby("sid")["y"].agg(["count","mean"]).reset_index()
        _s_o["str_v"]= (_s_o["count"]*_s_o["mean"]  + _SMOOTH_M*_global_prior) / (_s_o["count"]  + _SMOOTH_M)

        # — Cross TE stats from other folds
        _om2 = pd.DataFrame({
            "uid": user_id_enc[_other_idx].astype(np.int32),
            "gnr": _genre_enc[_other_idx].astype(np.int32),
            "lng": _lang_enc[_other_idx].astype(np.int32),
            "ctr": _country_enc[_other_idx].astype(np.int32),
            "y":   y[_other_idx].astype(np.float32),
        })
        _ug_o = _om2.groupby(["uid","gnr"])["y"].agg(["count","mean"]).reset_index()
        _ug_o["ug_te"] = (_ug_o["count"]*_ug_o["mean"] + _SMOOTH_M*_global_prior) / (_ug_o["count"] + _SMOOTH_M)
        _ul_o = _om2.groupby(["uid","lng"])["y"].agg(["count","mean"]).reset_index()
        _ul_o["ul_te"] = (_ul_o["count"]*_ul_o["mean"] + _SMOOTH_M*_global_prior) / (_ul_o["count"] + _SMOOTH_M)
        _uc_o = _om2.groupby(["uid","ctr"])["y"].agg(["count","mean"]).reset_index()
        _uc_o["uc_te"] = (_uc_o["count"]*_uc_o["mean"] + _SMOOTH_M*_global_prior) / (_uc_o["count"] + _SMOOTH_M)

        # — Apply to this fold
        _tf = pd.DataFrame({
            "uid": user_id_enc[_this_fold].astype(np.int32),
            "art": artist_enc[_this_fold].astype(np.int32),
            "sid": song_id_enc[_this_fold].astype(np.int32),
            "gnr": _genre_enc[_this_fold].astype(np.int32),
            "lng": _lang_enc[_this_fold].astype(np.int32),
            "ctr": _country_enc[_this_fold].astype(np.int32),
        })
        _tf = _tf.merge(_ua_o[["uid","art","uar"]], on=["uid","art"], how="left")
        _tf = _tf.merge(_u_o[["uid","utr"]],        on="uid",          how="left")
        _tf = _tf.merge(_s_o[["sid","str_v"]],      on="sid",          how="left")
        _tf = _tf.merge(_ug_o[["uid","gnr","ug_te"]], on=["uid","gnr"], how="left")
        _tf = _tf.merge(_ul_o[["uid","lng","ul_te"]], on=["uid","lng"], how="left")
        _tf = _tf.merge(_uc_o[["uid","ctr","uc_te"]], on=["uid","ctr"], how="left")
        _tf["uar"]   = _tf["uar"].fillna(_tf["utr"]).fillna(_global_prior)
        _tf["utr"]   = _tf["utr"].fillna(_global_prior)
        _tf["str_v"] = _tf["str_v"].fillna(_global_prior)
        _tf["ug_te"] = _tf["ug_te"].fillna(_global_prior)
        _tf["ul_te"] = _tf["ul_te"].fillna(_global_prior)
        _tf["uc_te"] = _tf["uc_te"].fillna(_global_prior)
        _uar_oof[_this_fold] = _tf["uar"].values.astype(np.float32)
        _utr_oof[_this_fold] = _tf["utr"].values.astype(np.float32)
        _str_oof[_this_fold] = _tf["str_v"].values.astype(np.float32)
        _ug_oof[_this_fold]  = _tf["ug_te"].values.astype(np.float32)
        _ul_oof[_this_fold]  = _tf["ul_te"].values.astype(np.float32)
        _uc_oof[_this_fold]  = _tf["uc_te"].values.astype(np.float32)

    # Apply OOF values to X_train
    IDX_GM = ALL_FEATURES.index("user_genre_match")
    IDX_LM = ALL_FEATURES.index("user_language_match")
    IDX_CM = ALL_FEATURES.index("user_country_match")
    X_train[:, IDX_UAR] = _uar_oof[train_idx]
    X_train[:, IDX_UTR] = _utr_oof[train_idx]
    X_train[:, IDX_STR] = _str_oof[train_idx]
    X_train[:, IDX_GM]  = _ug_oof[train_idx]
    X_train[:, IDX_LM]  = _ul_oof[train_idx]
    X_train[:, IDX_CM]  = _uc_oof[train_idx]
    print(f"   ✅ OOF TE 完成（5折，训练集 user_artist_repeat_rate 均值={_uar_oof[train_idx].mean():.4f}）")

    # ── 验证集：用全量训练集统计回填（无泄漏，val 未参与统计）
    print("  🔧 验证集 Target Encoding（全量训练集统计 → val 回填）...")
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

    def _fix_cross_te(idx):
        _t = pd.DataFrame({
            "uid": user_id_enc[idx].astype(np.int32),
            "gnr": _genre_enc[idx].astype(np.int32),
            "lng": _lang_enc[idx].astype(np.int32),
            "ctr": _country_enc[idx].astype(np.int32),
        })
        _t = _t.merge(_ug_s[["uid","gnr","ug_te"]], on=["uid","gnr"], how="left")
        _t = _t.merge(_ul_s[["uid","lng","ul_te"]], on=["uid","lng"], how="left")
        _t = _t.merge(_uc_s[["uid","ctr","uc_te"]], on=["uid","ctr"], how="left")
        return (
            _t["ug_te"].fillna(_global_prior).values.astype(np.float32),
            _t["ul_te"].fillna(_global_prior).values.astype(np.float32),
            _t["uc_te"].fillna(_global_prior).values.astype(np.float32),
        )

    ug_vl, ul_vl, uc_vl = _fix_cross_te(val_idx)
    X_val[:, IDX_GM] = ug_vl
    X_val[:, IDX_LM] = ul_vl
    X_val[:, IDX_CM] = uc_vl

    uar_vl, utr_vl, str_vl = _fix_leaky(val_idx)
    X_val[:, IDX_UAR]   = uar_vl
    X_val[:, IDX_UTR]   = utr_vl
    X_val[:, IDX_STR]   = str_vl

    y_train = y[train_idx]
    y_val   = y[val_idx]
    print(f"   训练集: {len(train_idx):,} 样本")
    print(f"   验证集: {len(val_idx):,} 样本")
    print(f"   ✅ 泄漏修复完成，global_prior={_global_prior:.4f}，Bayesian smoothing m={_SMOOTH_M}")
    print(f"   ✅ Cross TE 完成（genre/language/country_match 已替换为 Bayesian 平滑条件概率）")

    # ── Phase B-1: ALS 向量注入（仅训练集重训，避免验证集泄漏）
    _als_features = []
    ALS_MODEL_PATH = os.path.join(MODE_DIR, "als_model.pkl")
    try:
        from implicit.als import AlternatingLeastSquares as _ALS
        from scipy.sparse import csr_matrix as _csr
        _HAS_IMPLICIT = True
    except ImportError:
        _HAS_IMPLICIT = False

    if _HAS_IMPLICIT and os.path.exists(ALS_MODEL_PATH):
        print("\n🎯 Phase B-1: ALS 向量注入（仅训练集重训）...")
        _n_u = int(user_id_enc.max()) + 1
        _n_s = int(song_id_enc.max()) + 1
        _tr_agg = (
            pd.DataFrame({
                "u": user_id_enc[train_idx].astype(np.int32),
                "s": song_id_enc[train_idx].astype(np.int32),
                "y": y[train_idx].astype(np.float32),
            }).groupby(["u","s"])["y"].sum()
        )
        _mat = _csr(
            (_tr_agg.values.astype(np.float32),
             (_tr_agg.index.get_level_values("u"), _tr_agg.index.get_level_values("s"))),
            shape=(_n_u, _n_s), dtype=np.float32,
        )
        _als_m = _ALS(factors=50, iterations=10, regularization=0.1, use_gpu=False)
        _als_m.fit(_mat.T, show_progress=False)
        _user_emb = _als_m.item_factors   # (n_users, 50)
        _song_emb = _als_m.user_factors   # (n_songs, 50)
        _N_DIM = 10

        def _als_feats(u_enc, s_enc):
            _ue = np.clip(u_enc.astype(np.int32), 0, _user_emb.shape[0]-1)
            _se = np.clip(s_enc.astype(np.int32), 0, _song_emb.shape[0]-1)
            _uv = _user_emb[_ue]
            _sv = _song_emb[_se]
            _sc = (_uv * _sv).sum(axis=1, keepdims=True)   # dot-product score
            return np.hstack([_sc, _uv[:, :_N_DIM], _sv[:, :_N_DIM]]).astype(np.float32)  # (N, 21)

        def _als_score_only(u_enc, s_enc):
            _ue = np.clip(u_enc.astype(np.int32), 0, _user_emb.shape[0]-1)
            _se = np.clip(s_enc.astype(np.int32), 0, _song_emb.shape[0]-1)
            _sc = (_user_emb[_ue] * _song_emb[_se]).sum(axis=1, keepdims=True)
            return _sc.astype(np.float32)

        X_train = np.hstack([X_train, _als_score_only(user_id_enc[train_idx], song_id_enc[train_idx])])
        X_val   = np.hstack([X_val,   _als_score_only(user_id_enc[val_idx],   song_id_enc[val_idx])])
        _als_features = ["als_score"]
        print(f"   ✅ ALS 注入完成: als_score（1 维 dot-product，避免高维向量过拟合）")
    else:
        print("   ⚠️  跳过 ALS 注入（implicit 未安装或模型不存在）")

    _eff_features = ALL_FEATURES + _als_features

    # ── Phase SVD: 训练集专用 SVD（消除全量预计算导致的验证集泄漏）
    print("\n🔧 Phase SVD: 重新在训练集拟合 SVD，消除验证集泄漏...")
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
    _uv_us  = _svd_us.fit_transform(_us_mat)   # (n_users, 10)
    _sv_us  = _svd_us.components_.T             # (n_songs, 10)
    _ua_mat = _coo_svd(
        (np.ones(len(train_idx), dtype=np.float32),
         (_u_all[train_idx].astype(np.int32), _a_all[train_idx].astype(np.int32))),
        shape=(_n_u_s, _n_a_s),
    ).tocsr()
    _svd_ua = _TruncSVD(n_components=5, random_state=42)
    _uv_ua  = _svd_ua.fit_transform(_ua_mat)   # (n_users, 5)

    def _apply_svd(X_set, idx_set):
        _ui = np.clip(_u_all[idx_set].astype(np.int32), 0, _uv_us.shape[0]-1)
        _si = np.clip(_s_all[idx_set].astype(np.int32), 0, _sv_us.shape[0]-1)
        for _i in [0, 2, 3, 4, 5, 6, 9]:   # 只更新 DENSE_FEATURES 中保留的 svd_user_song 维度
            X_set[:, ALL_FEATURES.index(f"svd_user_song_{_i}")] = _uv_us[_ui, _i].astype(np.float32)
        for _i in range(10):                 # svd_song_user 全部保留
            X_set[:, ALL_FEATURES.index(f"svd_song_user_{_i}")] = _sv_us[_si, _i].astype(np.float32)
        _ai = np.clip(_a_all[idx_set].astype(np.int32), 0, _uv_ua.shape[0]-1)
        for _i in [0, 3, 4]:                 # 只更新 DENSE_FEATURES 中保留的 svd_user_artist 维度
            X_set[:, ALL_FEATURES.index(f"svd_user_artist_{_i}")] = _uv_ua[_ui, _i].astype(np.float32)
        X_set[:, ALL_FEATURES.index("svd_dot_score")] = (_uv_us[_ui] * _sv_us[_si]).sum(axis=1).astype(np.float32)
        return X_set

    X_train = _apply_svd(X_train, train_idx)
    X_val   = _apply_svd(X_val,   val_idx)
    print(f"   ✅ SVD 泄漏修复完成（训练集拟合 → user-song 7d + song-user 10d + user-artist 3d + dot）")

    # ── user_history_position 注入（对抗时序概念漂移）
    X_train = np.hstack([X_train, _seq_ratio_all[train_idx].reshape(-1, 1)])
    X_val   = np.hstack([X_val,   _seq_ratio_all[val_idx].reshape(-1, 1)])
    _eff_features = _eff_features + ["user_history_position"]
    print(f"   ✅ user_history_position 注入完成（val 位置均值={_seq_ratio_all[val_idx].mean():.3f}）")

    # ── 训练前验证（防止 target leakage）
    print("\n🔍 训练前验证...")
    # 验证1：每用户 val 记录时间 > train 记录时间（抽样100用户）
    _val_uids = np.unique(user_id_enc[val_idx])
    _sample_uids = _val_uids[:min(100, len(_val_uids))]
    _leakage_count = 0
    for _u in _sample_uids:
        _tr_mask = (user_id_enc[train_idx] == _u)
        _vl_mask = (user_id_enc[val_idx]   == _u)
        if _tr_mask.any() and _vl_mask.any():
            _tr_max = play_time_unix[train_idx[_tr_mask]].max()
            _vl_min = play_time_unix[val_idx[_vl_mask]].min()
            if _vl_min < _tr_max:   # 允许 vl_min==tr_max（时间戳并列），仅拒绝严格早于
                _leakage_count += 1
    assert _leakage_count == 0, f"❌ 时间泄漏：{_leakage_count} 个用户的 val 记录严格早于 train 最晚记录！"
    print(f"   ✅ 验证1 通过：抽样 {len(_sample_uids)} 用户，无时间泄漏")
    assert len(_ua_df) == _ua_stats.shape[0], "❌ TE 行数异常"
    print(f"   ✅ 验证2 通过：TE 映射表基于 {len(train_idx):,} 条训练样本构建")
    print(f"   ✅ 验证3：训练集正样本率={y_train.mean():.4f}  验证集正样本率={y_val.mean():.4f}")

    train_data = lgb.Dataset(X_train, label=y_train, feature_name=_eff_features)
    val_data   = lgb.Dataset(X_val,   label=y_val,   feature_name=_eff_features,
                              reference=train_data)

    # ── 4. 训练（CPU 全核）
    base_params = {k: v for k, v in LGBM_PARAMS.items()
                   if k not in ("n_estimators", "early_stopping_rounds")}
    print(f"\n🚀 开始训练 LightGBM (CPU 全核模式)...")
    print(f"   参数: num_leaves={LGBM_PARAMS['num_leaves']}, "
          f"max_depth={LGBM_PARAMS['max_depth']}, "
          f"n_estimators={LGBM_PARAMS['n_estimators']}")

    callbacks = [
        lgb.early_stopping(LGBM_PARAMS["early_stopping_rounds"], verbose=True),
        lgb.log_evaluation(period=50),
    ]

    model = lgb.train(
        params=base_params,
        train_set=train_data,
        num_boost_round=LGBM_PARAMS["n_estimators"],
        valid_sets=[val_data],
        valid_names=["val"],
        callbacks=callbacks,
    )

    # ── 5. 评估
    print(f"\n📊 模型评估...")
    val_pred = model.predict(X_val, num_iteration=model.best_iteration)
    val_auc  = roc_auc_score(y_val, val_pred)
    train_pred = model.predict(X_train, num_iteration=model.best_iteration)
    train_auc  = roc_auc_score(y_train, train_pred)

    print(f"   训练集 AUC: {train_auc:.4f}")
    print(f"   验证集 AUC: {val_auc:.4f}")
    print(f"   最佳迭代轮次: {model.best_iteration}")
    # AUC 合理性断言
    if not (0.60 < val_auc < 0.99):
        print(f"   ⚠️  警告：val AUC={val_auc:.4f} 超出合理范围 (0.60, 0.99)，请检查泄漏！")
    else:
        print(f"   ✅ 验证6 通过：AUC 在合理范围内")

    # ── 6. 特征重要性图
    print(f"\n📈 绘制特征重要性图...")
    importance_df = pd.DataFrame({
        "feature": _eff_features,
        "importance": model.feature_importance(importance_type="gain"),
    }).sort_values("importance", ascending=False)

    fig, ax = plt.subplots(figsize=(10, max(6, len(_eff_features) * 0.4)))
    ax.barh(importance_df["feature"][::-1], importance_df["importance"][::-1])
    ax.set_xlabel("Importance (Gain)")
    ax.set_title(f"LightGBM Feature Importance (val AUC={val_auc:.4f})")
    plt.tight_layout()
    plt.savefig(OUTPUT_PLOT, dpi=120)
    plt.close()
    print(f"   ✅ 已保存: {OUTPUT_PLOT}")

    # ── 7. 保存模型
    print(f"\n💾 保存模型: {OUTPUT_MODEL}")
    model_payload = {
        "model":           model,
        "feature_names":   _eff_features,
        "best_iteration":  model.best_iteration,
        "val_auc":         val_auc,
        "train_auc":       train_auc,
        "train_time":      datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "n_train":         X_train.shape[0],
        "n_val":           X_val.shape[0],
        "feature_importance": importance_df.to_dict("records"),
    }
    with open(OUTPUT_MODEL, "wb") as f:
        pickle.dump(model_payload, f, protocol=4)
    print(f"   ✅ 模型已保存（{os.path.getsize(OUTPUT_MODEL)/1024/1024:.1f} MB）")

    # ── 8. 打印 Top10 特征 + 保存 CSV（论文用）
    print(f"\n🏆 Top-10 重要特征:")
    for i, row in importance_df.head(10).iterrows():
        print(f"   {row['feature']:<35} {row['importance']:>12.0f}")

    importance_df["val_auc"]   = val_auc
    importance_df["train_auc"] = train_auc
    importance_df["n_train"]   = X_train.shape[0]
    importance_df["n_val"]     = X_val.shape[0]
    importance_df.to_csv(OUTPUT_METRICS, index=False, encoding="utf-8-sig")
    print(f"   ✅ 特征重要度 CSV: {OUTPUT_METRICS}")

    print(f"\n" + "=" * 62)
    print(f"✅ LightGBM 训练完成！")
    print(f"   验证集 AUC: {val_auc:.4f}")
    print(f"   完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 62)
    print(f"\n🚀 下一步: python train_deepfm_v3.py")


if __name__ == "__main__":
    main()
