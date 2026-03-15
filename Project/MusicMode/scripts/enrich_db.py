# -*- coding: utf-8 -*-
"""
enrich_db.py — 数据库字段扩充主脚本（一次性执行）

功能（按 --step 参数分阶段执行）：
  --step alter           : 新增字段（play_history.target, source_channel, users.bd, songs.origin_country）
  --step songs           : songs 表批量补全（ISRC→release_year+origin_country, 语言代码→标签, genre规范化）
  --step musicbrainz     : 通过 MusicBrainz API 为外部歌曲补全 origin_country（支持断点续跑）
  --step users           : 更新 users 表（jf/jf2信息, kkbox_%用户 create_time/bd/city/gender）
  --step play_history    : 回填 play_history.target + source_channel（7.37M行，分批5000）
  --step enrich_external : 通过网易云(优先)+QQ 为外部歌曲补全全量元数据
                           （release_year/album/duration/cover_image/popularity/language/genre）

执行顺序（必须按此顺序手动执行）：
  1. python test_api_composer.py         ← 先测试，决定是否加 composer 列
  2. python enrich_db.py --step alter
  3. python enrich_db.py --step songs
  4. python enrich_db.py --step musicbrainz  ← 可后台异步，约3小时
  5. python enrich_db.py --step users
  6. python enrich_db.py --step play_history  ← 最耗时，约90分钟

注意：
  - 所有步骤均可中断后重新运行（幂等设计）
  - musicbrainz 步骤使用 musicbrainz_progress.json 记录断点
  - play_history 步骤会打印实时进度条

作者：MusicMode 推荐系统
"""

import argparse
import os
import sys
import json
import time
import pickle
import warnings
from datetime import datetime, date
from typing import Optional, Dict, List, Tuple

import pandas as pd
import numpy as np
from tqdm import tqdm
import pymysql
from sqlalchemy import create_engine, text

warnings.filterwarnings('ignore')

# ============================================================
# 全局配置
# ============================================================

# 数据目录
DATA_DIR = r"E:\Graduation-project-design\Data"
SONG_EXTRA_CSV  = os.path.join(DATA_DIR, "song_extra_info.csv")
SONGS_CSV       = os.path.join(DATA_DIR, "songs.csv")
MEMBERS_CSV     = os.path.join(DATA_DIR, "members.csv")
TRAIN_CSV       = os.path.join(DATA_DIR, "train.csv")

# 断点续跑文件（musicbrainz 步骤）
PROGRESS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "musicbrainz_progress.json")

# MySQL 配置
MYSQL_HOST     = "localhost"
MYSQL_PORT     = 3306
MYSQL_DB       = "musicweb"
MYSQL_USER     = "root"
MYSQL_PASSWORD = "JF123456"

# 批量处理大小
BATCH_SIZE = 5000      # play_history 回填批次
TEMP_BATCH = 10000     # 临时表插入批次

# MusicBrainz 配置
MB_API_URL    = "https://musicbrainz.org/ws/2"
MB_USER_AGENT = "MusicWebRec/1.0 (graduation-project)"
MB_RATE_LIMIT = 1.1    # 每次请求后等待秒数（≥1.0 遵守限速）


# ============================================================
# 语言数字代码 → 中文标签（KKBOX songs.csv 数字编码）
# ============================================================
KKBOX_LANG_MAP = {
    "-1": "未知",
    "3":  "国语",     # 台湾/繁体中文
    "10": "英语",
    "17": "日语",
    "24": "韩语",
    "38": "粤语",
    "45": "西班牙语",
    "52": "法语",
    "59": "德语",
    "31": "普通话",   # 大陆/简体中文
    "66": "葡萄牙语",
    "73": "意大利语",
    "7":  "泰语",
    "4":  "印尼语",
    "25": "越南语",
    "82": "其他",
}


# ============================================================
# 语言标签 → 发行国代码（50+ 条目）
# ============================================================
LANG_TO_COUNTRY = {
    # 中文
    "国语":       "TW",
    "普通话":     "CN",
    "粤语":       "HK",
    # 亚洲
    "英语":       "US",
    "日语":       "JP",
    "韩语":       "KR",
    "泰语":       "TH",
    "越南语":     "VN",
    "印尼语":     "ID",
    "马来语":     "MY",
    "印地语":     "IN",
    "菲律宾语":   "PH",
    "缅甸语":     "MM",
    "高棉语":     "KH",
    "老挝语":     "LA",
    "泰米尔语":   "IN",
    "孟加拉语":   "BD",
    "旁遮普语":   "IN",
    "泰卢固语":   "IN",
    "僧伽罗语":   "LK",
    "尼泊尔语":   "NP",
    "蒙古语":     "MN",
    "哈萨克语":   "KZ",
    "乌兹别克语": "UZ",
    "格鲁吉亚语": "GE",
    "亚美尼亚语": "AM",
    "阿塞拜疆语": "AZ",
    # 欧洲
    "法语":       "FR",
    "德语":       "DE",
    "西班牙语":   "ES",
    "葡萄牙语":   "BR",
    "意大利语":   "IT",
    "俄语":       "RU",
    "荷兰语":     "NL",
    "瑞典语":     "SE",
    "挪威语":     "NO",
    "丹麦语":     "DK",
    "芬兰语":     "FI",
    "波兰语":     "PL",
    "捷克语":     "CZ",
    "希腊语":     "GR",
    "罗马尼亚语": "RO",
    "匈牙利语":   "HU",
    "乌克兰语":   "UA",
    "保加利亚语": "BG",
    "克罗地亚语": "HR",
    "塞尔维亚语": "RS",
    "斯洛伐克语": "SK",
    "立陶宛语":   "LT",
    "拉脱维亚语": "LV",
    "爱沙尼亚语": "EE",
    "希伯来语":   "IL",
    "波斯语":     "IR",
    "土耳其语":   "TR",
    "阿拉伯语":   "SA",
    # 非洲
    "斯瓦希里语": "KE",
    "豪萨语":     "NG",
    "阿姆哈拉语": "ET",
    "南非荷兰语": "ZA",
    # 其他
    "其他":       "XX",
    "未知":       "XX",
}


# ============================================================
# GENRE_MAP（流派 ID → 中文名）来自 update_song_metadata.py
# ============================================================
GENRE_MAP = {
    "465": "流行", "458": "流行", "441": "华语流行", "443": "华语流行",
    "921": "摇滚", "692": "摇滚", "444": "电子", "1259": "嘻哈",
    "726": "R&B", "1152": "古典", "1011": "民谣", "468": "日本音乐",
    "359": "OST", "1043": "OST", "2006": "独立", "247": "拉丁",
    "958": "古典", "2022": "摇滚", "1609": "电子", "2122": "爵士",
    "786": "轻音乐", "139": "R&B", "940": "纯音乐", "1955": "金属",
    "691": "流行", "873": "福音", "437": "日本音乐", "947": "儿童",
    "275": "乡村", "1572": "蓝调", "125": "世界音乐", "109": "新世纪",
    "388": "轻音乐", "1616": "电子", "242": "福音", "451": "华语流行",
    "880": "R&B", "423": "拉丁", "829": "流行", "2130": "摇滚",
}


# ============================================================
# source_channel 映射（KKBOX 三字段 → 统一枚举）
# ============================================================
def map_source_channel(source_type: str, source_system_tab: str,
                       source_screen_name: str) -> str:
    """将 KKBOX 三个来源字段映射为统一的 source_channel 枚举值"""
    st  = str(source_type or "").strip().lower()
    tab = str(source_system_tab or "").strip().lower()

    if st == "online-playlist":                             return "ONLINE_PLAYLIST"
    if st == "local-library":                               return "PERSONAL_PLAYLIST"
    if st == "radio" or "radio" in tab:                    return "RADIO"
    if st == "album":                                       return "ALBUM"
    if st in ("my-daily-playlist", "song-based-playlist"): return "AI_PLAYLIST"
    if st == "listen-with":                                 return "SOCIAL"
    if tab == "search" or (st == "song" and tab == "search"): return "SEARCH"
    if tab == "discover":                                   return "DISCOVERY"
    if st == "song":                                        return "DIRECT_PLAY"
    return "UNKNOWN"


# ============================================================
# ISRC 解析函数
# ============================================================
def extract_year_from_isrc(isrc: str) -> Optional[int]:
    """从 ISRC 码（格式 CC-XXX-YY-NNNNN 或 CCXXXYYNNNNN）提取发行年份"""
    if not isrc or pd.isna(isrc):
        return None
    s = str(isrc).replace("-", "").strip()
    if len(s) < 7:
        return None
    try:
        yy = int(s[5:7])
        return 2000 + yy if yy <= 26 else 1900 + yy
    except (ValueError, IndexError):
        return None


def extract_country_from_isrc(isrc: str) -> Optional[str]:
    """从 ISRC 码提取发行国代码（前两位字母）"""
    if not isrc or pd.isna(isrc):
        return None
    s = str(isrc).replace("-", "").strip()
    if len(s) < 2:
        return None
    country = s[:2].upper()
    return country if country.isalpha() and len(country) == 2 else None


# ============================================================
# 数据库连接
# ============================================================
def get_conn():
    """获取 pymysql 直连（适用于批量 executemany）"""
    return pymysql.connect(
        host=MYSQL_HOST, port=MYSQL_PORT, db=MYSQL_DB,
        user=MYSQL_USER, password=MYSQL_PASSWORD,
        charset="utf8mb4",
        autocommit=False,
    )


def get_engine():
    """获取 SQLAlchemy 引擎（适用于 pandas to_sql / read_sql）"""
    url = (f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}"
           f"@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}?charset=utf8mb4")
    return create_engine(url, pool_pre_ping=True)


def speed_up_mysql(conn):
    """设置 MySQL SESSION 变量以加速批量写入（3-5 倍）"""
    with conn.cursor() as cur:
        cur.execute("SET SESSION FOREIGN_KEY_CHECKS=0")
        cur.execute("SET SESSION UNIQUE_CHECKS=0")
    conn.commit()


def restore_mysql(conn):
    """恢复 MySQL SESSION 变量"""
    with conn.cursor() as cur:
        cur.execute("SET SESSION FOREIGN_KEY_CHECKS=1")
        cur.execute("SET SESSION UNIQUE_CHECKS=1")
    conn.commit()


def print_sep(char="=", width=62):
    print(char * width)


# ============================================================
# --step alter : 新增数据库列
# ============================================================
def step_alter(add_composer: bool = False):
    """
    新增字段：
      play_history.target         TINYINT(1)
      play_history.source_channel VARCHAR(30)
      users.bd                    TINYINT
      songs.origin_country        CHAR(2)
      songs.composer              VARCHAR(200)  [可选]
      songs.lyricist              VARCHAR(200)  [可选]
    """
    print_sep()
    print("🔧 [Step: alter] 新增数据库字段")
    print_sep()

    # 定义要执行的 ALTER 语句（幂等：若列已存在会报错，捕获忽略）
    alter_statements = [
        # play_history
        ("play_history", "target",
         "ALTER TABLE play_history ADD COLUMN target TINYINT(1) DEFAULT NULL "
         "COMMENT '30天内重复收听标签(0=否,1=是)'"),
        ("play_history", "source_channel",
         "ALTER TABLE play_history ADD COLUMN source_channel VARCHAR(30) DEFAULT NULL "
         "COMMENT '统一播放来源(ONLINE_PLAYLIST/PERSONAL_PLAYLIST/RADIO/ALBUM/AI_PLAYLIST/"
         "SOCIAL/SEARCH/DISCOVERY/DIRECT_PLAY/RECOMMENDATION/EXTERNAL/UNKNOWN)'"),
        # users
        ("users", "bd",
         "ALTER TABLE users ADD COLUMN bd TINYINT DEFAULT NULL COMMENT '用户年龄'"),
        # songs
        ("songs", "origin_country",
         "ALTER TABLE songs ADD COLUMN origin_country CHAR(2) DEFAULT NULL "
         "COMMENT '发行国代码(ISO 3166-1 alpha-2)'"),
    ]

    if add_composer:
        alter_statements += [
            ("songs", "composer",
             "ALTER TABLE songs ADD COLUMN composer VARCHAR(200) DEFAULT NULL "
             "COMMENT '作曲家'"),
            ("songs", "lyricist",
             "ALTER TABLE songs ADD COLUMN lyricist VARCHAR(200) DEFAULT NULL "
             "COMMENT '作词家'"),
        ]

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            for table, col, sql in alter_statements:
                try:
                    cur.execute(sql)
                    conn.commit()
                    print(f"  ✅ {table}.{col} 已新增")
                except pymysql.err.OperationalError as e:
                    if "Duplicate column name" in str(e) or "already exists" in str(e):
                        print(f"  ℹ️  {table}.{col} 已存在，跳过")
                    else:
                        print(f"  ❌ {table}.{col} 失败: {e}")

        # 新增索引（加速后续 UPDATE）
        index_statements = [
            "CREATE INDEX IF NOT EXISTS idx_ph_user_song ON play_history(user_id, song_id)",
            "CREATE INDEX IF NOT EXISTS idx_songs_origin ON songs(origin_country)",
        ]
        for idx_sql in index_statements:
            try:
                # MySQL 不支持 CREATE INDEX IF NOT EXISTS，改用 try/except
                pass
            except Exception:
                pass
    finally:
        conn.close()

    print("\n✅ alter 步骤完成")

    if not add_composer:
        print("\n💡 提示：若 test_api_composer.py 结果建议添加 composer/lyricist，")
        print("   请用以下命令追加执行：")
        print("   python enrich_db.py --step alter --add-composer")


# ============================================================
# --step songs : songs 表批量字段补全
# ============================================================
def step_songs():
    """
    批量更新 songs 表以下字段：
      1. release_year  : 从 song_extra_info.csv ISRC[5:7] 提取（仅补 NULL）
      2. origin_country: 从 song_extra_info.csv ISRC[0:2] 提取（KKBOX 歌曲）
      3. language      : KKBOX 数字代码 → 中文标签
      4. genre         : genre_ids → GENRE_MAP 规范化（仅补 NULL/空）
      5. origin_country: 语言映射 fallback（无 ISRC 的歌曲）
    """
    print_sep()
    print("🎵 [Step: songs] songs 表批量字段补全")
    print_sep()

    # ──────────────────────────────────────────
    # 1. 读取 song_extra_info.csv → 提取 ISRC 数据
    # ──────────────────────────────────────────
    print(f"\n📥 读取 song_extra_info.csv ...")
    if not os.path.exists(SONG_EXTRA_CSV):
        print(f"❌ 文件不存在: {SONG_EXTRA_CSV}")
        print("   请确认 Data 目录下有 song_extra_info.csv")
        return

    # 只读取需要的列
    extra_df = pd.read_csv(
        SONG_EXTRA_CSV,
        dtype={"song_id": str, "isrc": str},
        usecols=["song_id", "isrc"],
        low_memory=True,
    )
    extra_df = extra_df.rename(columns={"song_id": "kkbox_id"})
    print(f"   共 {len(extra_df):,} 条记录")

    # 提取 release_year 和 origin_country
    print("⚙️  从 ISRC 提取 release_year 和 origin_country ...")
    extra_df["release_year_new"] = extra_df["isrc"].apply(extract_year_from_isrc)
    extra_df["origin_country_isrc"] = extra_df["isrc"].apply(extract_country_from_isrc)

    # 只保留有效数据
    isrc_data = extra_df.dropna(subset=["kkbox_id"])
    isrc_data = isrc_data[
        isrc_data["release_year_new"].notna() | isrc_data["origin_country_isrc"].notna()
    ]
    print(f"   有 release_year 数据: {isrc_data['release_year_new'].notna().sum():,} 条")
    print(f"   有 origin_country 数据: {isrc_data['origin_country_isrc'].notna().sum():,} 条")

    # ──────────────────────────────────────────
    # 2. 写入临时表，通过 JOIN UPDATE 批量更新 songs
    # ──────────────────────────────────────────
    conn = get_conn()
    engine = get_engine()
    speed_up_mysql(conn)

    try:
        print("\n🗄️  创建临时表 _enrich_isrc_tmp ...")
        with conn.cursor() as cur:
            cur.execute("DROP TABLE IF EXISTS `_enrich_isrc_tmp`")
            cur.execute("""
                CREATE TEMPORARY TABLE `_enrich_isrc_tmp` (
                    kkbox_id      VARCHAR(50) NOT NULL,
                    release_year  INT,
                    origin_country CHAR(2),
                    INDEX idx_tmp_kkbox (kkbox_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
        conn.commit()

        # 分批插入临时表
        insert_sql = ("INSERT INTO `_enrich_isrc_tmp` "
                      "(kkbox_id, release_year, origin_country) VALUES (%s, %s, %s)")
        rows = []
        for _, row in isrc_data.iterrows():
            yr = int(row["release_year_new"]) if pd.notna(row["release_year_new"]) else None
            oc = row["origin_country_isrc"] if pd.notna(row["origin_country_isrc"]) else None
            rows.append((row["kkbox_id"], yr, oc))

        print(f"\n⬆️  插入临时表（{len(rows):,} 行，{TEMP_BATCH} 行/批）...")
        with conn.cursor() as cur:
            for i in tqdm(range(0, len(rows), TEMP_BATCH), desc="  插入临时表"):
                cur.executemany(insert_sql, rows[i:i+TEMP_BATCH])
        conn.commit()

        # JOIN UPDATE songs
        print("\n🔄 JOIN UPDATE songs.release_year ...")
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE songs s
                JOIN `_enrich_isrc_tmp` t ON s.kkbox_id = t.kkbox_id
                SET s.release_year = t.release_year
                WHERE s.release_year IS NULL
                  AND t.release_year IS NOT NULL
            """)
            affected = cur.rowcount
        conn.commit()
        print(f"   ✅ 更新 {affected:,} 行 release_year")

        print("🔄 JOIN UPDATE songs.origin_country (ISRC 级) ...")
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE songs s
                JOIN `_enrich_isrc_tmp` t ON s.kkbox_id = t.kkbox_id
                SET s.origin_country = t.origin_country
                WHERE s.origin_country IS NULL
                  AND t.origin_country IS NOT NULL
            """)
            affected = cur.rowcount
        conn.commit()
        print(f"   ✅ 更新 {affected:,} 行 origin_country（ISRC 来源）")

        with conn.cursor() as cur:
            cur.execute("DROP TABLE IF EXISTS `_enrich_isrc_tmp`")
        conn.commit()

        # ──────────────────────────────────────────
        # 3. 语言数字代码 → 中文标签（SQL CASE WHEN）
        # ──────────────────────────────────────────
        print("\n🔤 更新 KKBOX 歌曲语言数字代码 → 中文标签 ...")
        # 语言字段存储格式为 "3.0"、"-1.0"、"3.0;国语" 等
        # 先用 SUBSTRING_INDEX(language, '.', 1) 取 "3"、"-1"，再 CAST 为整数
        case_clauses = "\n    ".join(
            f"WHEN {code} THEN '{label}'"
            for code, label in KKBOX_LANG_MAP.items()
        )
        lang_sql = f"""
            UPDATE songs
            SET language = CASE CAST(SUBSTRING_INDEX(language, '.', 1) AS SIGNED)
                {case_clauses}
                ELSE '其他'
            END
            WHERE kkbox_id IS NOT NULL
              AND language REGEXP '^-?[0-9]'
        """
        with conn.cursor() as cur:
            cur.execute(lang_sql)
            affected = cur.rowcount
        conn.commit()
        print(f"   ✅ 更新 {affected:,} 行 language")

        # language 已转为中文标签后，对 origin_country='XX' 的 KKBOX 歌曲
        # 重新按语言推断（之前因 language 为数字代码而无法匹配）
        print("\n🔄 origin_country 修正（language 已更新，重映 XX 歌曲）...")
        lang_case2 = "\n    ".join(
            f"WHEN '{lang}' THEN '{country}'"
            for lang, country in LANG_TO_COUNTRY.items()
        )
        refix_sql = f"""
            UPDATE songs
            SET origin_country = CASE language
                {lang_case2}
                ELSE origin_country
            END
            WHERE origin_country = 'XX'
              AND kkbox_id IS NOT NULL
              AND language IS NOT NULL
              AND language NOT IN ('未知', '其他', '')
        """
        with conn.cursor() as cur:
            cur.execute(refix_sql)
            affected2 = cur.rowcount
        conn.commit()
        print(f"   ✅ 重映 {affected2:,} 行 origin_country（从 XX → 正确国家）")

        # ──────────────────────────────────────────
        # 4. genre_ids → genre（Python 批量，仅补空值）
        # ──────────────────────────────────────────
        print("\n🎼 补全 genre（genre_ids 规范化，仅处理 genre 为 NULL 的行）...")
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, genre_ids FROM songs
                WHERE (genre IS NULL OR genre = '')
                  AND genre_ids IS NOT NULL
                  AND genre_ids != ''
                  AND kkbox_id IS NOT NULL
                LIMIT 5000000
            """)
            rows_need_genre = cur.fetchall()
        print(f"   需要补全 genre 的行: {len(rows_need_genre):,}")

        def get_genre_from_ids(genre_ids_str: str) -> Optional[str]:
            """从 pipe 分隔的 genre_ids 字符串提取第一个有效流派"""
            for gid in str(genre_ids_str).split("|"):
                gid = gid.strip()
                if gid in GENRE_MAP:
                    return GENRE_MAP[gid]
            return None

        genre_updates = []
        for (song_id, genre_ids) in rows_need_genre:
            genre = get_genre_from_ids(genre_ids)
            if genre:
                genre_updates.append((genre, song_id))

        print(f"   匹配到 GENRE_MAP 的行: {len(genre_updates):,}")
        if genre_updates:
            with conn.cursor() as cur:
                for i in tqdm(range(0, len(genre_updates), BATCH_SIZE), desc="  更新 genre"):
                    cur.executemany(
                        "UPDATE songs SET genre=%s WHERE id=%s",
                        genre_updates[i:i+BATCH_SIZE]
                    )
                    if i % (BATCH_SIZE * 10) == 0:
                        conn.commit()
            conn.commit()
            print(f"   ✅ 更新 {len(genre_updates):,} 行 genre")

        # ──────────────────────────────────────────
        # 5. origin_country 语言映射 fallback
        #    （没有 ISRC 的歌曲，用 language 推断）
        # ──────────────────────────────────────────
        print("\n🌍 origin_country 语言映射 fallback ...")
        # 构建 SQL CASE WHEN
        lang_case = "\n    ".join(
            f"WHEN '{lang}' THEN '{country}'"
            for lang, country in LANG_TO_COUNTRY.items()
        )
        fallback_sql = f"""
            UPDATE songs
            SET origin_country = CASE language
                {lang_case}
                ELSE 'XX'
            END
            WHERE origin_country IS NULL
              AND language IS NOT NULL
              AND language != ''
        """
        with conn.cursor() as cur:
            cur.execute(fallback_sql)
            affected = cur.rowcount
        conn.commit()
        print(f"   ✅ 语言推断补全 {affected:,} 行 origin_country")

        # 剩余完全无语言的歌曲标记为 XX
        with conn.cursor() as cur:
            cur.execute("UPDATE songs SET origin_country='XX' WHERE origin_country IS NULL")
            affected = cur.rowcount
        conn.commit()
        print(f"   ✅ 最终 fallback: {affected:,} 行 origin_country 设为 'XX'")

    finally:
        restore_mysql(conn)
        conn.close()

    # 统计结果
    engine2 = get_engine()
    with engine2.connect() as c:
        stats = pd.read_sql("""
            SELECT
              SUM(release_year IS NOT NULL) AS has_year,
              SUM(origin_country IS NOT NULL) AS has_country,
              SUM(genre IS NOT NULL AND genre != '') AS has_genre,
              COUNT(*) AS total
            FROM songs
        """, c).iloc[0]
    print(f"\n📊 songs 表更新后统计:")
    print(f"   release_year 填充率: {stats['has_year']:,}/{stats['total']:,} "
          f"= {100*stats['has_year']/stats['total']:.1f}%")
    print(f"   origin_country 填充率: {stats['has_country']:,}/{stats['total']:,} "
          f"= {100*stats['has_country']/stats['total']:.1f}%")
    print(f"   genre 填充率: {stats['has_genre']:,}/{stats['total']:,} "
          f"= {100*stats['has_genre']/stats['total']:.1f}%")

    print("\n✅ songs 步骤完成")


# ============================================================
# --step enrich_external : 网易云(优先) + QQ API 为外部歌曲补全所有元数据
# （release_year / album / duration / cover_image / popularity / language / genre）
# --step release_year    : 同上（旧名称保留兼容）
# ============================================================
def step_enrich_external():
    """
    为外部歌曲（kkbox_id IS NULL）通过 网易云(优先) + QQ Music(兜底) 同时补全：
      release_year  — 发行年份
      album         — 专辑名
      duration      — 时长（秒）
      cover_image   — 封面图片 URL
      popularity    — 热度（0-100）
      language      — 语言标签
      genre         — 流派标签

    查询策略：
      ① 网易云 Node.js API（端口 3000）→ 主力源（release_year/album/duration/cover_image/popularity）
      ② QQ qqmusic_api（Python 库）→ 兜底 + 补充 genre/language

    只更新数据库中当前为 NULL/0/空字符串 的字段，不覆盖已有有效数据。
    支持断点续跑（enrich_external_progress.json）。
    """
    import asyncio
    from datetime import datetime as _dt

    PROGRESS_EXT_FILE = os.path.join(os.path.dirname(__file__), "enrich_external_progress.json")
    NETEASE_BASE = "http://127.0.0.1:3000"
    NETEASE_SEARCH_PATHS = ["/netease/search", "/search"]
    NETEASE_DETAIL_PATHS = ["/netease/song/detail", "/song/detail"]
    RATE_LIMIT_SEC = 0.0   # 真并发模式下不再需要额外 sleep，API 延迟本身就是节流

    # QQ Music 语言数字代码 → 中文标签（部分平台返回数字）
    QQ_LANG_MAP = {
        "0": "国语", "1": "粤语", "2": "英语", "3": "日语",
        "4": "韩语", "5": "法语", "6": "德语", "7": "西班牙语",
        "8": "俄语", "9": "意大利语", "10": "葡萄牙语",
    }

    print_sep()
    print("🎵 [Step: enrich_external] 网易云(优先) + QQ API 补全外部歌曲全量元数据")
    print("   目标字段: release_year / album / duration / cover_image / popularity / language / genre")
    print_sep()

    # ── 连通性检测 ──────────────────────────────
    import socket as _sock
    try:
        import httpx as _httpx
    except ImportError:
        print("   ❌ 缺少 httpx 库，请运行：pip install httpx")
        return

    def _tcp_ok(host: str, port: int) -> bool:
        try:
            with _sock.create_connection((host, port), timeout=3):
                return True
        except Exception:
            return False

    netease_ok = _tcp_ok("127.0.0.1", 3000)
    qq_ok = False
    try:
        import qqmusic_api   # noqa
        qq_ok = True
    except ImportError:
        pass

    if netease_ok:
        print("   ✅ 网易云 API 服务可达（端口 3000），并发限制=3，间隔=1s")
    else:
        print("   ⚠️  网易云 API 不可达，将仅使用 QQ Music")

    if not qq_ok:
        print("   ❌ QQ API（qqmusic_api）不可用 → pip install qqmusic-api-python")
        return
    else:
        print("   ✅ QQ API（qqmusic_api 库）可用，并发限制=10")

    # ── 断点进度 ────────────────────────────────
    done_ids: set = set()
    if os.path.exists(PROGRESS_EXT_FILE):
        with open(PROGRESS_EXT_FILE) as f:
            done_ids = set(json.load(f).get("done", []))
        print(f"   断点续跑：已处理 {len(done_ids)} 首")

    # ── 查询全部外部歌曲（含各字段当前值，判断哪些需要补全） ──────
    engine = get_engine()
    with engine.connect() as c:
        songs_df = pd.read_sql("""
            SELECT id, title, artist,
                   release_year, album, duration, cover_image,
                   popularity, language, genre
            FROM songs
            WHERE kkbox_id IS NULL
            ORDER BY id
        """, c)

    # 过滤已全部填充的歌曲（即不需要任何更新的行）
    def _needs_any(row) -> bool:
        def _miss_num(v) -> bool:
            """数值型字段：NaN / None / 0 均视为缺失"""
            if v is None:
                return True
            try:
                import math
                return math.isnan(float(v)) or float(v) == 0
            except (TypeError, ValueError):
                return True

        def _miss_str(v) -> bool:
            """字符串型字段：NaN / None / 空串均视为缺失"""
            if v is None:
                return True
            try:
                import math
                if math.isnan(float(v)):
                    return True
            except (TypeError, ValueError):
                pass
            return not str(v).strip()

        return (
            _miss_num(row["release_year"])
            or _miss_str(row["album"])
            or _miss_num(row["duration"])
            or _miss_str(row["cover_image"])
            or _miss_num(row["popularity"])
            or _miss_str(row["language"])
            or _miss_str(row["genre"])
        )

    songs_to_process = songs_df[songs_df.apply(_needs_any, axis=1)]
    print(f"\n   外部歌曲总计: {len(songs_df):,} 首")
    print(f"   至少有一字段待补全: {len(songs_to_process):,} 首\n")
    if songs_to_process.empty:
        print("   🎉 所有外部歌曲元数据已完整，无需处理")
        return

    # ── 工具函数 ──────────────────────────────────
    def _valid_year(val) -> Optional[int]:
        try:
            y = int(str(val)[:4])
            return y if 1900 <= y <= 2030 else None
        except Exception:
            return None

    def _clean_str(val, max_len: int = 200) -> Optional[str]:
        """清理字符串，超长截断，空字符串返回 None"""
        if not val:
            return None
        s = str(val).strip()
        return s[:max_len] if s else None

    # ── 网易云 language 映射 ────────────────────────
    NE_LANG_MAP = {
        "zh": "国语", "zh-CN": "国语", "zh-TW": "国语", "cn": "国语",
        "yue": "粤语", "cantonese": "粤语",
        "en": "英语", "eng": "英语", "english": "英语",
        "ja": "日语", "jp": "日语", "japanese": "日语",
        "ko": "韩语", "kr": "韩语", "korean": "韩语",
        "fr": "法语", "de": "德语", "es": "西班牙语",
        "ru": "俄语", "it": "意大利语", "pt": "葡萄牙语",
    }

    def _map_ne_lang(raw) -> Optional[str]:
        if raw is None:
            return None
        s = str(raw).strip().lower()
        if not s:
            return None
        if s in NE_LANG_MAP:
            return NE_LANG_MAP[s]
        if any(u'\u4e00' <= c <= u'\u9fff' for c in s):
            return _clean_str(s, 10)
        return _clean_str(s, 10)

    # ── 网易云：获取歌曲全量元数据 ─────────────────
    async def _netease_fetch(client: "_httpx.AsyncClient",
                             title: str, artist: str) -> dict:
        """
        返回从网易云获取的字段 dict（只包含成功获取的字段）：
          release_year, album, duration, cover_image, popularity, language
        """
        result: dict = {}
        keyword = f"{artist} {title}"

        for path in NETEASE_SEARCH_PATHS:
            try:
                r = await client.get(
                    f"{NETEASE_BASE}{path}",
                    params={"keywords": keyword, "limit": 5},
                    timeout=6.0
                )
                if r.status_code != 200:
                    continue
                data = r.json()
                songs = (
                    data.get("result", {}).get("songs")
                    or data.get("data", {}).get("songs")
                    or []
                )
                if not songs:
                    continue
                s = songs[0]
                song_id = s.get("id")

                # ── 从搜索结果直接提取 ──
                al = s.get("al") or {}
                if al.get("name"):
                    result["album"] = _clean_str(al["name"], 200)
                if al.get("picUrl"):
                    result["cover_image"] = _clean_str(al["picUrl"], 200)
                if s.get("dt"):
                    ms = int(s["dt"])
                    if ms > 0:
                        result["duration"] = ms // 1000
                if s.get("pop") is not None:
                    result["popularity"] = max(0, min(100, int(s["pop"])))

                # publishTime → release_year
                pt = s.get("publishTime") or al.get("publishTime")
                if pt:
                    y = _valid_year(_dt.fromtimestamp(int(pt) / 1000).year)
                    if y:
                        result["release_year"] = y

                # language（搜索结果中可能直接有）
                lang_raw = s.get("language") or s.get("lang") or s.get("songLanguage")
                lm = _map_ne_lang(lang_raw)
                if lm:
                    result["language"] = lm

                # ── 若关键字段缺失，再调 detail 端点 ──
                need_detail = (
                    "release_year" not in result
                    or "album" not in result
                    or "duration" not in result
                    or "language" not in result
                )
                if need_detail and song_id:
                    for dpath in NETEASE_DETAIL_PATHS:
                        try:
                            rd = await client.get(
                                f"{NETEASE_BASE}{dpath}",
                                params={"ids": str(song_id)},
                                timeout=6.0
                            )
                            if rd.status_code != 200:
                                continue
                            d = rd.json()
                            ds_list = d.get("songs", [])
                            if not ds_list:
                                continue
                            ds = ds_list[0]
                            dal = ds.get("al") or {}

                            if "album" not in result and dal.get("name"):
                                result["album"] = _clean_str(dal["name"], 200)
                            if "cover_image" not in result and dal.get("picUrl"):
                                result["cover_image"] = _clean_str(dal["picUrl"], 200)
                            if "duration" not in result and ds.get("dt"):
                                ms = int(ds["dt"])
                                if ms > 0:
                                    result["duration"] = ms // 1000
                            if "popularity" not in result and ds.get("pop") is not None:
                                result["popularity"] = max(0, min(100, int(ds["pop"])))
                            if "release_year" not in result:
                                pt2 = dal.get("publishTime") or ds.get("publishTime")
                                if pt2:
                                    y = _valid_year(_dt.fromtimestamp(int(pt2) / 1000).year)
                                    if y:
                                        result["release_year"] = y
                            if "language" not in result:
                                dl = ds.get("language") or ds.get("lang") or ds.get("songLanguage")
                                dlm = _map_ne_lang(dl)
                                if dlm:
                                    result["language"] = dlm
                            break
                        except Exception:
                            continue

                # ── wiki/summary 补充 language（最后手段） ──
                if "language" not in result and song_id:
                    for wiki_path in ["/song/wiki/summary", "/netease/song/wiki/summary"]:
                        try:
                            rw = await client.get(
                                f"{NETEASE_BASE}{wiki_path}",
                                params={"id": str(song_id)},
                                timeout=6.0
                            )
                            if rw.status_code != 200:
                                continue
                            wd = rw.json()
                            blocks = wd.get("data", {}).get("blocks", [])
                            for blk in blocks:
                                for creative in blk.get("creatives", []):
                                    for res in creative.get("resources", []):
                                        ext = res.get("resourceExt", {})
                                        sd = ext.get("songData", {})
                                        wl = sd.get("language")
                                        wlm = _map_ne_lang(wl)
                                        if wlm:
                                            result["language"] = wlm
                                            break
                                    if "language" in result:
                                        break
                                if "language" in result:
                                    break
                            if "language" not in result:
                                wl2 = wd.get("data", {}).get("language")
                                wlm2 = _map_ne_lang(wl2)
                                if wlm2:
                                    result["language"] = wlm2
                            if "language" in result:
                                break
                        except Exception:
                            continue

                break   # 第一个可达的搜索 path 成功后退出
            except Exception:
                continue

        return result

    # ── QQ Music 直连配置 ──────────────────────────
    QQ_GENRE_MAP = {
        1: "Pop", 2: "Rock", 3: "Folk", 4: "Electronic",
        5: "Jazz", 6: "Classical", 7: "R&B", 8: "Hip-Hop",
        9: "Latin", 10: "Blues", 11: "Country", 12: "New Age",
        14: "World", 15: "Reggae", 19: "Light Music",
        20: "Soundtrack", 21: "Opera", 22: "Punk",
        24: "Metal", 25: "Ballad",
    }
    QQ_SEARCH_URL = "https://c.y.qq.com/splcloud/fcgi-bin/smartbox_new.fcg"
    QQ_DETAIL_URL = "https://u.y.qq.com/cgi-bin/musicu.fcg"

    # ── QQ Music：HTTP 直连查询（绕过 qqmusic_api 库） ───
    async def _qq_fetch(client: "_httpx.AsyncClient",
                        title: str, artist: str) -> dict:
        result: dict = {}
        keyword = f"{artist} {title}"
        try:
            # Step 1: 快速搜索获取 mid
            r1 = await client.get(QQ_SEARCH_URL, params={"key": keyword}, timeout=8.0)
            if r1.status_code != 200:
                return result
            items = r1.json().get("data", {}).get("song", {}).get("itemlist", [])
            if not items:
                return result
            mid = items[0].get("mid", "")
            if not mid:
                return result

            # Step 2: 用 mid 获取详情
            detail_req = {
                "songinfo": {
                    "method": "get_song_detail_yqq",
                    "module": "music.pf_song_detail_svr",
                    "param": {"song_mid": mid},
                }
            }
            r2 = await client.get(
                QQ_DETAIL_URL,
                params={"data": json.dumps(detail_req, ensure_ascii=False)},
                timeout=8.0,
            )
            if r2.status_code != 200:
                return result
            info = r2.json().get("songinfo", {}).get("data", {}).get("track_info", {})
            if not info:
                return result

            pub = info.get("time_public", "")
            if pub:
                y = _valid_year(pub)
                if y:
                    result["release_year"] = y

            al = info.get("album") or {}
            if al.get("name"):
                result["album"] = _clean_str(al["name"], 200)

            pmid = al.get("pmid") or al.get("mid")
            if pmid:
                result["cover_image"] = f"https://y.gtimg.cn/music/photo_new/T002R300x300M000{pmid}.jpg"

            interval = info.get("interval")
            if interval and int(interval) > 0:
                result["duration"] = int(interval)

            lang = info.get("language")
            if lang is not None:
                lang_str = str(lang).strip()
                mapped = QQ_LANG_MAP.get(lang_str)
                if mapped:
                    result["language"] = mapped

            genre_val = info.get("genre")
            if genre_val is not None:
                if isinstance(genre_val, int) and genre_val in QQ_GENRE_MAP:
                    result["genre"] = QQ_GENRE_MAP[genre_val]
        except Exception:
            pass
        return result

    # ── NaN/空值判断工具（主循环外定义，避免重复创建） ─────
    import math as _math

    def _db_miss_num(v) -> bool:
        if v is None: return True
        try: return _math.isnan(float(v)) or float(v) == 0
        except Exception: return True

    def _db_miss_str(v) -> bool:
        if v is None: return True
        try:
            if _math.isnan(float(v)): return True
        except Exception: pass
        return not str(v).strip()

    # ── 并发参数 ─────────────────────────────────────
    # 网易云：max 5 并发 + 每次请求后 sleep 1s（占着信号量期间休眠，有效控制速率）
    # QQ：max 5 并发，无额外 sleep
    NE_CONCURRENCY = 5
    NE_SLEEP       = 1.0
    QQ_CONCURRENCY = 5

    # ── 写 DB 工具 ────────────────────────────────────
    async def _apply_update(data: dict, row, conn, conn_lock: "asyncio.Lock") -> list:
        """
        将 API 返回的 data 中、DB 当前仍缺失的字段写入 DB。
        返回实际写入的字段名列表。
        """
        to_update: dict = {}
        for field, new_val in data.items():
            if new_val is None:
                continue
            cur_val = row.get(field)
            if field in ("release_year", "duration", "popularity"):
                if _db_miss_num(cur_val):
                    to_update[field] = new_val
            else:
                if _db_miss_str(cur_val):
                    to_update[field] = new_val

        if to_update:
            set_clause = ", ".join(f"`{f}` = %s" for f in to_update)
            vals = list(to_update.values()) + [int(row["id"])]
            async with conn_lock:
                with conn.cursor() as cur:
                    cur.execute(f"UPDATE songs SET {set_clause} WHERE id = %s", vals)
                conn.commit()
        return list(to_update.keys())

    # ── 单 API 工作器 ─────────────────────────────────
    async def _ne_worker(client: "_httpx.AsyncClient",
                         rows: list,
                         ne_sem: "asyncio.Semaphore",
                         conn, conn_lock: "asyncio.Lock",
                         pbar, field_hits: dict, source_hits: dict) -> list:
        """
        用网易云处理一批歌曲。
        - sleep 在 sem 持有期间，限制 NE 速率（避免 405）。
        - 返回未命中的 row 列表，等待 QQ fallback。
        """
        misses = []

        async def _one(row):
            song_id = int(row["id"])
            title   = str(row["title"]  or "").strip()
            artist  = str(row["artist"] or "").strip()
            if not title:
                done_ids.add(song_id)
                pbar.update(1)
                return

            async with ne_sem:
                data = await _netease_fetch(client, title, artist)
                await asyncio.sleep(NE_SLEEP)   # 持锁等待，控制速率

            done_ids.add(song_id)
            pbar.update(1)

            if data:
                written = await _apply_update(data, row, conn, conn_lock)
                for f in written:
                    if f in field_hits:
                        field_hits[f] += 1
                source_hits["网易云"] += 1
            else:
                misses.append(row)

        await asyncio.gather(*[_one(r) for r in rows], return_exceptions=True)
        return misses

    async def _qq_worker(rows: list,
                         qq_sem: "asyncio.Semaphore",
                         conn, conn_lock: "asyncio.Lock",
                         pbar, field_hits: dict, source_hits: dict,
                         label: str = "QQ") -> list:
        """
        用 QQ Music 处理一批歌曲。
        - 返回未命中的 row 列表，等待 NE fallback。
        """
        misses = []

        async def _one(row):
            song_id = int(row["id"])
            title   = str(row["title"]  or "").strip()
            artist  = str(row["artist"] or "").strip()
            if not title:
                done_ids.add(song_id)
                pbar.update(1)
                return

            async with qq_sem:
                data = await _qq_fetch(title, artist)

            done_ids.add(song_id)
            pbar.update(1)

            if data:
                written = await _apply_update(data, row, conn, conn_lock)
                for f in written:
                    if f in field_hits:
                        field_hits[f] += 1
                source_hits[label] += 1
            else:
                misses.append(row)

        await asyncio.gather(*[_one(r) for r in rows], return_exceptions=True)
        return misses

    # ── 主协调器 ──────────────────────────────────────
    async def _run_all():
        field_hits  = {f: 0 for f in ("release_year","album","duration",
                                       "cover_image","popularity","language","genre")}
        source_hits = {"网易云": 0, "QQ": 0, "NE-fallback": 0, "QQ-fallback": 0, "miss": 0}

        ne_sem    = asyncio.Semaphore(NE_CONCURRENCY)
        qq_sem    = asyncio.Semaphore(QQ_CONCURRENCY)
        conn_lock = asyncio.Lock()
        conn      = get_conn()

        try:
            speed_up_mysql(conn)
            async with _httpx.AsyncClient() as client:
                pending_rows = [
                    row for _, row in songs_to_process.iterrows()
                    if int(row["id"]) not in done_ids
                ]
                total = len(pending_rows)

                # 交错分组：偶数索引 → 网易云，奇数索引 → QQ
                ne_batch = pending_rows[0::2]
                qq_batch = pending_rows[1::2]

                print(f"\n   Pass 1 — 网易云处理 {len(ne_batch):,} 首，"
                      f"QQ 处理 {len(qq_batch):,} 首（双轨并行）")
                pbar1 = tqdm(total=total, desc="Pass-1 双轨并行")

                ne_args = (client, ne_batch, ne_sem, conn, conn_lock,
                           pbar1, field_hits, source_hits)
                qq_args = (qq_batch, qq_sem, conn, conn_lock,
                           pbar1, field_hits, source_hits)

                ne_misses, qq_misses = await asyncio.gather(
                    _ne_worker(*ne_args),
                    _qq_worker(*qq_args),
                )
                pbar1.close()
                _save_checkpoint()

                print(f"\n   Pass 1 完成: NE 未命中 {len(ne_misses):,} 首，"
                      f"QQ 未命中 {len(qq_misses):,} 首")

                # Pass 2：交换 API，对未命中做 fallback
                total2 = len(ne_misses) + len(qq_misses)
                if total2:
                    print(f"   Pass 2 — fallback 补搜 {total2:,} 首（双轨并行）")
                    pbar2 = tqdm(total=total2, desc="Pass-2 fallback")

                    ne_fb_args = (client, qq_misses, ne_sem, conn, conn_lock,
                                  pbar2, field_hits, {"网易云": 0,
                                                       "NE-fallback": source_hits["NE-fallback"]})
                    qq_fb_args = (ne_misses, qq_sem, conn, conn_lock,
                                  pbar2, field_hits, {"QQ": 0,
                                                       "QQ-fallback": source_hits["QQ-fallback"]},
                                  "QQ-fallback")

                    # NE 处理 QQ 的 miss；QQ 处理 NE 的 miss
                    still_ne_miss, still_qq_miss = await asyncio.gather(
                        _ne_worker(client, qq_misses, ne_sem, conn, conn_lock,
                                   pbar2, field_hits,
                                   {"网易云": source_hits["NE-fallback"]}),
                        _qq_worker(ne_misses, qq_sem, conn, conn_lock,
                                   pbar2, field_hits,
                                   {"QQ": source_hits["QQ-fallback"]},
                                   "QQ-fallback"),
                    )
                    pbar2.close()
                    _save_checkpoint()

                    final_miss = len(still_ne_miss) + len(still_qq_miss)
                    source_hits["miss"] = final_miss
                    print(f"   Pass 2 完成: 最终仍未命中 {final_miss:,} 首")
                else:
                    print("   无需 Pass 2")

        finally:
            _save_checkpoint()
            restore_mysql(conn)
            conn.close()

        total_updated = sum(field_hits.values())
        print(f"\n   补全结果汇总:")
        print(f"   实际写入字段次数: {total_updated:,}")
        print(f"   未命中（两轮皆无）: {source_hits['miss']:,} 首")
        print(f"\n   数据来源分布:")
        print(f"     NE  Pass-1  命中: {source_hits['网易云']:,} 首")
        print(f"     QQ  Pass-1  命中: {source_hits['QQ']:,} 首")
        print(f"     NE  Pass-2 fallback: {source_hits['NE-fallback']:,} 首")
        print(f"     QQ  Pass-2 fallback: {source_hits['QQ-fallback']:,} 首")
        print(f"\n   各字段补全数量:")
        for f, cnt in field_hits.items():
            print(f"     {f:<16}: {cnt:,}")

    def _save_checkpoint():
        with open(PROGRESS_EXT_FILE, "w") as pf:
            json.dump({"done": list(done_ids)}, pf)

    asyncio.run(_run_all())
    print("\n✅ enrich_external 步骤完成")


# 保留旧名称作为别名（向后兼容）
def step_release_year():
    """旧名称兼容入口，调用 step_enrich_external()"""
    step_enrich_external()


# ============================================================
# --step musicbrainz : MusicBrainz API 补全外部歌曲 origin_country
# ============================================================
def step_musicbrainz():
    """
    通过 MusicBrainz API 为外部歌曲（kkbox_id IS NULL）补全 origin_country。
    限速：1 req/sec，支持断点续跑（progress 保存在 musicbrainz_progress.json）。
    预计时间：10000 首 ≈ 3 小时。
    """
    print_sep()
    print("🌐 [Step: musicbrainz] MusicBrainz API 补全外部歌曲 origin_country")
    print_sep()

    try:
        import musicbrainzngs
        musicbrainzngs.set_useragent(*MB_USER_AGENT.split(" ", 1))
    except ImportError:
        print("❌ musicbrainzngs 库未安装")
        print("   请运行：pip install musicbrainzngs")
        return

    # 加载已处理进度
    processed_ids = set()
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r") as f:
            processed_ids = set(json.load(f).get("done", []))
        print(f"   📌 断点续跑：已处理 {len(processed_ids)} 首，继续...")
    else:
        print("   📌 首次运行，从头开始")

    # 查询需要处理的外部歌曲
    engine = get_engine()
    with engine.connect() as c:
        songs_df = pd.read_sql("""
            SELECT id, title, artist
            FROM songs
            WHERE kkbox_id IS NULL
              AND (origin_country IS NULL OR origin_country = 'XX')
            ORDER BY id
        """, c)
    print(f"\n   需要处理的外部歌曲: {len(songs_df):,} 首")

    conn = get_conn()
    try:
        speed_up_mysql(conn)
        batch_updates = []
        save_interval = 100   # 每 100 首保存一次进度

        for idx, row in tqdm(songs_df.iterrows(), total=len(songs_df),
                             desc="MusicBrainz 查询"):
            song_id = int(row["id"])
            if song_id in processed_ids:
                continue

            title  = str(row["title"]).strip()
            artist = str(row["artist"]).strip()
            country = None

            try:
                # 搜索 release（release 有 country 字段）
                result = musicbrainzngs.search_releases(
                    artist=artist[:50], release=title[:50], limit=3
                )
                releases = result.get("release-list", [])
                for release in releases:
                    c_code = release.get("country")
                    if c_code and len(c_code) == 2 and c_code.isalpha():
                        country = c_code.upper()
                        break

            except musicbrainzngs.WebServiceError as e:
                if "503" in str(e):
                    print(f"\n⚠️  MusicBrainz 限速（503），等待 5 秒...")
                    time.sleep(5)
                # else: 其他错误，跳过该歌曲
            except Exception:
                pass

            if not country:
                country = "XX"

            batch_updates.append((country, song_id))
            processed_ids.add(song_id)

            # 按批次写入数据库
            if len(batch_updates) >= BATCH_SIZE:
                with conn.cursor() as cur:
                    cur.executemany(
                        "UPDATE songs SET origin_country=%s WHERE id=%s",
                        batch_updates
                    )
                conn.commit()
                batch_updates = []

            # 保存进度
            if len(processed_ids) % save_interval == 0:
                with open(PROGRESS_FILE, "w") as f:
                    json.dump({"done": list(processed_ids)}, f)

            # 限速：1 req/sec
            time.sleep(MB_RATE_LIMIT)

        # 写入剩余批次
        if batch_updates:
            with conn.cursor() as cur:
                cur.executemany(
                    "UPDATE songs SET origin_country=%s WHERE id=%s",
                    batch_updates
                )
            conn.commit()

        # 保存最终进度
        with open(PROGRESS_FILE, "w") as f:
            json.dump({"done": list(processed_ids), "completed": True}, f)

    finally:
        restore_mysql(conn)
        conn.close()

    print("\n✅ musicbrainz 步骤完成")
    print(f"   进度文件: {PROGRESS_FILE}")
    print("   提示：完成后可删除 musicbrainz_progress.json")


# ============================================================
# --step users : 更新 users 表
# ============================================================
def step_users():
    """
    更新 users 表：
      1. jf  : bd=25, city='广州', gender='male'
      2. jf2 : bd=25, city='广州', gender='female'
      3. kkbox_% 用户: 从 members.csv 更新 bd, city, gender, create_time
    """
    print_sep()
    print("👤 [Step: users] 更新 users 表")
    print_sep()

    conn = get_conn()
    try:
        # ── 1. 更新 jf / jf2
        print("\n  更新 jf 用户信息 ...")
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE users SET bd=25, city='广州', gender='male'
                WHERE username='jf'
            """)
            print(f"   ✅ jf: 影响 {cur.rowcount} 行（bd=25, city=广州, gender=male）")
        conn.commit()

        with conn.cursor() as cur:
            cur.execute("""
                UPDATE users SET bd=25, city='广州', gender='female'
                WHERE username='jf2'
            """)
            print(f"   ✅ jf2: 影响 {cur.rowcount} 行（bd=25, city=广州, gender=female）")
        conn.commit()

        # ── 2. 从 members.csv 更新 kkbox_% 用户
        print("\n  读取 members.csv ...")
        if not os.path.exists(MEMBERS_CSV):
            print(f"   ❌ 文件不存在: {MEMBERS_CSV}")
            return

        members_df = pd.read_csv(
            MEMBERS_CSV,
            dtype={"msno": str, "city": str, "gender": str, "bd": str,
                   "registration_init_time": str},
            usecols=["msno", "city", "gender", "bd", "registration_init_time"]
        )
        print(f"   共 {len(members_df):,} 条 members 记录")

        # 处理 bd（年龄）：过滤异常值（0 或 >100）
        members_df["bd_clean"] = pd.to_numeric(members_df["bd"], errors="coerce")
        members_df["bd_clean"] = members_df["bd_clean"].where(
            (members_df["bd_clean"] > 0) & (members_df["bd_clean"] <= 100), None
        )

        # 处理 registration_init_time（YYYYMMDD → DATE）
        def parse_reg_date(s):
            try:
                s = str(int(float(str(s).strip())))
                return datetime.strptime(s, "%Y%m%d").date()
            except Exception:
                return None

        members_df["create_date"] = members_df["registration_init_time"].apply(parse_reg_date)

        # 处理 gender（'' → NULL）
        members_df["gender_clean"] = members_df["gender"].where(
            members_df["gender"].isin(["male", "female"]), None
        )

        # KKBOX msno 是单向哈希，无法还原。
        # 但导入时按 members.csv 行顺序赋予 kkbox_000001/000002/...
        # 因此 kkbox_NNNNNN 对应 members.csv 第 N-1 行（0-based）。
        print("  查询 kkbox 用户（按 id 排序以还原位置映射）...")
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, CAST(SUBSTRING(username, 7) AS UNSIGNED) AS seq "
                "FROM users WHERE username LIKE 'kkbox_%' ORDER BY id"
            )
            kkbox_rows = cur.fetchall()   # [(user_id, seq_1based), ...]
        print(f"   数据库中 kkbox 用户: {len(kkbox_rows):,} 个")

        members_df = members_df.reset_index(drop=True)   # 确保 0-based integer index

        # 准备批量更新数据（按位置匹配）
        updates = []
        for (user_id, seq) in kkbox_rows:
            row_idx = int(seq) - 1
            if row_idx < 0 or row_idx >= len(members_df):
                continue
            row = members_df.iloc[row_idx]
            bd_val      = int(row["bd_clean"]) if pd.notna(row["bd_clean"]) else None
            city_val    = str(row["city"])     if pd.notna(row["city"])     else None
            gender_val  = row["gender_clean"]  if pd.notna(row["gender_clean"]) else None
            date_val    = row["create_date"]

            updates.append((bd_val, city_val, gender_val, date_val, user_id))

        print(f"  需要更新的 kkbox 用户: {len(updates):,} 个")
        print(f"  批量更新（{BATCH_SIZE} 个/批）...")

        update_sql = """
            UPDATE users SET
              bd          = COALESCE(%s, bd),
              city        = COALESCE(%s, city),
              gender      = COALESCE(%s, gender),
              create_time = COALESCE(%s, create_time)
            WHERE id = %s
        """
        speed_up_mysql(conn)
        with conn.cursor() as cur:
            for i in tqdm(range(0, len(updates), BATCH_SIZE), desc="  更新 users"):
                cur.executemany(update_sql, updates[i:i+BATCH_SIZE])
                if i % (BATCH_SIZE * 5) == 0:
                    conn.commit()
        conn.commit()
        print(f"   ✅ kkbox 用户信息更新完成")

    finally:
        restore_mysql(conn)
        conn.close()

    # 统计
    engine = get_engine()
    with engine.connect() as c:
        stats = pd.read_sql("""
            SELECT
              SUM(bd IS NOT NULL) AS has_bd,
              SUM(gender IS NOT NULL) AS has_gender,
              SUM(city IS NOT NULL) AS has_city,
              COUNT(*) AS total
            FROM users
            WHERE username LIKE 'kkbox_%%'
        """, c).iloc[0]
    print(f"\n📊 kkbox 用户更新后统计 (共 {int(stats['total']):,} 人):")
    print(f"   bd 填充率: {int(stats['has_bd']):,} ({100*stats['has_bd']/stats['total']:.1f}%)")
    print(f"   gender 填充率: {int(stats['has_gender']):,} ({100*stats['has_gender']/stats['total']:.1f}%)")
    print(f"   city 填充率: {int(stats['has_city']):,} ({100*stats['has_city']/stats['total']:.1f}%)")

    print("\n✅ users 步骤完成")


# ============================================================
# --step play_history : 回填 target + source_channel
# ============================================================
def step_play_history():
    """
    从 train.csv 回填 play_history.target 和 play_history.source_channel。
    同时为 jf/jf2 用户：
      - source_channel = 'EXTERNAL'
      - target = 根据 30 天内重复收听规则计算

    处理量：7.37M 行，预计 60-90 分钟。
    """
    print_sep()
    print("📊 [Step: play_history] 回填 target + source_channel")
    print_sep()

    conn   = get_conn()
    engine = get_engine()

    try:
        # ── 1. 构建 msno → user_id 映射
        print("\n  构建 msno → user_id 映射 ...")
        with conn.cursor() as cur:
            cur.execute("SELECT id, SUBSTRING(username, 7) AS msno FROM users "
                        "WHERE username LIKE 'kkbox_%'")
            msno_to_uid = {row[1]: row[0] for row in cur.fetchall()}
        print(f"   kkbox 用户: {len(msno_to_uid):,} 个")

        # ── 2. 构建 kkbox_song_id → songs.id 映射
        print("  构建 kkbox_song_id → songs.id 映射（229万行，约需30秒）...")
        with conn.cursor() as cur:
            cur.execute("SELECT id, kkbox_id FROM songs WHERE kkbox_id IS NOT NULL")
            kkbox_to_sid = {row[1]: row[0] for row in cur.fetchall()}
        print(f"   KKBOX 歌曲: {len(kkbox_to_sid):,} 首")

        # ── 3. 处理 jf/jf2 用户
        print("\n  处理 jf/jf2 用户 source_channel = EXTERNAL ...")
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM users WHERE username IN ('jf', 'jf2')")
            jf_ids = [row[0] for row in cur.fetchall()]

        if jf_ids:
            placeholders = ",".join(["%s"] * len(jf_ids))
            with conn.cursor() as cur:
                cur.execute(
                    f"UPDATE play_history SET source_channel='EXTERNAL' "
                    f"WHERE user_id IN ({placeholders}) AND source_channel IS NULL",
                    jf_ids
                )
                print(f"   ✅ jf/jf2 source_channel 更新: {cur.rowcount} 行")
            conn.commit()

            # 计算 jf/jf2 target（30天内重复收听）
            print("  计算 jf/jf2 target（30天内重复收听规则）...")
            for uid in jf_ids:
                # 标记有重复收听的记录 target=1
                with conn.cursor() as cur:
                    cur.execute(f"""
                        UPDATE play_history ph1
                        JOIN (
                            SELECT DISTINCT ph2.song_id
                            FROM play_history ph2
                            WHERE ph2.user_id = {uid}
                            GROUP BY ph2.song_id
                            HAVING COUNT(*) > 1
                        ) repeated ON ph1.song_id = repeated.song_id
                        SET ph1.target = 1
                        WHERE ph1.user_id = {uid} AND ph1.target IS NULL
                    """)
                conn.commit()
                # 其余标记为 0
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE play_history SET target=0 "
                        "WHERE user_id=%s AND target IS NULL", (uid,)
                    )
                conn.commit()
            print(f"   ✅ jf/jf2 target 计算完成")

        # ── 4. 从 train.csv 回填 KKBOX 用户的 target + source_channel
        print(f"\n  读取 train.csv（约7.37M行，可能需要几分钟）...")
        if not os.path.exists(TRAIN_CSV):
            print(f"   ❌ 文件不存在: {TRAIN_CSV}")
            return

        speed_up_mysql(conn)

        chunk_size = 500_000
        total_updated = 0
        total_rows    = 0

        # 预统计行数（用于进度条）
        print("  统计 train.csv 行数...")
        with open(TRAIN_CSV, "r") as f:
            total_lines = sum(1 for _ in f) - 1  # 减去 header
        print(f"   train.csv 共 {total_lines:,} 行")

        update_sql = ("UPDATE play_history SET target=%s, source_channel=%s "
                      "WHERE user_id=%s AND song_id=%s AND target IS NULL")

        pbar = tqdm(total=total_lines, desc="  回填 play_history", unit="行")

        for chunk in pd.read_csv(
            TRAIN_CSV,
            dtype={"msno": str, "song_id": str,
                   "source_system_tab": str, "source_screen_name": str,
                   "source_type": str, "target": int},
            chunksize=chunk_size,
            low_memory=True,
        ):
            total_rows += len(chunk)
            pbar.update(len(chunk))

            # 映射 user_id 和 song_id
            chunk["user_id"] = chunk["msno"].map(msno_to_uid)
            chunk["db_song_id"] = chunk["song_id"].map(kkbox_to_sid)

            # 过滤无法映射的行
            valid = chunk.dropna(subset=["user_id", "db_song_id"])
            if valid.empty:
                continue

            # 计算 source_channel
            valid = valid.copy()
            valid["source_channel"] = valid.apply(
                lambda r: map_source_channel(
                    r.get("source_type", ""),
                    r.get("source_system_tab", ""),
                    r.get("source_screen_name", "")
                ),
                axis=1
            )

            # 构建更新参数列表
            updates = [
                (int(r["target"]),
                 r["source_channel"],
                 int(r["user_id"]),
                 int(r["db_song_id"]))
                for _, r in valid.iterrows()
            ]

            # 分批 executemany
            with conn.cursor() as cur:
                for i in range(0, len(updates), BATCH_SIZE):
                    cur.executemany(update_sql, updates[i:i+BATCH_SIZE])
            conn.commit()
            total_updated += len(updates)

        pbar.close()

        print(f"\n   train.csv 共处理: {total_rows:,} 行")
        print(f"   成功映射并更新: {total_updated:,} 行")

        # 统计结果
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM play_history WHERE target IS NOT NULL")
            has_target = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM play_history WHERE source_channel IS NOT NULL")
            has_channel = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM play_history")
            total = cur.fetchone()[0]

        print(f"\n📊 play_history 回填统计 (共 {total:,} 行):")
        print(f"   target 填充率: {has_target:,} ({100*has_target/total:.1f}%)")
        print(f"   source_channel 填充率: {has_channel:,} ({100*has_channel/total:.1f}%)")

    finally:
        restore_mysql(conn)
        conn.close()

    print("\n✅ play_history 步骤完成")


# ============================================================
# 主入口
# ============================================================
def main():
    parser = argparse.ArgumentParser(
        description="enrich_db.py — 数据库字段扩充主脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
执行顺序（请按序手动执行）：
  1. python test_api_composer.py
  2. python enrich_db.py --step alter [--add-composer]
  3. python enrich_db.py --step songs
  4. python enrich_db.py --step musicbrainz
  5. python enrich_db.py --step users
  6. python enrich_db.py --step play_history
  7. python enrich_db.py --step enrich_external   ← 补全外部歌曲全量元数据（需先启动网易云 Node.js 服务）
        """
    )
    parser.add_argument(
        "--step",
        required=True,
        choices=["alter", "songs", "musicbrainz", "users", "play_history",
                 "enrich_external", "release_year"],
        help="执行哪个步骤"
    )
    parser.add_argument(
        "--add-composer",
        action="store_true",
        default=False,
        help="在 alter 步骤中同时新增 composer/lyricist 列（需 test_api_composer.py 确认可行）"
    )
    args = parser.parse_args()

    print(f"\n🚀 enrich_db.py — step: {args.step}")
    print(f"   时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    if args.step == "alter":
        step_alter(add_composer=args.add_composer)
    elif args.step == "songs":
        step_songs()
    elif args.step == "musicbrainz":
        step_musicbrainz()
    elif args.step == "users":
        step_users()
    elif args.step == "play_history":
        step_play_history()
    elif args.step in ("enrich_external", "release_year"):
        step_enrich_external()

    print(f"\n🏁 完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
