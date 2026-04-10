# -*- coding: utf-8 -*-
"""
数据清洗脚本
功能：
1. 处理缺失值
2. 处理异常值
3. 样本平衡（采样策略）
4. 保存清洗后的数据

作者：MusicMode 推荐系统
目标：提升模型精度至 AUC > 0.8
"""

import os
import sys
import pandas as pd
import numpy as np
from tqdm import tqdm
import pickle
import warnings
warnings.filterwarnings('ignore')

# ============================================
# 配置
# ============================================

# 数据路径
DATA_DIR = r"F:\Graduation-project-design\Data"
TRAIN_CSV = os.path.join(DATA_DIR, "train.csv")
SONGS_CSV = os.path.join(DATA_DIR, "songs.csv")
MEMBERS_CSV = os.path.join(DATA_DIR, "members.csv")

# 输出路径
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
MODE_DIR = os.path.join(os.path.dirname(PROJECT_DIR), "Mode")
CLEANED_TRAIN_PATH = os.path.join(MODE_DIR, "cleaned_train.pkl")
CLEANED_SONGS_PATH = os.path.join(MODE_DIR, "cleaned_songs.pkl")

# 清洗配置
RANDOM_SEED = 42
NEGATIVE_SAMPLE_RATIO = 3  # 正:负 = 1:3
MIN_USER_INTERACTIONS = 3   # 最少交互次数
MIN_SONG_INTERACTIONS = 1   # 最少被听次数（保留全部歌曲以最大化 Embedding 覆盖）


def load_data():
    """加载原始数据"""
    print("\n" + "=" * 60)
    print("📂 [Step 1/5] 加载原始数据")
    print("=" * 60)
    
    print(f"\n📥 加载 train.csv...")
    train_df = pd.read_csv(TRAIN_CSV, dtype={'msno': str, 'song_id': str})
    print(f"   ✅ 原始训练数据: {len(train_df):,} 条")
    
    print(f"\n📥 加载 songs.csv...")
    songs_df = pd.read_csv(SONGS_CSV, dtype={'song_id': str, 'genre_ids': str, 'language': str})
    print(f"   ✅ 歌曲数据: {len(songs_df):,} 首")
    
    return train_df, songs_df


def clean_missing_values(train_df, songs_df):
    """处理缺失值"""
    print("\n" + "=" * 60)
    print("🔧 [Step 2/5] 处理缺失值")
    print("=" * 60)
    
    # 歌曲表缺失值处理
    print("\n📋 songs.csv 缺失值处理:")
    
    # 填充策略
    fill_values = {
        'artist_name': 'unknown',
        'composer': 'unknown',
        'lyricist': 'unknown',
        'genre_ids': 'unknown',
        'language': '-1',  # 未知语言
        'song_length': songs_df['song_length'].median() if 'song_length' in songs_df.columns else 0
    }
    
    for col, fill_value in fill_values.items():
        if col in songs_df.columns:
            before = songs_df[col].isna().sum()
            songs_df[col] = songs_df[col].fillna(fill_value)
            after = songs_df[col].isna().sum()
            print(f"   - {col}: {before:,} -> {after} (填充: {fill_value})")
    
    # 训练数据缺失值（一般较少）
    print(f"\n📋 train.csv 缺失值: {train_df.isna().sum().sum()}")
    train_df = train_df.dropna()  # 直接删除缺失行
    
    return train_df, songs_df


def filter_cold_start(train_df):
    """过滤冷启动数据（低频用户和歌曲）"""
    print("\n" + "=" * 60)
    print("❄️ [Step 3/5] 过滤冷启动数据")
    print("=" * 60)
    
    original_size = len(train_df)
    
    # 过滤低活跃用户
    print(f"\n🔍 过滤低活跃用户 (交互次数 < {MIN_USER_INTERACTIONS})...")
    user_counts = train_df['msno'].value_counts()
    active_users = user_counts[user_counts >= MIN_USER_INTERACTIONS].index
    train_df = train_df[train_df['msno'].isin(active_users)]
    print(f"   - 保留用户: {len(active_users):,}")
    
    # 过滤冷门歌曲
    print(f"\n🔍 过滤冷门歌曲 (被听次数 < {MIN_SONG_INTERACTIONS})...")
    song_counts = train_df['song_id'].value_counts()
    popular_songs = song_counts[song_counts >= MIN_SONG_INTERACTIONS].index
    train_df = train_df[train_df['song_id'].isin(popular_songs)]
    print(f"   - 保留歌曲: {len(popular_songs):,}")
    
    # 统计
    filtered_size = len(train_df)
    print(f"\n📊 过滤结果:")
    print(f"   - 原始: {original_size:,}")
    print(f"   - 过滤后: {filtered_size:,}")
    print(f"   - 保留比例: {filtered_size/original_size*100:.1f}%")
    
    return train_df


def balance_samples(train_df):
    """样本平衡处理"""
    print("\n" + "=" * 60)
    print("⚖️ [Step 4/5] 样本平衡处理")
    print("=" * 60)
    
    # 统计当前分布
    pos_samples = train_df[train_df['target'] == 1]
    neg_samples = train_df[train_df['target'] == 0]
    
    print(f"\n📋 当前分布:")
    print(f"   - 正样本: {len(pos_samples):,}")
    print(f"   - 负样本: {len(neg_samples):,}")
    print(f"   - 比例: 1:{len(neg_samples)/len(pos_samples):.1f}")
    
    # 负采样（降低负样本比例）
    target_neg_count = len(pos_samples) * NEGATIVE_SAMPLE_RATIO
    
    if len(neg_samples) > target_neg_count:
        print(f"\n🎯 执行负采样 (目标比例 1:{NEGATIVE_SAMPLE_RATIO})...")
        np.random.seed(RANDOM_SEED)
        neg_sampled = neg_samples.sample(n=int(target_neg_count), random_state=RANDOM_SEED)
        train_balanced = pd.concat([pos_samples, neg_sampled])
    else:
        print(f"\n✅ 样本已相对平衡，无需采样")
        train_balanced = train_df
    
    # 打乱顺序
    train_balanced = train_balanced.sample(frac=1, random_state=RANDOM_SEED).reset_index(drop=True)
    
    print(f"\n📊 平衡后分布:")
    print(f"   - 正样本: {(train_balanced['target'] == 1).sum():,}")
    print(f"   - 负样本: {(train_balanced['target'] == 0).sum():,}")
    print(f"   - 总计: {len(train_balanced):,}")
    
    return train_balanced


def save_cleaned_data(train_df, songs_df):
    """保存清洗后的数据"""
    print("\n" + "=" * 60)
    print("💾 [Step 5/5] 保存清洗数据")
    print("=" * 60)
    
    os.makedirs(MODE_DIR, exist_ok=True)
    
    # 保存训练数据
    print(f"\n📦 保存训练数据: {CLEANED_TRAIN_PATH}")
    train_df.to_pickle(CLEANED_TRAIN_PATH)
    print(f"   ✅ 保存成功 ({len(train_df):,} 条)")
    
    # 保存歌曲数据
    print(f"\n📦 保存歌曲数据: {CLEANED_SONGS_PATH}")
    songs_df.to_pickle(CLEANED_SONGS_PATH)
    print(f"   ✅ 保存成功 ({len(songs_df):,} 首)")
    
    return CLEANED_TRAIN_PATH, CLEANED_SONGS_PATH


def main():
    """主函数"""
    print("\n" + "🎵" * 30)
    print("   MusicMode 数据清洗")
    print("   目标：提升模型精度")
    print("🎵" * 30)
    
    # 1. 加载数据
    train_df, songs_df = load_data()
    
    # 2. 处理缺失值
    train_df, songs_df = clean_missing_values(train_df, songs_df)
    
    # 3. 过滤冷启动数据
    train_df = filter_cold_start(train_df)
    
    # 4. 样本平衡
    train_df = balance_samples(train_df)
    
    # 5. 保存
    train_path, songs_path = save_cleaned_data(train_df, songs_df)
    
    print("\n" + "=" * 60)
    print("✅ 数据清洗完成!")
    print("=" * 60)
    print(f"\n📁 输出文件:")
    print(f"   - 训练数据: {train_path}")
    print(f"   - 歌曲数据: {songs_path}")
    print(f"\n🚀 下一步: 运行 prepare_features.py 进行特征工程")


if __name__ == "__main__":
    main()
