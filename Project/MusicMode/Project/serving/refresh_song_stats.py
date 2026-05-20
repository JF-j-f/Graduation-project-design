# -*- coding: utf-8 -*-
"""
refresh_song_stats.py — 歌曲滚动统计物化刷新脚本

功能：
  1. 从 play_history 读取 song_id + play_time
  2. 用 pandas 向量化聚合 cnt_7d / cnt_30d / total_plays / trending
  3. 结果批量写入 MySQL song_rolling_stats（持久化）
  4. 同步写入 Redis（hash + version key，TTL=25h）

触发时机：
  - 每次重训模型后运行一次
  - 或每天凌晨定时运行

设计说明（物化视图 + Redis 缓存）：
  - MySQL GROUP BY 在 737 万行无索引列上需 15 分钟+，不可用于在线
  - pandas 向量化聚合同量数据
  - Redis 读取：< 0.1s（亚毫秒），sync_recs_v3.py 强制要求 Redis 最新才允许推荐
  - sync_recs_v3.py 通过 song_rolling:version 与 MySQL MAX(updated_at) 对比
    验证 Redis 新鲜度，不一致则终止并提示重新运行本脚本

开发者：JunFu
"""

import os
import sys
import math
import time
import subprocess
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pymysql
import redis

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ============================================================
# 配置
# ============================================================

# MySQL 连接配置（从 secrets.txt 读取）
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from config_loader import get_mysql_config
_db_cfg        = get_mysql_config()
MYSQL_HOST     = _db_cfg["host"]
MYSQL_PORT     = _db_cfg["port"]
MYSQL_DB       = _db_cfg["db"]
MYSQL_USER     = _db_cfg["user"]
MYSQL_PASSWORD = _db_cfg["password"]

REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", "6379"))
REDIS_DB   = 0
REDIS_TTL        = 90000   # 单位秒，约 25 小时（保证每天定时刷新一次时，旧数据不会过期）
MYSQL_BATCH_SIZE = 5000    # MySQL executemany 每批行数

# ============================================================
# Redis 启停辅助
# ============================================================

_REDIS_PROC = None   # 记录由本脚本启动的 redis-server 进程


def _ensure_redis_running():
    """
    确保 Redis 运行中，返回 (redis连接, 是否由本进程启动)。
      - 已运行 → 打印提示，直接返回连接
      - 未运行 → 自动启动 redis-server，等待就绪后返回连接
    """
    global _REDIS_PROC
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB,
                    decode_responses=True, socket_connect_timeout=1)
    try:
        r.ping()
        print("   ✅ Redis 服务已启动")
        return r, False
    except Exception:
        pass

    print("   ⏳ Redis 未运行，正在启动 redis-server ...")
    _REDIS_PROC = subprocess.Popen(
        ["redis-server", "--save", ""],   # 禁用 RDB 持久化，纯缓存模式
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    for _ in range(20):       # 最多等待 10 秒
        time.sleep(0.5)
        try:
            r.ping()
            print("   ✅ Redis 启动成功")
            return r, True
        except Exception:
            pass
    raise SystemExit("❌ Redis 启动超时（10s），请检查 redis-server 是否在 PATH 中")


def _shutdown_redis():
    """写入完成后立即关闭 Redis（仅关闭由本脚本启动的实例）"""
    global _REDIS_PROC
    if _REDIS_PROC and _REDIS_PROC.poll() is None:
        try:
            redis.Redis(host=REDIS_HOST, port=REDIS_PORT).shutdown(nosave=True)
        except Exception:
            _REDIS_PROC.terminate()
        _REDIS_PROC = None
        print("   ✅ Redis 服务已关闭")


_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS song_rolling_stats (
    song_id     INT   NOT NULL,
    cnt_7d      INT   NOT NULL DEFAULT 0,
    cnt_30d     INT   NOT NULL DEFAULT 0,
    trending    FLOAT NOT NULL DEFAULT 1.0,
    total_plays INT   NOT NULL DEFAULT 0,
    updated_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                          ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (song_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""

# ============================================================
# Step 1：建表（仅首次执行）
# ============================================================

def ensure_table(conn):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_schema = %s AND table_name = 'song_rolling_stats'",
            (MYSQL_DB,)
        )
        if cur.fetchone()[0] > 0:
            print("   ✅ song_rolling_stats 表已存在，跳过建表")
        else:
            cur.execute(_CREATE_TABLE_SQL)
            conn.commit()
            print("   ✅ song_rolling_stats 建表完成")


# ============================================================
# Step 2/3：pandas 聚合
# ============================================================

def compute_stats():
    """
    从 MySQL 读取 play_history 的 song_id + play_time（仅 2 列），
    用 pandas 向量化聚合出 cnt_7d / cnt_30d / total_plays / trending。
    """
    from sqlalchemy import create_engine, text

    engine = create_engine(
        f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}"
        f"@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}?charset=utf8mb4",
        pool_pre_ping=True,
    )

    print("   ⏳ 从 MySQL 读取 play_history（song_id, play_time）...")
    t0 = time.time()
    df = pd.read_sql(
        "SELECT song_id, play_time FROM play_history",
        con=engine,
        parse_dates=["play_time"],
    )
    engine.dispose()
    print(f"   ✅ 读取完成：{len(df):,} 行，耗时 {time.time()-t0:.1f}s")

    print("   ⏳ pandas 向量化聚合...")
    t1 = time.time()
    today = pd.Timestamp(date.today())
    df["is_7d"]  = (df["play_time"] >= today - timedelta(days=7)).astype("int32")
    df["is_30d"] = (df["play_time"] >= today - timedelta(days=30)).astype("int32")

    #向量化聚合
    agg = df.groupby("song_id", sort=False).agg(
        cnt_7d      = ("is_7d",    "sum"),  # 近7天播放次数
        cnt_30d     = ("is_30d",   "sum"),  # 近30天播放次数
        total_plays = ("song_id",  "count"), # 总播放次数
    ).reset_index()

    # trending_ratio = 近7天日均 / 近30天日均（衡量是否"正在变火"）
    agg["trending"] = (
        (agg["cnt_7d"].astype("float64") + 1.0)
        / (agg["cnt_30d"].astype("float64") / 30.0 + 1.0)
    )
    agg["cnt_7d"]      = agg["cnt_7d"].astype("int32")
    agg["cnt_30d"]     = agg["cnt_30d"].astype("int32")
    agg["total_plays"] = agg["total_plays"].astype("int32")
    agg["trending"]    = agg["trending"].astype("float32")

    print(f"   ✅ 聚合完成：{len(agg):,} 首歌曲，耗时 {time.time()-t1:.1f}s")
    return agg


# ============================================================
# Step 4：写入 MySQL
# ============================================================

def write_to_mysql(agg, conn):
    """批量写入 song_rolling_stats（DELETE + INSERT，保证数据一致性）"""
    print("   ⏳ 写入 MySQL song_rolling_stats ...")
    t0 = time.time()

    rows = [
        (int(r.song_id), int(r.cnt_7d), int(r.cnt_30d),
         float(r.trending), int(r.total_plays))
        for r in agg.itertuples(index=False)
    ]

    with conn.cursor() as cur:
        # DELETE 替代 TRUNCATE：保持事务原子性
        # TRUNCATE 是 DDL，执行后隐式提交，后续 INSERT 失败时无法回滚；
        # DELETE 属于 DML，与后续 INSERT 处于同一事务，失败可整体回滚
        cur.execute("DELETE FROM song_rolling_stats")

        # 批量插入（executemany 每批 MYSQL_BATCH_SIZE 行）
        sql = ("INSERT INTO song_rolling_stats "
               "(song_id, cnt_7d, cnt_30d, trending, total_plays) "
               "VALUES (%s, %s, %s, %s, %s)")
        for i in range(0, len(rows), MYSQL_BATCH_SIZE):
            cur.executemany(sql, rows[i:i + MYSQL_BATCH_SIZE])
        conn.commit()

        # 查询权威时间戳（updated_at 由 DB 自动设置）
        cur.execute("SELECT MAX(updated_at) FROM song_rolling_stats")
        _val = cur.fetchone()[0]
        mysql_ts = str(_val) if _val else ""

    print(f"   ✅ MySQL 写入完成：{len(rows):,} 行，耗时 {time.time()-t0:.1f}s")
    print(f"   📌 权威时间戳：{mysql_ts}")
    return mysql_ts


# ============================================================
# Step 5：写入 Redis
# ============================================================

def write_to_redis(agg, mysql_ts):
    """
    批量写入 Redis，并设置 version key（供 sync_recs_v3.py 验证新鲜度）。
    - Redis 未启动 → 自动启动
    - Redis 已启动 → 直接写入
    - 写入完成后立即关闭由本脚本启动的 Redis 实例
    """
    print("   ⏳ 写入 Redis ...")
    t0 = time.time()

    # 自动启动 Redis（未运行时）
    r, started_by_us = _ensure_redis_running()

    # 先删除旧的 song_rolling:* 键（避免残留脏数据）
    # 使用 SCAN 替代 KEYS：KEYS 是阻塞命令，歌曲量大时会短暂冻结 Redis；
    # SCAN 分批迭代，每批不超过 1000 个 key，对 Redis 服务无感知影响
    cursor = 0
    while True:
        cursor, batch_keys = r.scan(cursor, match="song_rolling:[0-9]*", count=1000)
        if batch_keys:
            r.delete(*batch_keys)
        if cursor == 0:
            break

    # Pipeline 批量写入
    pipe = r.pipeline(transaction=False)
    for row in agg.itertuples(index=False):
        key = f"song_rolling:{row.song_id}"
        pipe.hset(key, mapping={
            "c7":  int(row.cnt_7d),
            "c30": int(row.cnt_30d),
            "tr":  float(row.trending),
            "tp":  int(row.total_plays),
        })
        pipe.expire(key, REDIS_TTL)
    # 写入 version key（与 MySQL updated_at 一致，供 sync_recs_v3.py 验证）
    pipe.set("song_rolling:version", mysql_ts, ex=REDIS_TTL)
    pipe.execute()

    print(f"   ✅ Redis 写入完成：{len(agg):,} 首歌曲，耗时 {time.time()-t0:.1f}s")
    print(f"   📌 Redis version key：song_rolling:version = {mysql_ts}")
    # Redis 保持运行，数据留在内存中供 sync_recs_v3.py 读取
    # Redis 的关闭由 sync_recs_v3.py 在推荐完成后负责
    if started_by_us:
        print("   ℹ️  Redis 保持运行（sync_recs_v3.py 读取完毕后将自动关闭）")


# ============================================================
# 主流程
# ============================================================

def main():
    print("\n" + "=" * 60)
    print("  refresh_song_stats.py — 歌曲滚动统计物化刷新")
    print("=" * 60)
    total_t0 = time.time()

    # 连接 MySQL
    conn = pymysql.connect(
        host=MYSQL_HOST, user=MYSQL_USER, password=MYSQL_PASSWORD,
        db=MYSQL_DB, charset="utf8mb4",
        cursorclass=pymysql.cursors.Cursor,
        connect_timeout=30,
    )

    print("\n【Step 1】建表检查")
    ensure_table(conn)

    print("\n【Step 2/3】pandas 聚合")
    agg = compute_stats()

    print("\n【Step 4】写入 MySQL")
    mysql_ts = write_to_mysql(agg, conn)
    conn.close()

    print("\n【Step 5】写入 Redis")
    write_to_redis(agg, mysql_ts)

    print(f"\n✅ 全部完成，总耗时 {time.time()-total_t0:.1f}s")
    print("   现在可以运行 sync_recs_v3.py 进行在线推荐\n")


if __name__ == "__main__":
    main()
