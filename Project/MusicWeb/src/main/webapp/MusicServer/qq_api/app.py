"""
QQ 音乐 API 桥接服务

基于 L-1124/QQMusicApi 库，为 MusicWeb 前端提供 RESTful API 接口。
支持搜索、播放链接获取、二维码登录、手机验证码登录等功能。

启动命令: uvicorn app:app --host 127.0.0.1 --port 8000 --reload
"""

import asyncio
import base64
import json
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager
import os

# ============================================
#    加载 QQ 音乐流派/语种映射表
# ============================================

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_MAPPING_FILE = os.path.join(_SCRIPT_DIR, "qq_music_mapping.json")

try:
    with open(_MAPPING_FILE, "r", encoding="utf-8") as f:
        QQ_MAPPING = json.load(f)
    print(f"✅ [映射表] 已加载 {_MAPPING_FILE}")
except Exception as e:
    print(f"⚠️ [映射表] 加载失败: {e}")
    QQ_MAPPING = {"language": {}, "genre": {}}

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# 导入 QQ 音乐 API 库
from qqmusic_api import search, song, login
from qqmusic_api.login import QRLoginType, QRCodeLoginEvents, PhoneLoginEvents
from qqmusic_api import Credential
from qqmusic_api.utils.session import Session, set_session

# 导入元数据聚合服务
from metadata_provider import get_metadata

# ============================================
#    全局状态管理
# ============================================

# 用户凭证字典 {userid: Credential}
credentials: Dict[str, Credential] = {}

# 二维码字典 {userid: QRObject}
qr_codes: Dict[str, Any] = {}

# 登录会话字典 {userid: Session}
# 用于保持登录过程中的 Session 状态 (如手机验证码流程)
login_sessions: Dict[str, Session] = {}


# ============================================
#    FastAPI 应用初始化
# ============================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    print("🎵 QQ 音乐 API 服务启动中...")
    # 启动时加载所有已保存的凭证
    await load_all_credentials()
    yield
    print("🎵 QQ 音乐 API 服务已关闭")

async def load_all_credentials():
    """扫描并加载所有用户的凭证"""
    import glob
    try:
        files = glob.glob("qq_credential_*.json")
        for filename in files:
            try:
                # filename format: qq_credential_{userid}.json
                # Extract userid. Note: userid might contain special chars? Assuming safe for now.
                # But safer to just load content.
                userid = filename[14:-5] # remove 'qq_credential_' and '.json'
                if not userid: continue
                
                await load_credential(userid)
            except Exception as e:
                print(f"⚠️ 加载 {filename} 失败: {e}")
    except Exception as e:
        print(f"⚠️ 扫描凭证文件失败: {e}")

async def load_credential(userid: str):
    """加载指定用户的凭证"""
    filename = f"qq_credential_{userid}.json"
    try:
        if os.path.exists(filename):
            import json
            with open(filename, "r", encoding="utf-8") as f:
                try:
                    data = json.load(f)
                    if not isinstance(data, dict):
                        raise ValueError("凭证格式错误")
                    
                    credential = Credential.from_cookies_dict(data)
                    
                    if await credential.is_expired():
                        print(f"⚠️ 用户 {userid} 凭证已过期")
                        os.remove(filename)
                        if userid in credentials:
                            del credentials[userid]
                        return

                    credentials[userid] = credential
                    print(f"✅ 用户 {userid} 凭证已加载")
                    
                except Exception as e:
                    print(f"⚠️ 用户 {userid} 凭证损坏: {e}")
                    try:
                        f.close()
                        os.remove(filename)
                    except: pass
                    if userid in credentials:
                        del credentials[userid]
    except Exception as e:
        print(f"⚠️ 加载凭证流程异常: {e}")

def save_credential(userid: str, credential: Credential):
    """保存用户凭证"""
    try:
        import json
        if credential:
            data = credential.as_dict()
            if hasattr(credential, "extra_fields"):
                data.update(credential.extra_fields)
            
            filename = f"qq_credential_{userid}.json"
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            credentials[userid] = credential
            print(f"✅ 用户 {userid} 凭证已保存")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"⚠️ 保存凭证失败: {e}")


app = FastAPI(
    title="QQ Music API Bridge",
    description="MusicWeb 项目的 QQ 音乐 API 桥接服务",
    version="1.0.0",
    lifespan=lifespan
)

# 配置 CORS (允许跨域)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================
#    请求/响应模型
# ============================================

class PhoneSendRequest(BaseModel):
    """手机验证码发送请求"""
    phone: int
    country_code: int = 86
    userid: str = "guest"


class PhoneVerifyRequest(BaseModel):
    """手机验证码验证请求"""
    phone: int
    code: int
    country_code: int = 86
    userid: str = "guest"


# ============================================
#    搜索接口
# ============================================

@app.get("/search")
async def search_songs(
    keywords: str = Query(..., description="搜索关键词"),
    limit: int = Query(30, description="返回数量"),
    page: int = Query(1, description="页码")
):
    """
    搜索歌曲
    
    返回 QQ 音乐搜索结果，包含歌曲 mid、名称、歌手等信息。
    """
    try:
        result = await search.search_by_type(
            keyword=keywords,
            num=limit,
            page=page
        )
        return {"code": 0, "data": result}
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/song/detail")
async def get_song_detail(
    mid: str = Query(..., description="歌曲 MID")
):
    """
    获取歌曲完整详情
    
    返回歌曲的完整信息，包括：
    - 基础信息：名称、歌手、专辑、时长
    - VIP 状态：pay.pay_play, pay.payplay
    - 专辑信息：封面、发行时间
    """
    try:
        # 调用 query_song 获取完整信息
        result = await song.query_song([mid])
        
        if not result or len(result) == 0:
            return {"code": 404, "message": "歌曲未找到", "data": None}
        
        song_info = result[0]
        
        # 提取并标准化字段
        enriched = {
            "mid": song_info.get("mid", mid),
            "id": song_info.get("id"),
            "name": song_info.get("name", "Unknown"),
            "title": song_info.get("title") or song_info.get("name", "Unknown"),
            # 歌手
            "singer": song_info.get("singer", []),
            "artists": " / ".join([s.get("name", "") for s in song_info.get("singer", [])]) or "Unknown Artist",
            # 专辑
            "album": song_info.get("album", {}),
            "albumName": song_info.get("album", {}).get("name", "Unknown Album"),
            "albumMid": song_info.get("album", {}).get("mid", ""),
            # 时长 (秒)
            "duration": song_info.get("interval", 0),
            # 封面
            "coverUrl": f"https://y.qq.com/music/photo_new/T002R300x300M000{song_info.get('album', {}).get('mid', '')}.jpg" if song_info.get("album", {}).get("mid") else "",
            # VIP/付费信息
            "pay": song_info.get("pay", {}),
            "vip": False,
            # 发行时间
            "pubTime": song_info.get("time_public", ""),
            "releaseYear": None,
            # 语言 (从索引转换为字符串)
            "language": QQ_MAPPING.get("language", {}).get(str(song_info.get("language", "")), None),
            # 流派 (从索引转换为字符串)
            "genre": QQ_MAPPING.get("genre", {}).get(str(song_info.get("genre", "")), None),
        }
        
        # 解析 VIP 状态
        pay_info = enriched["pay"]
        if pay_info:
            # pay_play > 0 表示需要付费播放
            pay_play = pay_info.get("pay_play", 0) or pay_info.get("payplay", 0)
            enriched["vip"] = pay_play > 0
        
        # 解析发行年份
        if enriched["pubTime"]:
            try:
                enriched["releaseYear"] = int(enriched["pubTime"].split("-")[0])
            except:
                pass
        
        return {"code": 0, "data": enriched}
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Get song detail failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
#    元数据聚合接口
# ============================================

@app.get("/song/metadata")
async def get_song_metadata(
    title: str = Query(..., description="歌曲名称"),
    artist: str = Query(..., description="歌手名称"),
    netease_id: str = Query(None, description="网易云歌曲ID (可选)")
):
    """
    多源聚合获取歌曲元数据 (流派和语种)
    
    采用五级降级策略:
    - P-1: 网易云百科 (需要 netease_id)
    - P0: QQ 音乐 (需要国内 IP)
    - P1: Last.fm (全球可用)
    - P2: MusicBrainz (全球可用)
    - P3: langdetect 本地检测 (语种兜底)
    
    Returns:
        {"code": 0, "data": {"genre": "流行", "language": "国语"}}
    """
    try:
        result = await get_metadata(title, artist, netease_id)
        return {"code": 0, "data": result}
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Get song metadata failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
#    播放链接接口
# ============================================

@app.get("/song/url")
async def get_song_url(
    mid: str = Query(..., description="歌曲 MID"),
    userid: str = Query("guest", description="用户 ID")
):
    """
    获取歌曲播放链接
    """
    credential = credentials.get(userid)
    
    try:
        # 尝试获取播放链接
        urls = await song.get_song_urls(
            mid=[mid],
            credential=credential
        )
        
        url = urls.get(mid, "")
        
        # 检查是否获取到有效链接
        if not url:
            # 链接获取失败，可能是 VIP 限制或凭证失效
            # 再次检查凭证状态
            is_valid = False
            if credential:
                try:
                    if await credential.is_expired():
                        print(f"⚠️ 用户 {userid} 凭证已过期")
                        if userid in credentials:
                            del credentials[userid]
                        # 尝试删除文件
                        filename = f"qq_credential_{userid}.json"
                        if os.path.exists(filename):
                            os.remove(filename)
                    else:
                        is_valid = True
                except:
                    if userid in credentials:
                        del credentials[userid]

            # 可能是 VIP 歌曲，需要登录
            return {
                "code": 0,
                "data": {
                    "url": "",
                    "needLogin": not is_valid,
                    "message": "需要登录 QQ 音乐账号" if not is_valid else "无法获取播放链接（可能需要 VIP）"
                }
            }
        
        return {
            "code": 0,
            "data": {
                "url": url,
                "needLogin": False
            }
        }
    except Exception as e:
        print(f"Get Song URL Error: {e}")
        # 发生异常（如凭证错误），保守起见认为需要重新登录
        return {
            "code": 0,
            "data": {
                "url": "",
                "needLogin": True,
                "message": "获取失败，请尝试重新登录"
            }
        }


# ============================================
#    二维码登录接口
# ============================================

@app.get("/login/qr")
async def get_qr_code(
    login_type: str = Query("qq", description="登录类型"),
    userid: str = Query("guest", description="用户ID")
):
    """获取登录二维码"""
    try:
        # 确定登录类型
        qr_type = QRLoginType.QQ
        if login_type == "wx":
            qr_type = QRLoginType.WX
        elif login_type == "mobile":
            qr_type = QRLoginType.MOBILE
        
        # 获取二维码
        qr = await login.get_qrcode(qr_type)
        qr_codes[userid] = qr  # 保存到用户专属位置
        
        qr_base64 = base64.b64encode(qr.data).decode("utf-8")
        
        return {
            "code": 0,
            "data": {
                "qrcode": f"data:{qr.mimetype};base64,{qr_base64}",
                "type": login_type,
                "identifier": qr.identifier
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/login/qr/check")
async def check_qr_code(
    userid: str = Query("guest", description="用户ID")
):
    """检查二维码扫描状态"""
    
    current_qr = qr_codes.get(userid)
    
    if current_qr is None:
        raise HTTPException(status_code=400, detail="请先获取二维码")
    
    try:
        # 处理手机客户端扫码
        if current_qr.qr_type == QRLoginType.MOBILE:
            async for event, credential in login.check_mobile_qr(current_qr):
                if event == QRCodeLoginEvents.DONE and credential:
                    credentials[userid] = credential
                    save_credential(userid, credential)
                    return {
                        "code": 0,
                        "data": {
                            "status": "DONE",
                            "message": "登录成功"
                        }
                    }
                return {
                    "code": 0,
                    "data": {
                        "status": event.name if event else "OTHER",
                        "message": _get_qr_status_message(event)
                    }
                }
        else:
            # QQ/微信扫码
            event, credential = await login.check_qrcode(current_qr)
            
            if event == QRCodeLoginEvents.DONE and credential:
                credentials[userid] = credential
                save_credential(userid, credential)
                return {
                    "code": 0,
                    "data": {
                        "status": "DONE",
                        "message": "登录成功"
                    }
                }
            
            return {
                "code": 0,
                "data": {
                    "status": event.name if event else "OTHER",
                    "message": _get_qr_status_message(event)
                }
            }
    except Exception as e:
        import traceback
        traceback.print_exc()
        # print(f"QR Check Error: {e}")
        return {
            "code": 0,
            "data": {
                "status": "WAIT",
                "message": "等待扫描..." 
            }
        }


def _get_qr_status_message(event: QRCodeLoginEvents) -> str:
    """获取二维码状态的中文描述"""
    messages = {
        QRCodeLoginEvents.SCAN: "请使用手机扫描二维码",
        QRCodeLoginEvents.CONF: "扫描成功，请在手机上确认登录",
        QRCodeLoginEvents.DONE: "登录成功",
        QRCodeLoginEvents.TIMEOUT: "二维码已过期，请重新获取",
        QRCodeLoginEvents.REFUSE: "用户取消了登录",
        QRCodeLoginEvents.OTHER: "未知状态"
    }
    return messages.get(event, "未知状态")


# ============================================
#    手机验证码登录接口
# ============================================

@app.post("/login/phone/send")
async def send_phone_code(request: PhoneSendRequest):
    """发送手机验证码"""
    try:
        # 获取或创建用户会话
        session = login_sessions.get(request.userid)
        if not session:
            session = Session()
            login_sessions[request.userid] = session
            print(f"DEBUG: Created new session for {request.userid}")
        
        # 设置当前上下文 Session
        set_session(session)
        
        event, data = await login.send_authcode(
            phone=request.phone,
            country_code=request.country_code
        )
        
        if event == PhoneLoginEvents.CAPTCHA:
            print(f"DEBUG: Captcha URL: {data}")
            return {
                "code": 0,
                "data": {
                    "status": "CAPTCHA",
                    "captcha_url": data,
                    "message": "请完成图形验证码后重试"
                }
            }
        elif event == PhoneLoginEvents.FREQUENCY:
            return {
                "code": 0,
                "data": {
                    "status": "FREQUENCY",
                    "message": "发送过于频繁，请稍后重试"
                }
            }
        elif event == PhoneLoginEvents.SEND:
            return {
                "code": 0,
                "data": {
                    "status": "SEND",
                    "message": "验证码已发送"
                }
            }
        else:
            return {
                "code": 0,
                "data": {
                    "status": "OTHER",
                    "message": str(data)
                }
            }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/login/phone/verify")
async def verify_phone_code(request: PhoneVerifyRequest):
    """验证手机验证码并登录"""
    try:
        # 获取用户会话
        session = login_sessions.get(request.userid)
        if not session:
            return {
                "code": 400,
                "data": {
                    "message": "会话已过期，请重新发送验证码"
                }
            }
            
        # 设置当前上下文 Session
        set_session(session)
        
        credential = await login.phone_authorize(
            phone=request.phone,
            auth_code=request.code,
            country_code=request.country_code
        )
        
        # 保存到当前用户
        credentials[request.userid] = credential
        save_credential(request.userid, credential)
        
        # 登录成功，清理会话 (Session 对象可以与其 close 方法一起清理，但 httpx async client 实际上应显式 close)
        # 这里为了确保连接释放，最好 close
        try:
            await session.aclose()
        except: pass
        if request.userid in login_sessions:
            del login_sessions[request.userid]
        
        return {
            "code": 0,
            "data": {
                "status": "DONE",
                "message": "登录成功"
            }
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Phone Verify Error: {e}")
        return {
            "code": 500,
            "data": {
                "message": f"验证失败: {str(e)}"
            }
        }


# ============================================
#    凭证管理接口
# ============================================

@app.get("/credential")
async def get_credential_status(
    userid: str = Query("guest", description="用户ID")
):
    """获取当前登录状态"""
    credential = credentials.get(userid)
    
    if credential is None:
        return {
            "code": 0,
            "data": {
                "logged_in": False
            }
        }
    
    return {
        "code": 0,
        "data": {
            "logged_in": True,
            "musicid": credential.musicid
        }
    }


@app.post("/credential/logout")
async def logout(
    userid: str = Query("guest", description="用户ID")
):
    """登出当前用户"""
    
    # 内存清除
    if userid in credentials:
        del credentials[userid]
    
    if userid in qr_codes:
        del qr_codes[userid]
        
    # 文件清除
    filename = f"qq_credential_{userid}.json"
    if os.path.exists(filename):
        try:
            os.remove(filename)
        except: pass
    
    return {
        "code": 0,
        "data": {
            "message": "已登出"
        }
    }


# ============================================
#    健康检查
# ============================================

@app.get("/health")
async def health_check():
    """健康检查接口"""
    return {
        "status": "ok",
        "service": "QQ Music API Bridge",
        "logged_in": len(credentials) > 0
    }


# ============================================
#    主入口
# ============================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
