# -*- coding: utf-8 -*-
r"""
MusicMode - 歌曲元数据更新脚本 (PySpark 简化版)

运行方式:
    $env:JAVA_HOME = "C:\Program Files\Eclipse Adoptium\jdk-21.0.9.10-hotspot"
    $env:HADOOP_HOME = "E:\毕业论文\hadoop"
    python update_song_metadata.py
"""

import os
import sys
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import StringType

# ============================================
# 配置区域
# ============================================

DATA_DIR = r"E:\毕业论文\Data"
SONGS_CSV = os.path.join(DATA_DIR, "songs.csv")
SONG_EXTRA_INFO_CSV = os.path.join(DATA_DIR, "song_extra_info.csv")
OUTPUT_CSV = os.path.join(DATA_DIR, "metadata_update.csv")

MYSQL_HOST = "localhost"
MYSQL_PORT = "3306"
MYSQL_DB = "musicweb"
MYSQL_USER = "root"
MYSQL_PASSWORD = "JF123456"

# Genre 映射（v2: 覆盖 KKBOX 全部主要 genre_id，将"其他"从 57% 降至 <10%）
GENRE_MAP = {
    # 原有映射
    "465": "流行", "458": "流行", "441": "华语流行", "443": "华语流行",
    "921": "摇滚", "692": "摇滚", "444": "电子", "1259": "嘻哈",
    "726": "R&B", "1152": "古典", "1011": "民谣", "468": "日本音乐",
    "359": "OST", "1043": "OST", "2006": "独立", "247": "拉丁",
    # v2 新增（采样确认）
    "958": "古典",       # 176K: Bizet, Chopin, Beethoven
    "2022": "摇滚",      # 169K: RADWIMPS, ONE OK ROCK, John Mayer (Alt/Indie Rock)
    "1609": "电子",      # 166K: The Chainsmokers, DJ Snake, Calvin Harris
    "2122": "爵士",      # 140K: Norah Jones, Tony Bennett, Lisa Ono
    "786": "轻音乐",     # 43K: Richard Clayderman, Eddy Kim
    "139": "R&B",        # 35K: The Weeknd, John Legend, Childish Gambino
    "940": "纯音乐",     # 33K: Yiruma, Kevin Kern (New Age/Piano)
    "1955": "金属",      # 21K: Korn, AC/DC, Slipknot
    "691": "流行",       # 19K: Mariah Carey, Justin Bieber (Holiday/Seasonal → 归入流行)
    "873": "福音",       # 18K: Faith/Gospel/Religious
    "437": "日本音乐",   # 17K: Hoshino Gen, PIKOTARO (J-Pop)
    "947": "儿童",       # 17K: Children's lullabies, nursery
    "275": "乡村",       # 复合 genre_id 中常见，Country
    "1572": "蓝调",      # Blues (常与 275 组合)
    "125": "世界音乐",   # World Music
    "109": "新世纪",     # New Age
    # v2 第二轮（剩余 >10K）
    "388": "轻音乐",     # 17K: 睡眠BGM, V.K, Andy Williams (Ambient/Easy Listening)
    "1616": "电子",      # 14K: Martin Garrix, Bebe Rexha (EDM/Dance)
    "242": "福音",       # 14K: Citizens & Saints, Gospel
    "451": "华语流行",   # 13K: Eason Chan 陈奕迅 (Cantopop/Mandopop)
    "880": "R&B",        # 13K: Mary Mary, Gospel R&B
    "423": "拉丁",       # 12K: Shakira, Don Omar (Latin Pop/Reggaeton)
    "829": "流行",       # 12K: 中日流行混合
    "2130": "摇滚",      # 11K: The Rolling Stones (Classic Rock)
}


def map_genre_ids(genre_ids_str):
    if not genre_ids_str or str(genre_ids_str) in ["nan", "None", ""]:
        return "其他"
    for gid in str(genre_ids_str).split("|"):
        if gid.strip() in GENRE_MAP:
            return GENRE_MAP[gid.strip()]
    return "其他"


def main():
    print("=" * 50)
    print("  MusicMode Metadata Update")
    print("=" * 50)
    
    # Step 1: Spark 处理 CSV
    print("\n[Step 1] Starting Spark...")
    
    try:
        spark = SparkSession.builder \
            .appName("MetadataUpdate") \
            .master("local[1]") \
            .config("spark.driver.memory", "1g") \
            .config("spark.python.worker.memory", "512m") \
            .getOrCreate()
        
        spark.sparkContext.setLogLevel("ERROR")
        print("  Spark session created")
        
        # 读取 songs.csv
        print(f"  Reading {SONGS_CSV}...")
        songs_df = spark.read.csv(SONGS_CSV, header=True)
        songs_count = songs_df.count()
        print(f"  Songs: {songs_count:,}")
        
        # 读取 song_extra_info.csv
        print(f"  Reading {SONG_EXTRA_INFO_CSV}...")
        extra_df = spark.read.csv(SONG_EXTRA_INFO_CSV, header=True)
        extra_count = extra_df.count()
        print(f"  Song names: {extra_count:,}")
        
        # 选择需要的列
        songs_df = songs_df.select(
            F.col("song_id").alias("kkbox_id"),
            F.col("genre_ids")
        )
        
        extra_df = extra_df.select(
            F.col("song_id").alias("kkbox_id"),
            F.col("name").alias("title")
        ).filter(F.col("title").isNotNull())
        
        # 连接
        print("  Joining...")
        result_df = songs_df.join(extra_df, "kkbox_id", "left")
        
        # 转为 Pandas 处理（避免 UDF 问题）
        print("  Converting to Pandas...")
        pdf = result_df.toPandas()
        print(f"  Records: {len(pdf):,}")
        
        # 在 Pandas 中处理
        pdf['title'] = pdf['title'].fillna(pdf['kkbox_id'])
        pdf['genre'] = pdf['genre_ids'].apply(map_genre_ids)
        
        # 保存 CSV
        print(f"  Saving to {OUTPUT_CSV}...")
        pdf[['kkbox_id', 'title', 'genre']].to_csv(OUTPUT_CSV, index=False, encoding='utf-8')
        print(f"  Saved!")
        
        spark.stop()
        print("  Spark stopped")
        
    except Exception as e:
        print(f"  ERROR in Step 1: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    # Step 2: 更新 MySQL
    print("\n[Step 2] Updating MySQL...")
    
    try:
        import pandas as pd
        from sqlalchemy import create_engine, text
        from tqdm import tqdm
        
        db_url = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}?charset=utf8mb4"
        engine = create_engine(db_url)
        
        df = pd.read_csv(OUTPUT_CSV, encoding='utf-8')
        print(f"  Loaded {len(df):,} records")
        
        batch_size = 1000
        updated = 0
        
        with engine.connect() as conn:
            for i in tqdm(range(0, len(df), batch_size), desc="  Updating"):
                batch = df.iloc[i:i+batch_size]
                for _, row in batch.iterrows():
                    try:
                        conn.execute(text(
                            "UPDATE songs SET title = :title, genre = :genre WHERE kkbox_id = :kkbox_id"
                        ), {"kkbox_id": str(row['kkbox_id']), "title": str(row['title']), "genre": str(row['genre'])})
                        updated += 1
                    except:
                        pass
                conn.commit()
        
        print(f"  Updated {updated:,} records")
        engine.dispose()
        
        os.remove(OUTPUT_CSV)
        print(f"  Cleaned up")
        
    except Exception as e:
        print(f"  ERROR in Step 2: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    print("\n" + "=" * 50)
    print("  All done!")
    print("=" * 50)


if __name__ == "__main__":
    main()
