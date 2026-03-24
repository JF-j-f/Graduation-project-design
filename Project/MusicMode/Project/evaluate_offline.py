#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
evaluate_offline.py — KKBox 验证集离线推荐效果评估

计算指标：HR@K、Precision@K、Recall@K、NDCG@K、MRR
评估集：从 features_v3.pkl 中按用户级时序切分出的验证集（VALID_RATIO=0.1）
模型：3 模型集成（LightGBM + DeepFM + DIN），与 build_ensemble.py 保持一致

输出：控制台 + Mode/offline_evaluation_report.txt

执行：
  python evaluate_offline.py

作者：MusicMode 推荐系统
"""

import os
import sys
import pickle
import math
import warnings
import datetime
import numpy as np
import pandas as pd
from collections import defaultdict

warnings.filterwarnings("ignore")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ── 路径配置 ────────────────────────────────────────────────────────────────
PROJECT_DIR   = os.path.dirname(os.path.abspath(__file__))
MODE_DIR      = os.path.join(os.path.dirname(PROJECT_DIR), "Mode")

FEATURES_PATH = os.path.join(MODE_DIR, "features_v3.pkl")
LGBM_PATH     = os.path.join(MODE_DIR, "lgbm",   "lgbm_model.pkl")
DEEPFM_CFG    = os.path.join(MODE_DIR, "deepfm", "model_config.pkl")
DEEPFM_PATH   = os.path.join(MODE_DIR, "deepfm", "deepfm_model.pth")
DIN_CFG       = os.path.join(MODE_DIR, "din",    "model_config.pkl")
DIN_PATH      = os.path.join(MODE_DIR, "din",    "din_model.pth")
ENSEMBLE_PATH = os.path.join(MODE_DIR, "ensemble", "ensemble_config.pkl")
REPORT_PATH   = os.path.join(MODE_DIR, "offline_evaluation_report.txt")

# ── 超参数（与训练脚本保持一致） ────────────────────────────────────────────
VALID_RATIO      = 0.1
RANDOM_SEED      = 42
MIN_INTERACTIONS = 5
BATCH_SIZE       = 8192
K_LIST           = [5, 10, 20]

# ── 特征列定义（与 build_ensemble.py 保持完全一致） ─────────────────────────
SPARSE_FEATURES = [
    "user_id_encoded", "song_id_encoded",
    "genre_encoded", "language_encoded",
    "artist_encoded", "origin_country_encoded",
    "source_channel_encoded",
]

DENSE_FEATURES = [
    "user_play_count_log", "user_avg_completion",
    "song_play_count_log", "song_avg_completion",
    "song_unique_users_log", "song_age_days_log",
    "user_genre_match", "user_artist_match",
    "user_language_match", "user_country_match",
    "user_target_rate", "song_target_rate",
    "user_skip_rate", "song_skip_rate",
    "hour_match", "days_since_artist_log",
    "user_artist_repeat_rate",
    *[f"svd_user_song_{i}" for i in [0, 2, 3, 4, 5, 6, 9]],
    *[f"svd_song_user_{i}" for i in range(10)],
    *[f"svd_user_artist_{i}" for i in [0, 3, 4]],
    "svd_dot_score",
]

ALL_FEATURES = SPARSE_FEATURES + DENSE_FEATURES


# ============================================================
# Step 1: 加载数据 & 时序切分 & 泄漏修复（与 build_ensemble.py 完全一致）
# ============================================================

def load_val_data():
    print("\n[Step 1] 加载特征 & 时序切分 & 泄漏修复")
    print("=" * 62)

    if not os.path.exists(FEATURES_PATH):
        print(f"❌ 特征文件不存在：{FEATURES_PATH}")
        print("   请先运行 prepare_features_v3.py")
        sys.exit(1)

    # 优先使用 npz 缓存
    _npz_cache = FEATURES_PATH.replace(".pkl", "_cache.npz")
    _use_cache = (os.path.exists(_npz_cache) and
                  os.path.getmtime(_npz_cache) >= os.path.getmtime(FEATURES_PATH))
    if _use_cache:
        print("   ⚡ 从 npz 缓存加载...")
        _raw = np.load(_npz_cache, allow_pickle=True)
        feat = {k: _raw[k].item() if _raw[k].ndim == 0 else _raw[k] for k in _raw.files}
    else:
        print("   首次加载 pkl...")
        with open(FEATURES_PATH, "rb") as f:
            feat = pickle.load(f)

    arrays = {col: feat[col] if col in feat else np.zeros(len(feat["target"]))
              for col in ALL_FEATURES}

    X = np.column_stack([arrays[c] for c in ALL_FEATURES]).astype(np.float32)
    y = feat["target"].astype(np.int8)

    play_time_unix = feat.get("play_time_unix", np.zeros(len(y), dtype=np.int64))
    user_id_enc    = feat["user_id_encoded"]
    song_id_enc    = feat["song_id_encoded"]
    artist_enc     = feat["artist_encoded"]

    # ── 用户级时序切分（向量化）
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

    n_users = len(np.unique(user_id_enc[val_idx]))
    n_samples = len(val_idx)
    print(f"   验证集：{n_users:,} 用户，{n_samples:,} 样本")

    # ── Target Leakage 修复
    _global_prior = float(y[train_idx].mean())
    _SMOOTH_M = 100
    _train_meta = pd.DataFrame({
        "uid": user_id_enc[train_idx].astype(np.int32),
        "art": artist_enc[train_idx].astype(np.int32),
        "sid": song_id_enc[train_idx].astype(np.int32),
        "y":   y[train_idx].astype(np.float32),
    })
    _ua_s = _train_meta.groupby(["uid","art"])["y"].agg(["count","mean"]).reset_index()
    _ua_s["uar"] = (_ua_s["count"]*_ua_s["mean"] + _SMOOTH_M*_global_prior) / (_ua_s["count"] + _SMOOTH_M)
    _u_s  = _train_meta.groupby("uid")["y"].agg(["count","mean"]).reset_index()
    _u_s["utr"] = (_u_s["count"]*_u_s["mean"] + _SMOOTH_M*_global_prior) / (_u_s["count"] + _SMOOTH_M)
    _s_s  = _train_meta.groupby("sid")["y"].agg(["count","mean"]).reset_index()
    _s_s["str_v"] = (_s_s["count"]*_s_s["mean"] + _SMOOTH_M*_global_prior) / (_s_s["count"] + _SMOOTH_M)

    def _fix_leaky(idx):
        _tmp = pd.DataFrame({
            "uid": user_id_enc[idx].astype(np.int32),
            "art": artist_enc[idx].astype(np.int32),
            "sid": song_id_enc[idx].astype(np.int32),
        })
        _tmp = _tmp.merge(_ua_s[["uid","art","uar"]], on=["uid","art"], how="left")
        _tmp = _tmp.merge(_u_s[["uid","utr"]], on="uid", how="left")
        _tmp = _tmp.merge(_s_s[["sid","str_v"]], on="sid", how="left")
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

    # ── Cross TE 修复
    _genre_enc   = feat.get("genre_encoded",          np.zeros(len(y), dtype=np.int32))
    _lang_enc    = feat.get("language_encoded",        np.zeros(len(y), dtype=np.int32))
    _country_enc = feat.get("origin_country_encoded",  np.zeros(len(y), dtype=np.int32))
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

    y_val       = y[val_idx]
    uid_val     = user_id_enc[val_idx]

    return X_val, y_val, uid_val, feat, val_idx, train_idx


# ============================================================
# Step 2: 模型推断
# ============================================================

def predict_lgbm(X_val):
    if not os.path.exists(LGBM_PATH):
        print(f"   ⚠️  LightGBM 模型不存在: {LGBM_PATH}")
        return None
    with open(LGBM_PATH, "rb") as f:
        pkg = pickle.load(f)
    model = pkg["model"]
    preds = model.predict(X_val, num_iteration=model.best_iteration_)
    print(f"   ✅ LightGBM 推断完成")
    return preds.astype(np.float32)


def predict_torch(model_path, cfg_path, feat, val_idx, name="DeepFM"):
    if not os.path.exists(model_path) or not os.path.exists(cfg_path):
        print(f"   ⚠️  {name} 文件不存在，跳过")
        return None
    try:
        import torch
        from deepctr_torch.models import DeepFM as _DeepFM
        from deepctr_torch.inputs import get_feature_names

        with open(cfg_path, "rb") as f:
            cfg = pickle.load(f)

        feature_columns = cfg["feature_columns"]
        feat_names      = get_feature_names(feature_columns)
        sparse_specs    = cfg.get("sparse_feat_specs", [])
        dense_specs     = cfg.get("dense_feat_specs",  [])

        m = _DeepFM(
            linear_feature_columns=feature_columns,
            dnn_feature_columns=feature_columns,
            dnn_hidden_units=cfg.get("dnn_hidden_units", (256, 128, 64)),
            dnn_dropout=cfg.get("dnn_dropout", 0.5),
            device="cpu",
        )
        sd = torch.load(model_path, map_location="cpu", weights_only=True)
        m.load_state_dict(sd)
        m.eval()

        # 构建输入字典（与 sync_recs_v3.py 的 build_pair_features 类似）
        user_id_enc = feat["user_id_encoded"]
        song_id_enc = feat["song_id_encoded"]

        data_dict = {}
        for sf in sparse_specs:
            col = sf["name"]
            raw = feat.get(col, np.zeros(len(user_id_enc), dtype=np.int32))
            data_dict[col] = raw[val_idx].reshape(-1, 1).astype(np.int32)
        for df_ in dense_specs:
            col = df_["name"]
            raw = feat.get(col, np.zeros(len(user_id_enc), dtype=np.float32))
            data_dict[col] = raw[val_idx].reshape(-1, 1).astype(np.float32)

        # 泄漏特征置全局先验
        _global_prior = float(feat["target"][val_idx].mean())
        for leak_col in ["user_artist_repeat_rate", "user_target_rate", "song_target_rate"]:
            if leak_col in data_dict:
                data_dict[leak_col][:] = _global_prior

        arrays = [data_dict[f].reshape(-1, 1) for f in feat_names if f in data_dict]
        X_tensor = torch.from_numpy(np.concatenate(arrays, axis=1)).float()

        preds_list = []
        with torch.no_grad():
            for start in range(0, X_tensor.shape[0], BATCH_SIZE):
                out = m(X_tensor[start:start+BATCH_SIZE]).squeeze().cpu().numpy()
                preds_list.append(out if out.ndim > 0 else np.array([float(out)]))
        preds = np.concatenate(preds_list).astype(np.float32)
        print(f"   ✅ {name} 推断完成")
        return preds
    except Exception as e:
        print(f"   ⚠️  {name} 推断失败: {e}")
        return None


# ============================================================
# Step 3: 集成得分（加权平均 + Stacking）
# ============================================================

def get_ensemble_score(preds_dict, y_val):
    """加权集成评分：使用 SLSQP 优化的 best_weights 加权平均三模型预测值。"""
    names  = list(preds_dict.keys())
    matrix = np.column_stack([preds_dict[n] for n in names])

    if os.path.exists(ENSEMBLE_PATH):
        with open(ENSEMBLE_PATH, "rb") as f:
            ec = pickle.load(f)
        bw = ec.get("best_weights", {})
        weights = np.array([bw.get(n, 1.0 / len(names)) for n in names], dtype=np.float64)
        weights /= weights.sum()
        print(f"   加权系数: { {n: f'{w:.4f}' for n,w in zip(names,weights)} }")
    else:
        weights = np.ones(len(names)) / len(names)
        print("   未找到 ensemble_config.pkl，使用等权")

    # 使用 SLSQP best_weights 加权平均（与线上 sync_recs_v3.py 一致）
    # 注：原 LR.fit(matrix, y_val) + predict_proba(matrix) 存在数据泄漏
    #     （在验证集上拟合后对同一批数据预测），已删除。
    stacking_preds = (matrix * weights).sum(axis=1).astype(np.float32)
    print(f"   ✅ 加权集成推断完成（best_weights 加权平均）")
    return stacking_preds


# ============================================================
# Step 4: 逐用户排名指标
# ============================================================

def compute_ranking_metrics(preds, y_val, uid_val, k_list=None):
    if k_list is None:
        k_list = [5, 10, 20]

    # 按用户分组
    user_groups = defaultdict(list)
    for i, uid in enumerate(uid_val):
        user_groups[uid].append((preds[i], int(y_val[i])))

    metrics = {k: {"hr": [], "prec": [], "recall": [], "ndcg": [], "mrr": []}
               for k in k_list}

    for uid, items in user_groups.items():
        if len(items) < 2:
            continue
        items_sorted = sorted(items, key=lambda x: -x[0])
        labels_sorted = [item[1] for item in items_sorted]
        n_relevant = sum(labels_sorted)
        if n_relevant == 0:
            continue

        for k in k_list:
            top_k = labels_sorted[:k]
            n_hit = sum(top_k)

            # HR@K
            metrics[k]["hr"].append(1.0 if n_hit > 0 else 0.0)

            # Precision@K
            metrics[k]["prec"].append(n_hit / k)

            # Recall@K
            metrics[k]["recall"].append(n_hit / n_relevant)

            # NDCG@K（修正：IDCG 基于用户全部正样本数，而非 Top-K 内部重排）
            dcg  = sum(rel / math.log2(i + 2) for i, rel in enumerate(top_k))
            idcg = sum(1.0 / math.log2(i + 2) for i in range(min(n_relevant, k)))
            metrics[k]["ndcg"].append(dcg / idcg if idcg > 0 else 0.0)

            # MRR（第一个命中的位置）
            rr = 0.0
            for i, rel in enumerate(labels_sorted[:k]):
                if rel == 1:
                    rr = 1.0 / (i + 1)
                    break
            metrics[k]["mrr"].append(rr)

    results = {}
    for k in k_list:
        m = metrics[k]
        n = len(m["hr"])
        results[k] = {
            "n_users":   n,
            "HR":        np.mean(m["hr"]),
            "Precision": np.mean(m["prec"]),
            "Recall":    np.mean(m["recall"]),
            "NDCG":      np.mean(m["ndcg"]),
            "MRR":       np.mean(m["mrr"]),
        }
    return results


# ============================================================
# Step 5: 格式化报告
# ============================================================

def format_report(results, n_total_users, n_total_samples, generated_at, model_names):
    lines = []
    lines.append("=" * 62)
    lines.append("  音乐推荐系统离线评估报告（KKBox 验证集）")
    lines.append(f"  生成时间：{generated_at}")
    lines.append("=" * 62)
    lines.append(f"\n  评估集：{n_total_users:,} 用户，{n_total_samples:,} 样本")
    lines.append(f"  使用模型：{' + '.join(model_names)} Stacking 集成")

    for k, m in sorted(results.items()):
        lines.append(f"\n【@K={k}，有效用户数={m['n_users']:,}】")
        lines.append(f"  HR@{k}         : {m['HR']:.4f}")
        lines.append(f"  Precision@{k}  : {m['Precision']:.4f}")
        lines.append(f"  Recall@{k}     : {m['Recall']:.4f}")
        lines.append(f"  NDCG@{k}       : {m['NDCG']:.4f}")
        lines.append(f"  MRR@{k}        : {m['MRR']:.4f}")

    lines.append("\n【指标说明】")
    lines.append("  HR@K        = 至少 1 首正样本在 Top-K 中的用户比例")
    lines.append("  Precision@K = Top-K 推荐中正样本占比均值")
    lines.append("  Recall@K    = Top-K 命中正样本占用户全部正样本的比例均值")
    lines.append("  NDCG@K      = 归一化折损累积增益（考虑位置权重）")
    lines.append("  MRR@K       = 第一个命中位置倒数的均值")
    lines.append("\n" + "=" * 62)
    return "\n".join(lines)


# ============================================================
# main
# ============================================================

def main():
    print("\n" + "=" * 62)
    print("   KKBox 验证集离线推荐效果评估")
    print(f"   开始时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 62)

    # Step 1: 加载数据
    X_val, y_val, uid_val, feat, val_idx, train_idx = load_val_data()

    # Step 2: 各模型推断
    print("\n[Step 2] 各模型验证集推断")
    print("=" * 62)
    preds_dict = {}

    p_lgbm = predict_lgbm(X_val)
    if p_lgbm is not None:
        preds_dict["LightGBM"] = p_lgbm

    p_deepfm = predict_torch(DEEPFM_PATH, DEEPFM_CFG, feat, val_idx, name="DeepFM")
    if p_deepfm is not None:
        preds_dict["DeepFM"] = p_deepfm

    p_din = predict_torch(DIN_PATH, DIN_CFG, feat, val_idx, name="DIN")
    if p_din is not None:
        preds_dict["DIN"] = p_din

    if len(preds_dict) == 0:
        print("\n❌ 无可用模型！请先训练至少一个模型。")
        sys.exit(1)

    # Step 3: 集成
    print("\n[Step 3] 集成得分")
    print("=" * 62)
    if len(preds_dict) >= 2:
        final_preds = get_ensemble_score(preds_dict, y_val)
        model_names = list(preds_dict.keys())
    else:
        final_preds = list(preds_dict.values())[0]
        model_names = list(preds_dict.keys())
        print(f"   使用单模型: {model_names[0]}")

    # Step 4: 计算排名指标
    print("\n[Step 4] 计算逐用户排名指标")
    print("=" * 62)
    results = compute_ranking_metrics(final_preds, y_val, uid_val, k_list=K_LIST)

    n_users   = len(np.unique(uid_val))
    n_samples = len(val_idx)

    for k, m in sorted(results.items()):
        print(f"   HR@{k}={m['HR']:.4f}  P@{k}={m['Precision']:.4f}  "
              f"R@{k}={m['Recall']:.4f}  NDCG@{k}={m['NDCG']:.4f}  MRR@{k}={m['MRR']:.4f}")

    # Step 5: 输出报告
    generated_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    report = format_report(results, n_users, n_samples, generated_at, model_names)
    print("\n" + report)

    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\n✅ 报告已写入: {os.path.abspath(REPORT_PATH)}")


if __name__ == "__main__":
    main()
