# -*- coding: utf-8 -*-
"""
enrich_db.py — 数据库字段扩充主脚本（一次性执行）

功能（按 --step 参数分阶段执行）：
  --step alter        : 新增字段（play_history.target, source_channel, users.bd, songs.origin_country）
  --step songs        : songs 表批量补全（ISRC→release_year+origin_country, 语言代码→标签, genre规范化）
  --step musicbrainz  : 通过 MusicBrainz API 为外部歌曲补全 origin_country（支持断点续跑）
  --step users        : 更新 users 表（jf/jf2信息, kkbox_%用户 create_time/bd/city/gender）
  --step play_history : 回填 play_history.target + source_channel（7.37M行，分批5000）

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
        # 构建 CASE WHEN
        case_clauses = "\n    ".join(
            f"WHEN '{code}' THEN '{label}'"
            for code, label in KKBOX_LANG_MAP.items()
        )
        lang_sql = f"""
            UPDATE songs
            SET language = CASE language
                {case_clauses}
                ELSE '其他'
            END
            WHERE kkbox_id IS NOT NULL
              AND language REGEXP '^-?[0-9]+$'
        """
        with conn.cursor() as cur:
            cur.execute(lang_sql)
            affected = cur.rowcount
        conn.commit()
        print(f"   ✅ 更新 {affected:,} 行 language")

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

        # 查询数据库中 kkbox 用户：{msno: user_id}
        print("  查询 kkbox 用户映射 ...")
        with conn.cursor() as cur:
            cur.execute("SELECT id, SUBSTRING(username, 7) AS msno FROM users "
                        "WHERE username LIKE 'kkbox_%'")
            kkbox_users = {row[1]: row[0] for row in cur.fetchall()}
        print(f"   数据库中 kkbox 用户: {len(kkbox_users):,} 个")

        # 准备批量更新数据
        updates = []
        for _, row in members_df.iterrows():
            msno = row["msno"]
            if msno not in kkbox_users:
                continue
            user_id = kkbox_users[msno]
            bd_val      = int(row["bd_clean"]) if pd.notna(row["bd_clean"]) else None
            city_val    = str(row["city"]) if pd.notna(row["city"]) else None
            gender_val  = row["gender_clean"] if pd.notna(row["gender_clean"]) else None
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
        """
    )
    parser.add_argument(
        "--step",
        required=True,
        choices=["alter", "songs", "musicbrainz", "users", "play_history"],
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

    print(f"\n🏁 完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
