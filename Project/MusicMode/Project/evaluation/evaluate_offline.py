#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
evaluate_offline.py — KKBox 验证集离线推荐效果评估

计算指标：HR@K、Precision@K、Recall@K、NDCG@K、MRR
评估集：从 features_v3.pkl 中按用户级时序切分出的验证集（VALID_RATIO=0.1）
模型：精排集成（DeepFM + LightGBM Meta-LR），BST 为粗排层，与 build_ensemble.py 保持一致

开发者：JunFu
"""
import os
import sys
import pickle
import math
import warnings
import datetime
from pathlib import Path
import numpy as np
import pandas as pd
from collections import defaultdict

warnings.filterwarnings("ignore")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ── 路径配置 ────────────────────────────────────────────────────────────────
MODE_DIR = Path(__file__).resolve().parents[2] / "Mode"
FE_DIR   = MODE_DIR / "feature_engineering"
FR_DIR   = MODE_DIR / "fine_rank"

# build_ensemble.py 位于 fine_rank/，predict_lgbm_model 需要从中 import
PROJECT_DIR = str(Path(__file__).resolve().parents[1] / "fine_rank")
CR_DIR      = MODE_DIR / "coarse_rank"                  # BST 粗排层模型所在目录

FEATURES_PATH = FE_DIR / "features_v3.pkl"
INPUT_SEQ     = FE_DIR / "features_seq.pkl"             # BST 序列特征（BST已迁至粗排层）
DEEPFM_CFG    = FR_DIR / "deepfm" / "model_config.pkl"
DEEPFM_PATH   = FR_DIR / "deepfm" / "deepfm_model.pth"
LGBM_PATH     = FR_DIR / "lgbm"   / "lgbm_model.pkl"   # LightGBM 精排集成用模型
ENSEMBLE_PATH = FR_DIR / "ensemble" / "ensemble_config.pkl"
REPORT_PATH   = MODE_DIR / "evaluation" / "offline_evaluation_report.txt"
REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)

# ── 超参数（与训练脚本保持一致） ────────────────────────────────────────────
VALID_RATIO      = 0.1
RANDOM_SEED      = 42
# 笔记4.1修复：原值=5会过滤掉真正的冷启动用户，导致全局NDCG实为"≥5次交互用户"的均值
# 改为1允许冷启动用户进入评估，配合分层分析真实揭示系统对各活跃度用户的表现
MIN_INTERACTIONS = 1
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
    print("\n[Step 1] 加载特征 & 时序切分 & 泄漏修复")
    print("=" * 62)

    if not os.path.exists(FEATURES_PATH):
        print(f"❌ 特征文件不存在：{FEATURES_PATH}")
        print("   请先运行 prepare_features_v3.py")
        sys.exit(1)

    # 优先使用 npz 缓存
    _npz_cache = FEATURES_PATH.with_name(FEATURES_PATH.stem + "_cache.npz")
    _use_cache = (_npz_cache.exists() and
                  _npz_cache.stat().st_mtime >= FEATURES_PATH.stat().st_mtime)
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

    # song_target_rate 泄漏修复：用训练集的 OOF 平滑均值替换验证集的原始目标编码
    _global_prior = float(y[train_idx].mean())
    _SMOOTH_M = 100
    _s_s = pd.DataFrame({
        "sid": song_id_enc[train_idx].astype(np.int32),
        "y":   y[train_idx].astype(np.float32),
    }).groupby("sid")["y"].agg(["count", "mean"]).reset_index()
    _s_s["str_v"] = (
        (_s_s["count"] * _s_s["mean"] + _SMOOTH_M * _global_prior)
        / (_s_s["count"] + _SMOOTH_M)
    )

    IDX_STR = ALL_FEATURES.index("song_target_rate")
    X_val = X[val_idx].copy()
    _sid_val = pd.DataFrame({"sid": song_id_enc[val_idx].astype(np.int32)})
    _sid_val = _sid_val.merge(_s_s[["sid", "str_v"]], on="sid", how="left")
    X_val[:, IDX_STR] = _sid_val["str_v"].fillna(_global_prior).values.astype(np.float32)

    y_val   = y[val_idx]
    uid_val = user_id_enc[val_idx]

    # 统计每个用户的总交互次数（_cnt 列包含全量 train+val 总数），供分层评估使用
    # 键为 encoded uid（int），值为总交互次数
    user_total_counts = (
        _df_meta.drop_duplicates("uid")
        .set_index("uid")["_cnt"]
        .astype(int)
        .to_dict()
    )

    return X_val, y_val, uid_val, feat, val_idx, train_idx, user_total_counts


# ============================================================
# Step 2: 模型推断
# ============================================================

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
        for feat_name, enc_key, _, _ in sparse_specs:
            raw = feat.get(enc_key, np.zeros(len(user_id_enc), dtype=np.int32))
            data_dict[feat_name] = raw[val_idx].astype(np.int32)
        for col in dense_specs:
            raw = feat.get(col, np.zeros(len(user_id_enc), dtype=np.float32))
            # nan_to_num：SVD特征对冷启动用户为 NaN，神经网络无法处理 NaN（会向后传播）
            # 与 sync_recs_v3.py 的 rank_with_deepfm 保持一致（nan=0.0）
            data_dict[col] = np.nan_to_num(raw[val_idx].astype(np.float32), nan=0.0)

        # song_target_rate 是基于全量数据的目标编码，推断时置全局先验以防泄漏
        _global_prior = float(feat["target"][val_idx].mean())
        if "song_target_rate" in data_dict:
            data_dict["song_target_rate"][:] = _global_prior

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

def predict_lgbm(X_val, y_val):
    """
    LightGBM 验证集推断，委托给 build_ensemble._predict_lgbm_direct()。

    使用 load_val_data() 已正确重算SVD的 X_val 直接推断，保留 NaN 路由，
    避免从 feat 字典逐列重建时 nan_to_num=0.0 造成的 Training-Serving Skew
    （该 Skew 会使 val AUC 从 0.82 错误降至 0.70）。
    """
    sys.path.insert(0, PROJECT_DIR)
    from build_ensemble import _predict_lgbm_direct
    cfg = {"model_path": LGBM_PATH}
    return _predict_lgbm_direct("LightGBM", cfg, X_val, y_val)


# ============================================================
# Step 3: 集成得分（加权平均 + Stacking）
# ============================================================

def get_ensemble_score(preds_dict, y_val):
    """加载 meta_learner.pkl（LightGBM元学习器），对各模型预测值集成输出。"""
    meta_path = ENSEMBLE_PATH.parent / "meta_learner.pkl"

    if meta_path.exists():
        with open(meta_path, "rb") as f:
            meta_lr = pickle.load(f)
        names = list(preds_dict.keys())
        matrix = np.column_stack([preds_dict[n] for n in names])
        stacking_preds = meta_lr.predict_proba(matrix)[:, 1].astype(np.float32)
        print(f"   ✅ 元学习器集成推断完成（LightGBM meta_learner）")
    else:
        print("   ⚠️  未找到 meta_learner.pkl，使用等权加权平均")
        names  = list(preds_dict.keys())
        matrix = np.column_stack([preds_dict[n] for n in names])
        weights = np.ones(len(names)) / len(names)
        stacking_preds = (matrix * weights).sum(axis=1).astype(np.float32)
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
        # 空列表时 np.mean([]) 返回 NaN，会导致下游 set_ylim / max 崩溃；
        # 改为空列表返回 0.0，语义清晰（该分层无有效用户，指标记为零）
        def _safe_mean(lst):
            return float(np.mean(lst)) if lst else 0.0

        results[k] = {
            "n_users":   n,
            "HR":        _safe_mean(m["hr"]),
            "Precision": _safe_mean(m["prec"]),
            "Recall":    _safe_mean(m["recall"]),
            "NDCG":      _safe_mean(m["ndcg"]),
            "MRR":       _safe_mean(m["mrr"]),
        }
    return results


# ============================================================
# Step 4.5: 冷启动分层评估（笔记6.5节）
# ============================================================

def compute_stratified_metrics(preds, y_val, uid_val, user_total_counts, k=5):
    """
    按用户历史交互次数将用户分四档，分别计算 NDCG@K 和 HR@K。

    设计依据（笔记4.2）：
    协同过滤SVD嵌入和OOF目标编码对少于10次交互的用户贡献几乎为零，
    全局平均NDCG会被Power Users拉高，掩盖冷启动用户的真实表现（辛普森悖论）。
    分层评估诚实披露系统对各类用户的服务能力差异。

    Args:
        preds:              全量验证集预测分数 (N,)
        y_val:              全量验证集标签 (N,)
        uid_val:            全量验证集用户 encoded_id (N,)
        user_total_counts:  {encoded_uid: 总交互次数} 字典
        k:                  评估截断位置（默认 K=5，对应论文首屏指标）

    Returns:
        dict: {stratum_name: {"label", "n_users", f"NDCG@{k}", f"HR@{k}"}}
    """
    STRATA = [
        ("cold",    1,   9,   "冷启动层（1~9次）"),
        ("growing", 10,  49,  "成长层（10~49次）"),
        ("active",  50,  199, "活跃层（50~199次）"),
        ("power",   200, None, "超级用户层（≥200次）"),
    ]

    results = {}
    for name, lo, hi, label in STRATA:
        stratum_users = set(
            uid for uid, cnt in user_total_counts.items()
            if cnt >= lo and (hi is None or cnt <= hi)
        )
        mask = np.array([int(uid) in stratum_users for uid in uid_val])
        if mask.sum() == 0:
            results[name] = {
                "label": label, "n_users": 0,
                f"NDCG@{k}": 0.0, f"HR@{k}": 0.0,
            }
            continue

        m = compute_ranking_metrics(
            preds[mask], y_val[mask], uid_val[mask], k_list=[k]
        )
        results[name] = {
            "label":      label,
            "n_users":    m[k]["n_users"],
            f"NDCG@{k}":  m[k]["NDCG"],
            f"HR@{k}":    m[k]["HR"],
        }

    return results


# ============================================================
# Step 4.6: 冷启动分层评估柱状图（笔记6.5节）
# ============================================================

def plot_stratified_bar(stratum_results):
    """
    冷启动分层评估柱状图（笔记6.5节）。

    X轴：四个用户层级（冷启动/成长/活跃/超级用户）
    Y轴：NDCG@5 和 HR@5（双色分组柱）

    设计依据：
    分层评估诚实披露系统对各类用户的服务能力差异，
    揭示全局NDCG被超级用户拉高掩盖的冷启动困境（笔记4.2 辛普森悖论）。

    Args:
        stratum_results: compute_stratified_metrics 的返回值
                         {stratum_name: {"label", "n_users", "NDCG@5", "HR@5"}}

    Returns:
        None（保存图片至 REPORT_PATH.parent/冷启动分层评估_NDCG@5.png）
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.font_manager as fm

    # 字体配置（宋体覆盖中文，Times New Roman用于数字）
    matplotlib.rcParams["font.family"]       = "sans-serif"
    matplotlib.rcParams["font.sans-serif"]   = ["SimSun", "Microsoft YaHei", "DejaVu Sans"]
    matplotlib.rcParams["axes.unicode_minus"] = False

    _tnr_sm = fm.FontProperties(family="Times New Roman", size=9)
    _cn_sm  = fm.FontProperties(family="SimSun", size=10)
    _cn_md  = fm.FontProperties(family="SimSun", size=11)

    # ── 取四档数据 ──────────────────────────────────────────
    keys    = ["cold", "growing", "active", "power"]
    labels  = [stratum_results[k]["label"] for k in keys]
    ndcg5   = [stratum_results[k].get("NDCG@5", 0.0) for k in keys]
    hr5     = [stratum_results[k].get("HR@5",   0.0) for k in keys]
    n_users = [stratum_results[k]["n_users"] for k in keys]

    # ── 绘图 ───────────────────────────────────────────────
    x       = np.arange(len(keys))
    bar_w   = 0.35
    fig, ax = plt.subplots(figsize=(10, 5.5))
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    bars_ndcg = ax.bar(x - bar_w/2, ndcg5, width=bar_w,
                       color="#3A7EBF", label="NDCG@5", zorder=3,
                       edgecolor="white", linewidth=0.5)
    bars_hr   = ax.bar(x + bar_w/2, hr5,   width=bar_w,
                       color="#E07B39", label="HR@5",   zorder=3,
                       edgecolor="white", linewidth=0.5)

    # 柱顶数值标注
    for bar in bars_ndcg:
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.005,
                f"{bar.get_height():.4f}", ha="center", va="bottom",
                fontproperties=_tnr_sm, color="#3A7EBF", fontsize=8, zorder=5)
    for bar in bars_hr:
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.005,
                f"{bar.get_height():.4f}", ha="center", va="bottom",
                fontproperties=_tnr_sm, color="#E07B39", fontsize=8, zorder=5)

    # X轴标签：层级名 + 有效用户数（双行）
    x_tick_labels = [f"{lb}\n(n={nu:,})" for lb, nu in zip(labels, n_users)]
    ax.set_xticks(x)
    ax.set_xticklabels(x_tick_labels, fontproperties=_cn_sm)
    ax.set_ylabel("指标值", fontproperties=_cn_md, labelpad=8)

    # Y轴从0开始，留足标注空间
    _y_max_val = max(max(ndcg5) if ndcg5 else 0.0, max(hr5) if hr5 else 0.0)
    ax.set_ylim(0, _y_max_val + 0.12)

    ax.legend(loc="upper left", prop=_cn_sm, framealpha=0.9, edgecolor="#BBBBBB")
    ax.yaxis.grid(True, linestyle="--", alpha=0.4, color="#BBBBBB", zorder=0)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#BBBBBB")
    ax.spines["bottom"].set_color("#BBBBBB")

    # ── 保存图片 ───────────────────────────────────────────
    _img_dir  = REPORT_PATH.parent
    _img_dir.mkdir(parents=True, exist_ok=True)
    save_path = str(_img_dir / "冷启动分层评估_NDCG@5.png")
    plt.tight_layout(pad=1.2)
    plt.savefig(save_path, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close()
    print(f"   ✅ 分层评估柱状图已保存: {save_path}")


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
    # 脚本级计时：在任何工作开始前记录，覆盖数据加载、推断、指标计算全程
    _start = datetime.datetime.now()
    print("\n" + "=" * 62)
    print("   KKBox 验证集离线推荐效果评估")
    print(f"   开始时间: {_start.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 62)

    # Step 1: 加载数据
    X_val, y_val, uid_val, feat, val_idx, train_idx, user_total_counts = load_val_data()

    # Step 2: 各模型推断
    # ⚠️ 列顺序关键：Meta-LR 训练时 column_stack 顺序为 [DeepFM, LightGBM]；
    # preds_dict 插入顺序必须与之一致（Python 3.7+ dict 保序），否则集成列映射错误
    print("\n[Step 2] 各模型验证集推断（DeepFM / LightGBM，精排集成层）")
    print("=" * 62)
    preds_dict = {}

    p_deepfm = predict_torch(DEEPFM_PATH, DEEPFM_CFG, feat, val_idx, name="DeepFM")
    if p_deepfm is not None:
        preds_dict["DeepFM"] = p_deepfm

    p_lgbm = predict_lgbm(X_val, y_val)
    if p_lgbm is not None:
        preds_dict["LightGBM"] = p_lgbm

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

    # Step 4.5: 冷启动分层评估（笔记6.5节：基于用户活跃度的NDCG@5分层对比）
    print("\n[Step 4.5] 冷启动分层评估（四档用户，NDCG@5 + HR@5）")
    print("=" * 62)
    stratum_results = compute_stratified_metrics(
        final_preds, y_val, uid_val, user_total_counts, k=5
    )
    for name, sr in stratum_results.items():
        print(f"   {sr['label']:<22} n={sr['n_users']:>5}  "
              f"NDCG@5={sr.get('NDCG@5', 0.0):.4f}  "
              f"HR@5={sr.get('HR@5', 0.0):.4f}")

    # Step 4.6: 分层评估柱状图（笔记6.5节：将分层数据可视化）
    plot_stratified_bar(stratum_results)

    # Step 5: 输出报告
    generated_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    report = format_report(results, n_users, n_samples, generated_at, model_names)
    print("\n" + report)

    # 分层评估结果追加到报告尾部
    stratum_lines = [
        "\n\n" + "=" * 62,
        "  冷启动分层评估（基于用户活跃度，NDCG@5 / HR@5）",
        "=" * 62,
        f"  {'用户层级':<22} {'有效用户数':>8}  {'NDCG@5':>8}  {'HR@5':>7}",
        "-" * 62,
    ]
    for name, sr in stratum_results.items():
        stratum_lines.append(
            f"  {sr['label']:<22} {sr['n_users']:>8}  "
            f"{sr.get('NDCG@5', 0.0):>8.4f}  "
            f"{sr.get('HR@5', 0.0):>7.4f}"
        )
    stratum_lines += [
        "-" * 62,
        "  说明：Power Users特征最丰富，NDCG最高；冷启动用户SVD嵌入近零，",
        "        个性化能力受限——这是协同过滤类系统的结构性局限，非实现bug。",
        "=" * 62,
    ]
    report_full = report + "\n".join(stratum_lines)

    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(report_full)
    print(f"\n✅ 报告已写入: {os.path.abspath(REPORT_PATH)}")

    _elapsed = str(datetime.datetime.now() - _start).split(".")[0]
    print(f"\n   结束时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   总耗时:   {_elapsed}")


if __name__ == "__main__":
    main()
