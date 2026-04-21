# -*- coding: utf-8 -*-
"""
ALS 召回模型训练（精简6组超参网格搜索 + Recall@200评估）

功能：
1. 加载特征数据，按用户级时序切分训练/验证集
2. 在训练集上进行6组超参组合的网格搜索，以 Recall@50/200 为评估指标
3. 选出 Recall@200 最高的组合，在全量数据上重新训练最终模型
4. 为每个用户生成候选歌曲集（Top-200）
5. 保存最终模型、候选集和网格搜索结果表（供论文引用）

超参网格（6组，覆盖低/中/高 rank 各层级）：
    rank:  [32, 50, 128, 256]
    reg:   [0.01, 0.1]
    alpha: [1, 40]（置信度缩放因子，c_ui = 1 + alpha × r_ui）
    iterations: 20（固定，不作为搜索维度）

训练环境：RTX 5090 32GB × 1 / CPU Xeon 8470Q 25核心 / 内存 90GB
开发者：JunFu
"""

import os
import sys
import pickle
from pathlib import Path
from collections import defaultdict
import time
import datetime
import numpy as np
import pandas as pd
from tqdm import tqdm
import warnings

warnings.filterwarnings("ignore")

# ============================================================
# 路径配置
# ============================================================

MODE_DIR = Path(__file__).resolve().parents[2] / "Mode"
FEATURE_PATH     = MODE_DIR / "feature_engineering" / "features_v3.pkl"
ALS_MODEL_PATH   = MODE_DIR / "recall" / "als_model.pkl"
CANDIDATES_PATH  = MODE_DIR / "recall" / "candidates.pkl"
GRID_RESULT_PATH = MODE_DIR / "recall" / "als_grid_search_results.txt"
ALS_MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)

# ============================================================
# 超参数配置
# ============================================================

# 6组精简网格——覆盖低/中/高 rank，各配一组 reg；alpha 控制置信度缩放
# 通过矩阵预乘方式传入 alpha：model.fit(matrix.T * alpha)
GRID_SEARCH = [
    {"rank": 32,  "reg": 0.1,  "alpha": 40, "label": "低维基准"},
    {"rank": 50,  "reg": 0.1,  "alpha": 40, "label": "原始值（对照组）"},
    {"rank": 128, "reg": 0.1,  "alpha": 40, "label": "中维"},
    {"rank": 128, "reg": 0.01, "alpha": 40, "label": "中维低正则"},
    {"rank": 256, "reg": 0.1,  "alpha": 40, "label": "高维"},
    {"rank": 256, "reg": 0.01, "alpha": 1,  "label": "高维低正则低alpha"},
]

ALS_ITERATIONS   = 20   # 固定迭代轮数，不参与网格搜索
TOP_K_CANDIDATES = 200  # 每用户候选数上限
VALID_RATIO      = 0.1  # 验证集比例（同其他模型保持一致）
MIN_INTERACTIONS = 5    # 参与评估的用户最少交互数


# ============================================================
# Step 1: 加载特征
# ============================================================

def load_features():
    """
    加载特征工程产出的 features_v3.pkl。

    Returns:
        dict: 含 user_id_encoded / song_id_encoded / target 等字段的特征字典

    Raises:
        SystemExit: 特征文件不存在时退出
    """
    print("\n" + "=" * 62)
    print("📂 [Step 1/5] 加载特征数据")
    print("=" * 62)

    if not FEATURE_PATH.exists():
        print(f"   ❌ 特征文件不存在: {FEATURE_PATH}")
        print("   请先运行 prepare_features_v3.py")
        sys.exit(1)

    with open(FEATURE_PATH, "rb") as f:
        features = pickle.load(f)

    print(f"   ✅ 用户数: {features['n_users']:,}")
    print(f"   ✅ 歌曲数: {features['n_songs']:,}")
    print(f"   ✅ 样本数: {len(features['user_id_encoded']):,}")

    return features


# ============================================================
# Step 2: 用户级时序切分
# ============================================================

def temporal_split(features):
    """
    按用户级时序切分训练集和验证集，与 train_deepfm_v3.py / train_lgbm.py
    保持完全一致的切分逻辑：每用户最后 VALID_RATIO 比例的记录为验证集。

    Args:
        features (dict): 特征字典

    Returns:
        tuple:
            train_idx (np.ndarray): 训练集样本索引
            val_positives (dict): {user_id: set(song_id)} 验证集正样本字典
    """
    print("\n" + "=" * 62)
    print("✂️  [Step 2/5] 用户级时序切分")
    print("=" * 62)

    # 若无时间戳则以全零代替（退化为随机切分）
    play_time = features.get(
        "play_time_unix",
        np.zeros(len(features["target"]), dtype=np.int64),
    )
    user_ids = features["user_id_encoded"]
    song_ids = features["song_id_encoded"]
    targets  = features["target"]

    df = pd.DataFrame({
        "orig_idx": np.arange(len(play_time)),
        "uid":      user_ids.astype(np.int32),
        "time":     play_time,
    }).sort_values(["uid", "time"])

    df["_cnt"]  = df.groupby("uid")["uid"].transform("count")
    df["_rank"] = df.groupby("uid").cumcount()
    _n_val = (df["_cnt"] * VALID_RATIO).astype(int).clip(lower=1)
    _is_val = (
        (df["_cnt"] >= MIN_INTERACTIONS) &
        (df["_rank"] >= df["_cnt"] - _n_val)
    )

    train_idx = df.loc[~_is_val, "orig_idx"].values
    val_idx   = df.loc[_is_val,  "orig_idx"].values

    # 只保留正样本（target=1）构建验证字典
    val_positives = defaultdict(set)
    for i in val_idx:
        if targets[i] == 1:
            val_positives[int(user_ids[i])].add(int(song_ids[i]))

    n_val_users = sum(1 for songs in val_positives.values() if songs)
    print(f"   训练集: {len(train_idx):,} 条")
    print(f"   验证集正样本用户数: {n_val_users:,}")

    return train_idx, val_positives


# ============================================================
# 构建交互矩阵（可选择仅用训练集子集）
# ============================================================

def build_interaction_matrix(features, indices=None):
    """
    构建用户-歌曲交互稀疏矩阵，值为 target 累加（播放次数之和）。

    Args:
        features (dict): 特征字典
        indices (np.ndarray, optional): 指定时只用这些索引的样本，
                                        None 则使用全量数据

    Returns:
        csr_matrix: shape=(n_users, n_songs)，dtype=float32
    """
    from scipy.sparse import csr_matrix

    n_users = features["n_users"]
    n_songs = features["n_songs"]

    if indices is not None:
        user_ids = features["user_id_encoded"][indices]
        song_ids = features["song_id_encoded"][indices]
        targets  = features["target"][indices]
        print(f"   使用 {len(indices):,} 条样本构建矩阵（训练集子集）")
    else:
        user_ids = features["user_id_encoded"]
        song_ids = features["song_id_encoded"]
        targets  = features["target"]
        print(f"   使用全量 {len(targets):,} 条样本构建矩阵")

    print(f"   矩阵维度: {n_users:,} × {n_songs:,}")

    # 向量化 groupby 统计每对(用户, 歌曲)的播放次数 (注意：必须要过滤掉目标值为 0 的负交叉，ALS仅依赖隐式正反馈)
    df_interactions = pd.DataFrame({"user": user_ids, "song": song_ids, "target": targets})
    df_interactions = df_interactions[df_interactions["target"] > 0]
    
    interaction_series = df_interactions.groupby(["user", "song"])["target"].sum()
    rows = interaction_series.index.get_level_values("user").tolist()
    cols = interaction_series.index.get_level_values("song").tolist()
    data = interaction_series.values.tolist()

    matrix = csr_matrix(
        (data, (rows, cols)),
        shape=(n_users, n_songs),
        dtype=np.float32,
    )
    print(f"   ✅ 非零元素: {matrix.nnz:,}  稀疏度: {1 - matrix.nnz / (n_users * n_songs):.6f}")

    return matrix


# ============================================================
# 评估函数：Recall@K
# ============================================================

def evaluate_recall_at_k(model, train_matrix, val_positives, k_list=(50, 200)):
    """
    计算 ALS 模型在验证集上的 Recall@K。

    Recall@K = 验证集正样本中有多少比例落入 Top-K 推荐结果，
               对所有有正样本的用户取均值。

    Args:
        model: 已训练的 implicit ALS 模型
        train_matrix (csr_matrix): 训练集交互矩阵（排除已交互歌曲时使用）
        val_positives (dict): {user_id: set(song_id)} 验证集正样本
        k_list (tuple): 需要计算的 K 值列表

    Returns:
        dict: {k: float} 各 K 值对应的 Recall 均值
    """
    recall_lists = {k: [] for k in k_list}
    max_k = max(k_list)

    eval_users = [uid for uid, songs in val_positives.items() if songs]

    for user_id in tqdm(eval_users, desc="   Recall@K 评估中"):
        try:
            # implicit要求这里的user_items必须传该用户的切片！
            ids, _ = model.recommend(
                userid=user_id,
                user_items=train_matrix[user_id],
                N=max_k,
                filter_already_liked_items=True,
            )
            positives = val_positives[user_id]
            for k in k_list:
                top_k_set  = set(ids[:k].tolist())
                hit_count  = len(positives & top_k_set)
                recall_lists[k].append(hit_count / len(positives))
        except Exception as e:
            # 如果出错打印出来，避免日后再出现神秘的 0分 消失案
            print(f"评估出错 user={user_id}: {e}")
            for k in k_list:
                recall_lists[k].append(0.0)

    return {k: float(np.mean(v)) if v else 0.0 for k, v in recall_lists.items()}


# ============================================================
# Step 3: 6组超参网格搜索
# ============================================================

def grid_search_als(train_matrix, val_positives):
    """
    对 6 组超参组合逐一训练 ALS，用 Recall@200 选出最优组合。

    alpha 通过矩阵预乘方式传入：model.fit(matrix.T * alpha)
    这等价于将置信度设为 c_ui = 1 + alpha × r_ui，
    是 implicit 库的标准用法（0.7.x 版本构造函数不含 alpha 参数）。

    Args:
        train_matrix (csr_matrix): 训练集交互矩阵
        val_positives (dict): 验证集正样本字典

    Returns:
        tuple:
            grid_results (list): 各组合的评估结果列表
            best_combo (dict): Recall@200 最高的超参字典
    """
    from implicit.als import AlternatingLeastSquares

    print("\n" + "=" * 62)
    print("🔍 [Step 3/5] 超参网格搜索（6组，以 Recall@200 选最优）")
    print("=" * 62)

    grid_results  = []
    best_recall200 = -1.0
    best_combo    = GRID_SEARCH[0]

    for idx, combo in enumerate(GRID_SEARCH, start=1):
        print(f"\n   [{idx}/6] rank={combo['rank']}, reg={combo['reg']}, "
              f"alpha={combo['alpha']}  —— {combo['label']}")

        # 考虑到 implicit 版本兼容性：新版 fit 接收 (users, items)，旧版接收 (items, users)
        # 统一做法：对 alpha 置信度矩阵做兼容调用
        import implicit
        scaled_matrix = (train_matrix * combo["alpha"]).astype(np.float32)
        if hasattr(implicit, '__version__') and implicit.__version__.startswith('0.4'):
            scaled_matrix = scaled_matrix.T

        model = AlternatingLeastSquares(
            factors=combo["rank"],
            regularization=combo["reg"],
            iterations=ALS_ITERATIONS,
            use_gpu=False,
            random_state=42,
        )
        try:
            model.fit(scaled_matrix, show_progress=True)
        except Exception as e:
            print(f"   ❌ 训练失败: {e}，跳过此组合")
            grid_results.append({
                **combo,
                "recall@50":  0.0,
                "recall@200": 0.0,
                "status":     "FAILED",
            })
            continue

        recalls = evaluate_recall_at_k(
            model, train_matrix, val_positives, k_list=[50, 200]
        )
        print(f"   ✅ Recall@50={recalls[50]:.4f}  Recall@200={recalls[200]:.4f}")

        grid_results.append({
            **combo,
            "recall@50":  recalls[50],
            "recall@200": recalls[200],
            "status":     "OK",
        })

        if recalls[200] > best_recall200:
            best_recall200 = recalls[200]
            best_combo = combo

    # 打印汇总表
    print("\n" + "=" * 62)
    print("📋 网格搜索结果汇总")
    print("=" * 62)
    print(f"  {'标签':<22} {'rank':>5} {'reg':>6} {'alpha':>6} "
          f"{'Recall@50':>10} {'Recall@200':>10}")
    print("  " + "-" * 60)
    for r in grid_results:
        is_best = (
            r["rank"]  == best_combo["rank"] and
            r["reg"]   == best_combo["reg"]  and
            r["alpha"] == best_combo["alpha"]
        )
        marker = " ← 最优" if is_best else ""
        print(f"  {r['label']:<22} {r['rank']:>5} {r['reg']:>6} {r['alpha']:>6} "
              f"{r.get('recall@50', 0.0):>10.4f} "
              f"{r.get('recall@200', 0.0):>10.4f}{marker}")
    print(f"\n  🏆 最优: rank={best_combo['rank']}, reg={best_combo['reg']}, "
          f"alpha={best_combo['alpha']}")

    return grid_results, best_combo


# ============================================================
# Step 4: 全量数据重新训练最终模型
# ============================================================

def train_als_final(full_matrix, best_combo):
    """
    用网格搜索选出的最优超参在全量交互矩阵上重新训练 ALS。
    全量训练可利用更多数据，使用户/歌曲向量更准确。

    Args:
        full_matrix (csr_matrix): 全量用户-歌曲交互矩阵
        best_combo (dict): 最优超参字典

    Returns:
        AlternatingLeastSquares: 已训练的最终模型
    """
    from implicit.als import AlternatingLeastSquares

    print("\n" + "=" * 62)
    print("🎯 [Step 4/5] 全量数据最终模型训练")
    print("=" * 62)
    print(f"   rank={best_combo['rank']}, reg={best_combo['reg']}, "
          f"alpha={best_combo['alpha']}, iterations={ALS_ITERATIONS}")

    import implicit
    scaled_matrix = (full_matrix * best_combo["alpha"]).astype(np.float32)
    if hasattr(implicit, '__version__') and implicit.__version__.startswith('0.4'):
            scaled_matrix = scaled_matrix.T

    model = AlternatingLeastSquares(
        factors=best_combo["rank"],
        regularization=best_combo["reg"],
        iterations=ALS_ITERATIONS,
        use_gpu=False,
        random_state=42,
    )
    model.fit(scaled_matrix, show_progress=True)
    print("   ✅ 最终模型训练完成")

    return model


# ============================================================
# Step 5: 生成候选集
# ============================================================

def generate_candidates(model, full_matrix, features):
    """
    为每个用户生成 Top-K 候选歌曲，排除已交互歌曲。

    Args:
        model: 已训练的 ALS 模型
        full_matrix (csr_matrix): 全量交互矩阵
        features (dict): 特征字典

    Returns:
        dict: {user_id: [(song_id, score), ...]} 每用户候选集
    """
    print("\n" + "=" * 62)
    print("📋 [Step 5/5] 生成候选集")
    print("=" * 62)

    n_users    = features["n_users"]
    candidates = {}

    print(f"   🎯 为 {n_users:,} 个用户各生成 Top-{TOP_K_CANDIDATES} 候选...")

    for user_id in tqdm(range(n_users), desc="   生成候选"):
        try:
            ids, scores = model.recommend(
                userid=user_id,
                user_items=full_matrix[user_id],
                N=TOP_K_CANDIDATES,
                filter_already_liked_items=True,
            )
            candidates[user_id] = list(zip(ids.tolist(), scores.tolist()))
        except Exception as e:
            print(f"生成出错 user={user_id}: {e}")
            candidates[user_id] = []

    print(f"   ✅ 候选集生成完成: {len(candidates):,} 个用户")

    return candidates


# ============================================================
# 保存模型、候选集和网格结果表
# ============================================================

def save_results(model, candidates, best_combo, grid_results, total_duration="未知"):
    """
    保存 ALS 模型、候选集和超参网格搜索结果文本表。
    结果表以纯文本格式保存，供论文召回层章节引用。

    Args:
        model: 已训练的最终 ALS 模型
        candidates (dict): 用户候选集
        best_combo (dict): 最优超参
        grid_results (list): 全部6组评估结果
        total_duration (str): 总耗时文本
    """
    print("\n" + "=" * 62)
    print("💾 保存模型与结果")
    print("=" * 62)

    with open(ALS_MODEL_PATH, "wb") as f:
        pickle.dump(model, f, protocol=4)
    print(f"   ✅ ALS 模型:  {ALS_MODEL_PATH}")

    with open(CANDIDATES_PATH, "wb") as f:
        pickle.dump(candidates, f, protocol=4)
    print(f"   ✅ 候选集:    {CANDIDATES_PATH}")

    # 生成纯文本结果表（供论文引用）
    lines = []
    lines.append("=" * 72)
    lines.append("  ALS 超参网格搜索结果（R3，iterations=20 固定不参与搜索）")
    lines.append("=" * 72)
    lines.append(
        f"  {'标签':<22} {'rank':>5} {'reg':>6} {'alpha':>6} "
        f"{'Recall@50':>10} {'Recall@200':>10} {'状态':>6}"
    )
    lines.append("  " + "-" * 68)
    for r in grid_results:
        is_best = (
            r["rank"]  == best_combo["rank"] and
            r["reg"]   == best_combo["reg"]  and
            r["alpha"] == best_combo["alpha"]
        )
        marker = " ★" if is_best else ""
        lines.append(
            f"  {r['label']:<22} {r['rank']:>5} {r['reg']:>6} {r['alpha']:>6} "
            f"{r.get('recall@50', 0.0):>10.4f} "
            f"{r.get('recall@200', 0.0):>10.4f} "
            f"{r.get('status', '?'):>6}{marker}"
        )
    lines.append("=" * 72)
    lines.append(
        f"  最优组合（Recall@200 最高）: rank={best_combo['rank']}, "
        f"reg={best_combo['reg']}, alpha={best_combo['alpha']}"
    )
    lines.append(f"  最优 Recall@200: "
                 f"{max(r.get('recall@200', 0.0) for r in grid_results):.4f}")
    lines.append("-" * 70)
    lines.append(f"  执行耗时统计: {total_duration}")
    lines.append("=" * 72)

    report = "\n".join(lines)
    print("\n" + report)

    with open(GRID_RESULT_PATH, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\n   ✅ 网格结果表: {GRID_RESULT_PATH}")


# ============================================================
# main
# ============================================================

def main():
    """
    主流程：
      加载特征 → 时序切分 → 构建训练矩阵 → 6组网格搜索
      → 全量重训 → 生成候选集 → 保存
    """
    start_time = time.time()
    print("\n" + "🎵" * 31)
    print(f"   MusicMode ALS 召回模型训练（R3: 6组超参网格搜索）")
    print(f"   启动时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("🎵" * 31)

    # Step 1: 加载特征
    features = load_features()

    # Step 2: 按时序切分，得到训练索引和验证集正样本字典
    train_idx, val_positives = temporal_split(features)

    # Step 3: 用训练集子集构建交互矩阵（网格搜索阶段）
    print("\n" + "=" * 62)
    print("📊 构建训练集交互矩阵（网格搜索用）")
    print("=" * 62)
    train_matrix = build_interaction_matrix(features, indices=train_idx)

    # Step 4: 6组网格搜索，选出最优超参
    grid_results, best_combo = grid_search_als(train_matrix, val_positives)

    # Step 5: 全量数据重训（利用所有样本提升向量质量）
    print("\n" + "=" * 62)
    print("📊 构建全量交互矩阵（最终训练用）")
    print("=" * 62)
    full_matrix = build_interaction_matrix(features, indices=None)
    final_model = train_als_final(full_matrix, best_combo)

    # Step 6: 生成候选集
    candidates = generate_candidates(final_model, full_matrix, features)

    # 计算总耗时
    end_time = time.time()
    total_duration = str(datetime.timedelta(seconds=int(end_time - start_time)))

    # Step 7: 保存所有产出
    save_results(final_model, candidates, best_combo, grid_results, total_duration)

    print("\n" + "=" * 62)
    print("✅ ALS 训练全部完成！")
    print(f"   结束时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   总耗时:   {total_duration}")
    print(f"   模型:     {ALS_MODEL_PATH}")
    print(f"   候选集:   {CANDIDATES_PATH}")
    print(f"   网格结果: {GRID_RESULT_PATH}")
    print("=" * 62)
    print("\n🚀 下一步: 运行 eval_recall_baseline.py 做召回层基线对比实验")


if __name__ == "__main__":
    main()
