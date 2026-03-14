# -*- coding: utf-8 -*-
"""
test_api_composer.py — composer/lyricist 字段可行性验证脚本

功能：
1. 检测本地 QQ 音乐 API / 网易云 API 服务连通性
2. 检测 QQ 音乐 API 是否可达外网（VPN 环境下可能超时）
3. 针对多首样本歌曲，探查 QQ 和网易云 API 返回的完整字段
4. 统计 composer / lyricist 字段覆盖率
5. 输出最终建议：是否值得为 songs 表新增这两列

执行方式：
  python test_api_composer.py

注意事项：
  - QQ 音乐 API 需要中国大陆 IP，使用 VPN 可能导致超时
  - 若脚本提示"QQ 超时"，请暂时关闭 VPN 后重新运行
  - 网易云 API 依赖本地 Node.js 服务（端口 3000）

作者：MusicMode 推荐系统
"""

import asyncio
import socket
import sys
import os
import json
from typing import Optional, Dict, Any, List

# ============================================================
# 配置
# ============================================================

# 网易云本地 Node.js API
NETEASE_API_URL = "http://127.0.0.1:3000"

# 本地 QQ API 服务（若有 Flask/FastAPI 封装层）
QQ_LOCAL_API_URL = "http://127.0.0.1:8000"

# 测试超时（秒）
CONNECT_TIMEOUT = 5.0
HTTP_TIMEOUT    = 15.0

# 测试样本：(歌曲名, 歌手, 网易云 ID)
# 网易云 ID 为 None 时跳过网易云 wiki 测试
TEST_SONGS = [
    ("晴天",          "周杰伦",      "186001"),      # 华语流行
    ("青花瓷",        "周杰伦",      "185809"),      # 华语流行
    ("Shape of You",  "Ed Sheeran",  "460965275"),   # 英语流行
    ("炎",            "廻尾彗",      "1416767583"),  # 日语 OST
    ("Dynamite",      "BTS",         "1489050420"),  # 韩语 K-Pop
    ("夜曲",          "周杰伦",      "186008"),      # 华语流行
    ("Rolling in the Deep", "Adele", "169025"),      # 英语流行
]

# ============================================================
# 连通性检测
# ============================================================

def check_tcp_port(host: str, port: int, timeout: float = CONNECT_TIMEOUT) -> bool:
    """检测 TCP 端口是否可达（不依赖 HTTP 库）"""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


def check_qqmusic_library() -> bool:
    """检测 qqmusic-api Python 库是否已安装"""
    try:
        import qqmusic_api  # noqa
        return True
    except ImportError:
        return False


def check_httpx() -> bool:
    """检测 httpx 库"""
    try:
        import httpx  # noqa
        return True
    except ImportError:
        return False


async def check_qqmusic_network() -> bool:
    """
    检测 QQ 音乐外网可达性
    通过 qqmusic-api 实际发起一次极小搜索来判断
    """
    try:
        import httpx
        from qqmusic_api import search as qq_search
        result = await asyncio.wait_for(
            qq_search.search_by_type(keyword="test", num=1, page=1),
            timeout=HTTP_TIMEOUT
        )
        return result is not None
    except asyncio.TimeoutError:
        return False
    except Exception:
        return False


async def check_netease_service() -> bool:
    """检测本地网易云 Node.js 服务是否运行"""
    if not check_tcp_port("127.0.0.1", 3000):
        return False
    try:
        import httpx
        async with httpx.AsyncClient(timeout=CONNECT_TIMEOUT) as client:
            resp = await client.get(f"{NETEASE_API_URL}/", follow_redirects=True)
            return resp.status_code < 500
    except Exception:
        return False


# ============================================================
# QQ 音乐字段探查
# ============================================================

async def probe_qq_song(title: str, artist: str) -> Dict[str, Any]:
    """
    查询 QQ 音乐，返回完整原始字段字典
    目的是探查 composer / lyricist 等字段是否存在
    """
    result = {"success": False, "fields": {}, "error": ""}
    try:
        from qqmusic_api import search, song

        # Step 1: 搜索
        search_result = await asyncio.wait_for(
            search.search_by_type(keyword=f"{title} {artist}", num=3, page=1),
            timeout=HTTP_TIMEOUT
        )

        # 兼容新旧版 API 返回格式
        song_info = None
        if isinstance(search_result, list) and search_result:
            candidate = search_result[0]
            songs_list = candidate.get("list") if isinstance(candidate, dict) else []
            if songs_list:
                song_info = songs_list[0]
            elif isinstance(candidate, dict) and candidate.get("mid"):
                song_info = candidate
        elif isinstance(search_result, dict):
            songs_list = search_result.get("list", [])
            if songs_list:
                song_info = songs_list[0]

        if not song_info:
            result["error"] = "搜索无结果"
            return result

        mid = song_info.get("mid", "")
        if not mid:
            result["error"] = "搜索结果无 mid"
            return result

        # Step 2: 获取详细信息
        await asyncio.sleep(0.5)  # 礼貌性等待
        detail_list = await asyncio.wait_for(
            song.query_song([mid]),
            timeout=HTTP_TIMEOUT
        )

        if not detail_list:
            result["error"] = "query_song 无返回"
            return result

        detail = detail_list[0] if isinstance(detail_list, list) else detail_list
        if isinstance(detail, dict):
            result["success"] = True
            result["fields"] = detail
        else:
            result["error"] = f"非预期返回类型: {type(detail)}"

    except asyncio.TimeoutError:
        result["error"] = "⏱️ 请求超时（VPN 影响？）"
    except Exception as e:
        result["error"] = str(e)

    return result


# ============================================================
# 网易云字段探查
# ============================================================

async def probe_netease_wiki(netease_id: str) -> Dict[str, Any]:
    """
    查询网易云 wiki 百科接口，返回完整字段
    """
    result = {"success": False, "fields": {}, "error": ""}
    try:
        import httpx
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            resp = await client.get(
                f"{NETEASE_API_URL}/netease/song/wiki/summary",
                params={"id": netease_id}
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("code") == 200 and data.get("data"):
                    result["success"] = True
                    result["fields"] = data["data"]
                else:
                    result["error"] = f"code={data.get('code')}, 无数据"
            else:
                result["error"] = f"HTTP {resp.status_code}"
    except Exception as e:
        result["error"] = str(e)
    return result


async def probe_netease_detail(netease_id: str) -> Dict[str, Any]:
    """
    查询网易云歌曲详情接口（/netease/song/detail），返回完整字段
    """
    result = {"success": False, "fields": {}, "error": ""}
    try:
        import httpx
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            resp = await client.get(
                f"{NETEASE_API_URL}/netease/song/detail",
                params={"ids": netease_id}
            )
            if resp.status_code == 200:
                data = resp.json()
                songs_list = data.get("songs", [])
                if songs_list:
                    result["success"] = True
                    result["fields"] = songs_list[0]
                else:
                    result["error"] = "无歌曲数据"
            else:
                result["error"] = f"HTTP {resp.status_code}"
    except Exception as e:
        result["error"] = str(e)
    return result


# ============================================================
# 字段覆盖率统计
# ============================================================

COMPOSER_FIELD_NAMES = [
    # QQ 音乐可能字段名
    "composer", "compose", "lyricist", "lyric", "writer",
    "lyric_writer", "作曲", "作词", " lyricists", "composers",
    # 网易云可能字段名
    "ar_composer", "sq_composer", "lyricist_name", "compose_name",
]


def extract_composer_fields(raw_fields: dict) -> Dict[str, Any]:
    """从原始字段字典中提取与 composer/lyricist 相关的字段"""
    found = {}
    all_keys = list(raw_fields.keys())

    # 精确匹配
    for name in COMPOSER_FIELD_NAMES:
        if name in raw_fields:
            found[name] = raw_fields[name]

    # 模糊匹配（包含关键词的字段名）
    for key in all_keys:
        key_lower = key.lower()
        if any(kw in key_lower for kw in ["compos", "lyric", "writer", "作曲", "作词"]):
            if key not in found:
                found[key] = raw_fields[key]

    return found


def print_separator(char: str = "=", width: int = 60):
    print(char * width)


# ============================================================
# 主流程
# ============================================================

async def main():
    print("\n" + "🎵" * 30)
    print("   test_api_composer.py — composer/lyricist 可行性验证")
    print("🎵" * 30)

    # ──────────────────────────────────────────
    # Phase 1: 环境与连通性检测
    # ──────────────────────────────────────────
    print_separator()
    print("📡 [Phase 1] 环境与连通性检测")
    print_separator()

    env_ok = True

    # 1.1 httpx
    has_httpx = check_httpx()
    print(f"  {'✅' if has_httpx else '❌'} httpx 库: {'已安装' if has_httpx else '未安装（pip install httpx）'}")
    if not has_httpx:
        env_ok = False

    # 1.2 qqmusic-api
    has_qq_lib = check_qqmusic_library()
    print(f"  {'✅' if has_qq_lib else '❌'} qqmusic-api 库: {'已安装' if has_qq_lib else '未安装（pip install qqmusic-api）'}")

    # 1.3 网易云 Node.js 服务（端口 3000）
    print(f"\n  🔍 检测网易云本地服务（127.0.0.1:3000）...")
    netease_service_up = await check_netease_service()
    print(f"  {'✅' if netease_service_up else '❌'} 网易云 Node.js 服务: "
          f"{'运行中' if netease_service_up else '未运行（请先启动 Node.js API 服务）'}")

    # 1.4 QQ 音乐外网可达性
    qq_network_ok = False
    if has_qq_lib:
        print(f"\n  🔍 检测 QQ 音乐外网可达性（可能因 VPN 超时，请耐心等待...）")
        qq_network_ok = await check_qqmusic_network()
        if qq_network_ok:
            print(f"  ✅ QQ 音乐 API 可达")
        else:
            print(f"  ❌ QQ 音乐 API 不可达")
            print(f"  ⚠️  可能原因：")
            print(f"     · VPN 开启导致中国服务器路由失败")
            print(f"     · QQ 音乐 Cookie 已过期")
            print(f"  💡 建议：暂时关闭 VPN 后重新运行本脚本")
    else:
        print(f"  ⏭️  跳过 QQ 音乐外网检测（库未安装）")

    # 汇总
    qq_test_enabled     = has_qq_lib and qq_network_ok
    netease_test_enabled = netease_service_up

    if not qq_test_enabled and not netease_test_enabled:
        print(f"\n❌ 两个平台均不可用，无法执行字段探查。")
        print(f"   请检查上述环境问题后重新运行。")
        return

    # ──────────────────────────────────────────
    # Phase 2: QQ 音乐字段探查
    # ──────────────────────────────────────────
    qq_results_summary = []
    qq_all_keys        = set()

    if qq_test_enabled:
        print_separator()
        print(f"🎵 [Phase 2] QQ 音乐字段探查（{len(TEST_SONGS)} 首样本）")
        print_separator()

        for title, artist, _ in TEST_SONGS:
            print(f"\n  🎵 {title} — {artist}")
            probe = await probe_qq_song(title, artist)
            if probe["success"]:
                fields = probe["fields"]
                qq_all_keys.update(fields.keys())
                composer_fields = extract_composer_fields(fields)
                if composer_fields:
                    print(f"    ✅ 找到 composer/lyricist 相关字段: {list(composer_fields.keys())}")
                    for k, v in composer_fields.items():
                        print(f"       {k}: {v}")
                else:
                    print(f"    ℹ️  未找到 composer/lyricist 字段")
                    print(f"    📋 返回字段列表: {sorted(fields.keys())}")
                qq_results_summary.append({
                    "title": title,
                    "artist": artist,
                    "success": True,
                    "composer_fields": composer_fields
                })
            else:
                print(f"    ❌ 查询失败: {probe['error']}")
                qq_results_summary.append({
                    "title": title,
                    "artist": artist,
                    "success": False,
                    "composer_fields": {}
                })
            await asyncio.sleep(1.0)  # 礼貌限速

        # QQ 小结
        print_separator("-")
        qq_success = sum(1 for r in qq_results_summary if r["success"])
        qq_with_composer = sum(1 for r in qq_results_summary if r["composer_fields"])
        print(f"  QQ 音乐查询成功: {qq_success}/{len(TEST_SONGS)}")
        print(f"  含 composer/lyricist 字段: {qq_with_composer}/{qq_success}")
        print(f"  QQ 全量字段（所有样本合并）: {sorted(qq_all_keys)}")
    else:
        print_separator()
        print(f"⏭️  [Phase 2] 跳过 QQ 音乐字段探查（不可达）")

    # ──────────────────────────────────────────
    # Phase 3: 网易云字段探查
    # ──────────────────────────────────────────
    netease_results_summary = []
    netease_all_keys        = set()

    if netease_test_enabled:
        print_separator()
        print(f"🎵 [Phase 3] 网易云字段探查（{len(TEST_SONGS)} 首样本）")
        print_separator()

        for title, artist, netease_id in TEST_SONGS:
            if not netease_id:
                print(f"\n  ⏭️  {title} — {artist}（无网易云 ID，跳过）")
                continue

            print(f"\n  🎵 {title} — {artist}（网易云 ID: {netease_id}）")

            # 3A: wiki summary
            print(f"    → wiki summary 接口...")
            wiki = await probe_netease_wiki(netease_id)
            if wiki["success"]:
                netease_all_keys.update(wiki["fields"].keys())
                composer_in_wiki = extract_composer_fields(wiki["fields"])
                if composer_in_wiki:
                    print(f"    ✅ wiki 找到 composer 相关字段: {list(composer_in_wiki.keys())}")
                    for k, v in composer_in_wiki.items():
                        print(f"       {k}: {v}")
                else:
                    print(f"    ℹ️  wiki 无 composer 字段。字段: {sorted(wiki['fields'].keys())}")
            else:
                print(f"    ❌ wiki 查询失败: {wiki['error']}")

            # 3B: song detail
            print(f"    → song detail 接口...")
            detail = await probe_netease_detail(netease_id)
            if detail["success"]:
                netease_all_keys.update(detail["fields"].keys())
                composer_in_detail = extract_composer_fields(detail["fields"])
                if composer_in_detail:
                    print(f"    ✅ detail 找到 composer 相关字段: {list(composer_in_detail.keys())}")
                    for k, v in composer_in_detail.items():
                        print(f"       {k}: {v}")
                else:
                    print(f"    ℹ️  detail 无 composer 字段。部分字段: {list(detail['fields'].keys())[:15]}...")
            else:
                print(f"    ❌ detail 查询失败: {detail['error']}")

            netease_results_summary.append({
                "title": title, "artist": artist, "netease_id": netease_id,
                "wiki_ok": wiki["success"],
                "composer_found": bool(extract_composer_fields(wiki["fields"]) or
                                       extract_composer_fields(detail["fields"]))
            })
            await asyncio.sleep(0.5)

        # 网易云小结
        print_separator("-")
        ne_success = sum(1 for r in netease_results_summary if r["wiki_ok"])
        ne_with_composer = sum(1 for r in netease_results_summary if r["composer_found"])
        print(f"  网易云查询成功: {ne_success}/{len([s for s in TEST_SONGS if s[2]])}")
        print(f"  含 composer/lyricist 字段: {ne_with_composer}/{ne_success}")
        print(f"  网易云全量字段（所有样本合并）: {sorted(netease_all_keys)}")
    else:
        print_separator()
        print(f"⏭️  [Phase 3] 跳过网易云字段探查（服务未运行）")

    # ──────────────────────────────────────────
    # Phase 4: 最终结论与建议
    # ──────────────────────────────────────────
    print_separator()
    print("📋 [Phase 4] 最终结论与建议")
    print_separator()

    total_with_composer = 0
    total_tested = 0

    if qq_test_enabled and qq_results_summary:
        qq_rate = sum(1 for r in qq_results_summary if r["composer_fields"]) / max(len(qq_results_summary), 1)
        total_with_composer += sum(1 for r in qq_results_summary if r["composer_fields"])
        total_tested += len(qq_results_summary)
        print(f"  QQ 音乐 composer/lyricist 覆盖率: {qq_rate*100:.0f}%")

    if netease_test_enabled and netease_results_summary:
        ne_rate = sum(1 for r in netease_results_summary if r["composer_found"]) / max(len(netease_results_summary), 1)
        total_with_composer += sum(1 for r in netease_results_summary if r["composer_found"])
        total_tested += len(netease_results_summary)
        print(f"  网易云 composer/lyricist 覆盖率: {ne_rate*100:.0f}%")

    if total_tested > 0:
        overall_rate = total_with_composer / total_tested
        print(f"\n  综合覆盖率: {total_with_composer}/{total_tested} = {overall_rate*100:.0f}%")

        print("\n  ─── 建议 ───")
        if overall_rate >= 0.6:
            print(f"  ✅ 建议新增 songs.composer + songs.lyricist 列")
            print(f"     理由：覆盖率 {overall_rate*100:.0f}% ≥ 60%，对推荐精度有实质帮助")
            print(f"     操作：在 enrich_db.py --step alter 中加入这两列的 ADD COLUMN")
        elif overall_rate >= 0.3:
            print(f"  ⚠️  覆盖率中等（{overall_rate*100:.0f}%），可选择性新增")
            print(f"     建议：仅在特定来源（如网易云歌曲）条件下填充，其余置 NULL")
        else:
            print(f"  ❌ 不建议新增这两列")
            print(f"     理由：覆盖率 {overall_rate*100:.0f}% 过低，大量 NULL 值对模型无意义")
            print(f"     结论：请在 enrich_db.py --step alter 中跳过这两列")
    else:
        print(f"  ⚠️  未能完成任何测试，请解决上述环境问题后重新运行")

    print_separator()
    print("✅ test_api_composer.py 运行完成")
    print_separator()
    print(f"\n📌 下一步操作：")
    print(f"   根据以上建议，执行：")
    print(f"   python enrich_db.py --step alter")
    print(f"   （若建议新增 composer/lyricist，已在脚本中自动处理）\n")


if __name__ == "__main__":
    asyncio.run(main())
