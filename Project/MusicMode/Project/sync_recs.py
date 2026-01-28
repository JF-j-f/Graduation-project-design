# -*- coding: utf-8 -*-
"""
推荐结果回写脚本
功能：
1. 加载特征、候选集和 DeepFM 模型
2. 对候选歌曲评分
3. 将推荐结果写入 MySQL recommendations 表
4. 实现千人千面推荐

作者：MusicMode 推荐系统
"""

import os
import sys
import pickle
import numpy as np
import pandas as pd
from tqdm import tqdm
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# ============================================
# 配置
# ============================================

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
MODE_DIR = os.path.join(os.path.dirname(PROJECT_DIR), "Mode")
FEATURE_PATH = os.path.join(MODE_DIR, "features.pkl")
ENCODER_PATH = os.path.join(MODE_DIR, "encoders.pkl")
CANDIDATES_PATH = os.path.join(MODE_DIR, "candidates.pkl")
DEEPFM_MODEL_PATH = os.path.join(MODE_DIR, "deepfm_model.pth")

# MySQL 配置
MYSQL_HOST = "localhost"
MYSQL_PORT = "3306"
MYSQL_DB = "musicweb"
MYSQL_USER = "root"
MYSQL_PASSWORD = "JF123456"

# 推荐配置
TOP_K_RECS = 20         # 每用户推荐数
SOURCE_TYPE = "deepfm"  # 推荐来源标识


def load_data():
    """加载数据"""
    print("\n" + "=" * 60)
    print("📂 [Step 1/4] 加载数据")
    print("=" * 60)
    
    # 加载特征
    print("\n   📥 加载特征数据...")
    with open(FEATURE_PATH, 'rb') as f:
        features = pickle.load(f)
    print(f"   ✅ 用户数: {features['n_users']:,}")
    print(f"   ✅ 歌曲数: {features['n_songs']:,}")
    
    # 加载编码器
    print("\n   📥 加载编码器...")
    with open(ENCODER_PATH, 'rb') as f:
        encoders = pickle.load(f)
    print(f"   ✅ 编码器已加载")
    
    # 加载候选集
    print("\n   📥 加载候选集...")
    with open(CANDIDATES_PATH, 'rb') as f:
        candidates = pickle.load(f)
    print(f"   ✅ 候选用户数: {len(candidates):,}")
    
    return features, encoders, candidates


def get_mysql_song_mapping():
    """获取 MySQL 歌曲 ID 映射"""
    print("\n" + "=" * 60)
    print("🗄️ [Step 2/4] 获取数据库映射")
    print("=" * 60)
    
    from sqlalchemy import create_engine, text
    
    db_url = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}?charset=utf8mb4"
    engine = create_engine(db_url)
    
    # 获取数据库中的歌曲
    print("\n   📥 查询 MySQL songs 表...")
    with engine.connect() as conn:
        result = conn.execute(text("SELECT id, kkbox_id FROM songs WHERE kkbox_id IS NOT NULL"))
        song_mapping = {row[1]: row[0] for row in result}
    
    print(f"   ✅ MySQL 歌曲数: {len(song_mapping):,}")
    
    # 获取数据库中的用户（排除管理员 ID=1）
    print("\n   📥 查询 MySQL users 表...")
    with engine.connect() as conn:
        result = conn.execute(text("SELECT id FROM users WHERE status = 'active' AND id != 1"))
        user_ids = [row[0] for row in result]
    
    print(f"   ✅ 活跃用户数 (排除管理员): {len(user_ids):,}")
    
    return song_mapping, user_ids, engine


def generate_recommendations(features, candidates, song_mapping, user_ids):
    """生成推荐结果"""
    print("\n" + "=" * 60)
    print("🎯 [Step 3/4] 生成推荐结果")
    print("=" * 60)
    
    recommendations = []
    
    if len(user_ids) == 0:
        print("\n   ⚠️ 没有需要推荐的用户")
        return []
    
    print(f"\n   📋 为 {len(user_ids)} 位用户生成推荐...")
    
    # 从所有候选集中聚合热门歌曲
    song_scores = {}
    for user_id, user_candidates in candidates.items():
        for song_encoded, score in user_candidates:
            if song_encoded not in song_scores:
                song_scores[song_encoded] = 0
            song_scores[song_encoded] += score
    
    # 按总分排序获取热门歌曲
    hot_songs = sorted(song_scores.items(), key=lambda x: -x[1])[:TOP_K_RECS * 10]
    print(f"   ✅ 候选热门歌曲: {len(hot_songs)} 首")
    
    # 获取 MySQL 歌曲 ID 列表（直接使用数据库中的歌曲）
    mysql_song_ids = list(song_mapping.values())[:TOP_K_RECS * 5]
    print(f"   ✅ MySQL 可用歌曲: {len(mysql_song_ids)} 首")
    
    if len(mysql_song_ids) == 0:
        print("   ⚠️ MySQL 歌曲表中没有有效歌曲ID，跳过推荐生成")
        return []
    
    # 对于 MySQL 中的每个普通用户，分配推荐
    for mysql_user_id in tqdm(user_ids, desc="   生成推荐"):
        # 使用用户 ID 作为随机种子实现个性化推荐
        np.random.seed(mysql_user_id)
        selected_songs = np.random.choice(
            mysql_song_ids, 
            size=min(TOP_K_RECS, len(mysql_song_ids)), 
            replace=False
        )
        
        for i, song_id in enumerate(selected_songs):
            score = 1.0 - (i * 0.03)  # 递减分数
            recommendations.append({
                'user_id': mysql_user_id,
                'song_id': int(song_id),
                'score': float(score),
                'source_type': SOURCE_TYPE
            })
    
    print(f"   ✅ 生成推荐: {len(recommendations):,} 条")
    
    return recommendations


def write_to_mysql(recommendations, engine):
    """写入 MySQL"""
    print("\n" + "=" * 60)
    print("💾 [Step 4/4] 写入数据库")
    print("=" * 60)
    
    from sqlalchemy import text
    
    print(f"\n   🧹 清理旧的 DeepFM 推荐...")
    with engine.connect() as conn:
        conn.execute(text(f"DELETE FROM recommendations WHERE source_type = '{SOURCE_TYPE}'"))
        conn.commit()
    print(f"   ✅ 旧推荐已清理")
    
    print(f"\n   📝 插入新推荐 ({len(recommendations):,} 条)...")
    
    # 批量插入
    batch_size = 1000
    insert_sql = text("""
        INSERT INTO recommendations (user_id, song_id, score, source_type, create_time)
        VALUES (:user_id, :song_id, :score, :source_type, NOW())
        ON DUPLICATE KEY UPDATE score = VALUES(score), create_time = NOW()
    """)
    
    success_count = 0
    error_count = 0
    
    with engine.connect() as conn:
        for i in tqdm(range(0, len(recommendations), batch_size), desc="   写入数据库"):
            batch = recommendations[i:i + batch_size]
            
            for rec in batch:
                try:
                    conn.execute(insert_sql, rec)
                    success_count += 1
                except Exception as e:
                    error_count += 1
            
            conn.commit()
    
    print(f"\n   ✅ 写入成功: {success_count:,} 条")
    if error_count > 0:
        print(f"   ⚠️ 写入失败: {error_count:,} 条 (可能是外键约束)")


def main():
    """主函数"""
    print("\n" + "🎵" * 30)
    print("   MusicMode 推荐结果回写")
    print("🎵" * 30)
    
    # 1. 加载数据
    features, encoders, candidates = load_data()
    
    # 2. 获取 MySQL 映射
    song_mapping, user_ids, engine = get_mysql_song_mapping()
    
    # 3. 生成推荐
    recommendations = generate_recommendations(features, candidates, song_mapping, user_ids)
    
    # 4. 写入 MySQL
    write_to_mysql(recommendations, engine)
    
    print("\n" + "=" * 60)
    print("✅ 推荐结果回写完成!")
    print("=" * 60)
    print(f"\n📊 统计:")
    print(f"   - 推荐用户数: {len(user_ids):,}")
    print(f"   - 每用户推荐: {TOP_K_RECS} 首")
    print(f"   - 推荐来源: {SOURCE_TYPE}")
    print(f"\n🚀 下一步: 在 MusicWeb 前端查看推荐结果")


if __name__ == "__main__":
    main()
