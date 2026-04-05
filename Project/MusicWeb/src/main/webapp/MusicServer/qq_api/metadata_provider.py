"""
多源元数据聚合服务

从多个数据源获取歌曲的流派(genre)和语种(language)信息。
采用四级降级策略：QQ音乐 -> Last.fm -> MusicBrainz -> 本地检测

作者: MusicWeb Team
日期: 2026-01-28
"""

import os
import json
import asyncio
from typing import Optional, Dict, Any

import httpx
from qqmusic_api import search, song, Credential
from qqmusic_api.utils.session import Session, set_session

# ============================================
#    隐私配置读取
# ============================================

# 隐私配置文件路径（项目根目录 secrets.txt，不提交到 Git）
_SECRETS_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "..", "..", "..", "secrets.txt")


def _load_secret(key: str) -> str:
    """
    从项目根目录的 secrets.txt 读取指定键的值。

    secrets.txt 格式：每行 KEY=VALUE，以 # 开头为注释行，空行忽略。
    该文件已加入 .gitignore，不会被提交到版本库。

    Args:
        key: 配置键名，例如 "LASTFM_API_KEY"
    Returns:
        对应的配置值，未找到时返回空字符串
    """
    secrets_path = os.path.normpath(_SECRETS_PATH)
    if not os.path.exists(secrets_path):
        print(f"⚠️  secrets.txt 未找到: {secrets_path}，{key} 将使用空值")
        return ""
    try:
        with open(secrets_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                if k.strip() == key:
                    return v.strip()
    except OSError as e:
        print(f"⚠️  读取 secrets.txt 失败: {e}")
    return ""


# ============================================
#    配置常量
# ============================================

# API 凭据文件路径
CREDENTIALS_PATH = os.path.join(os.path.dirname(__file__), "..", "Cookie", "api_credentials.json")
# QQ 音乐映射表路径
QQ_MAPPING_PATH = os.path.join(os.path.dirname(__file__), "qq_music_mapping.json")

# 网易云 Node.js API 地址 (本地服务)
NETEASE_API_URL = "http://127.0.0.1:3000"

# Last.fm API 配置
LASTFM_API_URL = "https://ws.audioscrobbler.com/2.0/"
LASTFM_API_KEY = _load_secret("LASTFM_API_KEY")

# MusicBrainz API 配置
MUSICBRAINZ_API_URL = "https://musicbrainz.org/ws/2"
MUSICBRAINZ_USER_AGENT = "MusicWeb/1.0 (contact@musicweb.com)"

# HTTP 客户端超时设置
HTTP_TIMEOUT = 10.0


# ============================================
#    工具函数
# ============================================

def load_qq_mapping() -> Dict[str, Dict[str, str]]:
    """
    加载 QQ 音乐流派/语种映射表
    
    Returns:
        包含 'genre' 和 'language' 映射的字典
    """
    try:
        if os.path.exists(QQ_MAPPING_PATH):
            with open(QQ_MAPPING_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        print(f"⚠️ 加载 QQ 映射表失败: {e}")
    
    # 返回默认映射
    return {
        "language": {
            "0": "港台", "1": "内地", "3": "欧美", 
            "14": "日本", "15": "韩国", "4": "其他"
        },
        "genre": {
            "1": "流行", "2": "摇滚", "3": "民谣", "4": "电子",
            "5": "舞曲", "6": "说唱", "7": "R&B", "8": "爵士"
        }
    }


def load_qq_cookie() -> str:
    """
    加载 QQ 音乐 Cookie
    
    Returns:
        Cookie 字符串
    """
    try:
        if os.path.exists(CREDENTIALS_PATH):
            with open(CREDENTIALS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("qqmusic", {}).get("cookie", "")
    except Exception as e:
        print(f"⚠️ 加载 QQ Cookie 失败: {e}")
    return ""


# 全局加载映射表
QQ_MAPPING = load_qq_mapping()

def init_qq_session():
    """初始化 QQ 音乐会话"""
    cookie_str = load_qq_cookie()
    if cookie_str:
        try:
            cookies = {}
            for item in cookie_str.split(";"):
                if "=" in item:
                    key, value = item.strip().split("=", 1)
                    cookies[key] = value
            
            credential = Credential.from_cookies_dict(cookies)
            set_session(Session(credential=credential))
            print("✅ QQ 音乐会话初始化成功")
        except Exception as e:
            print(f"⚠️ QQ 音乐会话初始化失败: {e}")
    else:
        print("⚠️ 未找到 QQ 音乐 Cookie")

# 初始化会话
init_qq_session()


# ============================================
#    P-1: 网易云百科 (最高优先级)
# ============================================

async def fetch_netease_wiki_metadata(song_id: str) -> Optional[Dict[str, str]]:
    """
    从网易云百科获取流派和语种 (需要歌曲ID，非搜索)
    
    调用本地 Node.js API: /netease/song/wiki/summary
    """
    if not song_id:
        return None
    
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            resp = await client.get(f"{NETEASE_API_URL}/netease/song/wiki/summary", params={"id": song_id})
            
            if resp.status_code == 200:
                data = resp.json()
                if data.get("code") == 200 and data.get("data"):
                    wiki_data = data["data"]
                    genre = wiki_data.get("genre")
                    language = wiki_data.get("language")
                    
                    if genre or language:
                        return {"genre": genre, "language": language}
        
        return None
        
    except Exception as e:
        print(f"      → 网易云百科异常: {e}")
        return None


# ============================================
#    P0: QQ 音乐元数据获取 (使用 qqmusic-api 库)
# ============================================

async def fetch_qq_metadata(title: str, artist: str) -> Optional[Dict[str, str]]:
    """
    使用 qqmusic-api 库从 QQ 音乐获取流派和语种
    
    注意: 需要国内 IP 才能访问
    """
    try:
        from qqmusic_api import search, song
        
        # Step 1: 搜索歌曲
        search_result = await search.search_by_type(keyword=f"{title} {artist}", num=1, page=1)
        
        # 兼容处理: search_by_type 可能返回 list (新版) 或 dict (旧版)
        data = {}
        if isinstance(search_result, list):
            if len(search_result) > 0:
                data = search_result[0]
        elif isinstance(search_result, dict):
            data = search_result
            
        song_info = None
        # 情况 1: 标准列表
        if data.get("list") and len(data["list"]) > 0:
             song_info = data["list"][0]
        # 情况 2: 直达结果 (Smart Box) - 直接包含 mid
        elif data.get("mid"):
             song_info = data
            
        if not song_info:
            print(f"      → QQ 搜索无结果")
            return None
        
        mid = song_info.get("mid", "")
        
        if not mid:
            return None
        
        # Step 2: 获取歌曲详情 (包含 genre 和 language 索引)
        detail = await song.query_song([mid])
        
        if not detail or len(detail) == 0:
            return None
        
        song_detail = detail[0]
        
        # 解析流派和语种索引
        genre_idx = str(song_detail.get("genre", ""))
        language_idx = str(song_detail.get("language", ""))
        
        print(f"      → QQ 原始数据: genre_idx={genre_idx}, language_idx={language_idx}")
        
        # 使用映射表转换
        genre = QQ_MAPPING.get("genre", {}).get(genre_idx)
        language = QQ_MAPPING.get("language", {}).get(language_idx)
        
        if genre or language:
            return {"genre": genre, "language": language}
        
        return None
        
    except ImportError:
        print("      → qqmusic-api 库未安装")
        return None
    except Exception as e:
        print(f"      → QQ 音乐异常: {e}")
        return None


# ============================================
#    P1: Last.fm 元数据获取
# ============================================

async def fetch_lastfm_metadata(title: str, artist: str) -> Optional[Dict[str, str]]:
    """
    从 Last.fm 获取流派信息 (通过 Top Tags)
    
    Args:
        title: 歌曲名称
        artist: 歌手名称
        
    Returns:
        {"genre": "pop"} 或 None
    """
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            params = {
                "method": "track.getInfo",
                "api_key": LASTFM_API_KEY,
                "artist": artist,
                "track": title,
                "format": "json"
            }
            
            resp = await client.get(LASTFM_API_URL, params=params)
            
            if resp.status_code != 200:
                print(f"⚠️ Last.fm 请求失败: HTTP {resp.status_code}")
                return None
            
            data = resp.json()
            
            # 检查是否有错误
            if "error" in data:
                return None
            
            # 获取 top tags
            tags = data.get("track", {}).get("toptags", {}).get("tag", [])
            
            if tags and len(tags) > 0:
                # 获取前 3 个 tags 作为流派，用；分隔
                genre_list = [tag.get("name", "") for tag in tags[:3] if tag.get("name")]
                genre = "；".join(genre_list) if genre_list else None
                if genre:
                    print(f"✅ Last.fm 获取成功: genre={genre}")
                    return {"genre": genre}
            
            return None
            
    except httpx.TimeoutException:
        print("⚠️ Last.fm 请求超时")
        return None
    except Exception as e:
        print(f"⚠️ Last.fm 获取失败: {e}")
        return None


# ============================================
#    P2: MusicBrainz 元数据获取
# ============================================

async def fetch_musicbrainz_metadata(title: str, artist: str) -> Optional[Dict[str, str]]:
    """
    从 MusicBrainz 获取流派和语种
    
    注意: MusicBrainz 限制每秒最多 1 次请求
    
    Args:
        title: 歌曲名称
        artist: 歌手名称
        
    Returns:
        {"genre": "pop", "language": "eng"} 或 None
    """
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            headers = {
                "User-Agent": MUSICBRAINZ_USER_AGENT,
                "Accept": "application/json"
            }
            
            # Step 1: 搜索 recording
            search_url = f"{MUSICBRAINZ_API_URL}/recording"
            search_params = {
                "query": f'"{title}" AND artist:"{artist}"',
                "fmt": "json",
                "limit": 1
            }
            
            resp = await client.get(search_url, params=search_params, headers=headers)
            
            if resp.status_code != 200:
                print(f"⚠️ MusicBrainz 搜索失败: HTTP {resp.status_code}")
                return None
            
            data = resp.json()
            recordings = data.get("recordings", [])
            
            if not recordings:
                return None
            
            recording = recordings[0]
            mbid = recording.get("id")
            
            if not mbid:
                return None
            
            # 等待 1 秒以遵守 API 限制
            await asyncio.sleep(1.0)
            
            # Step 2: Lookup 获取详细信息 (含 tags)
            lookup_url = f"{MUSICBRAINZ_API_URL}/recording/{mbid}"
            lookup_params = {
                "inc": "tags",
                "fmt": "json"
            }
            
            resp = await client.get(lookup_url, params=lookup_params, headers=headers)
            
            if resp.status_code != 200:
                return None
            
            detail = resp.json()
            
            result = {}
            
            # 获取 tags (流派)
            tags = detail.get("tags", [])
            if tags:
                # 按投票数排序，取前 3 个，用；分隔
                sorted_tags = sorted(tags, key=lambda x: x.get("count", 0), reverse=True)
                if sorted_tags:
                    genre_list = [tag.get("name", "") for tag in sorted_tags[:3] if tag.get("name")]
                    result["genre"] = "；".join(genre_list) if genre_list else None
            
            # 获取语种 (如果有)
            # MusicBrainz 的 recording 本身可能没有 language，但关联的 release 可能有
            # 这里简化处理，主要依赖 tags
            
            if result:
                print(f"✅ MusicBrainz 获取成功: {result}")
                return result
            
            return None
            
    except httpx.TimeoutException:
        print("⚠️ MusicBrainz 请求超时")
        return None
    except Exception as e:
        print(f"⚠️ MusicBrainz 获取失败: {e}")
        return None


# ============================================
#    P3: 本地语种检测
# ============================================

def detect_language_local(text: str) -> Optional[str]:
    """
    使用 langdetect 库检测文本语种
    
    Args:
        text: 待检测文本 (通常是歌名或歌手名)
        
    Returns:
        语种名称 (如 "国语", "英语") 或 None
    """
    try:
        from langdetect import detect
        
        lang = detect(text)
        
        # 映射到中文语种名称
        mapping = {
            "zh-cn": "国语",
            "zh-tw": "国语",
            "zh": "国语",
            "en": "英语",
            "ja": "日语",
            "ko": "韩语",
            "es": "西班牙语",
            "fr": "法语",
            "de": "德语",
            "pt": "葡萄牙语",
            "ru": "俄语",
            "ar": "阿拉伯语",
            "th": "泰语",
            "vi": "越南语"
        }
        
        result = mapping.get(lang, lang)
        print(f"✅ 本地检测语种: {result}")
        return result
        
    except ImportError:
        print("⚠️ langdetect 库未安装，跳过本地检测")
        return None
    except Exception as e:
        print(f"⚠️ 本地语种检测失败: {e}")
        return None


# ============================================
#    聚合入口
# ============================================

async def get_metadata(title: str, artist: str, netease_id: str = None) -> Dict[str, Optional[str]]:
    """
    多源聚合获取歌曲元数据
    
    采用五级降级策略:
    - P1: 网易云百科 (需要 netease_id)
    - P2: QQ 音乐 (需要国内 IP)
    - P3: Last.fm (全球可用)
    - P4: MusicBrainz (全球可用)
    - P5: langdetect 本地检测 (语种兜底)
    """
    result = {"genre": None, "language": None}
    
    print(f"🔍 [元数据聚合] 开始查询: {title} - {artist}")
    print(f"   📌 五级策略: 网易云百科(P1) → QQ音乐(P2) → Last.fm(P3) → MusicBrainz(P4) → langdetect(P5)")
    
    # ========== P1: 网易云百科 (需要歌曲ID) ==========
    if netease_id:
        print(f"   [P1] 📖 正在查询网易云百科 (ID: {netease_id})...")
        wiki_result = await fetch_netease_wiki_metadata(netease_id)
        if wiki_result:
            if wiki_result.get("genre"):
                result["genre"] = wiki_result["genre"]
                print(f"   [P1] ✅ 网易云百科返回 genre: {result['genre']}")
            if wiki_result.get("language"):
                result["language"] = wiki_result["language"]
                print(f"   [P1] ✅ 网易云百科返回 language: {result['language']}")
            if result["genre"] and result["language"]:
                print(f"📋 [完成] 数据来源: 网易云百科")
                return result
        else:
            print(f"   [P1] ❌ 网易云百科无数据")
    else:
        print(f"   [P1] ⏭️ 跳过 (未提供 netease_id)")
    
    # ========== P2: QQ 音乐 ==========
    print(f"   [P2] 🎵 正在查询 QQ 音乐...")
    qq_result = await fetch_qq_metadata(title, artist)
    if qq_result:
        if qq_result.get("genre"):
            result["genre"] = qq_result["genre"]
            print(f"   [P2] ✅ QQ 音乐返回 genre: {result['genre']}")
        if qq_result.get("language"):
            result["language"] = qq_result["language"]
            print(f"   [P2] ✅ QQ 音乐返回 language: {result['language']}")
        if result["genre"] and result["language"]:
            print(f"📋 [完成] 数据来源: QQ 音乐")
            return result
    else:
        print(f"   [P2] ❌ QQ 音乐无数据 (可能需要国内 IP)")
    
    # ========== P3: Last.fm ==========
    if not result["genre"]:
        print(f"   [P3] 🎸 正在查询 Last.fm...")
        lastfm_result = await fetch_lastfm_metadata(title, artist)
        if lastfm_result and lastfm_result.get("genre"):
            result["genre"] = lastfm_result["genre"]
            print(f"   [P3] ✅ Last.fm 返回 genre: {result['genre']}")
        else:
            print(f"   [P3] ❌ Last.fm 无标签数据")
    
    # ========== P4: MusicBrainz ==========
    if not result["genre"] or not result["language"]:
        print(f"   [P4] 📀 正在查询 MusicBrainz...")
        mb_result = await fetch_musicbrainz_metadata(title, artist)
        if mb_result:
            if not result["genre"] and mb_result.get("genre"):
                result["genre"] = mb_result["genre"]
                print(f"   [P4] ✅ MusicBrainz 返回 genre: {result['genre']}")
            if not result["language"] and mb_result.get("language"):
                result["language"] = mb_result["language"]
                print(f"   [P4] ✅ MusicBrainz 返回 language: {result['language']}")
        else:
            print(f"   [P4] ❌ MusicBrainz 无数据")
    
    # ========== P5: 本地语种检测 ==========
    if not result["language"]:
        print(f"   [P5] 🔤 正在使用 langdetect 本地检测...")
        result["language"] = detect_language_local(f"{title} {artist}")
        if result["language"]:
            print(f"   [P5] ✅ langdetect 检测结果: {result['language']}")
        else:
            print(f"   [P5] ❌ langdetect 检测失败")
    
    # 汇总来源
    sources = []
    if result["genre"]: sources.append("genre已获取")
    if result["language"]: sources.append("language已获取")
    print(f"📋 [完成] 最终结果: genre={result['genre']}, language={result['language']}")
    return result


# ============================================
#    测试入口
# ============================================

if __name__ == "__main__":
    import asyncio
    
    async def test():
        # 测试中文歌曲
        result = await get_metadata("晴天", "周杰伦")
        print(f"晴天 - 周杰伦: {result}")
        
        # 测试英文歌曲
        result = await get_metadata("Shape of You", "Ed Sheeran")
        print(f"Shape of You - Ed Sheeran: {result}")
    
    asyncio.run(test())
