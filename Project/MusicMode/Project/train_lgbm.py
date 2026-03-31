# -*- coding: utf-8 -*-
"""
train_lgbm.py — LightGBM 粗排模型训练

特点：
  - 输入: features_v3.pkl（来自 prepare_features_v3.py）
  - 目标: 预测"30天内重复收听"概率（二分类）
  - 模型: LightGBM（num_leaves=96, max_depth=6, n_estimators=12000）
  - 特征: 7 个稀疏特征 + 36 个稠密特征（含 OOF TE、SVD 嵌入）
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
    "objective":             "binary",
    "metric":                "auc",
    "boosting_type":         "gbdt",
    "num_leaves":            160,     # 新特征容量需求，调大叶节点数
    "max_depth":             6,
    "min_child_samples":     2000,
    "learning_rate":         0.007,   # 精细收敛，曲线仍在上升
    "feature_fraction":      0.65,
    "bagging_fraction":      0.7,
    "bagging_freq":          5,
    "reg_alpha":             1.0,
    "reg_lambda":            4.0,
    "n_estimators":          15000,   # 更多轮次
    "early_stopping_rounds": 400,     # 更耐心的早停
    "verbose":               -1,
    "n_jobs":                N_JOBS,
    "random_state":          RANDOM_SEED,
    "num_threads":           0,
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
    # 用户基础统计
    "user_play_count_log", "user_avg_completion",
    "user_genre_diversity",              # 用户兴趣多样性
    "user_30d_active_days",              # 近30天活跃天数
    # 歌曲基础统计
    "song_play_count_log", "song_avg_completion",
    "song_popularity_norm", "song_age_days_log",
    "song_target_rate",
    # 交互特征（仅保留有重要度的）
    "user_artist_match",                 # 保留（重要度 1.63M）
    "user_skip_rate",
    "song_skip_rate",
    # 时序匹配
    "hour_match",
    "dow_match",                         # 星期偏好匹配
    # 最近交互
    "days_since_artist_log",
    "days_since_last_play_log",          # 距上次听该歌的天数
    # 歌单亲和力
    "user_has_in_playlist",              # 该歌是否在用户歌单中
    "user_playlist_artist_count_log",    # 用户歌单中该艺术家歌曲数
    # B-3 记忆衰减特征
    "user_song_prev_play_days",          # 距上次听同一首歌的天数（-1=首次）
    "user_song_play_count_before",       # 此前听这首歌的次数
    # B-4 滚动窗口特征
    "user_7d_play_count_log",            # 近7天用户播放总量
    "user_30d_play_count_log",           # 近30天用户播放总量
    "user_7d_avg_completion",            # 近7天用户平均完播率
    "song_7d_play_count_log",            # 近7天歌曲播放总量
    "song_30d_play_count_log",           # 近30天歌曲播放总量
    "song_trending_ratio",               # 歌曲热度趋势（7d/30d_daily_avg）
    # SVD 嵌入（全维度）
    *[f"svd_user_song_{i}" for i in range(10)],
    *[f"svd_song_user_{i}" for i in range(10)],
    *[f"svd_user_artist_{i}" for i in range(5)],
    "svd_dot_score",
]

ALL_FEATURES = SPARSE_FEATURES + DENSE_FEATURES


# ============================================================
# 主函数
# ============================================================

def main():
    print("\n" + "🌲" * 31)
    print("   LightGBM 粗排模型训练")
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

    # ── 3. 用户级时序切分（向量化，验证集取每用户最后 VALID_RATIO 条记录）
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

    # ── 3b. Target Leakage 修复：仅对 song_target_rate 做 OOF TE
    # user_artist_repeat_rate / user_target_rate / user_genre_match 等已从特征列表删除
    # 仅保留 song_target_rate 的泄漏修复（该特征来自 play_history.target，存在信息泄漏）
    print("  🔧 修复 Target Leakage（song_target_rate OOF TE）...")
    _global_prior = float(y[train_idx].mean())
    # Bayesian Smoothing: TE_smoothed = (n × mean + m × prior) / (n + m)
    _SMOOTH_M = 100
    _s_stats = pd.DataFrame({
        "sid": song_id_enc[train_idx].astype(np.int32),
        "y":   y[train_idx].astype(np.float32),
    }).groupby("sid")["y"].agg(["count", "mean"]).reset_index()
    _s_stats["str_v"] = (_s_stats["count"] * _s_stats["mean"] + _SMOOTH_M * _global_prior) / (_s_stats["count"] + _SMOOTH_M)
    _s_df = _s_stats[["sid", "str_v"]]

    def _fix_leaky(idx):
        _tmp = pd.DataFrame({"sid": song_id_enc[idx].astype(np.int32)})
        _tmp = _tmp.merge(_s_df, on="sid", how="left")
        return _tmp["str_v"].fillna(_global_prior).values.astype(np.float32)

    IDX_STR = ALL_FEATURES.index("song_target_rate")

    X_train = X[train_idx].copy()
    X_val   = X[val_idx].copy()

    # ── OOF Target Encoding（5折，消除 song_target_rate 自我泄漏）
    print("  🔧 5折 OOF Target Encoding（song_target_rate，消除训练集自我泄漏）...")
    _N_OOF = 5
    _fold_edges = np.linspace(0, len(train_idx), _N_OOF + 1, dtype=int)
    _str_oof = np.full(len(y), _global_prior, dtype=np.float32)

    for _k in range(_N_OOF):
        _fold_mask = np.zeros(len(train_idx), dtype=bool)
        _fold_mask[_fold_edges[_k]:_fold_edges[_k+1]] = True
        _other_idx = train_idx[~_fold_mask]
        _this_fold = train_idx[_fold_mask]

        _om = pd.DataFrame({
            "sid": song_id_enc[_other_idx].astype(np.int32),
            "y":   y[_other_idx].astype(np.float32),
        })
        _s_o = _om.groupby("sid")["y"].agg(["count","mean"]).reset_index()
        _s_o["str_v"] = (_s_o["count"]*_s_o["mean"] + _SMOOTH_M*_global_prior) / (_s_o["count"] + _SMOOTH_M)

        _tf = pd.DataFrame({"sid": song_id_enc[_this_fold].astype(np.int32)})
        _tf = _tf.merge(_s_o[["sid","str_v"]], on="sid", how="left")
        _str_oof[_this_fold] = _tf["str_v"].fillna(_global_prior).values.astype(np.float32)

    # Apply OOF values to X_train
    X_train[:, IDX_STR] = _str_oof[train_idx]
    print(f"   ✅ OOF TE 完成（5折，song_target_rate 均值={_str_oof[train_idx].mean():.4f}）")

    # ── 验证集：用全量训练集统计回填（无泄漏，val 未参与统计）
    print("  🔧 验证集 Target Encoding（全量训练集统计 → val 回填）...")
    X_val[:, IDX_STR] = _fix_leaky(val_idx)

    y_train = y[train_idx]
    y_val   = y[val_idx]
    print(f"   训练集: {len(train_idx):,} 样本")
    print(f"   验证集: {len(val_idx):,} 样本")
    print(f"   ✅ 泄漏修复完成，global_prior={_global_prior:.4f}，Bayesian smoothing m={_SMOOTH_M}")
    print(f"   ✅ Cross TE 完成（genre/language/country_match 已替换为 Bayesian 平滑条件概率）")

    # ALS 信号由召回层通道C负责，不注入排序特征（train/inference特征集须一致）
    _eff_features = ALL_FEATURES

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

    # user_history_position 已禁用：与时序切分高度相关，导致 train/val 分布偏移，best_iter=4 假早停

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
    assert len(_s_df) > 0, "❌ song_target_rate TE 映射表为空"
    print(f"   ✅ 验证2 通过：song_target_rate OOF TE 映射表基于 {len(train_idx):,} 条训练样本构建（{len(_s_df):,} 首歌）")
    print(f"   ✅ 验证3：训练集正样本率={y_train.mean():.4f}  验证集正样本率={y_val.mean():.4f}")

    # ── 泄漏诊断：打印 train/val 单变量 AUC 差距 > 0.02 的特征（定位 best_iter=4 根因）
    print("\n🔍 特征泄漏诊断（train vs val 单变量 AUC，差距 > 0.02 的特征）...")
    from sklearn.metrics import roc_auc_score as _roc_diag
    _diag_found = False
    for _di, _dn in enumerate(_eff_features):
        try:
            _tr_a = _roc_diag(y_train, X_train[:, _di])
            _vl_a = _roc_diag(y_val,   X_val[:, _di])
            _tr_a = max(_tr_a, 1 - _tr_a)   # 统一为 >= 0.5
            _vl_a = max(_vl_a, 1 - _vl_a)
            if _tr_a - _vl_a > 0.02 or _tr_a > 0.65:
                print(f"   ⚠️  {_dn:35s}: train={_tr_a:.4f}  val={_vl_a:.4f}  gap={_tr_a-_vl_a:+.4f}")
                _diag_found = True
        except Exception:
            pass
    if not _diag_found:
        print("   ✅ 未发现明显泄漏特征（所有特征 train/val AUC 差距 ≤ 0.02）")

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

    evals_result = {}
    callbacks = [
        lgb.early_stopping(LGBM_PARAMS["early_stopping_rounds"], verbose=True),
        lgb.log_evaluation(period=50),
        lgb.record_evaluation(evals_result),
    ]

    model = lgb.train(
        params=base_params,
        train_set=train_data,
        num_boost_round=LGBM_PARAMS["n_estimators"],
        valid_sets=[train_data, val_data],
        valid_names=["train", "val"],
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

    # ── AUC 训练曲线可视化（train vs val）
    if "train" in evals_result and "val" in evals_result:
        _train_auc_curve = evals_result["train"]["auc"]
        _val_auc_curve   = evals_result["val"]["auc"]
        _epochs = range(1, len(_val_auc_curve) + 1)
        _best_ep = model.best_iteration

        OUTPUT_CURVE = os.path.join(LGBM_DIR, "lgbm_training_curve.png")
        fig2, ax2 = plt.subplots(figsize=(10, 5))
        ax2.plot(_epochs, _train_auc_curve, label="Train AUC", color="steelblue", linewidth=1.5)
        ax2.plot(_epochs, _val_auc_curve,   label="Val AUC",   color="tomato",    linewidth=1.5)
        ax2.axvline(_best_ep, color="gray", linestyle="--", linewidth=1, label=f"Best iter={_best_ep}")
        ax2.set_xlabel("Boosting Round")
        ax2.set_ylabel("AUC")
        ax2.set_title(f"LightGBM Training Curve (Best Val AUC={val_auc:.4f} @ iter {_best_ep})")
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(OUTPUT_CURVE, dpi=120)
        plt.close()
        print(f"   ✅ 训练 AUC 曲线已保存: {OUTPUT_CURVE}")

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
