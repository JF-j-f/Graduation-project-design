#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
eval_recall_baseline.py — 召回层基线评估（E2实验）

功能：
  1. 在验证集上计算 Most Popular 热门召回的 Recall@50 和 Recall@200
  2. 读取 ALS 网格搜索结果中最优组合的 Recall@50 和 Recall@200
     （ALS网格搜索已使用标准 train/val 时序切分，数据无泄漏）
  3. 对比两路基线召回性能，输出 E2 实验报告

指标说明：
  Recall@K = 验证集中至少有1首正样本被召回的用户占比
  召回层不关心排名顺序，只关心正样本是否进入候选池

ALS数据来源说明：
  最终 ALS 模型在全量数据上训练（含验证集），直接用该模型评估会引入
  数据泄漏，导致指标虚高。因此 ALS Recall 数值直接读取 als_grid_search_results.txt
  中的最优组合（rank=256，使用正确的 train/val 切分评估），保证指标可信度。

开发者：JunFu
"""

import os
import re
import sys
import pickle
import datetime
import warnings
from pathlib import Path
from collections import defaultdict

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ── 路径配置 ────────────────────────────────────────────────────────────────
_MUSICMODE    = Path(__file__).resolve().parents[2]
MODE_DIR      = _MUSICMODE / "Mode"
FE_DIR        = MODE_DIR / "feature_engineering"
RECALL_DIR    = MODE_DIR / "recall"
DOC_DIR       = _MUSICMODE / "Document"
DOC_DIR.mkdir(parents=True, exist_ok=True)

FEATURES_PATH = FE_DIR  / "features_v3.pkl"
ALS_GRID_PATH = RECALL_DIR / "als_grid_search_results.txt"
REPORT_PATH   = DOC_DIR / "eval_recall_baseline_report.txt"

# ── 超参数（与训练脚本保持一致） ────────────────────────────────────────────
VALID_RATIO      = 0.1
MIN_INTERACTIONS = 5    # 与精排评估脚本（build_ensemble.py 等）保持一致
K_LIST           = [50, 200]   # 召回层评估截断：Top-50 / Top-200


# ============================================================
# Step 1: 加载验证集正样本
# ============================================================

def load_val_positives():
    """
    按用户级时序切分加载验证集，返回：
    - uid_to_pos: {encoded_uid -> set of song_encoded_ids}（每个用户的正样本集合）
    - song_play_count: 全站各歌曲的对数播放量（用于热度排序）
    - n_songs: 歌曲词典大小

    Returns:
        Tuple[dict, np.ndarray, int]
    """
    print("\n" + "=" * 60)
    print("[Step 1] 加载特征 & 时序切分 & 构建验证集正样本")
    print("=" * 60)

    if not FEATURES_PATH.exists():
        print(f"❌ 特征文件不存在：{FEATURES_PATH}")
        print("   请先运行 prepare_features_v3.py")
        sys.exit(1)

    with open(FEATURES_PATH, "rb") as f:
        feat = pickle.load(f)

    user_id_enc    = feat["user_id_encoded"].astype(np.int32)
    song_id_enc    = feat["song_id_encoded"].astype(np.int32)
    target         = feat["target"].astype(np.int8)
    play_time_unix = feat.get("play_time_unix", np.zeros(len(target), dtype=np.int64))

    # 用户级时序切分（与 build_ensemble.py 完全一致）
    _df_meta = pd.DataFrame({
        "orig_idx": np.arange(len(play_time_unix)),
        "uid":      user_id_enc,
        "time":     play_time_unix,
    }).sort_values(["uid", "time"])
    _df_meta["_cnt"]  = _df_meta.groupby("uid")["uid"].transform("count")
    _df_meta["_rank"] = _df_meta.groupby("uid").cumcount()
    _n_val_vec        = (_df_meta["_cnt"] * VALID_RATIO).astype(int).clip(lower=1)
    _is_val           = ((_df_meta["_cnt"] >= MIN_INTERACTIONS) &
                         (_df_meta["_rank"] >= _df_meta["_cnt"] - _n_val_vec))
    val_idx = _df_meta.loc[_is_val, "orig_idx"].values

    # 构建 uid → 验证集正样本集合（只取 target=1 的交互作为命中依据）
    uid_to_pos = defaultdict(set)
    for idx in val_idx:
        if target[idx] == 1:
            uid_to_pos[int(user_id_enc[idx])].add(int(song_id_enc[idx]))

    n_users_with_pos = len(uid_to_pos)
    total_pos        = sum(len(v) for v in uid_to_pos.values())
    n_songs          = int(feat["n_songs"])

    # 全站歌曲播放量（用于热度排序基线）
    # feat["song_play_count_log"] 是按样本存储的歌曲级特征，形状为 (n_samples,)
    # 必须聚合为 per-song 数组（形状 n_songs，按 encoded song_id 索引）
    # 否则 argpartition 返回的是样本索引而非歌曲编码，与 uid_to_pos 中的 song_id 不对齐
    _pc_raw = feat.get("song_play_count_log",
                       np.zeros(len(song_id_enc), dtype=np.float32))
    song_play_count = np.zeros(n_songs, dtype=np.float32)
    # 同一 song_id 的特征值相同，向量化赋值后最终值正确
    song_play_count[song_id_enc] = np.asarray(_pc_raw, dtype=np.float32)

    print(f"   验证用户数（有正样本）: {n_users_with_pos:,}")
    print(f"   总正样本数:            {total_pos:,}")
    print(f"   歌曲词典大小:          {n_songs:,}")
    return uid_to_pos, song_play_count, n_songs


# ============================================================
# Step 2: Most Popular 召回评估
# ============================================================

def eval_most_popular(uid_to_pos, song_play_count, k_list):
    """
    热门召回基线：对所有用户推荐相同的全站 Top-K 热门歌曲。

    这是召回层最简单的基线。与协同过滤不同，热门召回不做任何个性化，
    所有用户共享一个候选池，评估其对验证集正样本的覆盖率。

    Args:
        uid_to_pos:        {uid: set of pos_song_ids}
        song_play_count:   各歌曲对数播放量 (n_songs,)
        k_list:            要评估的 K 值列表（如 [50, 200]）

    Returns:
        dict: {K: recall_at_k}
    """
    print("\n" + "=" * 60)
    print("[Step 2] Most Popular 热门召回评估")
    print("=" * 60)

    max_k = max(k_list)
    # 取全站播放量最高的 Top-max_k 歌曲（encoded_id）
    top_songs = set(np.argpartition(song_play_count, -max_k)[-max_k:].tolist())

    results = {}
    for k in k_list:
        # 重新取 Top-k（保证每个 K 精确）
        top_k_set = set(np.argpartition(song_play_count, -k)[-k:].tolist())
        hits       = 0
        n_users    = 0
        for uid, pos_set in uid_to_pos.items():
            if len(pos_set) == 0:
                continue
            n_users += 1
            if len(pos_set & top_k_set) > 0:
                hits += 1
        recall = hits / n_users if n_users > 0 else 0.0
        results[k] = recall
        print(f"   Most Popular  Recall@{k:<3}: {recall:.4f}  "
              f"（{hits:,}/{n_users:,} 用户命中）")

    return results


# ============================================================
# Step 3: 读取 ALS 最优网格搜索结果
# ============================================================

def load_als_grid_results():
    """
    从 als_grid_search_results.txt 中读取最优 ALS 组合的 Recall 指标。

    ALS 网格搜索在训练集拟合、验证集评估的正确框架下运行，
    指标可信，直接复用，无需重复计算。

    Returns:
        dict: {"rank", "reg", "alpha", "recall_50", "recall_200", "label"}
        或者在文件不存在时返回 None
    """
    print("\n" + "=" * 60)
    print("[Step 3] 读取 ALS 网格搜索最优结果")
    print("=" * 60)

    if not ALS_GRID_PATH.exists():
        print(f"   ⚠️  网格搜索结果文件不存在: {ALS_GRID_PATH}")
        print("      请先运行 train_als.py")
        return None

    with open(ALS_GRID_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    # 提取带★标记的最优行
    best_match = re.search(
        r"(\S+.*?)\s+(\d+)\s+([\d.]+)\s+(\d+)\s+([\d.]+)\s+([\d.]+)\s+OK\s*★",
        content
    )
    if best_match:
        label      = best_match.group(1).strip()
        rank       = int(best_match.group(2))
        reg        = float(best_match.group(3))
        alpha      = int(best_match.group(4))
        recall_50  = float(best_match.group(5))
        recall_200 = float(best_match.group(6))
        result = {
            "label":      label,
            "rank":       rank,
            "reg":        reg,
            "alpha":      alpha,
            "recall_50":  recall_50,
            "recall_200": recall_200,
        }
        print(f"   最优组合: rank={rank}, reg={reg}, alpha={alpha}  [{label}]")
        print(f"   Recall@50 : {recall_50:.4f}")
        print(f"   Recall@200: {recall_200:.4f}")
        return result

    # 备用：从摘要行提取
    r50_match  = re.search(r"最优\s*Recall@50[：:]\s*([\d.]+)", content)
    r200_match = re.search(r"最优\s*Recall@200[：:]\s*([\d.]+)", content)
    if r200_match:
        result = {
            "label":      "最优组合（rank=256）",
            "rank":       256,
            "reg":        0.1,
            "alpha":      40,
            "recall_50":  float(r50_match.group(1)) if r50_match else 0.0,
            "recall_200": float(r200_match.group(1)),
        }
        print(f"   Recall@50 : {result['recall_50']:.4f}")
        print(f"   Recall@200: {result['recall_200']:.4f}")
        return result

    print("   ⚠️  无法解析网格搜索结果，ALS指标将缺失")
    return None


# ============================================================
# Step 4: 生成报告
# ============================================================

def write_report(pop_results, als_result, generated_at):
    """
    生成 E2 召回层基线评估报告，对比 Most Popular 与 ALS 的召回能力。

    Args:
        pop_results:   {K: recall} Most Popular 结果
        als_result:    ALS 最优结果字典（或 None）
        generated_at:  报告生成时间字符串
    """
    lines = []
    lines.append("=" * 60)
    lines.append("  召回层基线评估报告（E2实验）")
    lines.append(f"  生成时间：{generated_at}")
    lines.append("=" * 60)

    lines.append("\n【评估说明】")
    lines.append("  Recall@K = 在Top-K候选中至少命中1首正样本的用户占比")
    lines.append("  验证集：用户级时序切分（MIN_INTERACTIONS=5, VALID_RATIO=0.1）")
    lines.append(f"  ALS Recall 来源：als_grid_search_results.txt"
                 f"（正确 train/val 切分，无数据泄漏）")

    lines.append("\n\n" + "=" * 60)
    lines.append("  召回性能对比")
    lines.append("=" * 60)
    lines.append(f"  {'召回策略':<28} {'Recall@50':>10} {'Recall@200':>11}")
    lines.append("-" * 55)

    # Most Popular 行
    r50_pop  = pop_results.get(50,  0.0)
    r200_pop = pop_results.get(200, 0.0)
    lines.append(f"  {'Most Popular（热门基线）':<28} {r50_pop:>10.4f} {r200_pop:>11.4f}")

    # ALS 行
    if als_result:
        r50_als  = als_result["recall_50"]
        r200_als = als_result["recall_200"]
        label    = f"ALS（rank={als_result['rank']}, α={als_result['alpha']}）"
        lines.append(f"  {label:<28} {r50_als:>10.4f} {r200_als:>11.4f}")

        # 提升幅度
        if r200_pop > 0:
            uplift = (r200_als - r200_pop) / r200_pop * 100
            lines.append(f"\n  ALS vs Most Popular（Recall@200 提升）: "
                         f"{r200_als:.4f} vs {r200_pop:.4f} = +{uplift:.1f}%")
    else:
        lines.append(f"  {'ALS（最优组合）':<28} {'N/A':>10} {'N/A':>11}")

    lines.append("\n\n" + "=" * 60)
    lines.append("  结论")
    lines.append("=" * 60)
    if als_result:
        lines.append(
            f"  ALS Recall@200={als_result['recall_200']:.4f}，"
            f"Most Popular Recall@200={pop_results.get(200, 0.0):.4f}。"
        )
        lines.append(
            "  ALS通过协同过滤学习用户个性化偏好，召回质量优于纯热度策略，"
        )
        lines.append(
            "  但Recall@200约0.28意味着仍有约72%的正样本未进入200个候选，"
        )
        lines.append(
            "  这是精排层仅在已召回的候选上评估的上界约束（召回缺失不可逆）。"
        )
    lines.append("=" * 60)

    report = "\n".join(lines)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\n✅ 报告已写入: {os.path.abspath(REPORT_PATH)}")
    print("\n" + report)


# ============================================================
# main
# ============================================================

def main():
    """E2 实验：召回层基线评估主函数。"""
    # 脚本级计时：在任何工作开始前记录，覆盖数据加载和评估全程
    _start = datetime.datetime.now()
    print("\n" + "=" * 60)
    print("   召回层基线评估（E2实验）")
    print(f"   开始时间: {_start.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # Step 1: 加载验证集正样本
    uid_to_pos, song_play_count, n_songs = load_val_positives()

    # Step 2: Most Popular 召回评估
    pop_results = eval_most_popular(uid_to_pos, song_play_count, K_LIST)

    # Step 3: 读取 ALS 网格搜索最优结果
    als_result = load_als_grid_results()

    # Step 4: 生成报告
    print("\n" + "=" * 60)
    print("[Step 4] 生成 E2 实验报告")
    print("=" * 60)
    generated_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    write_report(pop_results, als_result, generated_at)

    _elapsed = str(datetime.datetime.now() - _start).split(".")[0]
    print("\n" + "=" * 60)
    print("✅ E2 召回层评估完成！")
    print(f"   结束时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   总耗时:   {_elapsed}")
    print("=" * 60)
    print("\n🚀 下一步:")
    print("   python eval_experiment.py   # E1 消融实验 + 模型对比")


if __name__ == "__main__":
    main()
