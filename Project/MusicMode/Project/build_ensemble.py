# -*- coding: utf-8 -*-
"""
build_ensemble.py — LightGBM + DeepFM 集成系数校准

功能：
  在验证集上搜索最优混合系数 α：
    final_score = α × LightGBM_score + (1-α) × DeepFM_score
  输出: ensemble_config.pkl（含最优 α 和集成 AUC）

执行：
  python build_ensemble.py

预计时间：约 3-5 分钟

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

# ============================================================
# 配置
# ============================================================

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
MODE_DIR    = os.path.join(os.path.dirname(PROJECT_DIR), "Mode")

INPUT_FEATURES   = os.path.join(MODE_DIR, "features_v3.pkl")
INPUT_LGBM       = os.path.join(MODE_DIR, "lgbm_model.pkl")
INPUT_DEEPFM     = os.path.join(MODE_DIR, "deepfm_model_v3.pth")
INPUT_DEEPFM_CFG = os.path.join(MODE_DIR, "model_config_v3.pkl")
OUTPUT_ENSEMBLE  = os.path.join(MODE_DIR, "ensemble_config.pkl")

# 搜索 α 的范围（步长 0.05，从偏 LightGBM 到偏 DeepFM）
ALPHA_RANGE = np.arange(0.0, 1.05, 0.05)

VALID_RATIO  = 0.1
RANDOM_SEED  = 42
BATCH_SIZE   = 8192   # DeepFM 推断批次


# ============================================================
# 工具
# ============================================================

def check_files():
    missing = []
    for path, name in [
        (INPUT_FEATURES,   "features_v3.pkl"),
        (INPUT_LGBM,       "lgbm_model.pkl"),
        (INPUT_DEEPFM,     "deepfm_model_v3.pth"),
        (INPUT_DEEPFM_CFG, "model_config_v3.pkl"),
    ]:
        if not os.path.exists(path):
            missing.append(name)
    if missing:
        print("❌ 缺少必要文件:")
        for m in missing:
            print(f"   - {m}")
        print("\n   请按顺序执行:")
        print("   1. python prepare_features_v3.py")
        print("   2. python train_lgbm.py")
        print("   3. python train_deepfm_v3.py")
        sys.exit(1)


# ============================================================
# Step 1: 加载数据 & 划分验证集
# ============================================================

def load_val_data():
    print("\n" + "=" * 62)
    print("📂 [Step 1/4] 加载特征数据 & 划分验证集")
    print("=" * 62)

    with open(INPUT_FEATURES, "rb") as f:
        feat = pickle.load(f)

    # ── LightGBM 需要的特征矩阵（与 train_lgbm.py 保持完全一致，Phase C 已移除零重要度特征）
    SPARSE_FEATURES = [
        "user_id_encoded", "song_id_encoded",
        "age_bucket_encoded", "city_encoded",
        "tenure_bucket_encoded", "genre_encoded", "language_encoded",
        "artist_encoded", "origin_country_encoded",
        "year_bucket_encoded", "duration_bucket_encoded",
        "source_channel_encoded",
        "user_peak_hour_encoded",
    ]
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

    arrays = {}
    for col in ALL_FEATURES:
        if col in feat:
            arrays[col] = feat[col]
        else:
            arrays[col] = np.zeros(len(feat["target"]))

    X = np.column_stack([arrays[c] for c in ALL_FEATURES]).astype(np.float32)
    y = feat["target"].astype(np.int8)

    # ── 时序切分（与 train_lgbm.py / train_deepfm_v3.py 保持一致）
    play_time_unix = feat.get("play_time_unix", np.zeros(len(y), dtype=np.int64))
    user_id_enc    = feat["user_id_encoded"]
    song_id_enc    = feat["song_id_encoded"]
    artist_enc     = feat["artist_encoded"]

    # 用户级时序切分（与 train_lgbm.py / train_deepfm_v3.py 保持完全一致）
    MIN_INTERACTIONS = 5
    _df_meta = pd.DataFrame({
        "orig_idx": np.arange(len(play_time_unix)),
        "uid":      user_id_enc.astype(np.int32),
        "time":     play_time_unix,
    })
    _train_list, _val_list = [], []
    for _u, _grp in _df_meta.groupby("uid", sort=False):
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

    # ── Target Leakage 修复（训练集先验 → 验证集）
    _global_prior = float(y[train_idx].mean())
    _train_meta = pd.DataFrame({
        "uid": user_id_enc[train_idx].astype(np.int32),
        "art": artist_enc[train_idx].astype(np.int32),
        "sid": song_id_enc[train_idx].astype(np.int32),
        "y":   y[train_idx].astype(np.float32),
    })
    _ua_df = _train_meta.groupby(["uid", "art"])["y"].mean().reset_index()
    _ua_df.columns = ["uid", "art", "uar"]
    _u_df  = _train_meta.groupby("uid")["y"].mean().reset_index()
    _u_df.columns  = ["uid", "utr"]
    _s_df  = _train_meta.groupby("sid")["y"].mean().reset_index()
    _s_df.columns  = ["sid", "str_v"]

    def _fix_leaky_ens(idx):
        _tmp = pd.DataFrame({"uid": user_id_enc[idx].astype(np.int32),
                              "art": artist_enc[idx].astype(np.int32),
                              "sid": song_id_enc[idx].astype(np.int32)})
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

    X_val = X[val_idx].copy()
    uar_vl, utr_vl, str_vl = _fix_leaky_ens(val_idx)
    X_val[:, IDX_UAR] = uar_vl
    X_val[:, IDX_UTR] = utr_vl
    X_val[:, IDX_STR] = str_vl

    # ── Phase B-2: Cross TE（user×genre/language/country，与 train_lgbm.py 完全一致）
    _SMOOTH_M = 15
    _global_prior = float(y[train_idx].mean())
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

    def _fix_cross_te_ens(idx):
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
    ug_vl, ul_vl, uc_vl = _fix_cross_te_ens(val_idx)
    X_val[:, IDX_GM] = ug_vl
    X_val[:, IDX_LM] = ul_vl
    X_val[:, IDX_CM] = uc_vl
    print(f"   ✅ B-2 Cross TE 完成")

    # ── Phase B-1: ALS 向量注入（仅训练集重训，与 train_lgbm.py 完全一致）
    ALS_MODEL_PATH = os.path.join(MODE_DIR, "als_model.pkl")
    _als_col = None
    try:
        from implicit.als import AlternatingLeastSquares as _ALS
        from scipy.sparse import csr_matrix as _csr
        if os.path.exists(ALS_MODEL_PATH):
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
            _user_emb = _als_m.item_factors
            _song_emb = _als_m.user_factors

            def _als_score_only(u_enc, s_enc):
                _ue = np.clip(u_enc.astype(np.int32), 0, _user_emb.shape[0]-1)
                _se = np.clip(s_enc.astype(np.int32), 0, _song_emb.shape[0]-1)
                return (_user_emb[_ue] * _song_emb[_se]).sum(axis=1, keepdims=True).astype(np.float32)

            _als_col = _als_score_only(user_id_enc[val_idx], song_id_enc[val_idx])
            ALL_FEATURES = ALL_FEATURES + ["als_score"]
            print(f"   ✅ B-1 ALS 注入完成: als_score（1 维 dot-product）")
    except Exception as _e:
        print(f"   ⚠️  ALS 注入跳过: {_e}")

    if _als_col is not None:
        X_val = np.hstack([X_val, _als_col])

    y_val = y[val_idx]
    print(f"   验证集: {len(y_val):,} 样本  |  正样本率: {y_val.mean():.4f}")
    print(f"   ✅ 时序切分 + 泄漏修复完成  |  X_val.shape={X_val.shape}")

    return X_val, y_val, feat, ALL_FEATURES, val_idx


# ============================================================
# Step 2: LightGBM 推断
# ============================================================

def lgbm_predict(X_val):
    print("\n" + "=" * 62)
    print("🌲 [Step 2/4] LightGBM 预测")
    print("=" * 62)

    with open(INPUT_LGBM, "rb") as f:
        payload = pickle.load(f)

    lgbm_model = payload["model"]
    best_iter  = payload.get("best_iteration", None)
    val_auc    = payload.get("val_auc", float("nan"))

    preds = lgbm_model.predict(X_val, num_iteration=best_iter)
    print(f"   LightGBM 验证集 AUC（来自训练记录）: {val_auc:.4f}")
    return preds


# ============================================================
# Step 3: DeepFM 推断
# ============================================================

def deepfm_predict(feat, val_idx):
    print("\n" + "=" * 62)
    print("🧠 [Step 3/4] DeepFM v3 预测")
    print("=" * 62)

    import torch
    from deepctr_torch.models import DeepFM
    from deepctr_torch.inputs import get_feature_names

    with open(INPUT_DEEPFM_CFG, "rb") as f:
        cfg = pickle.load(f)

    feature_columns  = cfg["feature_columns"]
    dnn_hidden_units = cfg.get("dnn_hidden_units", (512, 256, 128, 64))
    dnn_dropout      = cfg.get("dnn_dropout", 0.2)
    sparse_specs     = cfg.get("sparse_feat_specs", [])
    dense_specs      = cfg.get("dense_feat_specs", [])

    model = DeepFM(
        linear_feature_columns=feature_columns,
        dnn_feature_columns=feature_columns,
        dnn_hidden_units=dnn_hidden_units,
        dnn_dropout=dnn_dropout,
        device='cpu',
    )
    state_dict = torch.load(INPUT_DEEPFM, map_location='cpu', weights_only=True)
    model.load_state_dict(state_dict)
    model.eval()
    print(f"   DeepFM v3 加载完成  |  特征列: {len(feature_columns)} 个")

    # 重建数据字典（使用时序切分的 val_idx，与 LightGBM 验证集保持一致）
    feature_names = get_feature_names(feature_columns)

    data_dict = {}
    for feat_name, enc_key, n_key, _ in sparse_specs:
        if enc_key in feat:
            data_dict[feat_name] = feat[enc_key][val_idx].astype(np.int32)
    for feat_name in dense_specs:
        if feat_name in feat:
            arr = feat[feat_name][val_idx].astype(np.float32)
            data_dict[feat_name] = np.nan_to_num(arr, nan=0.0)

    # ── Target Leakage 修复（使用时序训练集先验）
    n_total   = len(feat["target"])
    sort_idx  = np.argsort(feat.get("play_time_unix", np.zeros(n_total, dtype=np.int64)), kind="stable")
    n_val     = len(val_idx)
    train_idx = sort_idx[:n_total - n_val]
    y_train   = feat["target"][train_idx].astype(np.float32)
    _gp = float(y_train.mean())
    _uid = feat["user_id_encoded"]; _art = feat["artist_encoded"]; _sid = feat["song_id_encoded"]
    _tm = pd.DataFrame({"uid": _uid[train_idx].astype(np.int32),
                         "art": _art[train_idx].astype(np.int32),
                         "sid": _sid[train_idx].astype(np.int32), "y": y_train})
    _ua = _tm.groupby(["uid","art"])["y"].mean().reset_index(); _ua.columns=["uid","art","uar"]
    _uu = _tm.groupby("uid")["y"].mean().reset_index();        _uu.columns=["uid","utr"]
    _ss = _tm.groupby("sid")["y"].mean().reset_index();        _ss.columns=["sid","str_v"]
    _tv = pd.DataFrame({"uid": _uid[val_idx].astype(np.int32),
                         "art": _art[val_idx].astype(np.int32),
                         "sid": _sid[val_idx].astype(np.int32)})
    _tv = _tv.merge(_ua, on=["uid","art"], how="left").merge(_uu, on="uid", how="left").merge(_ss, on="sid", how="left")
    _tv["uar"]   = _tv["uar"].fillna(_tv["utr"]).fillna(_gp)
    _tv["utr"]   = _tv["utr"].fillna(_gp)
    _tv["str_v"] = _tv["str_v"].fillna(_gp)
    if "user_artist_repeat_rate" in data_dict: data_dict["user_artist_repeat_rate"] = _tv["uar"].values.astype(np.float32)
    if "user_target_rate"        in data_dict: data_dict["user_target_rate"]        = _tv["utr"].values.astype(np.float32)
    if "song_target_rate"        in data_dict: data_dict["song_target_rate"]        = _tv["str_v"].values.astype(np.float32)

    # 构建 Tensor
    arrays = [data_dict[f].reshape(-1, 1) for f in feature_names]
    X_tensor = torch.from_numpy(np.concatenate(arrays, axis=1)).float()

    # 批量推断
    val_preds = []
    n = X_tensor.shape[0]
    with torch.no_grad():
        for start in range(0, n, BATCH_SIZE):
            batch = X_tensor[start:start+BATCH_SIZE]
            out = model(batch).squeeze().cpu().numpy()
            val_preds.append(out)

    preds = np.concatenate(val_preds)
    print(f"   推断完成: {len(preds):,} 个样本")
    return preds


# ============================================================
# Step 4: 搜索最优 α
# ============================================================

def search_alpha(y_val, lgbm_preds, deepfm_preds):
    print("\n" + "=" * 62)
    print("🔍 [Step 4/4] 搜索最优集成系数 α")
    print("=" * 62)

    from sklearn.metrics import roc_auc_score

    y_val_f = y_val.astype(np.float32)
    lgbm_auc   = roc_auc_score(y_val_f, lgbm_preds)
    deepfm_auc = roc_auc_score(y_val_f, deepfm_preds)
    print(f"\n   LightGBM  AUC: {lgbm_auc:.4f}")
    print(f"   DeepFM v3 AUC: {deepfm_auc:.4f}")

    print(f"\n   {'α':>6}  {'集成 AUC':>12}")
    print("   " + "-" * 22)

    best_alpha = 0.5
    best_auc   = 0.0
    results    = []

    for alpha in ALPHA_RANGE:
        ensemble = alpha * lgbm_preds + (1 - alpha) * deepfm_preds
        auc = roc_auc_score(y_val_f, ensemble)
        results.append((alpha, auc))
        marker = " ← 最优" if auc > best_auc else ""
        print(f"   α={alpha:.2f}   AUC={auc:.4f}{marker}")
        if auc > best_auc:
            best_auc   = auc
            best_alpha = alpha

    print(f"\n{'='*62}")
    print(f"   最优 α = {best_alpha:.2f}")
    print(f"   集成 AUC = {best_auc:.4f}")
    print(f"   vs 单模型最优 = {max(lgbm_auc, deepfm_auc):.4f}")
    improvement = (best_auc - max(lgbm_auc, deepfm_auc)) * 100
    print(f"   集成提升: +{improvement:.2f} AUC 百分点")

    return best_alpha, best_auc, lgbm_auc, deepfm_auc, results


# ============================================================
# 保存配置
# ============================================================

def save_ensemble_config(best_alpha, best_auc, lgbm_auc, deepfm_auc, results):
    config = {
        "alpha":       best_alpha,      # final_score = α*LGBM + (1-α)*DeepFM
        "ensemble_auc": best_auc,
        "lgbm_auc":    lgbm_auc,
        "deepfm_auc":  deepfm_auc,
        "search_results": results,      # [(alpha, auc), ...]
        "calibrated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "version":     "v3",
    }
    with open(OUTPUT_ENSEMBLE, "wb") as f:
        pickle.dump(config, f, protocol=4)
    print(f"\n   ✅ 集成配置已保存: {OUTPUT_ENSEMBLE}")


# ============================================================
# main
# ============================================================

def main():
    print("\n" + "=" * 62)
    print("   集成系数校准 — LightGBM + DeepFM")
    print(f"   开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 62)

    check_files()

    X_val, y_val, feat, all_features, val_idx = load_val_data()
    lgbm_preds   = lgbm_predict(X_val)
    deepfm_preds = deepfm_predict(feat, val_idx)

    best_alpha, best_auc, lgbm_auc, deepfm_auc, results = search_alpha(
        y_val, lgbm_preds, deepfm_preds
    )
    save_ensemble_config(best_alpha, best_auc, lgbm_auc, deepfm_auc, results)

    print("\n" + "=" * 62)
    print("✅ 集成系数校准完成！")
    print(f"   final_score = {best_alpha:.2f} × LightGBM + "
          f"{1-best_alpha:.2f} × DeepFM")
    print(f"   集成 AUC: {best_auc:.4f}")
    print("=" * 62)
    print("\n🚀 下一步:")
    print("   python sync_recs_v3.py   # 生成个性化推荐")


if __name__ == "__main__":
    main()
