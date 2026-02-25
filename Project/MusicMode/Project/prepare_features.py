# -*- coding: utf-8 -*-
"""
特征工程脚本 - 准备 ALS 和 DeepFM 训练数据
功能：
1. 加载 KKBOX train.csv 和 songs.csv
2. 加载 MySQL play_history 增量数据
3. 特征处理：LabelEncoder 编码
4. 输出：训练数据集

作者：MusicMode 推荐系统
"""

import os
import sys
import pandas as pd
import numpy as np
from sklearn.preprocessing import LabelEncoder
from tqdm import tqdm
import pickle
import warnings
warnings.filterwarnings('ignore')

# ============================================
# 配置
# ============================================

# 数据路径
DATA_DIR = r"E:\Graduation-project-design\Data"
TRAIN_CSV = os.path.join(DATA_DIR, "train.csv")
SONGS_CSV = os.path.join(DATA_DIR, "songs.csv")
MEMBERS_CSV = os.path.join(DATA_DIR, "members.csv")

# 输出路径
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
MODE_DIR = os.path.join(os.path.dirname(PROJECT_DIR), "Mode")
FEATURE_OUTPUT = os.path.join(MODE_DIR, "features.pkl")
ENCODER_OUTPUT = os.path.join(MODE_DIR, "encoders.pkl")

# 清洗后数据路径（优先使用）
CLEANED_TRAIN_PATH = os.path.join(MODE_DIR, "cleaned_train.pkl")
CLEANED_SONGS_PATH = os.path.join(MODE_DIR, "cleaned_songs.pkl")

# MySQL 配置
MYSQL_HOST = "localhost"
MYSQL_PORT = "3306"
MYSQL_DB = "musicweb"
MYSQL_USER = "root"
MYSQL_PASSWORD = "JF123456"

# 采样配置（内存优化，仅在使用原始数据时生效）
SAMPLE_RATE = 1.0  # 使用全量数据训练（提升模型精度和 Embedding 覆盖量）
RANDOM_SEED = 42


def load_kkbox_data():
    """加载 KKBOX 数据集（优先使用清洗后的数据）"""
    print("\n" + "=" * 60)
    print("📂 [Step 1/4] 加载数据集")
    print("=" * 60)
    
    # 检查是否存在清洗后的数据
    if os.path.exists(CLEANED_TRAIN_PATH) and os.path.exists(CLEANED_SONGS_PATH):
        print("\n✅ 检测到清洗后的数据，优先使用...")
        
        print(f"\n📥 加载 cleaned_train.pkl...")
        train_df = pd.read_pickle(CLEANED_TRAIN_PATH)
        print(f"   ✅ 训练数据: {len(train_df):,} 条记录 (已清洗)")
        
        print(f"\n📥 加载 cleaned_songs.pkl...")
        songs_df = pd.read_pickle(CLEANED_SONGS_PATH)
        print(f"   ✅ 歌曲数据: {len(songs_df):,} 首歌曲 (已清洗)")
        
        return train_df, songs_df, None
    
    # 使用原始数据
    print("\n📌 使用原始数据（建议先运行 data_cleaning.py）...")
    
    # 加载训练数据
    print(f"\n📥 正在加载 train.csv...")
    train_df = pd.read_csv(TRAIN_CSV, dtype={'msno': str, 'song_id': str})
    print(f"   ✅ 训练数据: {len(train_df):,} 条记录")
    
    # 采样以节省内存
    if SAMPLE_RATE < 1.0:
        sample_size = int(len(train_df) * SAMPLE_RATE)
        train_df = train_df.sample(n=sample_size, random_state=RANDOM_SEED)
        print(f"   📊 采样后: {len(train_df):,} 条记录 (采样率 {SAMPLE_RATE*100:.0f}%)")
    
    # 加载歌曲数据
    print(f"\n📥 正在加载 songs.csv...")
    songs_df = pd.read_csv(SONGS_CSV, dtype={'song_id': str, 'genre_ids': str, 'language': str})
    print(f"   ✅ 歌曲数据: {len(songs_df):,} 首歌曲")
    
    # 加载用户数据（如果存在）
    members_df = None
    if os.path.exists(MEMBERS_CSV):
        print(f"\n📥 正在加载 members.csv...")
        members_df = pd.read_csv(MEMBERS_CSV, dtype={'msno': str})
        print(f"   ✅ 用户数据: {len(members_df):,} 个用户")
    
    return train_df, songs_df, members_df


def load_mysql_data():
    """加载 MySQL 增量数据"""
    print("\n" + "=" * 60)
    print("🗄️ [Step 2/4] 加载 MySQL 增量数据")
    print("=" * 60)
    
    try:
        from sqlalchemy import create_engine
        
        db_url = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}?charset=utf8mb4"
        engine = create_engine(db_url)
        
        # 查询播放历史
        query = """
        SELECT 
            user_id,
            song_id,
            play_duration,
            1 as target
        FROM play_history
        """
        
        play_history = pd.read_sql(query, engine)
        print(f"   ✅ MySQL 播放历史: {len(play_history):,} 条记录")
        
        return play_history
        
    except Exception as e:
        print(f"   ⚠️ MySQL 连接失败: {e}")
        print(f"   📌 将仅使用 KKBOX 数据进行训练")
        return None


def process_features(train_df, songs_df, members_df=None, mysql_data=None):
    """特征处理"""
    print("\n" + "=" * 60)
    print("⚙️ [Step 3/4] 特征工程")
    print("=" * 60)
    
    # 合并歌曲信息
    print("\n🔗 合并歌曲特征...")
    df = train_df.merge(songs_df[['song_id', 'genre_ids', 'language', 'artist_name']], 
                        on='song_id', how='left')
    
    # 填充缺失值
    df['genre_ids'] = df['genre_ids'].fillna('unknown')
    df['language'] = df['language'].fillna('unknown')
    df['artist_name'] = df['artist_name'].fillna('unknown')
    
    # 提取主流派（取第一个）
    df['main_genre'] = df['genre_ids'].apply(lambda x: str(x).split('|')[0] if pd.notna(x) else 'unknown')
    
    print(f"   ✅ 合并后数据: {len(df):,} 条记录")
    
    # LabelEncoder 编码
    print("\n🏷️ LabelEncoder 编码...")
    encoders = {}
    
    # 用户编码
    print("   - 编码 user_id (msno)...")
    encoders['user'] = LabelEncoder()
    df['user_encoded'] = encoders['user'].fit_transform(df['msno'].astype(str))
    
    # 歌曲编码
    print("   - 编码 song_id...")
    encoders['song'] = LabelEncoder()
    df['song_encoded'] = encoders['song'].fit_transform(df['song_id'].astype(str))
    
    # 流派编码
    print("   - 编码 genre...")
    encoders['genre'] = LabelEncoder()
    df['genre_encoded'] = encoders['genre'].fit_transform(df['main_genre'].astype(str))
    
    # 语言编码
    print("   - 编码 language...")
    encoders['language'] = LabelEncoder()
    df['language_encoded'] = encoders['language'].fit_transform(df['language'].astype(str))
    
    # 艺术家编码
    print("   - 编码 artist...")
    encoders['artist'] = LabelEncoder()
    df['artist_encoded'] = encoders['artist'].fit_transform(df['artist_name'].astype(str))
    
    print(f"\n📊 特征维度统计:")
    print(f"   - 用户数: {df['user_encoded'].nunique():,}")
    print(f"   - 歌曲数: {df['song_encoded'].nunique():,}")
    print(f"   - 流派数: {df['genre_encoded'].nunique():,}")
    print(f"   - 语言数: {df['language_encoded'].nunique():,}")
    print(f"   - 艺术家数: {df['artist_encoded'].nunique():,}")
    
    return df, encoders


def save_features(df, encoders):
    """保存特征数据"""
    print("\n" + "=" * 60)
    print("💾 [Step 4/4] 保存特征数据")
    print("=" * 60)
    
    # 确保目录存在
    os.makedirs(MODE_DIR, exist_ok=True)
    
    # 保存特征数据
    print(f"\n📦 保存特征到: {FEATURE_OUTPUT}")
    feature_data = {
        'user_encoded': df['user_encoded'].values,
        'song_encoded': df['song_encoded'].values,
        'genre_encoded': df['genre_encoded'].values,
        'language_encoded': df['language_encoded'].values,
        'artist_encoded': df['artist_encoded'].values,
        'target': df['target'].values,
        'n_users': df['user_encoded'].nunique(),
        'n_songs': df['song_encoded'].nunique(),
        'n_genres': df['genre_encoded'].nunique(),
        'n_languages': df['language_encoded'].nunique(),
        'n_artists': df['artist_encoded'].nunique(),
    }
    
    with open(FEATURE_OUTPUT, 'wb') as f:
        pickle.dump(feature_data, f)
    print(f"   ✅ 特征数据已保存")
    
    # 保存编码器
    print(f"\n📦 保存编码器到: {ENCODER_OUTPUT}")
    with open(ENCODER_OUTPUT, 'wb') as f:
        pickle.dump(encoders, f)
    print(f"   ✅ 编码器已保存")
    
    return FEATURE_OUTPUT, ENCODER_OUTPUT


def main():
    """主函数"""
    print("\n" + "🎵" * 30)
    print("   MusicMode 特征工程")
    print("🎵" * 30)
    
    # 1. 加载 KKBOX 数据
    train_df, songs_df, members_df = load_kkbox_data()
    
    # 2. 加载 MySQL 增量数据
    mysql_data = load_mysql_data()
    
    # 3. 特征处理
    df, encoders = process_features(train_df, songs_df, members_df, mysql_data)
    
    # 4. 保存
    feature_path, encoder_path = save_features(df, encoders)
    
    print("\n" + "=" * 60)
    print("✅ 特征工程完成!")
    print("=" * 60)
    print(f"\n📁 输出文件:")
    print(f"   - 特征: {feature_path}")
    print(f"   - 编码器: {encoder_path}")
    print(f"\n🚀 下一步: 运行 train_als.py 训练召回模型")


if __name__ == "__main__":
    main()
