# -*- coding: utf-8 -*-
"""
prepare_features_v3.py — 特征工程 v3（25特征全集）

数据来源：MySQL musicweb 数据库（全量）
输出文件：
  features_v3.pkl   — 训练特征矩阵（LightGBM 和 DeepFM 共用）
  encoders_v3.pkl   — LabelEncoder 字典
  user_stats.pkl    — 用户统计特征（播放数、完播率、流派分布等）
  song_stats.pkl    — 歌曲统计特征（播放数、完播率、popularity等）

25 个特征清单：
  用户侧（9）: user_id, gender, age_bucket, city, user_tenure_bucket,
               user_play_count_log, user_avg_completion,
               user_genre_diversity, user_30d_active_days
  歌曲侧（11）: song_id, genre, language, artist, origin_country,
                year_bucket, duration_bucket,
                song_play_count_log, song_avg_completion,
                song_popularity_norm, song_age_days_log
  上下文（1）: source_channel
  交互（4）: user_genre_match, user_artist_match,
              user_language_match, user_country_match

作者：MusicMode 推荐系统
"""

import os
import sys
import pickle
import warnings
import numpy as np
import pandas as pd
from datetime import date, datetime
from scipy.stats import entropy as scipy_entropy
from sklearn.preprocessing import LabelEncoder
from tqdm import tqdm

warnings.filterwarnings('ignore')

# ============================================================
# 配置
# ============================================================

MYSQL_HOST     = "localhost"
MYSQL_PORT     = "3306"
MYSQL_DB       = "musicweb"
MYSQL_USER     = "root"
MYSQL_PASSWORD = "JF123456"

# 输出目录
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
MODE_DIR    = os.path.join(os.path.dirname(PROJECT_DIR), "Mode")
os.makedirs(MODE_DIR, exist_ok=True)

OUTPUT_FEATURES  = os.path.join(MODE_DIR, "features_v3.pkl")
OUTPUT_ENCODERS  = os.path.join(MODE_DIR, "encoders_v3.pkl")
OUTPUT_USER_STATS= os.path.join(MODE_DIR, "user_stats.pkl")
OUTPUT_SONG_STATS= os.path.join(MODE_DIR, "song_stats.pkl")

# 今天的日期（用于计算 song_age_days 和 user_tenure）
TODAY = date.today()

# source_channel 默认值（训练数据中缺失时）
DEFAULT_SOURCE = "UNKNOWN"


# ============================================================
# 数据库连接
# ============================================================

def get_engine():
    from sqlalchemy import create_engine
    url = (f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}"
           f"@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}?charset=utf8mb4")
    return create_engine(url, pool_pre_ping=True)


# ============================================================
# Step 1: 加载原始数据
# ============================================================

def load_raw_data(engine):
    """从 MySQL 加载全量训练数据"""
    print("\n" + "=" * 62)
    print("📂 [Step 1/5] 从 MySQL 加载数据")
    print("=" * 62)

    # ── 1A. 加载 play_history（含 target 的行才用于训练）
    print("\n  📥 加载 play_history（含 target 标签）...")
    ph_df = pd.read_sql("""
        SELECT
            ph.user_id,
            ph.song_id,
            ph.play_duration,
            ph.play_time,
            ph.target,
            ph.source_channel
        FROM play_history ph
        WHERE ph.target IS NOT NULL
    """, engine)
    print(f"     ✅ play_history 含 target: {len(ph_df):,} 条")

    # ── 1B. 加载 songs 表（全量，用于歌曲侧特征）
    print("\n  📥 加载 songs 表...")
    songs_df = pd.read_sql("""
        SELECT
            id         AS song_id,
            genre,
            language,
            artist,
            origin_country,
            release_year,
            duration,
            popularity
        FROM songs
    """, engine)
    print(f"     ✅ songs: {len(songs_df):,} 首")

    # ── 1C. 加载 users 表（全量，用于用户侧特征）
    print("\n  📥 加载 users 表...")
    users_df = pd.read_sql("""
        SELECT
            id          AS user_id,
            gender,
            bd,
            city,
            create_time
        FROM users
    """, engine)
    print(f"     ✅ users: {len(users_df):,} 个用户")

    return ph_df, songs_df, users_df


# ============================================================
# Step 2: 用户统计特征预计算
# ============================================================

def compute_user_stats(ph_df: pd.DataFrame, songs_df: pd.DataFrame) -> pd.DataFrame:
    """
    预计算用户侧统计特征：
      user_play_count_log    : log1p(总播放次数)
      user_avg_completion    : 平均完播率（0-1）
      user_genre_diversity   : 流派香农熵
      user_30d_active_days   : 近30天活跃天数
      user_genre_dist        : 流派分布 dict（用于交互特征）
      user_artist_dist       : 艺术家分布 dict
      user_language_dist     : 语言分布 dict
      user_country_dist      : 国家分布 dict
    """
    print("\n  ⚙️  预计算用户统计特征...")

    # 合并歌曲信息到 play_history
    ph_songs = ph_df.merge(
        songs_df[["song_id", "genre", "artist", "language", "origin_country", "duration"]],
        on="song_id", how="left"
    )

    # 完播率（play_duration / duration），限制在 [0, 1]
    ph_songs["completion"] = np.where(
        (ph_songs["duration"] > 0) & ph_songs["duration"].notna(),
        np.clip(ph_songs["play_duration"] / ph_songs["duration"], 0, 1),
        np.nan
    )

    # 解析 play_time
    ph_songs["play_time"] = pd.to_datetime(ph_songs["play_time"], errors="coerce")
    cutoff_30d = pd.Timestamp(TODAY) - pd.Timedelta(days=30)

    print("     计算用户基础统计量...")
    # 基础统计
    user_basic = ph_songs.groupby("user_id").agg(
        play_count=("song_id", "count"),
        avg_completion=("completion", "mean"),
        active_30d=("play_time", lambda x: x[x >= cutoff_30d].dt.date.nunique()),
    ).reset_index()
    user_basic["user_play_count_log"]  = np.log1p(user_basic["play_count"])
    user_basic["user_avg_completion"]  = user_basic["avg_completion"].fillna(0).clip(0, 1)
    user_basic["user_30d_active_days"] = user_basic["active_30d"].fillna(0).astype(int)

    # 流派分布和香农熵
    print("     计算用户流派分布和香农熵...")
    user_genre_rows = ph_songs.dropna(subset=["genre"])

    def build_dist(group_df, col):
        """构建某列的归一化分布 dict"""
        counts = group_df[col].value_counts(normalize=True)
        return counts.to_dict()

    user_genre_dist    = {}
    user_artist_dist   = {}
    user_language_dist = {}
    user_country_dist  = {}
    user_genre_entropy = {}

    for uid, grp in tqdm(ph_songs.groupby("user_id"),
                         desc="     用户分布计算", leave=False):
        user_genre_dist[uid]    = build_dist(grp.dropna(subset=["genre"]),    "genre")
        user_artist_dist[uid]   = build_dist(grp.dropna(subset=["artist"]),   "artist")
        user_language_dist[uid] = build_dist(grp.dropna(subset=["language"]), "language")
        user_country_dist[uid]  = build_dist(grp.dropna(subset=["origin_country"]), "origin_country")
        # 香农熵
        genre_counts = grp["genre"].dropna().value_counts(normalize=True).values
        user_genre_entropy[uid] = float(scipy_entropy(genre_counts)) if len(genre_counts) > 1 else 0.0

    user_basic["user_genre_diversity"] = user_basic["user_id"].map(user_genre_entropy).fillna(0)

    # 合并
    stats_dict = {
        "user_basic":        user_basic[["user_id", "user_play_count_log",
                                         "user_avg_completion", "user_30d_active_days",
                                         "user_genre_diversity"]],
        "user_genre_dist":    user_genre_dist,
        "user_artist_dist":   user_artist_dist,
        "user_language_dist": user_language_dist,
        "user_country_dist":  user_country_dist,
    }
    print(f"     ✅ 用户统计特征计算完成（{len(user_genre_dist)} 个用户）")
    return stats_dict


# ============================================================
# Step 3: 歌曲统计特征预计算
# ============================================================

def compute_song_stats(ph_df: pd.DataFrame, songs_df: pd.DataFrame) -> pd.DataFrame:
    """
    预计算歌曲侧统计特征：
      song_play_count_log  : log1p(全局播放次数)
      song_avg_completion  : 全局平均完播率
    """
    print("\n  ⚙️  预计算歌曲统计特征...")

    ph_songs = ph_df.merge(
        songs_df[["song_id", "duration"]],
        on="song_id", how="left"
    )
    ph_songs["completion"] = np.where(
        (ph_songs["duration"] > 0) & ph_songs["duration"].notna(),
        np.clip(ph_songs["play_duration"] / ph_songs["duration"], 0, 1),
        np.nan
    )

    song_stats = ph_songs.groupby("song_id").agg(
        play_count=("user_id", "count"),
        avg_completion=("completion", "mean"),
    ).reset_index()
    song_stats["song_play_count_log"] = np.log1p(song_stats["play_count"])
    song_stats["song_avg_completion"] = song_stats["avg_completion"].fillna(0).clip(0, 1)

    # 归一化 popularity
    max_pop = songs_df["popularity"].max()
    songs_df["song_popularity_norm"] = (songs_df["popularity"].fillna(0) /
                                         max(max_pop, 1)).clip(0, 1)

    # 歌曲年龄（距今天数）
    songs_df["song_age_days"] = songs_df["release_year"].apply(
        lambda y: (TODAY - date(int(y), 1, 1)).days if pd.notna(y) and y > 1900 else None
    )
    songs_df["song_age_days_log"] = np.log1p(songs_df["song_age_days"].fillna(0))

    song_stats = song_stats.merge(
        songs_df[["song_id", "song_popularity_norm", "song_age_days_log"]],
        on="song_id", how="left"
    )
    song_stats["song_popularity_norm"] = song_stats["song_popularity_norm"].fillna(0)
    song_stats["song_age_days_log"]    = song_stats["song_age_days_log"].fillna(0)

    print(f"     ✅ 歌曲统计特征计算完成（{len(song_stats):,} 首）")
    return song_stats


# ============================================================
# Step 4: 分桶函数
# ============================================================

def age_bucket(bd):
    """年龄分5档"""
    try:
        bd = int(bd)
        if bd < 18:  return "under18"
        if bd < 26:  return "18_25"
        if bd < 36:  return "26_35"
        if bd < 51:  return "36_50"
        return "50plus"
    except Exception:
        return "unknown"


def tenure_bucket(create_time):
    """账户成熟度分4档（相对于今天）"""
    try:
        if pd.isna(create_time):
            return "unknown"
        ct = pd.Timestamp(create_time)
        days = (pd.Timestamp(TODAY) - ct).days
        if days < 0:   days = 0
        if days < 30:  return "new"
        if days < 180: return "growing"
        if days < 365: return "active"
        return "loyal"
    except Exception:
        return "unknown"


def year_bucket(release_year):
    """年代分6档"""
    try:
        y = int(release_year)
        if y < 1980: return "pre1980"
        if y < 1990: return "1980s"
        if y < 2000: return "1990s"
        if y < 2010: return "2000s"
        if y < 2020: return "2010s"
        return "2020s"
    except Exception:
        return "unknown"


def duration_bucket(duration_sec):
    """时长分4档（秒）"""
    try:
        d = int(duration_sec)
        if d < 90:  return "short"
        if d < 240: return "medium"
        if d < 420: return "long"
        return "very_long"
    except Exception:
        return "unknown"


# ============================================================
# Step 5: 组装 25 特征矩阵
# ============================================================

def build_feature_matrix(ph_df, songs_df, users_df, user_stats_dict, song_stats):
    """
    将全部 25 个特征组装成训练矩阵
    返回：
      df_features   : 全量特征 DataFrame（含 target）
      encoders      : LabelEncoder 字典（用于 DeepFM）
    """
    print("\n" + "=" * 62)
    print("⚙️  [Step 4/5] 组装 25 特征矩阵")
    print("=" * 62)

    # 从 stats_dict 取出各子结构
    user_basic       = user_stats_dict["user_basic"]
    user_genre_dist  = user_stats_dict["user_genre_dist"]
    user_artist_dist = user_stats_dict["user_artist_dist"]
    user_lang_dist   = user_stats_dict["user_language_dist"]
    user_cntry_dist  = user_stats_dict["user_country_dist"]

    # ── 合并 users 特征到 play_history
    print("\n  合并 users 特征...")
    users_feat = users_df.copy()
    users_feat["age_bucket"]    = users_feat["bd"].apply(age_bucket)
    users_feat["tenure_bucket"] = users_feat["create_time"].apply(tenure_bucket)

    df = ph_df.merge(users_feat[["user_id", "gender", "age_bucket",
                                  "city", "tenure_bucket"]], on="user_id", how="left")

    # 合并用户统计特征
    df = df.merge(user_basic, on="user_id", how="left")
    df["user_play_count_log"]  = df["user_play_count_log"].fillna(0)
    df["user_avg_completion"]  = df["user_avg_completion"].fillna(0)
    df["user_30d_active_days"] = df["user_30d_active_days"].fillna(0)
    df["user_genre_diversity"] = df["user_genre_diversity"].fillna(0)

    # ── 合并 songs 特征
    print("  合并 songs 特征...")
    songs_feat = songs_df.copy()
    songs_feat["year_bucket"]     = songs_feat["release_year"].apply(year_bucket)
    songs_feat["duration_bucket"] = songs_feat["duration"].apply(duration_bucket)

    df = df.merge(
        songs_feat[["song_id", "genre", "language", "artist",
                    "origin_country", "year_bucket", "duration_bucket"]],
        on="song_id", how="left"
    )

    # 合并歌曲统计特征
    df = df.merge(
        song_stats[["song_id", "song_play_count_log",
                    "song_avg_completion", "song_popularity_norm",
                    "song_age_days_log"]],
        on="song_id", how="left"
    )
    for col in ["song_play_count_log", "song_avg_completion",
                "song_popularity_norm", "song_age_days_log"]:
        df[col] = df[col].fillna(0)

    # ── source_channel
    df["source_channel"] = df["source_channel"].fillna(DEFAULT_SOURCE)

    # ── 填充稀疏特征缺失值
    for col in ["gender", "age_bucket", "city", "tenure_bucket",
                "genre", "language", "artist", "origin_country",
                "year_bucket", "duration_bucket"]:
        df[col] = df[col].fillna("unknown").astype(str)

    # ── 交互特征（用户-歌曲匹配度）
    print("  计算交互特征（user_genre/artist/language/country_match）...")
    def match_score(uid, song_val, dist_dict):
        dist = dist_dict.get(uid, {})
        return float(dist.get(str(song_val), 0.0)) if song_val and str(song_val) != "nan" else 0.0

    tqdm.pandas(desc="  user_genre_match")
    df["user_genre_match"] = df.progress_apply(
        lambda r: match_score(r["user_id"], r["genre"], user_genre_dist), axis=1)
    tqdm.pandas(desc="  user_artist_match")
    df["user_artist_match"] = df.progress_apply(
        lambda r: match_score(r["user_id"], r["artist"], user_artist_dist), axis=1)
    tqdm.pandas(desc="  user_language_match")
    df["user_language_match"] = df.progress_apply(
        lambda r: match_score(r["user_id"], r["language"], user_lang_dist), axis=1)
    tqdm.pandas(desc="  user_country_match")
    df["user_country_match"] = df.progress_apply(
        lambda r: match_score(r["user_id"], r["origin_country"], user_cntry_dist), axis=1)

    print(f"\n  ✅ 特征矩阵组装完成: {len(df):,} 行 × {len(df.columns)} 列")
    return df


# ============================================================
# Step 5: LabelEncoder 编码
# ============================================================

def encode_features(df: pd.DataFrame):
    """
    对所有稀疏（分类）特征进行 LabelEncoder 编码。
    返回：
      df          : 新增 *_encoded 列的 DataFrame
      encoders    : {feature_name: LabelEncoder} 字典
    """
    print("\n" + "=" * 62)
    print("🏷️  [Step 5/5] LabelEncoder 编码")
    print("=" * 62)

    # 需要编码的分类特征
    SPARSE_FEATURES = [
        "user_id", "song_id",
        "gender", "age_bucket", "city", "tenure_bucket",
        "genre", "language", "artist", "origin_country",
        "year_bucket", "duration_bucket", "source_channel",
    ]

    encoders = {}
    for feat in SPARSE_FEATURES:
        if feat not in df.columns:
            print(f"   ⚠️  特征 {feat} 不在 df 中，跳过")
            continue
        le = LabelEncoder()
        df[f"{feat}_encoded"] = le.fit_transform(df[feat].astype(str))
        encoders[feat] = le
        print(f"   ✅ {feat}: {df[feat].nunique():,} 个类别")

    return df, encoders


# ============================================================
# 保存函数
# ============================================================

def save_outputs(df, encoders, user_stats_dict, song_stats):
    """保存特征矩阵、编码器和统计字典"""
    print("\n" + "=" * 62)
    print("💾 保存输出文件")
    print("=" * 62)

    # ── features_v3.pkl
    DENSE_FEATURES = [
        "user_play_count_log", "user_avg_completion",
        "user_genre_diversity", "user_30d_active_days",
        "song_play_count_log", "song_avg_completion",
        "song_popularity_norm", "song_age_days_log",
        "user_genre_match", "user_artist_match",
        "user_language_match", "user_country_match",
    ]
    SPARSE_ENCODED = [
        "user_id_encoded", "song_id_encoded",
        "gender_encoded", "age_bucket_encoded", "city_encoded",
        "tenure_bucket_encoded", "genre_encoded", "language_encoded",
        "artist_encoded", "origin_country_encoded",
        "year_bucket_encoded", "duration_bucket_encoded",
        "source_channel_encoded",
    ]

    feature_data = {
        "target": df["target"].values.astype(np.int8),
        # 稀疏特征（encoded）
        **{col: df[col].values for col in SPARSE_ENCODED if col in df.columns},
        # 稠密特征（float32）
        **{col: df[col].values.astype(np.float32) for col in DENSE_FEATURES},
        # 基数统计（用于 DeepFM Embedding 层初始化）
        "n_users":        int(df["user_id_encoded"].max() + 1),
        "n_songs":        int(df["song_id_encoded"].max() + 1),
        "n_genders":      int(df["gender_encoded"].max() + 1),
        "n_age_buckets":  int(df["age_bucket_encoded"].max() + 1),
        "n_cities":       int(df["city_encoded"].max() + 1),
        "n_tenures":      int(df["tenure_bucket_encoded"].max() + 1),
        "n_genres":       int(df["genre_encoded"].max() + 1),
        "n_languages":    int(df["language_encoded"].max() + 1),
        "n_artists":      int(df["artist_encoded"].max() + 1),
        "n_countries":    int(df["origin_country_encoded"].max() + 1),
        "n_year_buckets": int(df["year_bucket_encoded"].max() + 1),
        "n_dur_buckets":  int(df["duration_bucket_encoded"].max() + 1),
        "n_sources":      int(df["source_channel_encoded"].max() + 1),
    }

    print(f"\n  保存 features_v3.pkl ...")
    with open(OUTPUT_FEATURES, "wb") as f:
        pickle.dump(feature_data, f, protocol=4)
    size_mb = os.path.getsize(OUTPUT_FEATURES) / 1024 / 1024
    print(f"   ✅ {OUTPUT_FEATURES}  ({size_mb:.1f} MB)")

    # ── encoders_v3.pkl
    print(f"\n  保存 encoders_v3.pkl ...")
    with open(OUTPUT_ENCODERS, "wb") as f:
        pickle.dump(encoders, f, protocol=4)
    print(f"   ✅ {OUTPUT_ENCODERS}")

    # ── user_stats.pkl
    print(f"\n  保存 user_stats.pkl ...")
    with open(OUTPUT_USER_STATS, "wb") as f:
        pickle.dump(user_stats_dict, f, protocol=4)
    print(f"   ✅ {OUTPUT_USER_STATS}")

    # ── song_stats.pkl
    print(f"\n  保存 song_stats.pkl ...")
    with open(OUTPUT_SONG_STATS, "wb") as f:
        pickle.dump(song_stats, f, protocol=4)
    print(f"   ✅ {OUTPUT_SONG_STATS}")

    # 打印维度统计
    print(f"\n📊 特征维度统计:")
    print(f"   训练样本数: {len(df):,}")
    print(f"   稀疏特征数: {len(SPARSE_ENCODED)}")
    print(f"   稠密特征数: {len(DENSE_FEATURES)}")
    print(f"   总特征数: {len(SPARSE_ENCODED) + len(DENSE_FEATURES)}")
    print(f"   用户数: {feature_data['n_users']:,}")
    print(f"   歌曲数: {feature_data['n_songs']:,}")
    print(f"   正样本率: {df['target'].mean():.3f}")


# ============================================================
# 主函数
# ============================================================

def main():
    print("\n" + "🎵" * 31)
    print("   MusicMode 特征工程 v3.0")
    print("   全量 MySQL 数据 + 25 特征体系")
    print("🎵" * 31)
    print(f"\n  今天: {TODAY}")

    engine = get_engine()

    # Step 1: 加载原始数据
    ph_df, songs_df, users_df = load_raw_data(engine)
    engine.dispose()

    if len(ph_df) == 0:
        print("\n❌ play_history 中无含 target 的记录！")
        print("   请先运行: python enrich_db.py --step play_history")
        return

    # Step 2: 用户统计特征
    print("\n" + "=" * 62)
    print("⚙️  [Step 2/5] 预计算用户统计特征")
    print("=" * 62)
    user_stats_dict = compute_user_stats(ph_df, songs_df)

    # Step 3: 歌曲统计特征
    print("\n" + "=" * 62)
    print("⚙️  [Step 3/5] 预计算歌曲统计特征")
    print("=" * 62)
    song_stats = compute_song_stats(ph_df, songs_df)

    # Step 4: 组装 25 特征矩阵
    df = build_feature_matrix(ph_df, songs_df, users_df, user_stats_dict, song_stats)

    # Step 5: LabelEncoder 编码
    df, encoders = encode_features(df)

    # 保存
    save_outputs(df, encoders, user_stats_dict, song_stats)

    print("\n" + "=" * 62)
    print("✅ 特征工程 v3.0 完成！")
    print("=" * 62)
    print(f"\n📁 输出文件:")
    print(f"   {OUTPUT_FEATURES}")
    print(f"   {OUTPUT_ENCODERS}")
    print(f"   {OUTPUT_USER_STATS}")
    print(f"   {OUTPUT_SONG_STATS}")
    print(f"\n🚀 下一步: python train_lgbm.py && python train_deepfm_v3.py")


if __name__ == "__main__":
    main()
