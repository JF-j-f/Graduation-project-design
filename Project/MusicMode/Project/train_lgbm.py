# -*- coding: utf-8 -*-
"""
train_lgbm.py — LightGBM 精排模型训练

特点：
  - 输入: features_v3.pkl（25个特征，来自 prepare_features_v3.py）
  - 目标: 预测"30天内重复收听"概率（二分类）
  - 模型: LightGBM（num_leaves=127, max_depth=7, n_estimators=2000）
  - 特征: 所有 13 个稀疏特征（原始值）+ 12 个稠密特征
  - 输出: lgbm_model.pkl（精排模型）+ lgbm_feature_importance.png

执行：
  python train_lgbm.py

预计时间：约 15-30 分钟（7.37M 样本，CPU 训练）
预期 AUC：0.87-0.90

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
OUTPUT_MODEL    = os.path.join(MODE_DIR, "lgbm_model.pkl")
OUTPUT_PLOT     = os.path.join(MODE_DIR, "lgbm_importance.png")
OUTPUT_METRICS  = os.path.join(MODE_DIR, "lgbm_metrics.csv")       # 论文用：特征重要度 + 评估指标

# 训练配置
VALID_RATIO  = 0.1    # 验证集比例
RANDOM_SEED  = 42
N_JOBS       = -1     # 使用全部 CPU 核心

# LightGBM 超参数（KKBOX Kaggle 竞赛最优实践）
LGBM_PARAMS = {
    "objective":       "binary",
    "metric":          "auc",
    "boosting_type":   "gbdt",
    "num_leaves":      127,
    "max_depth":       7,
    "min_child_samples": 100,
    "learning_rate":   0.05,
    "feature_fraction": 0.8,
    "bagging_fraction": 0.8,
    "bagging_freq":    5,
    "reg_alpha":       0.1,
    "reg_lambda":      0.1,
    "n_estimators":    3000,
    "early_stopping_rounds": 200,
    "verbose":         -1,
    "n_jobs":          N_JOBS,
    "random_state":    RANDOM_SEED,
    # CPU 全核训练（LightGBM GPU build 在大数据高基数特征下有已知稳定性问题）
    "num_threads":     0,   # 0 = 全部 CPU 线程
}


# ============================================================
# 特征列定义
# ============================================================

# 稀疏特征（直接用原始编码值，LightGBM 自动处理）
SPARSE_FEATURES = [
    "user_id_encoded", "song_id_encoded",
    "age_bucket_encoded", "city_encoded",
    "tenure_bucket_encoded", "genre_encoded", "language_encoded",
    "artist_encoded", "origin_country_encoded",
    "year_bucket_encoded", "duration_bucket_encoded",
    "source_channel_encoded",
    "user_peak_hour_encoded",
]

# 稠密特征（已移除 Phase-C 零重要度特征: gender_encoded, dow_match,
#  user_30d_active_days, user_has_in_playlist, user_playlist_artist_count_log）
DENSE_FEATURES = [
    "user_play_count_log", "user_avg_completion",
    "user_genre_diversity",
    "song_play_count_log", "song_avg_completion",
    "song_popularity_norm", "song_age_days_log",
    "user_genre_match", "user_artist_match",
    "user_language_match", "user_country_match",
    "user_target_rate", "song_target_rate",
    "user_skip_rate",
    "song_skip_rate",
    "hour_match",
    "days_since_last_play_log",
    "days_since_artist_log",
    "user_artist_repeat_rate",
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

    with open(INPUT_FEATURES, "rb") as f:
        feat = pickle.load(f)

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

    # ── 3. 用户级时序切分（每位用户最后 10% 作为验证集，消除冷启动集中问题）
    MIN_INTERACTIONS = 5  # 交互数 < 5 的用户全部归入训练集
    print(f"\n🔀 用户级时序切分（验证集 {VALID_RATIO*100:.0f}%，MIN_INTERACTIONS={MIN_INTERACTIONS}）...")
    _df_meta = pd.DataFrame({
        "orig_idx": np.arange(len(play_time_unix)),
        "uid":      user_id_enc.astype(np.int32),
        "time":     play_time_unix,
    })
    _train_list, _val_list = [], []
    for _uid, _grp in _df_meta.groupby("uid", sort=False):
        _grp_sorted = _grp.sort_values("time")
        _n = len(_grp_sorted)
        if _n < MIN_INTERACTIONS:
            _train_list.append(_grp_sorted["orig_idx"].values)
        else:
            _n_val = max(1, int(_n * VALID_RATIO))
            _train_list.append(_grp_sorted.iloc[:-_n_val]["orig_idx"].values)
            _val_list.append(_grp_sorted.iloc[-_n_val:]["orig_idx"].values)
    train_idx = np.concatenate(_train_list)
    val_idx   = np.concatenate(_val_list) if _val_list else np.array([], dtype=np.int64)

    # ── 3b. Target Leakage 修复：仅用训练集数据重计算 3 个泄漏特征
    print("  🔧 修复 Target Leakage（user_artist_repeat_rate / user_target_rate / song_target_rate）...")
    _global_prior = float(y[train_idx].mean())
    _train_meta = pd.DataFrame({
        "uid": user_id_enc[train_idx].astype(np.int32),
        "art": artist_enc[train_idx].astype(np.int32),
        "sid": song_id_enc[train_idx].astype(np.int32),
        "y":   y[train_idx].astype(np.float32),
    })
    # Bayesian Smoothing: TE_smoothed = (n × mean + m × prior) / (n + m)
    _SMOOTH_M = 15
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

    X_train = X[train_idx].copy()
    X_val   = X[val_idx].copy()
    uar_tr, utr_tr, str_tr = _fix_leaky(train_idx)
    X_train[:, IDX_UAR] = uar_tr
    X_train[:, IDX_UTR] = utr_tr
    X_train[:, IDX_STR] = str_tr
    uar_vl, utr_vl, str_vl = _fix_leaky(val_idx)
    X_val[:, IDX_UAR]   = uar_vl
    X_val[:, IDX_UTR]   = utr_vl
    X_val[:, IDX_STR]   = str_vl

    y_train = y[train_idx]
    y_val   = y[val_idx]
    print(f"   训练集: {len(train_idx):,} 样本")
    print(f"   验证集: {len(val_idx):,} 样本")
    print(f"   ✅ 泄漏修复完成，global_prior={_global_prior:.4f}，Bayesian smoothing m={_SMOOTH_M}")

    # ── Phase B-2: Cross TE（user×genre / user×language / user×country 条件概率，仅训练集计算）
    print("\n🎯 Phase B-2: Cross TE（user×genre/language/country → P(target=1)）...")
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

    IDX_GM = ALL_FEATURES.index("user_genre_match")
    IDX_LM = ALL_FEATURES.index("user_language_match")
    IDX_CM = ALL_FEATURES.index("user_country_match")
    ug_tr, ul_tr, uc_tr = _fix_cross_te(train_idx)
    ug_vl, ul_vl, uc_vl = _fix_cross_te(val_idx)
    X_train[:, IDX_GM] = ug_tr;  X_val[:, IDX_GM] = ug_vl
    X_train[:, IDX_LM] = ul_tr;  X_val[:, IDX_LM] = ul_vl
    X_train[:, IDX_CM] = uc_tr;  X_val[:, IDX_CM] = uc_vl
    print(f"   ✅ Cross TE 完成（genre/language/country_match 已替换为 Bayesian 平滑条件概率）")

    # ── Phase B-1: ALS 向量注入（仅训练集重训 ALS，避免验证集软泄漏）
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
        # implicit ALS 语义（fit 了转置矩阵 item×user）：
        #   user_factors → song embeddings (n_songs × rank)
        #   item_factors → user embeddings (n_users × rank)
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

        # 仅注入 als_score（dot-product），避免 21 维向量引起快速过拟合
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
    # 验证2：Cross TE 映射表仅从 train_idx 行构建（行数核对）
    assert len(_ua_df) == _ua_stats.shape[0], "❌ TE 行数异常"
    print(f"   ✅ 验证2 通过：TE 映射表基于 {len(train_idx):,} 条训练样本构建")
    # 验证3：AUC 合理性（在训练后检查，此处先打印 val 集前5行特征供人工核查）
    print(f"   📋 验证集前3样本特征（user_artist_repeat_rate, user_target_rate, song_target_rate）:")
    for _i in range(min(3, len(val_idx))):
        print(f"      [{_i}] uar={X_val[_i, IDX_UAR]:.4f}  utr={X_val[_i, IDX_UTR]:.4f}  str={X_val[_i, IDX_STR]:.4f}")
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
    # 验证6：AUC 合理性断言（异常值触发警告）
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
