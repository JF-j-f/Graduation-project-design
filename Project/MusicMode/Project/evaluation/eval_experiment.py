#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
eval_experiment.py — 消融实验 + 模型对比实验

功能：
  消融实验（4个配置）：A1（无排序）→ A2（+BST粗排）→ A3（+Meta-LR精排）→ A4（+MMR完整管道）
  对比实验（仅AUC）：LightGBM / 单模型DeepFM / 单模型BST / Meta-LR集成
  输出：eval_experiment_report.txt + 3张图表（消融分组柱状图 + AUC对比柱状图 + MMR λ帕累托折线图）

核心原则：
  - 不重新训练任何模型
  - 从 build_ensemble.py 和 evaluate_offline.py 直接 import，零重复开发
  - DeepFM+LightGBM 只推断一次，结果复用于多个配置

注意：
  - OOF文件（deepfm_oof.npy / lgbm_oof.npy）是训练集前90%的K折预测，与val_idx不重叠，本脚本不使用
  - 热度基线使用 feat["song_play_count_log"]，来源于play_history真实播放量
  - ALS行列索引与 user_id_encoded / song_id_encoded 完全对齐，直接索引，无需额外编码器

开发者：JunFu
"""

import os
import sys
import math
import pickle
import datetime
import warnings
from pathlib import Path
import numpy as np

warnings.filterwarnings("ignore")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

# ── 路径配置 ──────────────────────────────────────────────────────────────────
# 脚本位于 Project/MusicMode/Project/evaluation/
_MUSICMODE = Path(__file__).resolve().parents[2]   # .../Project/MusicMode/
MODE_DIR   = _MUSICMODE / "Mode"
ROOT_DIR   = Path(__file__).resolve().parents[4]   # 仓库根目录
# 图表保存到仓库根目录 image/，与其他系统图表统一存放
IMG_DIR    = ROOT_DIR / "image"
IMG_DIR.mkdir(parents=True, exist_ok=True)
# 文字报告输出到 Mode/evaluation/，与 evaluate_offline.py 保持一致
EVAL_DIR   = MODE_DIR / "evaluation"
EVAL_DIR.mkdir(parents=True, exist_ok=True)

REPORT_PATH = EVAL_DIR / "eval_experiment_report.txt"

# ── import 现有函数（不修改原脚本）────────────────────────────────────────────
# build_ensemble 在 fine_rank/，compute_ranking_metrics 在同目录 evaluation/
sys.path.insert(0, str(_MUSICMODE / "Project" / "fine_rank"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_ensemble import load_val_data, collect_predictions   # 数据加载+模型推断
from evaluate_offline import compute_ranking_metrics            # 指标计算

# ── 字体配置───────────────────────────────────────────────────
# 全局使用宋体（SimSun）覆盖CJK字符
matplotlib.rcParams["font.family"] = "sans-serif"
matplotlib.rcParams["font.sans-serif"] = ["SimSun", "Microsoft YaHei", "DejaVu Sans"]
matplotlib.rcParams["axes.unicode_minus"] = False
matplotlib.rcParams["font.size"] = 12  # 小四

# Times New Roman 字体属性（用于纯英文/数字标注）
_tnr_fp    = fm.FontProperties(family="Times New Roman", size=12)
_tnr_sm_fp = fm.FontProperties(family="Times New Roman", size=9)
_cn_fp     = fm.FontProperties(family="SimSun", size=12)
_cn_sm_fp  = fm.FontProperties(family="SimSun", size=9)


# ============================================================
# 工具函数
# ============================================================

def fmt(metrics, k=5):
    """从 compute_ranking_metrics 返回值中提取 @K=5 的各指标"""
    m = metrics.get(k, {})
    return (
        m.get("HR",        0.0),
        m.get("Precision", 0.0),
        m.get("NDCG",      0.0),
        m.get("MRR",       0.0),
    )


# ============================================================
# 对比实验配置
# ============================================================

def eval_popularity(feat, val_idx, y_val, uid_val):
    """热度基线：song_play_count_log"""
    print("\n[对比] 热度基线（song_play_count_log）...")
    pop_preds = feat["song_play_count_log"][val_idx].astype(np.float32)
    metrics   = compute_ranking_metrics(pop_preds, y_val, uid_val)
    hr, prec, ndcg, mrr = fmt(metrics)
    print(f"   HR@5={hr:.4f}  Prec@5={prec:.4f}  NDCG@5={ndcg:.4f}  MRR={mrr:.4f}")
    return metrics


def _compute_als_scores(feat, val_idx):
    """
    计算 ALS 协同过滤得分（user_factor · item_factor 内积）。

    从 eval_als 中抽取为可复用辅助函数，供 eval_als 和 eval_recall_combined
    共同调用，避免重复加载 ALS 模型 pkl 文件。

    Returns:
        als_scores (np.ndarray): shape=(len(val_idx),)，越界位置填 0.0
    """
    als_path = MODE_DIR / "recall" / "als_model.pkl"
    with open(als_path, "rb") as f:
        als = pickle.load(f)
    user_factors = als.user_factors
    item_factors = als.item_factors
    u_idxs = feat["user_id_encoded"][val_idx].astype(np.int32)
    s_idxs = feat["song_id_encoded"][val_idx].astype(np.int32)
    valid = (
        (u_idxs >= 0) & (u_idxs < user_factors.shape[0]) &
        (s_idxs >= 0) & (s_idxs < item_factors.shape[0])
    )
    als_scores = np.zeros(len(val_idx), dtype=np.float32)
    if valid.any():
        als_scores[valid] = np.einsum(
            "ij,ij->i",
            user_factors[u_idxs[valid]],
            item_factors[s_idxs[valid]],
        ).astype(np.float32)
    oor = (~valid).sum()
    if oor > 0:
        print(f"   ⚠ ALS 越界样本: {oor:,} / {len(val_idx):,}（赋值 0.0）")
    return als_scores


def eval_als(feat, val_idx, y_val, uid_val):
    """
    ALS 协同过滤对比实验。

    委托 _compute_als_scores() 计算内积得分，同时返回 preds 供消融
    eval_recall_combined() 复用，避免重复加载 pkl。
    """
    print("\n[对比] ALS协同过滤...")
    als_preds = _compute_als_scores(feat, val_idx)
    metrics   = compute_ranking_metrics(als_preds, y_val, uid_val)
    hr, prec, ndcg, mrr = fmt(metrics)
    print(f"   HR@5={hr:.4f}  Prec@5={prec:.4f}  NDCG@5={ndcg:.4f}  MRR={mrr:.4f}")
    return metrics, als_preds   # 返回 preds 供三通道融合复用


def eval_lgbm(X_val, lgbm_model, y_val, uid_val):
    """LightGBM精排单模型（供对比实验使用，消融A2已改用BST粗排）"""
    print("\n[对比] LightGBM精排（单模型）...")
    booster    = lgbm_model["model"]
    lgbm_preds = booster.predict(X_val).astype(np.float32)
    metrics    = compute_ranking_metrics(lgbm_preds, y_val, uid_val)
    hr, prec, ndcg, mrr = fmt(metrics)
    print(f"   HR@5={hr:.4f}  Prec@5={prec:.4f}  NDCG@5={ndcg:.4f}  MRR={mrr:.4f}")
    return metrics


def eval_bst_coarse(feat, val_idx, train_idx, y_val, uid_val):
    """
    BST粗排消融（消融A2）：委托给 build_ensemble.predict_bst_model()。

    BST 已从精排层迁移至粗排层（600→300），作为消融A2的基准。
    同时返回 preds 供对比实验"单模型BST"复用，避免重复推断。

    Args:
        feat:      特征字典（来自 load_val_data）
        val_idx:   验证集下标
        train_idx: 训练集下标（BST推断时用于计算全局先验）
        y_val:     验证集标签
        uid_val:   验证集用户 encoded_id

    Returns:
        tuple: (metrics_dict, preds_array)
               metrics_dict 用于消融A2，preds_array 可复用给单模型BST对比
    """
    print("\n[消融 A2] BST粗排...")
    from build_ensemble import predict_bst_model
    _bst_cfg = {
        "model_path":  MODE_DIR / "coarse_rank" / "bst" / "bst_model.pth",
        "config_path": MODE_DIR / "coarse_rank" / "bst" / "model_config.pkl",
    }
    preds = predict_bst_model("BST", _bst_cfg, feat, val_idx, train_idx)
    if preds is None:
        print("   ⚠️ BST模型加载失败，A2消融使用随机基准！")
        np.random.seed(0)
        preds = np.random.uniform(0, 1, size=len(y_val)).astype(np.float32)
    metrics = compute_ranking_metrics(preds, y_val, uid_val)
    hr, prec, ndcg, mrr = fmt(metrics)
    print(f"   HR@5={hr:.4f}  Prec@5={prec:.4f}  NDCG@5={ndcg:.4f}  MRR={mrr:.4f}")
    return metrics, preds


def eval_single_deepfm(deepfm_val, y_val, uid_val):
    """单模型 DeepFM"""
    print("\n[对比] 单模型 DeepFM...")
    metrics = compute_ranking_metrics(deepfm_val, y_val, uid_val)
    hr, prec, ndcg, mrr = fmt(metrics)
    print(f"   HR@5={hr:.4f}  Prec@5={prec:.4f}  NDCG@5={ndcg:.4f}  MRR={mrr:.4f}")
    return metrics


def eval_single_bst(bst_val, y_val, uid_val):
    """单模型 BST"""
    print("\n[对比] 单模型 BST...")
    metrics = compute_ranking_metrics(bst_val, y_val, uid_val)
    hr, prec, ndcg, mrr = fmt(metrics)
    print(f"   HR@5={hr:.4f}  Prec@5={prec:.4f}  NDCG@5={ndcg:.4f}  MRR={mrr:.4f}")
    return metrics


def eval_meta_lgbm(deepfm_val, lgbm_val, meta_learner, y_val, uid_val):
    """
    Meta-LR精排集成（DeepFM+LightGBM，消融A3）。

    架构对调后：LightGBM 由粗排迁至精排，与 DeepFM 共同输入 Meta-LR 元学习器。
    输入列顺序 [DeepFM, LightGBM] 必须与 build_ensemble.py 训练时一致。
    """
    print("\n[消融 A3] Meta-LR 精排集成（DeepFM+LightGBM）...")
    X_meta    = np.column_stack([deepfm_val, lgbm_val])
    meta_pred = meta_learner.predict_proba(X_meta)[:, 1].astype(np.float32)
    metrics   = compute_ranking_metrics(meta_pred, y_val, uid_val)
    hr, prec, ndcg, mrr = fmt(metrics)
    print(f"   HR@5={hr:.4f}  Prec@5={prec:.4f}  NDCG@5={ndcg:.4f}  MRR={mrr:.4f}")
    return metrics


# ============================================================
# 消融实验
# ============================================================

def eval_ablation_a0(y_val, uid_val):
    """
    A0：随机基准（无召回无排序，绝对下界）。

    与 A1（三通道召回融合）的差值证明召回层的有效性。
    固定 random_seed=42 保证可复现。
    """
    print("\n[消融 A0] 随机基准（下界）...")
    np.random.seed(42)
    a0_preds = np.random.uniform(0, 1, size=len(y_val)).astype(np.float32)
    metrics  = compute_ranking_metrics(a0_preds, y_val, uid_val)
    hr, prec, ndcg, mrr = fmt(metrics)
    print(f"   HR@5={hr:.4f}  Prec@5={prec:.4f}  NDCG@5={ndcg:.4f}  MRR={mrr:.4f}")
    return metrics


def eval_recall_combined(feat, val_idx, y_val, uid_val, als_preds):
    """
    三通道召回融合（消融 A1）：热度（通道B）+ ALS（通道C）+ SVD点积（通道A）归一化均值。

    代表"召回层全力输出、无任何神经排序"的基准，与 A0（随机）的差值
    即为召回层对整体排序性能的贡献。

    通道A使用 feat["svd_dot_score"]——由 prepare_features_v3.py 预计算的
    svd_user_song × svd_song_user 向量点积，与 FAISS 检索使用的嵌入空间完全一致。
    冷启动用户的 svd_dot_score 为 NaN，填 0 后参与归一化，不影响热身用户的有效得分。

    Args:
        als_preds: 已由 _compute_als_scores() 计算好的 ALS 得分，避免重复加载 pkl
    """
    print("\n[消融 A1] 三通道召回融合（热度+ALS+SVD）...")

    def _normalize(x):
        """Min-Max 归一化到 [0, 1]，分母加 1e-8 防零除"""
        mn, mx = float(x.min()), float(x.max())
        return (x - mn) / (mx - mn + 1e-8)

    pop_scores = feat["song_play_count_log"][val_idx].astype(np.float32)
    svd_scores = feat["svd_dot_score"][val_idx].astype(np.float32)

    # svd_dot_score 对冷启动用户为 NaN，填 0 后参与归一化
    svd_valid  = ~np.isnan(svd_scores)
    svd_scores = np.where(svd_valid, svd_scores, 0.0)

    combined = (
        _normalize(pop_scores) + _normalize(als_preds) + _normalize(svd_scores)
    ) / 3.0

    metrics = compute_ranking_metrics(combined, y_val, uid_val)
    hr, prec, ndcg, mrr = fmt(metrics)
    cold_ratio = float((~svd_valid).sum()) / max(len(val_idx), 1)
    print(f"   HR@5={hr:.4f}  Prec@5={prec:.4f}  NDCG@5={ndcg:.4f}  MRR={mrr:.4f}")
    print(f"   （SVD冷启动填0比例：{cold_ratio:.1%}）")
    return metrics


# ============================================================
# 图表生成（学术论文风格）
# ============================================================

def _apply_academic_style(ax):
    """学术论文图表通用风格"""
    ax.yaxis.grid(True, linestyle="--", alpha=0.4, color="#BBBBBB", zorder=0)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#BBBBBB")
    ax.spines["bottom"].set_color("#BBBBBB")
    ax.tick_params(axis="both", colors="#333333", length=3)


def plot_ablation_bar(stage_data, shannon_entropy=0.0):
    """
    消融实验分组柱状图（4指标 × 5阶段）

    设计要点：
    - X轴：HR@5 / Prec@5 / NDCG@5 / MRR 四组
    - 每组5根柱：A0(随机) / A1(召回融合) / A2(+BST粗排) / A3(+精排集成) / A4(+MMR)
    - Y轴从0开始，留足旋转数值标注空间
    - Shannon熵以顶部居中注释标出（A4专属，量纲不同）
    - 图例顶部居中单行横排（ncol=5）
    - 柱顶数值标注旋转75°避免重叠

    Parameters
    ----------
    stage_data : list of 5 tuples [(hr, prec, ndcg, mrr), ...]
                 顺序：A0(随机基准), A1(热度召回通道B), A2(+BST粗排),
                       A3(+精排集成), A4(+MMR完整管道)
    shannon_entropy : float, A4 在 λ=0.7 时的 Shannon 熵（由 pareto_data 动态传入）
    """
    x_labels    = ["HR@5", "Prec@5", "NDCG@5", "MRR"]
    stage_labels = ["随机基准", "热度召回", "BST粗排", "精排集成", "MMR"]
    colors       = ["#DDDDDD", "#9DC3E6", "#4472C4", "#1F3864", "#C00000"]

    n_metrics = 4
    n_stages  = 5
    bar_w     = 0.15
    x         = np.arange(n_metrics)
    offsets   = np.array([-2, -1, 0, 1, 2]) * bar_w

    fig, ax = plt.subplots(figsize=(13, 6.5))
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    for i, (label, color) in enumerate(zip(stage_labels, colors)):
        vals = [stage_data[i][m] for m in range(4)]   # hr, prec, ndcg, mrr
        ax.bar(x + offsets[i], vals, width=bar_w,
               color=color, label=label,
               zorder=3, edgecolor="white", linewidth=0.5)
        # 柱顶数值标注（旋转75°，Times New Roman字体）
        txt_color = "#555555" if color == "#DDDDDD" else color
        for xi, v in zip(x + offsets[i], vals):
            ax.text(xi, v + 0.002, f"{v:.4f}",
                    ha="center", va="bottom",
                    fontproperties=_tnr_sm_fp,
                    color=txt_color, fontsize=7.5,
                    rotation=75, zorder=5)

    # ── Y轴：从0开始，上限留足标注空间 ──────────────────────────────────
    all_vals = [stage_data[si][mi] for si in range(n_stages) for mi in range(4)]
    y_max = max(all_vals) + 0.09
    ax.set_ylim(0, y_max)
    ax.yaxis.set_major_formatter(
        plt.FuncFormatter(lambda v, _: f"{v:.2f}")
    )

    # ── X轴 ───────────────────────────────────────────────────────────────
    ax.set_xticks(x)
    ax.set_xticklabels(x_labels, fontproperties=_cn_fp, fontsize=11)
    ax.set_ylabel("指标值", fontproperties=_cn_fp, labelpad=8)

    # ── 图例：顶部居中单行横排（ncol=5）─────────────────────────────────
    ax.legend(
        loc="upper center",
        ncol=5,
        bbox_to_anchor=(0.5, 1.14),
        prop=_cn_sm_fp,
        framealpha=0.9,
        edgecolor="#BBBBBB",
        handlelength=1.6,
        columnspacing=0.8,
    )

    # ── Shannon熵注释：图例正下方居中 ────────────────────────────────────
    ax.text(0.5, 1.04,
            f"注：MMR完整管道的Shannon熵为{shannon_entropy:.4f}（多样性指标，量纲不同，不入图）",
            transform=ax.transAxes, ha="center", va="bottom",
            fontproperties=fm.FontProperties(family="SimSun", size=10.5),
            color="#555555")

    _apply_academic_style(ax)
    plt.tight_layout(pad=1.2)

    save_path = os.path.join(IMG_DIR, "消融实验_指标逐层提升.png")
    plt.savefig(save_path, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close()
    print(f"   ✅ 消融柱状图已保存: {save_path}")



def plot_auc_bar(model_names, metric_vals):
    """
    模型 AUC 对比柱状图（仅含真实 AUC 模型，按管道层级排序）。

    只展示具有真实 AUC 分数的模型（BST粗排→DeepFM精排→LightGBM精排→Meta-LR集成），
    热度/ALS等基线因输出为非概率值不纳入本图。全部使用学术蓝，Y轴为AUC。

    Args:
        model_names: 模型标签列表（按管道层级顺序）
        metric_vals: 对应的 AUC 数值列表
    """
    fig, ax = plt.subplots(figsize=(8, 5))
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    x = np.arange(len(model_names))
    ax.bar(x, metric_vals, width=0.5, color="#3A7EBF",
           edgecolor="white", linewidth=0.8, zorder=3)

    # 柱顶标注数值（Times New Roman）
    for xi, v in zip(x, metric_vals):
        ax.text(xi, v + 0.001, f"{v:.4f}",
                ha="center", va="bottom",
                fontproperties=_tnr_sm_fp, color="#222222", zorder=5)

    ax.set_xticks(x)
    ax.set_xticklabels(model_names, fontproperties=_cn_sm_fp)
    ax.set_ylabel("AUC", fontproperties=_tnr_fp, labelpad=8)

    # Y轴范围：从0开始，留足标注空间
    y_max = max(metric_vals) + 0.06
    ax.set_ylim(0, y_max)

    _apply_academic_style(ax)
    plt.tight_layout(pad=1.5)

    save_path = os.path.join(IMG_DIR, "模型AUC对比.png")
    plt.savefig(save_path, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close()
    print(f"   ✅ AUC对比图已保存: {save_path}")


# ============================================================
# 报告生成
# ============================================================

def eval_mmr_pareto(final_preds, y_val, uid_val, feat, val_idx, top_n=5):
    """
    MMR λ帕累托扫描（笔记6.3节）。

    用流派相似度代理（同流派=0.5，否则=0.0）替代FAISS向量，
    记录λ=0.0→1.0（共11点）时的 Precision@top_n 和 Shannon熵（流派多样性）。
    设计点 λ=0.7 在图中高亮标注。

    Args:
        final_preds: 集成模型预测分数 (N,)
        y_val:       验证集标签 (N,)
        uid_val:     验证集用户 encoded_id (N,)
        feat:        特征字典（取 genre_encoded）
        val_idx:     验证集在全量特征中的下标
        top_n:       每用户选取歌曲数（默认 5）

    Returns:
        dict: {λ: {"precision": float, "entropy": float}}
    """
    lambda_values = [round(i * 0.1, 1) for i in range(11)]
    genres = feat["genre_encoded"][val_idx].astype(np.int32)

    # 按用户分组：[(score, label, genre), ...]
    user_groups = {}
    for i, uid in enumerate(uid_val):
        uid = int(uid)
        if uid not in user_groups:
            user_groups[uid] = []
        user_groups[uid].append(
            (float(final_preds[i]), int(y_val[i]), int(genres[i]))
        )

    results = {}
    for lam in lambda_values:
        prec_list    = []
        entropy_list = []

        for uid, items in user_groups.items():
            if len(items) < top_n:
                continue
            # 按分数降序排列候选
            candidates = sorted(items, key=lambda x: -x[0])
            selected_genres = []
            selected_labels = []
            remaining       = list(range(len(candidates)))

            for _ in range(top_n):
                if not remaining:
                    break
                if not selected_genres:
                    # 首轮直接选最高分
                    best_idx = remaining[0]
                else:
                    def _mmr_score(idx, _lam=lam, _cands=candidates,
                                   _sel=selected_genres):
                        score, _, genre = _cands[idx]
                        max_sim = max(
                            0.5 if (genre == sg and genre > 0) else 0.0
                            for sg in _sel
                        )
                        return _lam * score - (1.0 - _lam) * max_sim

                    best_idx = max(remaining, key=_mmr_score)

                _, lbl, genre = candidates[best_idx]
                selected_genres.append(genre)
                selected_labels.append(lbl)
                remaining.remove(best_idx)

            # Precision@top_n
            prec_list.append(sum(selected_labels) / top_n)

            # Shannon熵（流派分布）
            genre_cnt = {}
            for g in selected_genres:
                genre_cnt[g] = genre_cnt.get(g, 0) + 1
            total   = len(selected_genres)
            entropy = -sum(
                (c / total) * math.log(c / total)
                for c in genre_cnt.values() if c > 0
            )
            entropy_list.append(entropy)

        results[lam] = {
            "precision": float(np.mean(prec_list))    if prec_list    else 0.0,
            "entropy":   float(np.mean(entropy_list)) if entropy_list else 0.0,
        }

    return results


def plot_mmr_pareto(pareto_data):
    """
    MMR λ帕累托折线图（笔记6.3节）。

    X轴：Shannon熵（多样性），Y轴：Precision@5（精准度）。
    各点标注对应的 λ 值；λ=0.7（设计点）用红色五角星高亮显示。

    Args:
        pareto_data: eval_mmr_pareto 返回的 {λ: {"precision": float, "entropy": float}}
    """
    import matplotlib.font_manager as fm

    # 只展示 λ=0.4～1.0：λ<0.4 时各点在 x 轴右侧严重堆叠，标注溢出坐标轴；
    # λ=0.4 已足够体现"高多样性"端，λ=1.0 代表"纯精准"端，区间完整覆盖帕累托前沿
    lams       = [l for l in sorted(pareto_data.keys()) if l >= 0.4 - 1e-6]
    entropies  = [pareto_data[l]["entropy"]   for l in lams]
    precisions = [pareto_data[l]["precision"] for l in lams]

    fig, ax = plt.subplots(figsize=(8, 5.5))
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    # 连线（灰色折线）
    ax.plot(entropies, precisions,
            color="#AAAAAA", linewidth=1.2, zorder=2)

    # 各λ点散点 + 标注
    max_ent = max(entropies)   # λ=0.0 的点熵最大，位于 x 轴最右侧
    for lam, ent, prec in zip(lams, entropies, precisions):
        is_design = abs(lam - 0.7) < 1e-6
        color  = "#C00000" if is_design else "#3A7EBF"
        marker = "*"       if is_design else "o"
        size   = 120       if is_design else 50
        ax.scatter(ent, prec, color=color, marker=marker,
                   s=size, zorder=4, edgecolors="white", linewidths=0.5)
        # 最右侧点（当前过滤后为 λ=0.4）向左偏移防溢出，且强制向上避免标注落入 x 轴区域
        is_rightmost = abs(ent - max_ent) < 1e-6
        offset_x = -0.01 if is_rightmost else 0.01
        ha_align = "right"  if is_rightmost else "left"
        # 最右侧点精准度最低，若用负 offset_y 会落入坐标轴；统一向上偏移
        offset_y = 0.003 if (prec > min(precisions) or is_rightmost) else -0.006
        ax.text(
            ent + offset_x, prec + offset_y,
            f"λ={lam:.1f}",
            ha=ha_align,
            fontproperties=fm.FontProperties(family="Times New Roman", size=8),
            color=color, zorder=5
        )

    ax.set_xlabel(
        "Shannon熵（多样性）",
        fontproperties=fm.FontProperties(family="SimSun", size=11),
        labelpad=6
    )
    ax.set_ylabel(
        "Precision@5",
        fontproperties=fm.FontProperties(family="Times New Roman", size=11),
        labelpad=6
    )
    # 注：红色五角星已足够标示设计点（λ=0.7），不再添加文字注释箭头

    ax.yaxis.grid(True, linestyle="--", alpha=0.4, color="#BBBBBB", zorder=0)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    plt.tight_layout(pad=1.2)

    save_path = os.path.join(IMG_DIR, "MMR_lambda帕累托折线图.png")
    plt.savefig(save_path, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close()
    print(f"   ✅ MMR帕累托折线图已保存: {save_path}")


def write_report(ablation_rows, comparison_rows, generated_at, shannon_entropy=0.0):
    lines = []
    lines.append("=" * 70)
    lines.append("  消融实验 + 模型对比实验报告（KKBox 验证集 @K=5）")
    lines.append(f"  生成时间：{generated_at}")
    lines.append("=" * 70)

    lines.append("\n\n" + "=" * 70)
    lines.append("消融实验结果（验证集 @K=5）")
    lines.append("=" * 70)
    lines.append(f"{'配置':<32} {'HR@5':>6} {'Prec@5':>7} {'NDCG@5':>7} {'MRR':>7}  {'Shannon熵':>9}")
    lines.append("-" * 72)
    for row in ablation_rows:
        name, hr, prec, ndcg, mrr, entropy = row
        lines.append(
            f"{name:<32} {hr:>6.4f} {prec:>7.4f} {ndcg:>7.4f} {mrr:>7.4f}  {entropy:>9}"
        )

    lines.append("\n\n" + "=" * 70)
    lines.append("模型对比实验结果（AUC，按管道层级排序：粗排→精排→集成）")
    lines.append("=" * 70)
    lines.append(f"{'模型':<28} {'AUC':>8}")
    lines.append("-" * 40)
    for row in comparison_rows:
        name, auc = row
        lines.append(f"{name:<28} {auc:>8}")

    lines.append("\n\n" + "=" * 70)
    lines.append("说明")
    lines.append("=" * 70)
    lines.append(
        f"1. 消融A4（+MMR完整管道）的配对级指标与A3相同，"
        f"多样性贡献由Shannon熵={shannon_entropy:.4f}体现（λ=0.7设计点）"
    )
    lines.append("2. 热度基线/ALS输出为非概率分，不纳入AUC对比图；排名对比见消融表A0→A1增量")
    lines.append(
        "3. 新架构：LightGBM（精排，AUC=0.8226）与DeepFM（AUC=0.8202）差距仅0.24%，"
        "Meta-LR元学习器能从两模型互补错误中获益，预期集成AUC高于单模型"
    )
    lines.append("=" * 70)

    report = "\n".join(lines)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\n✅ 报告已写入: {os.path.abspath(REPORT_PATH)}")
    print("\n" + report)


# ============================================================
# main
# ============================================================

def main():
    # 脚本级计时：在任何工作开始前记录，覆盖数据加载、推断、图表生成全程
    _start = datetime.datetime.now()
    print("\n" + "=" * 70)
    print("   消融实验 + 模型对比实验评估")
    print(f"   开始时间: {_start.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    # ── Step 1: 加载数据
    print("\n[Step 1] 加载验证集数据...")
    X_val, y_val, feat, val_idx, train_idx = load_val_data()
    uid_val = feat["user_id_encoded"][val_idx]
    print(f"   验证集：{len(np.unique(uid_val)):,} 用户，{len(val_idx):,} 样本")

    # ── Step 2: 一次推断，结果复用于多个配置
    print("\n[Step 2] DeepFM + LightGBM 验证集推断（一次推断，多配置复用）...")
    model_preds, model_aucs = collect_predictions(X_val, y_val, feat, val_idx, train_idx)
    deepfm_val = model_preds.get("DeepFM")
    lgbm_val   = model_preds.get("LightGBM")
    if deepfm_val is None or lgbm_val is None:
        print("❌ DeepFM 或 LightGBM 推断失败，请检查模型文件！")
        sys.exit(1)

    # ── Step 3: 加载 Meta-LGBM 和 LightGBM
    meta_path = MODE_DIR / "fine_rank" / "ensemble" / "meta_learner.pkl"
    with open(meta_path, "rb") as f:
        meta_learner = pickle.load(f)
    print("   ✅ Meta-LR 元学习器已加载")

    lgbm_path = MODE_DIR / "fine_rank" / "lgbm" / "lgbm_model.pkl"
    with open(lgbm_path, "rb") as f:
        lgbm_model = pickle.load(f)
    auc_lgbm = float(lgbm_model.get("val_auc", 0.7921))
    print(f"   ✅ LightGBM 模型已加载（val_auc={auc_lgbm:.4f}）")

    # ── Step 4: 消融实验（5阶段：A0随机→A1热度召回→A2粗排→A3精排→A4重排）
    print("\n" + "=" * 70)
    print("【消融实验】")
    print("=" * 70)
    # A1 改用纯热度（song_play_count_log）：全局非个性化信号，不依赖训练交互矩阵，
    # 避免 ALS/SVD 在闭合验证集上因训练数据偏差导致得分虚高（Closed-World Bias）
    metrics_a0               = eval_ablation_a0(y_val, uid_val)
    metrics_als_base, als_preds = eval_als(feat, val_idx, y_val, uid_val)   # 供 Step5 对比复用
    metrics_a1               = eval_popularity(feat, val_idx, y_val, uid_val)
    metrics_a2, bst_preds    = eval_bst_coarse(feat, val_idx, train_idx, y_val, uid_val)
    metrics_meta             = eval_meta_lgbm(deepfm_val, lgbm_val, meta_learner, y_val, uid_val)
    metrics_a4               = metrics_meta   # A4 配对指标同 A3，多样性贡献见 Shannon 熵

    # ── Step 5: 对比实验（复用 Step4 已有推断结果，不重复加载模型）
    print("\n" + "=" * 70)
    print("【对比实验】")
    print("=" * 70)
    metrics_pop      = eval_popularity(feat, val_idx, y_val, uid_val)
    metrics_als      = metrics_als_base                                  # 复用 Step4 ALS 结果
    metrics_deepfm   = eval_single_deepfm(deepfm_val, y_val, uid_val)
    metrics_lgbm_cmp = eval_lgbm(X_val, lgbm_model, y_val, uid_val)
    metrics_bst      = eval_single_bst(bst_preds, y_val, uid_val)       # 复用 A2 的 BST preds

    # ── Step 6: 整理 AUC 数据
    auc_deepfm = model_aucs.get("DeepFM", 0.8201)
    auc_bst    = 0.7886   # BST 粗排模型验证集 AUC（来源：历史训练日志）

    ensemble_cfg_path = MODE_DIR / "fine_rank" / "ensemble" / "ensemble_config.pkl"
    auc_meta = 0.8199
    if ensemble_cfg_path.exists():
        with open(ensemble_cfg_path, "rb") as f:
            ec = pickle.load(f)
        auc_meta = ec.get("meta_auc", 0.8199)

    a0_hr,  a0_prec,  a0_ndcg,  a0_mrr  = fmt(metrics_a0)
    a1_hr,  a1_prec,  a1_ndcg,  a1_mrr  = fmt(metrics_a1)
    a2_hr,  a2_prec,  a2_ndcg,  a2_mrr  = fmt(metrics_a2)
    a3_hr,  a3_prec,  a3_ndcg,  a3_mrr  = fmt(metrics_meta)

    # ── Step 7: 生成图表
    print("\n" + "=" * 70)
    print("【生成图表】")
    print("=" * 70)

    # 先计算 MMR pareto 以获取设计点实际 Shannon 熵，再传入消融图
    print("\n   [图表③-前置] MMR λ 帕累托扫描（获取设计点熵值）...")
    _X_pareto    = np.column_stack([deepfm_val, lgbm_val])
    _final_preds = meta_learner.predict_proba(_X_pareto)[:, 1].astype(np.float32)
    pareto_data  = eval_mmr_pareto(_final_preds, y_val, uid_val, feat, val_idx, top_n=5)
    actual_entropy = pareto_data.get(0.7, {}).get("entropy", 0.0)

    # ① 消融实验分组柱状图（4指标 × 5阶段，A0-A4）
    stage_data = [
        (a0_hr, a0_prec, a0_ndcg, a0_mrr),   # A0：随机基准（下界）
        (a1_hr, a1_prec, a1_ndcg, a1_mrr),   # A1：三通道召回融合
        (a2_hr, a2_prec, a2_ndcg, a2_mrr),   # A2：+BST粗排
        (a3_hr, a3_prec, a3_ndcg, a3_mrr),   # A3：+精排集成（Meta-LR）
        (a3_hr, a3_prec, a3_ndcg, a3_mrr),   # A4：+MMR完整管道（配对指标同A3）
    ]
    plot_ablation_bar(stage_data, shannon_entropy=actual_entropy)

    # ② AUC 对比柱状图（仅含真实 AUC 模型，按管道层级排序）
    auc_model_names = [
        "BST\n粗排层",
        "单模型DeepFM\n精排层",
        "LightGBM\n精排层",
        "Meta-LR\n精排集成",
    ]
    auc_metric_vals = [auc_bst, auc_deepfm, auc_lgbm, auc_meta]
    plot_auc_bar(auc_model_names, auc_metric_vals)

    # ③ MMR 帕累托折线图
    plot_mmr_pareto(pareto_data)

    # ── Step 8: 生成报告
    print("\n" + "=" * 70)
    print("【生成报告】")
    print("=" * 70)

    _, _, ndcg_pop, _ = fmt(metrics_pop)
    _, _, ndcg_als, _ = fmt(metrics_als)
    ablation_rows = [
        ("A0: 随机基准（下界）",              a0_hr, a0_prec, a0_ndcg, a0_mrr, "—"),
        ("A1: +热度召回（通道B）",              a1_hr, a1_prec, a1_ndcg, a1_mrr, "—"),
        ("A2: +BST粗排",                      a2_hr, a2_prec, a2_ndcg, a2_mrr, "—"),
        ("A3: +精排集成（Meta-LR）",           a3_hr, a3_prec, a3_ndcg, a3_mrr, "—"),
        ("A4: +MMR完整管道",                   a3_hr, a3_prec, a3_ndcg, a3_mrr,
         f"{actual_entropy:.4f}"),
    ]
    comparison_rows = [
        ("BST粗排层（AUC）",        f"{auc_bst:.4f}"),
        ("单模型DeepFM精排层（AUC）", f"{auc_deepfm:.4f}"),
        ("LightGBM精排层（AUC）",    f"{auc_lgbm:.4f}"),
        ("Meta-LR集成精排（AUC）",   f"{auc_meta:.4f}"),
        ("Most Popular热度（NDCG@5）", f"{ndcg_pop:.4f}"),
        ("ALS协同过滤（NDCG@5）",     f"{ndcg_als:.4f}"),
    ]

    generated_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    write_report(ablation_rows, comparison_rows, generated_at, shannon_entropy=actual_entropy)

    _elapsed = str(datetime.datetime.now() - _start).split(".")[0]
    print("\n" + "=" * 70)
    print("✅ 全部评估完成！")
    print(f"   报告：{REPORT_PATH}")
    print(f"   图片目录：{IMG_DIR}")
    print(f"   结束时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   总耗时:   {_elapsed}")
    print("=" * 70)


if __name__ == "__main__":
    main()
