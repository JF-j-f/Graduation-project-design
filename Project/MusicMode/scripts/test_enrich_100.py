# -*- coding: utf-8 -*-
"""
test_enrich_100.py — 外部歌曲元数据补全（串行模式）

策略（逐首串行，交替使用两个 API）：
  Pass 1: 偶数索引 → 网易云先查，奇数索引 → QQ先查
          若主 API 未命中 → 加入 miss 列表
          若主 API 命中但仍缺字段 → 立即用另一个 API 补充
  Pass 2: miss 列表用另一个 API 重试

每次 API 调用后间隔 sleep，避免触发反爬。

用法（关闭 VPN 后运行）：
  python -X utf8 test_enrich_100.py                 # 测试 100 首
  python -X utf8 test_enrich_100.py --limit 50      # 测 50 首
  python -X utf8 test_enrich_100.py --limit 0       # 跑全部（正式模式）
  python -X utf8 test_enrich_100.py --sleep 2.0     # 加大间隔（更安全）
"""

import argparse
import asyncio
import json
import math
import os
import sys
import time
from datetime import datetime as _dt
from typing import Optional

import httpx
import pymysql
from tqdm import tqdm

# ============================================================
# 数据库配置
# ============================================================
MYSQL_HOST     = "localhost"
MYSQL_PORT     = 3306
MYSQL_DB       = "musicweb"
MYSQL_USER     = "root"
MYSQL_PASSWORD = "JF123456"

# API 配置
NETEASE_BASE         = "http://127.0.0.1:3000"
NETEASE_SEARCH_PATHS = ["/netease/search", "/search"]
NETEASE_DETAIL_PATHS = ["/netease/song/detail", "/song/detail"]

QQ_LANG_MAP = {
    "0": "国语", "1": "粤语", "2": "英语", "3": "日语",
    "4": "韩语", "5": "法语", "6": "德语", "7": "西班牙语",
    "8": "俄语", "9": "意大利语", "10": "葡萄牙语",
}

NE_LANG_MAP = {
    "zh": "国语", "zh-cn": "国语", "zh-tw": "国语", "cn": "国语",
    "yue": "粤语", "cantonese": "粤语",
    "en": "英语", "eng": "英语", "english": "英语",
    "ja": "日语", "jp": "日语", "japanese": "日语",
    "ko": "韩语", "kr": "韩语", "korean": "韩语",
    "fr": "法语", "de": "德语", "es": "西班牙语",
    "ru": "俄语", "it": "意大利语", "pt": "葡萄牙语",
}

# 断点进度文件
PROGRESS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "enrich_external_progress.json")


# ============================================================
# 工具函数
# ============================================================
def get_conn():
    return pymysql.connect(
        host=MYSQL_HOST, port=MYSQL_PORT, db=MYSQL_DB,
        user=MYSQL_USER, password=MYSQL_PASSWORD,
        charset="utf8mb4", autocommit=False,
    )


def _valid_year(val) -> Optional[int]:
    try:
        y = int(str(val)[:4])
        return y if 1900 <= y <= 2030 else None
    except Exception:
        return None


def _clean_str(val, max_len: int = 200) -> Optional[str]:
    if not val:
        return None
    s = str(val).strip()
    return s[:max_len] if s else None


def _miss_num(v) -> bool:
    if v is None:
        return True
    try:
        return math.isnan(float(v)) or float(v) == 0
    except Exception:
        return True


def _miss_str(v) -> bool:
    if v is None:
        return True
    try:
        if math.isnan(float(v)):
            return True
    except (TypeError, ValueError):
        pass
    return not str(v).strip()


def _map_ne_lang(raw) -> Optional[str]:
    """网易云 language 标准化"""
    if raw is None:
        return None
    s = str(raw).strip().lower()
    if not s:
        return None
    if s in NE_LANG_MAP:
        return NE_LANG_MAP[s]
    if any('\u4e00' <= c <= '\u9fff' for c in s):
        return _clean_str(s, 10)
    return _clean_str(s, 10)


# 待补全字段列表
TARGET_FIELDS = ["release_year", "popularity", "language"]


def _song_needs(song: dict) -> list:
    """返回该歌曲仍需补全的字段列表"""
    missing = []
    if _miss_num(song.get("release_year")):
        missing.append("release_year")
    if _miss_num(song.get("popularity")):
        missing.append("popularity")
    if _miss_str(song.get("language")):
        missing.append("language")
    return missing


# ============================================================
# API 查询函数（串行安全，无并发）
# ============================================================
async def netease_fetch(client: httpx.AsyncClient,
                        title: str, artist: str) -> dict:
    """网易云查询 → release_year / album / duration / cover_image / popularity / language"""
    result: dict = {}
    keyword = f"{artist} {title}"

    for path in NETEASE_SEARCH_PATHS:
        try:
            r = await client.get(
                f"{NETEASE_BASE}{path}",
                params={"keywords": keyword, "limit": 5},
                timeout=8.0,
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

            pt = s.get("publishTime") or al.get("publishTime")
            if pt:
                y = _valid_year(_dt.fromtimestamp(int(pt) / 1000).year)
                if y:
                    result["release_year"] = y

            # language — 搜索结果
            lang_raw = s.get("language") or s.get("lang") or s.get("songLanguage")
            lm = _map_ne_lang(lang_raw)
            if lm:
                result["language"] = lm

            # detail 补充
            need_detail = (
                "release_year" not in result
                or "language" not in result
            )
            if need_detail and song_id:
                for dpath in NETEASE_DETAIL_PATHS:
                    try:
                        rd = await client.get(
                            f"{NETEASE_BASE}{dpath}",
                            params={"ids": str(song_id)},
                            timeout=8.0,
                        )
                        if rd.status_code != 200:
                            continue
                        d = rd.json()
                        ds_list = d.get("songs", [])
                        if not ds_list:
                            continue
                        ds = ds_list[0]
                        dal = ds.get("al") or {}
                        if "release_year" not in result:
                            pt2 = dal.get("publishTime") or ds.get("publishTime")
                            if pt2:
                                y = _valid_year(_dt.fromtimestamp(int(pt2) / 1000).year)
                                if y:
                                    result["release_year"] = y
                        if "popularity" not in result and ds.get("pop") is not None:
                            result["popularity"] = max(0, min(100, int(ds["pop"])))
                        if "language" not in result:
                            dl = ds.get("language") or ds.get("lang") or ds.get("songLanguage")
                            dlm = _map_ne_lang(dl)
                            if dlm:
                                result["language"] = dlm
                        break
                    except Exception:
                        continue

            # wiki/summary 补充 language
            if "language" not in result and song_id:
                for wiki_path in ["/song/wiki/summary", "/netease/song/wiki/summary"]:
                    try:
                        rw = await client.get(
                            f"{NETEASE_BASE}{wiki_path}",
                            params={"id": str(song_id)},
                            timeout=6.0,
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

            break
        except Exception:
            continue

    return result


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


async def qq_fetch(client: httpx.AsyncClient,
                   title: str, artist: str) -> dict:
    """QQ Music 直接 HTTP 查询（绕过 qqmusic_api 库，避免 2001 错误）
    两步：smartbox 搜索 → musicu.fcg 详情
    """
    result: dict = {}
    keyword = f"{artist} {title}"
    try:
        # Step 1: 快速搜索获取 mid
        r1 = await client.get(
            QQ_SEARCH_URL,
            params={"key": keyword},
            timeout=8.0,
        )
        if r1.status_code != 200:
            return result
        items = r1.json().get("data", {}).get("song", {}).get("itemlist", [])
        if not items:
            return result
        mid = items[0].get("mid", "")
        if not mid:
            return result

        # Step 2: 用 mid 获取详细信息
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

        # 提取各字段
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

    except Exception as e:
        print(f"    [QQ ERR] {title[:20]}: {e}")
    return result


# ============================================================
# DB 更新
# ============================================================
def apply_update(conn, song_id: int, song: dict, data: dict) -> list:
    """只更新 DB 中仍缺失的字段，返回实际更新的字段名列表"""
    to_update: dict = {}
    for field, new_val in data.items():
        if new_val is None:
            continue
        cur_val = song.get(field)
        if field in ("release_year", "duration", "popularity"):
            if _miss_num(cur_val):
                to_update[field] = new_val
        else:
            if _miss_str(cur_val):
                to_update[field] = new_val

    if to_update:
        set_clause = ", ".join(f"`{f}` = %s" for f in to_update.keys())
        vals = list(to_update.values()) + [song_id]
        with conn.cursor() as cur:
            cur.execute(f"UPDATE songs SET {set_clause} WHERE id = %s", vals)
        conn.commit()
        # 更新内存中的 song dict（后续判断仍需最新值）
        for f, v in to_update.items():
            song[f] = v

    return list(to_update.keys())


# ============================================================
# 主流程：串行交替
# ============================================================
async def run(songs: list, ne_ok: bool, qq_ok: bool, sleep_sec: float):
    conn = get_conn()

    # 统计
    stats = {
        "ne_hit": 0, "ne_miss": 0, "ne_err": 0,
        "qq_hit": 0, "qq_miss": 0, "qq_err": 0,
        "fields": {},
        "pass2_hit": 0, "pass2_miss": 0,
    }

    def _count_fields(updated: list):
        for f in updated:
            stats["fields"][f] = stats["fields"].get(f, 0) + 1

    # 加载断点（注意：只有三个目标字段全部填满的歌曲才算 done）
    done_ids: set = set()
    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE) as f:
                done_ids = set(json.load(f).get("done", []))
        except Exception:
            pass

    # 过滤：SQL 已确保只查仍缺字段的歌曲，再排除断点中确认完成的
    # 但如果断点中的 ID 仍然出现在 SQL 结果中，说明上次标记有误，需要重新处理
    actually_done = set()
    still_need = []
    for s in songs:
        if s["id"] in done_ids and not _song_needs(s):
            actually_done.add(s["id"])
        else:
            still_need.append(s)

    if actually_done:
        print(f"  断点续跑：{len(actually_done)} 首已确认完成")
    # 清理旧断点（只保留真正完成的）
    done_ids = actually_done

    pending = still_need
    if not pending:
        print("  所有歌曲已处理完毕！")
        conn.close()
        return stats

    print(f"  实际待处理: {len(pending)} 首\n")

    ne_misses = []  # 网易云未命中 → Pass 2 用 QQ 补搜
    qq_misses = []  # QQ 未命中 → Pass 2 用网易云补搜

    async with httpx.AsyncClient() as client:
        # ═══════ Pass 1: 真并行 — NE 搜 A 歌曲，QQ 搜 B 歌曲，同时进行 ═══════
        # 分组：偶数索引 → 网易云，奇数索引 → QQ
        ne_songs = [(i, pending[i]) for i in range(0, len(pending), 2)]
        qq_songs = [(i, pending[i]) for i in range(1, len(pending), 2)]
        total_pairs = max(len(ne_songs), len(qq_songs))
        pbar = tqdm(total=len(pending), desc="Pass 1 (并行)")

        for pair_idx in range(total_pairs):
            tasks = []
            task_labels = []  # ("ne", song) or ("qq", song)

            # 网易云任务
            if pair_idx < len(ne_songs) and ne_ok:
                _, ne_song = ne_songs[pair_idx]
                t = str(ne_song["title"] or "").strip()
                a = str(ne_song["artist"] or "").strip()
                if t:
                    tasks.append(netease_fetch(client, t, a))
                    task_labels.append(("ne", ne_song))
                else:
                    done_ids.add(ne_song["id"])
                    pbar.update(1)

            # QQ 任务
            if pair_idx < len(qq_songs) and qq_ok:
                _, qq_song = qq_songs[pair_idx]
                t = str(qq_song["title"] or "").strip()
                a = str(qq_song["artist"] or "").strip()
                if t:
                    tasks.append(qq_fetch(client, t, a))
                    task_labels.append(("qq", qq_song))
                else:
                    done_ids.add(qq_song["id"])
                    pbar.update(1)

            if not tasks:
                continue

            # 真并行：NE + QQ 同时发出请求
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for (api, song), res in zip(task_labels, results):
                song_id = song["id"]
                key = "ne" if api == "ne" else "qq"

                if isinstance(res, Exception):
                    stats[f"{key}_err"] += 1
                    (ne_misses if api == "ne" else qq_misses).append(song)
                elif res:
                    stats[f"{key}_hit"] += 1
                    updated = apply_update(conn, song_id, song, res)
                    _count_fields(updated)
                    if not _song_needs(song):
                        done_ids.add(song_id)
                else:
                    stats[f"{key}_miss"] += 1
                    (ne_misses if api == "ne" else qq_misses).append(song)
                pbar.update(1)

            # 每对之后稍微间隔，避免触发反爬
            await asyncio.sleep(sleep_sec)

            # 每 200 首保存断点
            processed = pbar.n
            if processed % 200 == 0 and processed > 0:
                with open(PROGRESS_FILE, "w") as pf:
                    json.dump({"done": list(done_ids)}, pf)

        pbar.close()

        # ═══════ Pass 2: 补搜 — NE 未命中→QQ, QQ 未命中→NE ═══════
        pass2_songs = []
        if qq_ok:
            pass2_songs += [("qq", s) for s in ne_misses]   # NE miss → QQ
        if ne_ok:
            pass2_songs += [("ne", s) for s in qq_misses]   # QQ miss → NE

        if pass2_songs:
            print(f"\nPass 2: {len(pass2_songs)} 首待补搜 (NE miss→QQ: {len(ne_misses)}, QQ miss→NE: {len(qq_misses)})")
            for api, song in tqdm(pass2_songs, desc="Pass 2 (补搜)"):
                song_id = song["id"]
                title  = str(song["title"] or "").strip()
                artist = str(song["artist"] or "").strip()

                try:
                    if api == "ne":
                        data = await netease_fetch(client, title, artist)
                    else:
                        data = await qq_fetch(client, title, artist)
                except Exception:
                    data = {}

                await asyncio.sleep(sleep_sec)

                if data:
                    stats["pass2_hit"] += 1
                    updated = apply_update(conn, song_id, song, data)
                    _count_fields(updated)
                else:
                    stats["pass2_miss"] += 1

                if not _song_needs(song):
                    done_ids.add(song_id)

        # ═══════ Pass 3: 本地降级（不依赖任何 API） ═══════
        # 收集仍有缺失字段的歌曲
        still_missing_songs = [s for s in pending if _song_needs(s)]
        if still_missing_songs:
            print(f"\nPass 3: {len(still_missing_songs)} 首仍缺字段 → 本地降级策略")
            stats["pass3_filled"] = 0

            # 预加载：同艺人歌曲的 release_year 中位数
            artist_years: dict = {}
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT artist, release_year FROM songs
                    WHERE release_year IS NOT NULL AND release_year > 0
                """)
                for row in cur.fetchall():
                    a = row[0]
                    if a not in artist_years:
                        artist_years[a] = []
                    artist_years[a].append(row[1])

            # 预加载：从 play_history 统计每首歌播放次数 → 归一化为 popularity
            song_play_counts: dict = {}
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT song_id, COUNT(*) as cnt FROM play_history
                    GROUP BY song_id
                """)
                for row in cur.fetchall():
                    song_play_counts[row[0]] = row[1]
            max_plays = max(song_play_counts.values()) if song_play_counts else 1

            for song in tqdm(still_missing_songs, desc="Pass 3 (降级)"):
                song_id = song["id"]
                title  = str(song.get("title") or "")
                artist = str(song.get("artist") or "")
                missing = _song_needs(song)
                fallback_data: dict = {}

                # ① language 降级：字符分析推断
                if "language" in missing:
                    text = title + artist
                    has_cjk = any('\u4e00' <= c <= '\u9fff' for c in text)
                    has_kana = any(('\u3040' <= c <= '\u309f') or ('\u30a0' <= c <= '\u30ff') for c in text)
                    has_hangul = any('\uac00' <= c <= '\ud7a3' for c in text)
                    is_ascii = all(ord(c) < 128 or c in ' ' for c in text.replace(' ', ''))

                    if has_kana:
                        fallback_data["language"] = "日语"
                    elif has_hangul:
                        fallback_data["language"] = "韩语"
                    elif has_cjk:
                        fallback_data["language"] = "国语"
                    elif is_ascii and text.strip():
                        fallback_data["language"] = "英语"

                # ② popularity 降级：播放次数归一化
                if "popularity" in missing:
                    plays = song_play_counts.get(song_id, 0)
                    if plays > 0:
                        # 对数归一化，避免头部歌曲挤压
                        import math as _m
                        norm = _m.log1p(plays) / _m.log1p(max_plays) * 100
                        fallback_data["popularity"] = max(1, min(100, int(norm)))
                    else:
                        fallback_data["popularity"] = 1  # 无播放记录给最低分

                # ③ release_year 降级：同艺人中位数
                if "release_year" in missing:
                    years = artist_years.get(artist, [])
                    if years:
                        sorted_years = sorted(years)
                        median_year = sorted_years[len(sorted_years) // 2]
                        fallback_data["release_year"] = median_year

                if fallback_data:
                    updated = apply_update(conn, song_id, song, fallback_data)
                    _count_fields(updated)
                    stats["pass3_filled"] += len(updated)

                if not _song_needs(song):
                    done_ids.add(song_id)

    # 最终保存断点
    with open(PROGRESS_FILE, "w") as pf:
        json.dump({"done": list(done_ids)}, pf)
    conn.close()
    return stats


# ============================================================
# 主入口
# ============================================================
def main():
    parser = argparse.ArgumentParser(description="外部歌曲元数据补全（串行交替模式）")
    parser.add_argument("--limit", type=int, default=100,
                        help="测试歌曲数, 0=全部 (默认100)")
    parser.add_argument("--sleep", type=float, default=1.0,
                        help="每次 API 调用后等待秒数 (默认1.0)")
    args = parser.parse_args()

    print(f"{'='*60}")
    print(f"外部歌曲元数据补全 — 串行交替模式")
    print(f"  数量: {'全部' if args.limit == 0 else args.limit}  |  间隔: {args.sleep}s")
    print(f"  时间: {_dt.now():%Y-%m-%d %H:%M:%S}")
    print(f"{'='*60}")

    # 连通性检测
    import socket
    ne_ok = False
    try:
        s = socket.create_connection(("127.0.0.1", 3000), timeout=3)
        s.close()
        ne_ok = True
        print("  [OK] 网易云 API 端口 3000 可达")
    except Exception:
        print("  [!!] 网易云 API 不可达（端口 3000），将仅用 QQ")

    qq_ok = False
    try:
        r = httpx.get(QQ_SEARCH_URL, params={"key": "test"}, timeout=5)
        if r.status_code == 200:
            qq_ok = True
            print("  [OK] QQ Music API 可达 (HTTP 直连)")
        else:
            print(f"  [!!] QQ Music API 返回 {r.status_code}")
    except Exception as e:
        print(f"  [!!] QQ Music API 不可达: {e}")

    if not ne_ok and not qq_ok:
        print("\n  两个 API 均不可用，退出")
        return

    # 查询待补全歌曲
    conn = get_conn()
    cur = conn.cursor(pymysql.cursors.DictCursor)
    limit_clause = f"LIMIT {args.limit}" if args.limit > 0 else ""
    cur.execute(f"""
        SELECT id, title, artist, album, duration, genre,
               release_year, cover_image, language, popularity
        FROM songs
        WHERE kkbox_id IS NULL
          AND (
            release_year IS NULL OR release_year = 0
            OR popularity IS NULL OR popularity = 0
            OR language IS NULL OR TRIM(language) = ''
          )
        ORDER BY id
        {limit_clause}
    """)
    songs = cur.fetchall()
    conn.close()

    print(f"\n  待补全歌曲: {len(songs)} 首")
    if not songs:
        print("  所有歌曲已补全！")
        return

    # 样本
    print(f"\n  前 5 首样本:")
    for s in songs[:5]:
        yr = s.get("release_year") or "-"
        pop = s.get("popularity") or "-"
        lang = s.get("language") or "-"
        print(f"    [{s['id']:>6}] {s['artist'][:15]:15s} - {s['title'][:25]:25s}  "
              f"year={yr}  pop={pop}  lang={lang}")
    print()

    # 运行
    t0 = time.time()
    stats = asyncio.run(run(songs, ne_ok, qq_ok, args.sleep))
    elapsed = time.time() - t0

    # ═══════ 报告 ═══════
    print(f"\n{'='*60}")
    print(f"结果 ({elapsed:.1f}s, {elapsed/max(len(songs),1):.2f}s/首)")
    print(f"{'='*60}")
    print(f"  Pass 1:")
    print(f"    网易云: 命中={stats['ne_hit']}, 未命中={stats['ne_miss']}, 错误={stats['ne_err']}")
    print(f"    QQ:     命中={stats['qq_hit']}, 未命中={stats['qq_miss']}, 错误={stats['qq_err']}")
    if stats["pass2_hit"] + stats["pass2_miss"] > 0:
        print(f"  Pass 2:")
        print(f"    补搜命中={stats['pass2_hit']}, 仍未命中={stats['pass2_miss']}")
    if stats.get("pass3_filled", 0) > 0:
        print(f"  Pass 3 (本地降级):")
        print(f"    降级填充字段数={stats['pass3_filled']}")

    print(f"\n  各字段更新数:")
    for f in ["release_year", "popularity", "language", "album", "duration",
              "cover_image", "genre"]:
        cnt = stats["fields"].get(f, 0)
        if cnt > 0:
            print(f"    {f:15s}: {cnt}")

    total_updated = sum(stats["fields"].values())
    print(f"\n  总更新字段数: {total_updated}")

    # 验证 DB
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT COUNT(*) FROM songs WHERE kkbox_id IS NULL AND (
            release_year IS NULL OR release_year = 0
            OR popularity IS NULL OR popularity = 0
            OR language IS NULL OR TRIM(language) = ''
        )
    """)
    remaining = cur.fetchone()[0]
    conn.close()
    print(f"\n  DB 中仍待补全: {remaining:,} 首")

    if args.limit > 0 and remaining > 0:
        est_min = remaining * (elapsed / max(len(songs), 1)) / 60
        print(f"  预计跑全部: ~{est_min:.0f} 分钟")
        print(f"\n  正式运行命令:")
        print(f"    python -X utf8 test_enrich_100.py --limit 0 --sleep {args.sleep}")


if __name__ == "__main__":
    main()
