# -*- coding: utf-8 -*-
"""
prepare_features_v3.py — 特征工程 （62特征全集，含 SVD 嵌入）

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

开发者：JunFun
"""

import os
import sys
import pickle
import warnings
import numpy as np
import pandas as pd
from datetime import date, datetime
from scipy.stats import entropy as scipy_entropy
from scipy.sparse import coo_matrix
from sklearn.preprocessing import LabelEncoder
from sklearn.decomposition import TruncatedSVD
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
OUTPUT_SVD_VECS  = os.path.join(MODE_DIR, "svd_vecs.pkl")   # SVD向量，供在线推断查找

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

    # ── 1D. 加载 playlist_songs（用户主动收藏 = 强正向信号）
    print("\n  📥 加载 playlist_songs（用户歌单数据）...")
    pl_df = pd.read_sql("""
        SELECT up.user_id, ps.song_id
        FROM playlist_songs ps
        JOIN user_playlists up ON ps.playlist_id = up.id
    """, engine)
    print(f"     ✅ playlist_songs: {len(pl_df):,} 条")

    return ph_df, songs_df, users_df, pl_df


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

    # 流派分布和香农熵（向量化，替代 for 循环，速度提升 10-20×）
    print("     计算用户分布（向量化 groupby）...")

    def _build_dist_fast(ph: pd.DataFrame, col: str) -> dict:
        """向量化构建 {uid: {val: prob}} 分布 dict（内存安全，适用高基数列如 artist）"""
        valid  = ph.dropna(subset=[col])
        counts = valid.groupby(["user_id", col]).size()
        totals = counts.groupby(level=0).transform("sum")
        probs  = counts / totals
        # 遍历预聚合后的 probs（行数 = 唯一(user,val)对数，远小于原始 7.37M）
        result: dict = {}
        for (uid, val), prob in probs.items():
            if uid not in result:
                result[uid] = {}
            result[uid][val] = float(prob)
        return result

    user_genre_dist    = _build_dist_fast(ph_songs, "genre")
    user_artist_dist   = _build_dist_fast(ph_songs, "artist")
    user_language_dist = _build_dist_fast(ph_songs, "language")
    user_country_dist  = _build_dist_fast(ph_songs, "origin_country")

    # 香农熵（向量化，复用 genre groupby 计算结果）
    print("     计算流派香农熵（向量化）...")
    _valid_genre      = ph_songs.dropna(subset=["genre"])
    _genre_counts_ser = _valid_genre.groupby(["user_id", "genre"]).size()
    _genre_totals     = _genre_counts_ser.groupby(level=0).transform("sum")
    _genre_probs_ser  = _genre_counts_ser / _genre_totals
    user_genre_entropy = (
        _genre_probs_ser.groupby(level=0)
        .apply(lambda x: float(scipy_entropy(x.values)) if len(x) > 1 else 0.0)
        .to_dict()
    )

    user_basic["user_genre_diversity"] = user_basic["user_id"].map(user_genre_entropy).fillna(0)

    # 用户重复收听率：该用户历史中 target=1 的比例（直接预测目标的先验）
    user_target_rate = ph_df.groupby("user_id")["target"].mean().rename("user_target_rate")
    user_basic = user_basic.merge(user_target_rate, on="user_id", how="left")
    user_basic["user_target_rate"] = user_basic["user_target_rate"].fillna(0.5)

    # ── 新增：时序特征
    print("     计算时序特征（peak_hour / top3_hours / top3_dows）...")
    ph_songs["hour"] = ph_songs["play_time"].dt.hour
    ph_songs["dow"]  = ph_songs["play_time"].dt.dayofweek  # 0=Monday...6=Sunday

    # user_peak_hour（稀疏，0-23）：用户最高频收听时段
    user_peak_hour = (
        ph_songs.dropna(subset=["hour"])
        .groupby("user_id")["hour"]
        .agg(lambda x: int(x.value_counts().index[0]) if len(x) > 0 else 0)
        .rename("user_peak_hour")
        .reset_index()
    )
    user_basic = user_basic.merge(user_peak_hour, on="user_id", how="left")
    user_basic["user_peak_hour"] = user_basic["user_peak_hour"].fillna(0).astype(int)

    # user_top3_hours / user_top3_dows（中间变量，用于 hour_match / dow_match）
    _hour_counts = (
        ph_songs.dropna(subset=["hour"])
        .groupby(["user_id", "hour"]).size()
        .reset_index(name="_cnt")
        .sort_values(["user_id", "_cnt"], ascending=[True, False])
    )
    user_top3_hours = _hour_counts.groupby("user_id")["hour"].apply(
        lambda x: set(x.head(3).tolist())
    ).to_dict()

    _dow_counts = (
        ph_songs.dropna(subset=["dow"])
        .groupby(["user_id", "dow"]).size()
        .reset_index(name="_cnt")
        .sort_values(["user_id", "_cnt"], ascending=[True, False])
    )
    user_top3_dows = _dow_counts.groupby("user_id")["dow"].apply(
        lambda x: set(x.head(3).tolist())
    ).to_dict()

    # ── 新增：跳过率特征
    print("     计算用户跳过率...")
    ph_songs["is_skip"] = (ph_songs["completion"] < 0.10).astype(float)
    user_skip_rate = ph_songs.groupby("user_id")["is_skip"].mean().rename("user_skip_rate").reset_index()
    user_basic = user_basic.merge(user_skip_rate, on="user_id", how="left")
    user_basic["user_skip_rate"] = user_basic["user_skip_rate"].fillna(0.2)

    # 合并
    stats_dict = {
        "user_basic":        user_basic[["user_id", "play_count",
                                         "user_play_count_log",
                                         "user_avg_completion", "user_30d_active_days",
                                         "user_genre_diversity", "user_target_rate",
                                         "user_peak_hour", "user_skip_rate"]],
        "user_genre_dist":    user_genre_dist,
        "user_artist_dist":   user_artist_dist,
        "user_language_dist": user_language_dist,
        "user_country_dist":  user_country_dist,
        "user_top3_hours":    user_top3_hours,
        "user_top3_dows":     user_top3_dows,
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

    # 歌曲重复收听率：被播放后触发重复收听的比例（直接预测目标的先验）
    song_target_rate = ph_df.groupby("song_id")["target"].mean().rename("song_target_rate")
    song_stats = song_stats.merge(song_target_rate, on="song_id", how="left")
    song_stats["song_target_rate"] = song_stats["song_target_rate"].fillna(0.5)

    # ── 新增：歌曲跳过率
    ph_songs["is_skip"] = (ph_songs["completion"] < 0.10).astype(float)
    song_skip_rate = ph_songs.groupby("song_id")["is_skip"].mean().rename("song_skip_rate")
    song_stats = song_stats.merge(song_skip_rate, on="song_id", how="left")
    song_stats["song_skip_rate"] = song_stats["song_skip_rate"].fillna(0.2)

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
    song_stats["song_skip_rate"]       = song_stats["song_skip_rate"].fillna(0.2)

    print(f"     ✅ 歌曲统计特征计算完成（{len(song_stats):,} 首）")
    return song_stats


# ============================================================
# Step 3b: 时序特征（B-3 记忆衰减 + B-4 滚动窗口）
# ============================================================

def compute_temporal_features(ph_df: pd.DataFrame, songs_df: pd.DataFrame) -> pd.DataFrame:
    """
    严格无泄漏时序特征（窗口上界 < 当前行 play_time）。

    B-3 记忆衰减：
      user_song_prev_play_days     : 距上次听同一首歌的天数（-1 = 首次）
      user_song_play_count_before  : 当前播放之前听过该首歌的次数

    B-4 滚动窗口（使用 pandas rolling closed="left" 排除当前行）：
      user_7d_play_count_log       : 近 7 天用户播放总量 log1p
      user_30d_play_count_log      : 近 30 天用户播放总量 log1p
      user_7d_avg_completion       : 近 7 天用户平均完播率
      song_7d_play_count_log       : 近 7 天歌曲播放总量 log1p
      song_30d_play_count_log      : 近 30 天歌曲播放总量 log1p
      song_trending_ratio          : 热度趋势 = (7d_count+1) / (30d_daily_avg+1)

    返回：与 ph_df 等行数等顺序的 DataFrame（通过 _orig_idx 对齐）。
    """
    print("\n  ⚙️  计算时序特征（B-3 记忆衰减 + B-4 滚动窗口）...")

    ph = ph_df[["user_id", "song_id", "play_time", "play_duration"]].copy()
    ph["_orig_idx"] = np.arange(len(ph))
    ph["play_time"] = pd.to_datetime(ph["play_time"], errors="coerce")

    # 合入 duration，用于计算 completion
    ph = ph.merge(songs_df[["song_id", "duration"]], on="song_id", how="left")
    ph["completion_fill"] = np.where(
        (ph["duration"] > 0) & ph["duration"].notna(),
        np.clip(ph["play_duration"] / ph["duration"], 0, 1).astype(np.float32),
        0.0,
    ).astype(np.float32)

    # ── B-3: 记忆衰减
    print("     B-3 记忆衰减特征...")
    ph_us = (
        ph.dropna(subset=["play_time"])
        .sort_values(["user_id", "song_id", "play_time"])
        .reset_index(drop=True)
    )
    ph_us["user_song_play_count_before"] = (
        ph_us.groupby(["user_id", "song_id"]).cumcount()   # 0 for first play
    )
    ph_us["_prev_time"] = ph_us.groupby(["user_id", "song_id"])["play_time"].shift(1)
    ph_us["user_song_prev_play_days"] = (
        (ph_us["play_time"] - ph_us["_prev_time"]).dt.total_seconds() / 86400
    ).fillna(-1.0).astype(np.float32)

    b3 = ph_us[["_orig_idx", "user_song_prev_play_days", "user_song_play_count_before"]]

    # ── B-4: 滚动窗口（closed="left" 严格排除当前行）
    print("     B-4 滚动窗口特征（7d / 30d）...")
    ph_t = (
        ph.dropna(subset=["play_time"])
        .sort_values("play_time")
        .reset_index(drop=True)
    )
    ph_t["_one"] = 1.0
    ph_idx = ph_t.set_index("play_time")

    def _roll(gb_col, agg_col, window):
        return (
            ph_idx.groupby(gb_col)[agg_col]
            .rolling(window, min_periods=0, closed="left")
            .sum()
            .reset_index(level=gb_col, drop=True)
        )

    u7   = _roll("user_id", "_one",           "7D")
    u30  = _roll("user_id", "_one",           "30D")
    u7c  = _roll("user_id", "completion_fill","7D")
    s7   = _roll("song_id", "_one",           "7D")
    s30  = _roll("song_id", "_one",           "30D")

    ph_t["user_7d_play_count_log"]  = np.log1p(u7.values).astype(np.float32)
    ph_t["user_30d_play_count_log"] = np.log1p(u30.values).astype(np.float32)
    ph_t["user_7d_avg_completion"]  = (u7c.values / (u7.values + 1)).astype(np.float32)
    ph_t["song_7d_play_count_log"]  = np.log1p(s7.values).astype(np.float32)
    ph_t["song_30d_play_count_log"] = np.log1p(s30.values).astype(np.float32)
    ph_t["song_trending_ratio"]     = (
        (s7.values + 1) / (s30.values / 30.0 + 1)
    ).astype(np.float32)

    b4 = ph_t[["_orig_idx",
               "user_7d_play_count_log", "user_30d_play_count_log",
               "user_7d_avg_completion",
               "song_7d_play_count_log", "song_30d_play_count_log",
               "song_trending_ratio"]]

    # ── 对齐回原始行顺序
    base = pd.DataFrame({"_orig_idx": np.arange(len(ph_df))})
    result = base.merge(b3, on="_orig_idx", how="left").merge(b4, on="_orig_idx", how="left")

    result["user_song_prev_play_days"]    = result["user_song_prev_play_days"].fillna(-1.0).astype(np.float32)
    result["user_song_play_count_before"] = result["user_song_play_count_before"].fillna(0).astype(np.float32)
    for col in ["user_7d_play_count_log", "user_30d_play_count_log", "user_7d_avg_completion",
                "song_7d_play_count_log", "song_30d_play_count_log", "song_trending_ratio"]:
        result[col] = result[col].fillna(0.0).astype(np.float32)

    print(f"     ✅ 时序特征完成: {len(result):,} 行 × 8 个新特征")
    return result


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

def build_feature_matrix(ph_df, songs_df, users_df, user_stats_dict, song_stats, pl_df):
    """
    将全部 36 个特征组装成训练矩阵
    返回：
      df_features   : 全量特征 DataFrame（含 target）
      encoders      : LabelEncoder 字典（用于 DeepFM）
    """
    print("\n" + "=" * 62)
    print("⚙️  [Step 4/5] 组装 36 特征矩阵")
    print("=" * 62)

    # 从 stats_dict 取出各子结构
    user_basic        = user_stats_dict["user_basic"]
    user_genre_dist   = user_stats_dict["user_genre_dist"]
    user_artist_dist  = user_stats_dict["user_artist_dist"]
    user_lang_dist    = user_stats_dict["user_language_dist"]
    user_cntry_dist   = user_stats_dict["user_country_dist"]
    user_top3_hours   = user_stats_dict["user_top3_hours"]
    user_top3_dows    = user_stats_dict["user_top3_dows"]

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
    df["user_target_rate"]     = df["user_target_rate"].fillna(0.5)
    df["user_peak_hour"]       = df["user_peak_hour"].fillna(0).astype(int)
    df["user_skip_rate"]       = df["user_skip_rate"].fillna(0.2)

    # ── 合并 songs 特征
    print("  合并 songs 特征...")
    songs_feat = songs_df.copy()
    songs_feat["year_bucket"]     = songs_feat["release_year"].apply(year_bucket)
    songs_feat["duration_bucket"] = songs_feat["duration"].apply(duration_bucket)

    df = df.merge(
        songs_feat[["song_id", "genre", "language", "artist",
                    "origin_country", "year_bucket", "duration_bucket", "duration"]],
        on="song_id", how="left"
    )

    # 合并歌曲统计特征
    df = df.merge(
        song_stats[["song_id", "song_play_count_log",
                    "song_avg_completion", "song_popularity_norm",
                    "song_age_days_log", "song_target_rate", "song_skip_rate"]],
        on="song_id", how="left"
    )
    for col in ["song_play_count_log", "song_avg_completion",
                "song_popularity_norm", "song_age_days_log"]:
        df[col] = df[col].fillna(0)
    df["song_target_rate"] = df["song_target_rate"].fillna(0.5)
    df["song_skip_rate"]   = df["song_skip_rate"].fillna(0.2)

    # ── source_channel
    df["source_channel"] = df["source_channel"].fillna(DEFAULT_SOURCE)

    # ── 填充稀疏特征缺失值
    for col in ["gender", "age_bucket", "city", "tenure_bucket",
                "genre", "language", "artist", "origin_country",
                "year_bucket", "duration_bucket"]:
        df[col] = df[col].fillna("unknown").astype(str)
    # user_peak_hour: int → str (LabelEncoder 期望 str 输入)
    df["user_peak_hour"] = df["user_peak_hour"].astype(str)

    # ── 交互特征（用户-歌曲匹配度，向量化 merge，替代 4× row-wise apply）
    print("  计算交互特征（向量化 merge，速度提升 10-15×）...")

    def _match_vectorized(df: pd.DataFrame, col: str, out_col: str) -> np.ndarray:
        """
        向量化计算用户-歌曲 col 维度匹配度：用户历史中该值出现的频率。
        基于 df（play_history + song 特征已 merge），等价于原 match_score 逻辑。
        """
        counts = df.dropna(subset=[col]).groupby(["user_id", col]).size()
        totals = counts.groupby(level=0).transform("sum")
        probs  = (counts / totals).reset_index(name=out_col)
        probs.columns = ["user_id", col, out_col]
        return df[["user_id", col]].merge(probs, on=["user_id", col], how="left")[out_col].fillna(0.0).values

    df["user_genre_match"]    = _match_vectorized(df, "genre",          "user_genre_match")
    df["user_artist_match"]   = _match_vectorized(df, "artist",         "user_artist_match")
    df["user_language_match"] = _match_vectorized(df, "language",       "user_language_match")
    df["user_country_match"]  = _match_vectorized(df, "origin_country", "user_country_match")

    # ── 新增：时序特征（hour_match / dow_match）
    print("  计算时序匹配特征（hour_match / dow_match）...")
    df["play_time"] = pd.to_datetime(df["play_time"], errors="coerce")
    df["_hour"] = df["play_time"].dt.hour
    df["_dow"]  = df["play_time"].dt.dayofweek

    df["hour_match"] = df.apply(
        lambda r: 1.0 if (r["_hour"] in user_top3_hours.get(r["user_id"], set())) else 0.0,
        axis=1
    )
    df["dow_match"] = df.apply(
        lambda r: 1.0 if (r["_dow"] in user_top3_dows.get(r["user_id"], set())) else 0.0,
        axis=1
    )
    df.drop(columns=["_hour", "_dow"], inplace=True)

    # ── 新增：最近交互特征（days_since_last_play_log / days_since_artist_log）
    print("  计算最近交互特征（days_since）...")
    TODAY_TS = pd.Timestamp(TODAY)

    # days_since_last_play: per (user_id, song_id)
    last_play = (
        df.dropna(subset=["play_time"])
        .groupby(["user_id", "song_id"])["play_time"].max()
        .reset_index(name="_last_play")
    )
    last_play["days_since_last_play_log"] = np.log1p(
        (TODAY_TS - last_play["_last_play"]).dt.days.clip(lower=0).fillna(9999)
    )
    df = df.merge(last_play[["user_id", "song_id", "days_since_last_play_log"]],
                  on=["user_id", "song_id"], how="left")
    df["days_since_last_play_log"] = df["days_since_last_play_log"].fillna(np.log1p(9999))

    # days_since_artist: per (user_id, artist)
    last_artist = (
        df.dropna(subset=["play_time"])
        .groupby(["user_id", "artist"])["play_time"].max()
        .reset_index(name="_last_artist")
    )
    last_artist["days_since_artist_log"] = np.log1p(
        (TODAY_TS - last_artist["_last_artist"]).dt.days.clip(lower=0).fillna(9999)
    )
    df = df.merge(last_artist[["user_id", "artist", "days_since_artist_log"]],
                  on=["user_id", "artist"], how="left")
    df["days_since_artist_log"] = df["days_since_artist_log"].fillna(np.log1p(9999))

    # ── 新增：用户-艺术家重复收听率
    print("  计算用户-艺术家重复收听率...")
    global_prior = ph_df["target"].mean()
    ua_repeat = (
        df.groupby(["user_id", "artist"])["target"].mean()
        .reset_index(name="user_artist_repeat_rate")
    )
    df = df.merge(ua_repeat, on=["user_id", "artist"], how="left")
    df["user_artist_repeat_rate"] = df["user_artist_repeat_rate"].fillna(global_prior)

    # ── 新增：歌单亲和力特征
    print("  计算歌单亲和力特征（user_has_in_playlist / user_playlist_artist_count_log）...")
    if len(pl_df) > 0:
        # user_has_in_playlist: 该 (user, song) 是否在用户歌单中
        pl_flag = pl_df[["user_id", "song_id"]].drop_duplicates()
        pl_flag["user_has_in_playlist"] = 1.0
        df = df.merge(pl_flag, on=["user_id", "song_id"], how="left")
        df["user_has_in_playlist"] = df["user_has_in_playlist"].fillna(0.0)

        # user_playlist_artist_count_log: 用户歌单中该艺术家的歌曲数量
        pl_with_artist = pl_df.merge(
            songs_df[["song_id", "artist"]], on="song_id", how="left"
        )
        pl_artist_cnt = (
            pl_with_artist.groupby(["user_id", "artist"]).size()
            .reset_index(name="_pl_art_cnt")
        )
        pl_artist_cnt["user_playlist_artist_count_log"] = np.log1p(pl_artist_cnt["_pl_art_cnt"])
        df = df.merge(
            pl_artist_cnt[["user_id", "artist", "user_playlist_artist_count_log"]],
            on=["user_id", "artist"], how="left"
        )
        df["user_playlist_artist_count_log"] = df["user_playlist_artist_count_log"].fillna(0.0)
    else:
        df["user_has_in_playlist"]           = 0.0
        df["user_playlist_artist_count_log"] = 0.0

    # ── Phase B-3/B-4: 时序特征（记忆衰减 + 滚动窗口）
    print("  计算时序特征（B-3/B-4）...")
    df = df.reset_index(drop=True)
    temporal = compute_temporal_features(ph_df, songs_df)
    df["user_song_prev_play_days"]    = temporal["user_song_prev_play_days"].values
    df["user_song_play_count_before"] = temporal["user_song_play_count_before"].values
    df["user_7d_play_count_log"]      = temporal["user_7d_play_count_log"].values
    df["user_30d_play_count_log"]     = temporal["user_30d_play_count_log"].values
    df["user_7d_avg_completion"]      = temporal["user_7d_avg_completion"].values
    df["song_7d_play_count_log"]      = temporal["song_7d_play_count_log"].values
    df["song_30d_play_count_log"]     = temporal["song_30d_play_count_log"].values
    df["song_trending_ratio"]         = temporal["song_trending_ratio"].values

    # ── SVD 嵌入特征（KKBOX 冠军方案核心技术: TruncatedSVD 矩阵分解）
    print("  计算 SVD 嵌入特征（user-song 10d + song-user 10d + user-artist 5d + dot_score）...")
    _user_codes = df["user_id"].astype("category").cat.codes.values.astype(np.int32)
    _song_codes = df["song_id"].astype("category").cat.codes.values.astype(np.int32)
    _n_u_svd = int(_user_codes.max()) + 1
    _n_s_svd = int(_song_codes.max()) + 1

    # user×song 交互矩阵 → TruncatedSVD(10)
    _us_mat = coo_matrix(
        (np.ones(len(df), dtype=np.float32), (_user_codes, _song_codes)),
        shape=(_n_u_svd, _n_s_svd),
    ).tocsr()
    _svd_us = TruncatedSVD(n_components=10, random_state=42)
    _user_vecs_us = _svd_us.fit_transform(_us_mat)    # (n_users, 10)
    _song_vecs_us = _svd_us.components_.T              # (n_songs, 10)

    for i in range(10):
        df[f"svd_user_song_{i}"] = _user_vecs_us[_user_codes, i].astype(np.float32)
        df[f"svd_song_user_{i}"] = _song_vecs_us[_song_codes, i].astype(np.float32)

    # user×artist 交互矩阵 → TruncatedSVD(5)
    _artist_codes = df["artist"].astype("category").cat.codes.values.astype(np.int32)
    _n_a_svd = int(_artist_codes.max()) + 1
    _ua_mat = coo_matrix(
        (np.ones(len(df), dtype=np.float32), (_user_codes, _artist_codes)),
        shape=(_n_u_svd, _n_a_svd),
    ).tocsr()
    _svd_ua = TruncatedSVD(n_components=5, random_state=42)
    _user_vecs_ua = _svd_ua.fit_transform(_ua_mat)    # (n_users, 5)

    for i in range(5):
        df[f"svd_user_artist_{i}"] = _user_vecs_ua[_user_codes, i].astype(np.float32)

    # SVD dot score: user_vec · song_vec（类似 ALS 协同过滤分数）
    _uv = _user_vecs_us[_user_codes]  # (N, 10)
    _sv = _song_vecs_us[_song_codes]  # (N, 10)
    df["svd_dot_score"] = (_uv * _sv).sum(axis=1).astype(np.float32)

    print(f"     ✅ SVD 嵌入完成: 26 维（user-song 10 + song-user 10 + user-artist 5 + dot_score 1）")

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

    # 需要编码的分类特征（14个：新增 user_peak_hour）
    SPARSE_FEATURES = [
        "user_id", "song_id",
        "gender", "age_bucket", "city", "tenure_bucket",
        "genre", "language", "artist", "origin_country",
        "year_bucket", "duration_bucket", "source_channel",
        "user_peak_hour",
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

    # ── features_v3.pkl（36 特征：14 稀疏 + 22 稠密）
    DENSE_FEATURES = [
        # 原 14 个
        "user_play_count_log", "user_avg_completion",
        "user_genre_diversity", "user_30d_active_days",
        "song_play_count_log", "song_avg_completion",
        "song_popularity_norm", "song_age_days_log",
        "user_genre_match", "user_artist_match",
        "user_language_match", "user_country_match",
        "user_target_rate",
        "song_target_rate",
        # 新增 8 个
        "user_skip_rate",                   # 用户跳过率
        "song_skip_rate",                   # 歌曲被跳过率
        "hour_match",                       # 当前时段是否在用户 Top-3 时段
        "dow_match",                        # 当前星期是否在用户 Top-3 活跃日
        "days_since_last_play_log",         # 最近一次听该歌距今（天，log1p）
        "days_since_artist_log",            # 最近一次听该艺术家距今（天，log1p）
        "user_artist_repeat_rate",          # 用户对该艺术家的精准复听率
        "user_has_in_playlist",             # 该歌是否在用户歌单中（0/1）
        "user_playlist_artist_count_log",   # 用户歌单中该艺术家歌曲数（log1p）
        # Phase B-3: 记忆衰减特征
        "user_song_prev_play_days",         # 距上次听同一首歌的天数（-1=首次）
        "user_song_play_count_before",      # 此前听这首歌的次数
        # Phase B-4: 滚动窗口特征
        "user_7d_play_count_log",           # 近7天用户播放总量 log1p
        "user_30d_play_count_log",          # 近30天用户播放总量 log1p
        "user_7d_avg_completion",           # 近7天用户平均完播率
        "song_7d_play_count_log",           # 近7天歌曲播放总量 log1p
        "song_30d_play_count_log",          # 近30天歌曲播放总量 log1p
        "song_trending_ratio",              # 歌曲热度趋势（7d/30d_daily_avg）
        # SVD 嵌入特征（KKBOX 冠军方案核心）
        *[f"svd_user_song_{i}" for i in range(10)],   # user-song SVD 10d
        *[f"svd_song_user_{i}" for i in range(10)],   # song-user SVD 10d
        *[f"svd_user_artist_{i}" for i in range(5)],  # user-artist SVD 5d
        "svd_dot_score",                    # user·song SVD 点积分数
    ]
    SPARSE_ENCODED = [
        "user_id_encoded", "song_id_encoded",
        "gender_encoded", "age_bucket_encoded", "city_encoded",
        "tenure_bucket_encoded", "genre_encoded", "language_encoded",
        "artist_encoded", "origin_country_encoded",
        "year_bucket_encoded", "duration_bucket_encoded",
        "source_channel_encoded",
        "user_peak_hour_encoded",           # 新增：用户收听高峰时段
    ]

    # ── 时序切分元数据：UNIX 秒时间戳（不作为模型特征，仅供训练脚本切分用）
    _pt = pd.to_datetime(df["play_time"], errors="coerce").fillna(pd.Timestamp("2000-01-01"))
    _play_time_unix = (_pt.astype("int64") // 10**9).values

    feature_data = {
        "target": df["target"].values.astype(np.int8),
        # 元数据（时序切分用，非模型特征）
        "play_time_unix": _play_time_unix,
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
        "n_peak_hours":   int(df["user_peak_hour_encoded"].max() + 1),
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

    # ── _uid_map：MySQL user_id（整数）→ ALS 编码索引（整数）
    # sync_recs_v3.py 通过此映射判断用户是否在 ALS 训练集中（Tier 3 判断）
    # 若缺失此 key，所有用户均被判断为新用户，ALS 通道完全失效
    if "user_id" in encoders:
        _user_le = encoders["user_id"]
        user_stats_dict["_uid_map"] = {
            int(uid_str): int(idx)
            for idx, uid_str in enumerate(_user_le.classes_)
        }
        print(f"   ✅ _uid_map 已生成：{len(user_stats_dict['_uid_map']):,} 个用户")
    else:
        print("   ⚠️  encoders 中无 user_id，_uid_map 未生成")

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

    # ── svd_vecs.pkl（SVD向量，按 *_encoded 索引，供在线推断时 O(1) 查找）
    # 说明：SVD 是按 category codes 计算的（与 LabelEncoder 编码不同），
    #       但 df 中同时拥有两列，groupby(user_id_encoded).first() 即可完成对齐。
    #       同一用户的所有行 SVD 值完全相同（由 _user_codes 决定），first() 足够精确。
    print(f"\n  保存 svd_vecs.pkl ...")
    _user_svd_cols = [f"svd_user_song_{i}" for i in range(10)] + \
                     [f"svd_user_artist_{i}" for i in range(5)]
    _song_svd_cols = [f"svd_song_user_{i}" for i in range(10)]
    # 检查所有 SVD 列是否存在（build_feature_matrix 已计算）
    _user_svd_cols = [c for c in _user_svd_cols if c in df.columns]
    _song_svd_cols = [c for c in _song_svd_cols if c in df.columns]
    _user_svd_df = df.groupby("user_id_encoded")[_user_svd_cols].first()
    _song_svd_df = df.groupby("song_id_encoded")[_song_svd_cols].first()
    svd_vecs = {
        "user": _user_svd_df.to_dict("index"),   # {enc_id: {"svd_user_song_0": v, ...}}
        "song": _song_svd_df.to_dict("index"),   # {enc_id: {"svd_song_user_0": v, ...}}
    }
    with open(OUTPUT_SVD_VECS, "wb") as f:
        pickle.dump(svd_vecs, f, protocol=4)
    size_mb = os.path.getsize(OUTPUT_SVD_VECS) / 1024 / 1024
    print(f"   ✅ {OUTPUT_SVD_VECS}  ({size_mb:.1f} MB, "
          f"{len(svd_vecs['user']):,} 用户 / {len(svd_vecs['song']):,} 歌曲)")

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
    print("   MusicMode 特征工程 v3.2")
    print("   全量 MySQL 数据 + 62 特征体系（含 SVD 嵌入 + 歌单/时序/跳过/复听）")
    print("🎵" * 31)
    print(f"\n  今天: {TODAY}")

    engine = get_engine()

    # Step 1: 加载原始数据
    ph_df, songs_df, users_df, pl_df = load_raw_data(engine)
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

    # Step 4: 组装 36 特征矩阵
    df = build_feature_matrix(ph_df, songs_df, users_df, user_stats_dict, song_stats, pl_df)

    # Step 5: LabelEncoder 编码
    df, encoders = encode_features(df)

    # 保存
    save_outputs(df, encoders, user_stats_dict, song_stats)

    print("\n" + "=" * 62)
    print("✅ 特征工程 v3.2 完成！")
    print("=" * 62)
    print(f"\n📁 输出文件:")
    print(f"   {OUTPUT_FEATURES}")
    print(f"   {OUTPUT_ENCODERS}")
    print(f"   {OUTPUT_USER_STATS}")
    print(f"   {OUTPUT_SONG_STATS}")
    print(f"\n🚀 下一步: python train_lgbm.py && python train_deepfm_v3.py")


if __name__ == "__main__":
    main()
