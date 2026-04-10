# -*- coding: utf-8 -*-
"""
============================================
MusicMode - PySpark ETL 脚本 (Phase 1)
功能：全量导入 KKBOX songs.csv 到 MySQL，同时计算歌曲热度
项目：MusicMode (Python 后端/模型训练)
作者：Antigravity Assistant
============================================

数据流说明:
1. 读取 KKBOX songs.csv (229万歌曲元数据)
2. 读取 train.csv 统计每首歌的出现次数 (热度计算)
3. 合并两个数据集
4. 读取现有 MySQL songs 表，排除已存在的歌曲（增量导入）
5. 批量写入 MySQL

运行方式:
    spark-submit spark_etl_songs.py
    或
    python spark_etl_songs.py (需要 PySpark 已安装)
"""

import os
import sys
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import IntegerType, StringType


# ============================================
# 配置区域 - 请根据实际情况修改
# ============================================

# KKBOX 数据集路径
DATA_DIR = r"F:\Graduation-project-design\Data"
SONGS_CSV = os.path.join(DATA_DIR, "songs.csv")
TRAIN_CSV = os.path.join(DATA_DIR, "train.csv")

# MySQL 连接配置
MYSQL_HOST = "localhost"
MYSQL_PORT = "3306"
MYSQL_DB = "musicweb"
MYSQL_USER = "root"
MYSQL_PASSWORD = "JF123456"  # TODO: 请修改为实际密码

# JDBC URL
JDBC_URL = f"jdbc:mysql://{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}?useSSL=false&allowPublicKeyRetrieval=true&serverTimezone=UTC&rewriteBatchedStatements=true&characterEncoding=UTF-8"

# MySQL JDBC 驱动路径
# Maven 项目自动从本地仓库加载，无需手动下载
# 路径格式: C:/Users/用户名/.m2/repository/mysql/mysql-connector-java/8.0.33/mysql-connector-java-8.0.33.jar
MAVEN_REPO = os.path.expanduser("~/.m2/repository")
JDBC_DRIVER_PATH = os.path.join(MAVEN_REPO, "mysql", "mysql-connector-java", "8.0.30", "mysql-connector-java-8.0.30.jar")

# 检查 JDBC 驱动是否存在
if not os.path.exists(JDBC_DRIVER_PATH):
    print(f"⚠️ 警告: 未找到 JDBC 驱动: {JDBC_DRIVER_PATH}")
    print(f"   请先运行: cd F:\\Graduation-project-design\\Project\\MusicWeb && mvn dependency:resolve")
    print(f"   或检查 Maven 本地仓库路径是否正确")


def create_spark_session():
    """
    创建 SparkSession
    配置：Local 模式，4个并行线程，4GB Driver 内存
    """
    spark = SparkSession.builder \
        .appName("MusicMode_KKBOX_ETL") \
        .master("local[4]") \
        .config("spark.driver.memory", "4g") \
        .config("spark.executor.memory", "4g") \
        .config("spark.sql.shuffle.partitions", "8") \
        .config("spark.jars", JDBC_DRIVER_PATH) \
        .config("spark.driver.extraClassPath", JDBC_DRIVER_PATH) \
        .getOrCreate()
    
    # 设置日志级别为 WARN，减少输出噪音
    spark.sparkContext.setLogLevel("WARN")
    print("✅ SparkSession 创建成功")
    return spark


def load_songs_csv(spark):
    """
    加载 KKBOX songs.csv
    字段：song_id, song_length, genre_ids, artist_name, composer, lyricist, language
    """
    print(f"📂 正在读取 {SONGS_CSV} ...")
    
    df = spark.read.csv(
        SONGS_CSV,
        header=True,
        inferSchema=True,
        encoding="UTF-8"
    )
    
    print(f"   ├─ 原始记录数: {df.count():,}")
    print(f"   └─ 字段: {df.columns}")
    return df


def load_train_csv(spark):
    """
    加载 KKBOX train.csv
    用于统计每首歌的出现次数（热度）
    """
    print(f"📂 正在读取 {TRAIN_CSV} ...")
    
    df = spark.read.csv(
        TRAIN_CSV,
        header=True,
        inferSchema=True,
        encoding="UTF-8"
    )
    
    print(f"   └─ 交互记录数: {df.count():,}")
    return df


def calculate_popularity(train_df):
    """
    计算歌曲热度
    逻辑：统计每首歌在 train.csv 中出现的次数
    """
    print("🔥 正在计算歌曲热度...")
    
    popularity_df = train_df.groupBy("song_id") \
        .agg(F.count("*").alias("popularity"))
    
    print(f"   └─ 有热度数据的歌曲数: {popularity_df.count():,}")
    return popularity_df


def prepare_songs_for_mysql(songs_df, popularity_df):
    """
    准备待导入的歌曲数据
    
    转换逻辑：
    - kkbox_id = song_id (原始 KKBOX ID)
    - title = song_id (暂用 ID 代替，后续可通过 song_extra_info 补充)
    - artist = artist_name
    - album = NULL (KKBOX 数据集无专辑信息)
    - duration = song_length (毫秒转秒)
    - genre = 通过映射表转换为中文 (TODO: 后续实现)
    - genre_ids = 原始 genre_ids 保留
    - language = 原始 language
    - popularity = 计算值
    """
    print("🔄 正在转换数据格式...")
    
    # 合并热度数据
    df = songs_df.join(popularity_df, on="song_id", how="left")
    
    # 缺失热度填充为 0
    df = df.fillna({"popularity": 0})
    
    # 选择并重命名字段以匹配 MySQL songs 表
    result_df = df.select(
        F.col("song_id").cast(StringType()).alias("kkbox_id"),
        # title 暂用 song_id，后续可从 song_extra_info.csv 补充真实歌名
        F.coalesce(F.col("song_id"), F.lit("Unknown")).cast(StringType()).alias("title"),
        F.coalesce(F.col("artist_name"), F.lit("Unknown")).alias("artist"),
        F.lit(None).cast(StringType()).alias("album"),
        # song_length 从毫秒转换为秒
        (F.col("song_length") / 1000).cast(IntegerType()).alias("duration"),
        # genre 暂时留空，后续可建立映射表
        F.lit(None).cast(StringType()).alias("genre"),
        F.col("genre_ids").cast(StringType()).alias("genre_ids"),
        F.col("language").cast(StringType()).alias("language"),
        F.col("popularity").cast(IntegerType()).alias("popularity"),
        F.lit(None).cast(StringType()).alias("release_year"),
        F.lit(None).cast(StringType()).alias("file_path"),
        F.lit("img/cover.jpg").alias("cover_image")
    )
    
    print(f"   └─ 转换后记录数: {result_df.count():,}")
    return result_df


def load_existing_songs(spark):
    """
    从 MySQL 读取现有 songs 表
    用于增量导入：排除已存在的歌曲
    """
    print("📦 正在读取 MySQL 现有歌曲...")
    
    try:
        existing_df = spark.read \
            .format("jdbc") \
            .option("url", JDBC_URL) \
            .option("dbtable", "songs") \
            .option("user", MYSQL_USER) \
            .option("password", MYSQL_PASSWORD) \
            .option("driver", "com.mysql.cj.jdbc.Driver") \
            .load()
        
        count = existing_df.count()
        print(f"   └─ 现有歌曲数: {count:,}")
        return existing_df
    except Exception as e:
        print(f"   ⚠️ 无法读取 MySQL: {e}")
        print("   └─ 将导入全部数据（忽略去重）")
        return None


def incremental_filter(new_songs_df, existing_df):
    """
    增量过滤：排除已存在于 MySQL 的歌曲
    通过 kkbox_id 判断是否已存在
    """
    if existing_df is None:
        return new_songs_df
    
    # 获取已存在的 kkbox_id 集合
    existing_ids = existing_df.select("kkbox_id").filter(F.col("kkbox_id").isNotNull())
    
    # 左反连接：只保留新歌
    filtered_df = new_songs_df.join(
        existing_ids,
        on="kkbox_id",
        how="left_anti"
    )
    
    new_count = filtered_df.count()
    print(f"🆕 新增歌曲数: {new_count:,}")
    return filtered_df


def write_to_mysql(df):
    """
    批量写入 MySQL
    使用 append 模式，不覆盖现有数据
    """
    print("💾 正在写入 MySQL...")
    
    df.write \
        .format("jdbc") \
        .option("url", JDBC_URL) \
        .option("dbtable", "songs") \
        .option("user", MYSQL_USER) \
        .option("password", MYSQL_PASSWORD) \
        .option("driver", "com.mysql.cj.jdbc.Driver") \
        .option("batchsize", "5000") \
        .option("isolationLevel", "NONE") \
        .mode("append") \
        .save()
    
    print("✅ 数据写入完成！")


def main():
    """
    主函数：协调 ETL 流程
    """
    print("=" * 50)
    print("  MusicMode KKBOX ETL 启动")
    print("=" * 50)
    
    # 1. 创建 Spark Session
    spark = create_spark_session()
    
    try:
        # 2. 加载 KKBOX 数据
        songs_df = load_songs_csv(spark)
        train_df = load_train_csv(spark)
        
        # 3. 计算热度
        popularity_df = calculate_popularity(train_df)
        
        # 4. 准备导入数据
        prepared_df = prepare_songs_for_mysql(songs_df, popularity_df)
        
        # 5. 读取现有 MySQL 数据（用于增量过滤）
        existing_df = load_existing_songs(spark)
        
        # 6. 增量过滤
        final_df = incremental_filter(prepared_df, existing_df)
        
        # 7. 写入 MySQL
        if final_df.count() > 0:
            write_to_mysql(final_df)
        else:
            print("ℹ️ 无新数据需要导入")
        
        print("=" * 50)
        print("  ETL 任务完成！")
        print("=" * 50)
        
    finally:
        spark.stop()
        print("🛑 SparkSession 已关闭")


if __name__ == "__main__":
    main()
