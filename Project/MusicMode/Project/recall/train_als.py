# -*- coding: utf-8 -*-
"""
ALS 召回模型训练
功能：
1. 加载特征数据
2. 训练 ALS 协同过滤模型
3. 为每个用户生成候选歌曲集
4. 保存模型和候选集

开发者：JunFun
"""

import os
import sys
import pickle
from pathlib import Path
import numpy as np
import pandas as pd
from tqdm import tqdm
import warnings
warnings.filterwarnings('ignore')

# ============================================
# 配置
# ============================================

MODE_DIR = Path(__file__).resolve().parents[2] / "Mode"
FEATURE_PATH    = MODE_DIR / "feature_engineering" / "features_v3.pkl"
ALS_MODEL_PATH  = MODE_DIR / "recall" / "als_model.pkl"
CANDIDATES_PATH = MODE_DIR / "recall" / "candidates.pkl"
ALS_MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)

# ALS 超参数
ALS_RANK = 50           # 隐向量维度
ALS_ITERATIONS = 10     # 迭代次数
ALS_REGULARIZATION = 0.1
TOP_K_CANDIDATES = 200  # 每用户候选数


def load_features():
    """加载特征数据"""
    print("\n" + "=" * 60)
    print("📂 [Step 1/4] 加载特征数据")
    print("=" * 60)
    
    if not os.path.exists(FEATURE_PATH):
        print(f"   ❌ 特征文件不存在: {FEATURE_PATH}")
        print(f"   📌 请先运行 prepare_features_v3.py")
        sys.exit(1)
    
    with open(FEATURE_PATH, 'rb') as f:
        features = pickle.load(f)
    
    print(f"   ✅ 用户数: {features['n_users']:,}")
    print(f"   ✅ 歌曲数: {features['n_songs']:,}")
    print(f"   ✅ 样本数: {len(features['user_id_encoded']):,}")
    
    return features


def build_interaction_matrix(features):
    """构建用户-歌曲交互矩阵"""
    print("\n" + "=" * 60)
    print("📊 [Step 2/4] 构建交互矩阵")
    print("=" * 60)
    
    n_users = features['n_users']
    n_songs = features['n_songs']
    
    print(f"   📐 矩阵维度: {n_users:,} x {n_songs:,}")
    
    # 创建稀疏交互矩阵
    from scipy.sparse import csr_matrix, lil_matrix
    
    print("   🔨 构建稀疏矩阵...")
    
    # 使用 lil_matrix 构建（更快的增量添加）
    user_ids = features['user_id_encoded']
    song_ids = features['song_id_encoded']
    targets = features['target']
    
    # 统计每个 (user, song) 的交互次数（向量化，替代 Python for 循环）
    print("   统计交互（向量化 groupby）...")
    interaction_series = (
        pd.DataFrame({"user": user_ids, "song": song_ids, "target": targets})
        .groupby(["user", "song"])["target"].sum() #统计每对(用户,歌曲)的播放次数
    )
    rows = interaction_series.index.get_level_values("user").tolist()
    cols = interaction_series.index.get_level_values("song").tolist()
    data = interaction_series.values.tolist()
    
    #将交互数据转换为稀疏矩阵
    interaction_matrix = csr_matrix((data, (rows, cols)), 
                                    shape=(n_users, n_songs),
                                    dtype=np.float32)
    
    print(f"   ✅ 非零元素: {interaction_matrix.nnz:,}")
    print(f"   ✅ 稀疏度: {1 - interaction_matrix.nnz / (n_users * n_songs):.6f}")
    
    return interaction_matrix


def train_als(interaction_matrix):
    """训练 ALS 模型"""
    print("\n" + "=" * 60)
    print("🎯 [Step 3/4] 训练 ALS 模型")
    print("=" * 60)
    
    try:
        from implicit.als import AlternatingLeastSquares
        print("   ✅ 使用 implicit 库的 ALS 实现")
    except ImportError:
        print("   ⚠️ implicit 库未安装，使用简化版 ALS")
        return train_simple_als(interaction_matrix)
    
    # 配置模型
    print(f"\n   📋 模型配置:")
    print(f"      - rank (隐向量维度): {ALS_RANK}")
    print(f"      - iterations: {ALS_ITERATIONS}")
    print(f"      - regularization: {ALS_REGULARIZATION}")
    
    # 训练
    print(f"\n   🚀 开始训练...")
    model = AlternatingLeastSquares(
        factors=ALS_RANK,
        iterations=ALS_ITERATIONS,
        regularization=ALS_REGULARIZATION,
        use_gpu=False  # CPU 训练，因为 implicit GPU 需要额外配置
    )
    
    # implicit 需要 item-user 矩阵（转置）
    model.fit(interaction_matrix.T, show_progress=True)
    
    print(f"   ✅ 训练完成!")
    
    return model


def train_simple_als(interaction_matrix):
    """简化版 ALS（不依赖 implicit 库）"""
    print("\n   🔧 使用矩阵分解实现...")
    
    from scipy.sparse.linalg import svds
    
    n_users, n_songs = interaction_matrix.shape
    
    # SVD 分解
    print(f"   🔨 SVD 分解 (k={ALS_RANK})...")
    
    # 限制 k 不超过矩阵维度
    k = min(ALS_RANK, min(n_users, n_songs) - 1)
    
    U, sigma, Vt = svds(interaction_matrix, k=k)
    
    # 构建模型对象
    model = {
        'user_factors': U * np.sqrt(sigma),
        'item_factors': (Vt.T * np.sqrt(sigma)),
        'type': 'simple_als'
    }
    
    print(f"   ✅ SVD 分解完成!")
    print(f"      - 用户因子: {model['user_factors'].shape}")
    print(f"      - 物品因子: {model['item_factors'].shape}")
    
    return model


def generate_candidates(model, interaction_matrix, features):
    """为每个用户生成候选歌曲"""
    print("\n" + "=" * 60)
    print("📋 [Step 4/4] 生成候选集")
    print("=" * 60)
    
    n_users = features['n_users']
    candidates = {}
    
    print(f"   🎯 为每个用户生成 Top-{TOP_K_CANDIDATES} 候选...")
    
    if isinstance(model, dict) and model.get('type') == 'simple_als':
        # 简化版：矩阵乘法计算分数
        user_factors = model['user_factors']
        item_factors = model['item_factors']
        
        # 批量计算（节省内存）
        batch_size = 1000
        
        for start in tqdm(range(0, n_users, batch_size), desc="   生成候选"):
            end = min(start + batch_size, n_users)
            
            # 计算这批用户的分数
            scores = user_factors[start:end] @ item_factors.T
            
            # 获取 Top-K
            for i, user_id in enumerate(range(start, end)):
                user_scores = scores[i]
                
                # 排除已交互的
                interacted = set(interaction_matrix[user_id].indices)
                user_scores_filtered = [(s, score) for s, score in enumerate(user_scores) 
                                       if s not in interacted]
                
                # 排序取 Top-K
                top_k = sorted(user_scores_filtered, key=lambda x: -x[1])[:TOP_K_CANDIDATES]
                candidates[user_id] = [(s, float(score)) for s, score in top_k]
    else:
        # implicit 库版本
        for user_id in tqdm(range(n_users), desc="   生成候选"):
            try:
                ids, scores = model.recommend(
                    user_id, 
                    interaction_matrix[user_id], 
                    N=TOP_K_CANDIDATES,
                    filter_already_liked_items=True
                )
                candidates[user_id] = list(zip(ids.tolist(), scores.tolist()))
            except Exception as e:
                candidates[user_id] = []
    
    print(f"   ✅ 候选集生成完成: {len(candidates):,} 个用户")
    
    return candidates


def save_model(model, candidates):
    """保存模型和候选集"""
    print("\n" + "=" * 60)
    print("💾 保存模型")
    print("=" * 60)
    
    # 保存 ALS 模型
    print(f"   📦 保存 ALS 模型: {ALS_MODEL_PATH}")
    with open(ALS_MODEL_PATH, 'wb') as f:
        pickle.dump(model, f)
    
    # 保存候选集
    print(f"   📦 保存候选集: {CANDIDATES_PATH}")
    with open(CANDIDATES_PATH, 'wb') as f:
        pickle.dump(candidates, f)
    
    print(f"   ✅ 保存完成!")


def main():
    """主函数"""
    print("\n" + "🎵" * 30)
    print("   MusicMode ALS 召回模型训练")
    print("🎵" * 30)
    
    # 1. 加载特征
    features = load_features()
    
    # 2. 构建交互矩阵
    interaction_matrix = build_interaction_matrix(features)
    
    # 3. 训练 ALS
    model = train_als(interaction_matrix)
    
    # 4. 生成候选集
    candidates = generate_candidates(model, interaction_matrix, features)
    
    # 5. 保存
    save_model(model, candidates)
    
    print("\n" + "=" * 60)
    print("✅ ALS 召回模型训练完成!")
    print("=" * 60)
    print(f"\n📁 输出文件:")
    print(f"   - 模型: {ALS_MODEL_PATH}")
    print(f"   - 候选集: {CANDIDATES_PATH}")
    print(f"\n🚀 下一步: 运行 train_lgbm.py 和 train_deepfm_v3.py 训练精排模型")


if __name__ == "__main__":
    main()
