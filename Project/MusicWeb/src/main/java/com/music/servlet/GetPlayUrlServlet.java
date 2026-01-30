package com.music.servlet;

import com.music.dao.RedisUtil;
import com.music.dao.SongDAO;
import com.music.javabean.User;
import jakarta.servlet.ServletException;
import jakarta.servlet.annotation.WebServlet;
import jakarta.servlet.http.HttpServlet;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;

import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;

import com.google.gson.*;

/**
 * 动态获取播放链接 Servlet
 * 
 * 功能：
 * 1. 通过歌曲名+歌手搜索外部 API 获取播放链接
 * 2. 使用 Redis 缓存结果，避免重复请求
 * 3. 优先使用网易云音乐，失败后尝试 QQ 音乐
 * 
 * 请求：GET /api/getPlayUrl?title=xxx&artist=xxx
 * 响应：{ "success": true, "url": "...", "source": "netease", "externalId": "..."
 * }
 */
@WebServlet("/api/getPlayUrl")
public class GetPlayUrlServlet extends HttpServlet {
    private static final long serialVersionUID = 1L;

    // Node.js API 服务地址
    private static final String API_BASE_URL = "http://localhost:3000";

    // HTTP 请求超时时间
    private static final int CONNECT_TIMEOUT = 5000;
    private static final int READ_TIMEOUT = 10000;

    private static final Gson gson = new Gson();

    @Override
    protected void doGet(HttpServletRequest request, HttpServletResponse response)
            throws ServletException, IOException {

        response.setContentType("application/json;charset=UTF-8");
        PrintWriter out = response.getWriter();
        JsonObject result = new JsonObject();

        try {
            // 获取参数
            String title = request.getParameter("title");
            String artist = request.getParameter("artist");

            // 参数验证
            if (title == null || title.trim().isEmpty()) {
                result.addProperty("success", false);
                result.addProperty("message", "缺少歌曲标题");
                out.print(gson.toJson(result));
                return;
            }

            title = title != null ? title.trim() : "";
            artist = (artist != null) ? artist.trim() : "";
            String externalId = request.getParameter("id");
            String source = request.getParameter("source");

            // 获取当前登录用户
            User user = (User) request.getSession().getAttribute("user");
            String userId = (user != null) ? user.getUsername() : "guest";

            // 0. 如果提供了 id 和 source，直接获取播放链接 (用于 VIP 重试等场景)
            if (externalId != null && !externalId.isEmpty() && source != null && !source.isEmpty()) {
                handleDirectRequest(externalId, source, userId, out, result);
                return;
            }

            // 1. 先查询 Redis 缓存
            String cacheKey = RedisUtil.getPlayUrlKey(title, artist);
            String cachedData = RedisUtil.get(cacheKey);

            if (cachedData != null && !cachedData.isEmpty()) {
                // 缓存命中
                System.out.println("🎵 [缓存命中] " + title + " - " + artist);
                JsonObject cached = JsonParser.parseString(cachedData).getAsJsonObject();
                cached.addProperty("cached", true);
                out.print(gson.toJson(cached));
                return;
            }

            // 2. 缓存未命中，调用外部 API
            System.out.println("🔍 [搜索] " + title + " - " + artist);

            // 构建搜索关键词
            String keyword = title;
            if (!artist.isEmpty()) {
                keyword = title + " " + artist;
            }

            // ========================================
            // 双音源搜索策略：优先网易云，备用 QQ 音乐
            // ========================================
            JsonObject playInfo = null;
            String errorMessage = "未找到可播放的音源";
            boolean needQQLogin = false;

            // 第一步：尝试网易云音乐
            try {
                System.out.println("🎵 [Step 1] 尝试网易云音乐...");
                playInfo = searchAndGetPlayUrl(keyword, "netease", userId);
                if (playInfo != null) {
                    System.out.println("✅ [网易云] 成功获取播放链接");
                }
            } catch (Exception e) {
                errorMessage = e.getMessage();
                System.err.println("⚠️ [网易云] 播放获取失败: " + e.getMessage());
            }

            // 第二步：如果网易云失败，尝试 QQ 音乐作为备用
            if (playInfo == null) {
                try {
                    System.out.println("🎵 [Step 2] 网易云失败，尝试 QQ 音乐...");
                    // 使用完整版本获取 VIP 状态
                    playInfo = searchAndGetPlayUrlWithVipCheck(keyword, userId);

                    if (playInfo != null) {
                        // 检查是否需要 VIP 登录
                        if (playInfo.has("needLogin") && playInfo.get("needLogin").getAsBoolean()) {
                            needQQLogin = true;
                            System.out.println("🔐 [QQ 音乐] 需要 VIP 登录");
                        } else if (playInfo.has("url") && !playInfo.get("url").getAsString().isEmpty()) {
                            System.out.println("✅ [QQ 音乐] 成功获取播放链接");
                        }
                    }
                } catch (Exception e) {
                    System.err.println("⚠️ [QQ 音乐] 播放获取失败: " + e.getMessage());
                }
            }

            // 第三步：构建响应
            if (needQQLogin) {
                // QQ 音乐 VIP 歌曲，提示用户登录
                result.addProperty("success", true);
                result.addProperty("needLogin", true);
                result.addProperty("message", "此歌曲需要 QQ 音乐 VIP，请登录您的 QQ 音乐账号");
                result.addProperty("url", "");
                result.addProperty("source", "qq");
                if (playInfo != null && playInfo.has("externalId")) {
                    result.addProperty("externalId", playInfo.get("externalId").getAsString());
                }
            } else if (playInfo != null && playInfo.has("url") && !playInfo.get("url").getAsString().isEmpty()) {
                // 成功获取播放链接，写入缓存（24 小时）
                RedisUtil.set(cacheKey, gson.toJson(playInfo), RedisUtil.TTL_DAY);

                // ============================================================
                // 🚀 核心功能：异步持久化元数据 (遵循 V3 强制更新策略)
                // ============================================================
                final String fTitle = title != null ? title : "";
                final String fArtist = artist != null ? artist : "";
                final JsonObject fPlayInfo = playInfo;

                new Thread(() -> {
                    try {
                        String pTitle = fTitle;
                        String pArtist = fArtist;
                        String pSource = fPlayInfo.get("source").getAsString();
                        String pExtId = fPlayInfo.get("externalId").getAsString();

                        // 尝试从 fPlayInfo 获取基础信息，如果没有，再调用 getSongDetail
                        // 注意：fPlayInfo 可能由 searchAndGetPlayUrl 返回，对于 QQ 音乐可能缺字段
                        String pAlbum = "";
                        String pCover = "";
                        int pYear = 0;
                        String pGenre = "";
                        String pLang = "";
                        int pDuration = 0;

                        // 再次获取完整详情以确保元数据最全 (特别是 Genre, Language, Duration)
                        JsonObject details = getSongDetail(pExtId, pSource);

                        if (details != null) {
                            if (details.has("album"))
                                pAlbum = details.get("album").getAsString();
                            if (details.has("coverUrl"))
                                pCover = details.get("coverUrl").getAsString();
                            if (details.has("releaseYear"))
                                pYear = details.get("releaseYear").getAsInt();
                            if (details.has("genre"))
                                pGenre = details.get("genre").getAsString();
                            if (details.has("language"))
                                pLang = details.get("language").getAsString();
                            if (details.has("duration"))
                                pDuration = details.get("duration").getAsInt();
                        } else {
                            // Fallback: 如果 getSongDetail 失败（罕见），尝试从 fPlayInfo 读一点是一点
                            if (fPlayInfo.has("releaseYear"))
                                pYear = fPlayInfo.get("releaseYear").getAsInt();
                            if (fPlayInfo.has("genre"))
                                pGenre = fPlayInfo.get("genre").getAsString();
                            if (fPlayInfo.has("language"))
                                pLang = fPlayInfo.get("language").getAsString();
                        }

                        // 执行数据库更新 (SongDAO V3: 强制更新模式)
                        SongDAO songDao = new SongDAO();
                        songDao.addOrUpdateFromExternal(pTitle, pArtist, pAlbum, pDuration, pSource, pCover, pYear,
                                pGenre, pLang);

                    } catch (Exception e) {
                        // 🔇 异常静默原则：只记录日志，不影响主线程
                        System.err.println("❌ [Async DB Update] Failed: " + e.getMessage());
                    }
                }).start();

                result.addProperty("success", true);
                result.addProperty("url", playInfo.get("url").getAsString());
                result.addProperty("source", playInfo.get("source").getAsString());
                result.addProperty("externalId", playInfo.get("externalId").getAsString());
                result.addProperty("cached", false);
            } else {
                result.addProperty("success", false);
                result.addProperty("message", errorMessage);
            }

        } catch (Exception e) {
            e.printStackTrace();
            result.addProperty("success", false);
            result.addProperty("message", "服务器错误: " + e.getMessage());
        }

        out.print(gson.toJson(result));
    }

    /**
     * 搜索并获取播放链接
     * 
     * @param keyword 搜索关键词 (title + artist)
     * @param source  音乐源 (netease/qq)
     * @param userId  用户ID
     * @return 包含 url, source, externalId 的 JsonObject，失败返回 null
     */
    private JsonObject searchAndGetPlayUrl(String keyword, String source, String userId) {
        try {
            // 1. 搜索歌曲
            String searchUrl;
            if ("netease".equals(source)) {
                searchUrl = API_BASE_URL + "/netease/search?keywords=" +
                        URLEncoder.encode(keyword, StandardCharsets.UTF_8) + "&limit=1";
            } else {
                // 修复参数: server.js 需 keywords 和 limit
                searchUrl = API_BASE_URL + "/qq/search?keywords=" +
                        URLEncoder.encode(keyword, StandardCharsets.UTF_8) + "&limit=1&userid="
                        + URLEncoder.encode(userId, StandardCharsets.UTF_8);
            }

            String searchResult = callApi(searchUrl);
            if (searchResult == null)
                return null;

            // 2. 解析搜索结果获取歌曲 ID
            String songId = parseSongId(searchResult, source);
            if (songId == null)
                return null;

            // 3. 获取播放链接 (网易云支持三级降级)
            String playUrl;
            if ("netease".equals(source)) {
                // 提取 title 和 artist 用于 QQ Fallback
                String[] parts = keyword.split(" ", 2);
                String title = parts.length > 0 ? parts[0] : "";
                String artist = parts.length > 1 ? parts[1] : "";
                playUrl = getNeteasePlayUrl(songId, title, artist);
            } else {
                playUrl = getQQPlayUrl(songId, userId);
            }

            if (playUrl == null || playUrl.isEmpty())
                return null;

            // 4. 构建返回结果
            JsonObject result = new JsonObject();
            result.addProperty("url", playUrl);
            result.addProperty("source", source);
            result.addProperty("externalId", songId);

            // 5. 获取并添加详细信息 (年份、曲风、语言)
            if ("netease".equals(source)) {
                JsonObject details = getSongDetail(songId, source);
                if (details != null) {
                    if (details.has("releaseYear"))
                        result.add("releaseYear", details.get("releaseYear"));
                    if (details.has("genre"))
                        result.add("genre", details.get("genre"));
                    if (details.has("language"))
                        result.add("language", details.get("language"));
                    if (details.has("coverUrl"))
                        result.add("coverUrl", details.get("coverUrl"));
                }
            }

            return result;

        } catch (Exception e) {
            System.err.println("搜索播放链接失败 [" + source + "]: " + e.getMessage());
            // 将具体错误抛出或记录，以便上层捕获
            throw new RuntimeException(e.getMessage());
        }
    }

    /**
     * QQ 音乐搜索并获取播放链接（带 VIP 检测）
     * 
     * 该方法专门用于 QQ 音乐的备用搜索流程：
     * 1. 搜索歌曲获取 songmid
     * 2. 获取播放链接
     * 3. 如果歌曲存在但没有播放链接，标记为需要 VIP 登录
     * 
     * @param keyword 搜索关键词
     * @param userId  用户 ID（用于加载 QQ 音乐凭证）
     * @return 包含 url, source, externalId, needLogin 的 JsonObject
     */
    private JsonObject searchAndGetPlayUrlWithVipCheck(String keyword, String userId) {
        try {
            // 1. 搜索 QQ 音乐
            String searchUrl = API_BASE_URL + "/qq/search?keywords=" +
                    URLEncoder.encode(keyword, StandardCharsets.UTF_8) + "&limit=1&userid=" +
                    URLEncoder.encode(userId, StandardCharsets.UTF_8);

            String searchResult = callApi(searchUrl);
            if (searchResult == null) {
                return null;
            }

            // 2. 解析搜索结果获取歌曲 ID
            String songMid = parseSongId(searchResult, "qq");
            if (songMid == null) {
                System.out.println("🔍 [QQ 音乐] 未找到匹配歌曲");
                return null;
            }

            // 3. 获取完整播放信息（包含 needLogin 状态）
            JsonObject playInfo = getQQPlayUrlFull(songMid, userId);

            if (playInfo == null) {
                // API 调用失败
                return null;
            }

            // 4. 构建返回结果
            JsonObject result = new JsonObject();
            result.addProperty("source", "qq");
            result.addProperty("externalId", songMid);

            if (playInfo.has("url") && !playInfo.get("url").isJsonNull()
                    && !playInfo.get("url").getAsString().isEmpty()) {
                // 成功获取播放链接
                result.addProperty("url", playInfo.get("url").getAsString());
                result.addProperty("needLogin", false);
            } else {
                // 歌曲存在但无法播放 -> 需要 VIP 登录
                result.addProperty("url", "");
                result.addProperty("needLogin", true);
            }

            return result;

        } catch (Exception e) {
            System.err.println("QQ 音乐 VIP 检测搜索失败: " + e.getMessage());
            return null;
        }
    }

    /**
     * 解析搜索结果获取歌曲 ID
     */
    private String parseSongId(String json, String source) {
        try {
            JsonObject root = JsonParser.parseString(json).getAsJsonObject();

            if ("netease".equals(source)) {
                // 网易云格式: { "result": { "songs": [{ "id": 123 }] } }
                if (root.has("result")) {
                    JsonObject result = root.getAsJsonObject("result");
                    if (result.has("songs")) {
                        JsonArray songs = result.getAsJsonArray("songs");
                        if (songs.size() > 0) {
                            return songs.get(0).getAsJsonObject().get("id").getAsString();
                        }
                    }
                }
            } else {
                // QQ 音乐格式: { "data": { "list": [{ "songmid": "xxx" }] } }
                if (root.has("data")) {
                    JsonElement data = root.get("data");
                    JsonArray list = null;

                    if (data.isJsonObject() && data.getAsJsonObject().has("list")) {
                        list = data.getAsJsonObject().getAsJsonArray("list");
                    } else if (data.isJsonArray()) {
                        list = data.getAsJsonArray();
                    }

                    if (list != null && list.size() > 0) {
                        JsonObject first = list.get(0).getAsJsonObject();
                        if (first.has("songmid")) {
                            return first.get("songmid").getAsString();
                        } else if (first.has("mid")) {
                            return first.get("mid").getAsString();
                        }
                    }
                }
            }
        } catch (Exception e) {
            System.err.println("解析歌曲 ID 失败: " + e.getMessage());
        }
        return null;
    }

    /**
     * 获取网易云音乐播放链接 (支持三级降级: Native -> Unblock -> QQ)
     * 
     * @param songId 网易云歌曲ID
     * @param title  歌曲标题 (用于QQ Fallback)
     * @param artist 歌手名 (用于QQ Fallback)
     */
    private String getNeteasePlayUrl(String songId, String title, String artist) {
        try {
            // 传递 title 和 artist 给 Node.js 以支持三级降级
            String apiUrl = API_BASE_URL + "/netease/song/url?id=" + songId
                    + "&title=" + URLEncoder.encode(title, StandardCharsets.UTF_8)
                    + "&artist=" + URLEncoder.encode(artist, StandardCharsets.UTF_8);
            String result = callApi(apiUrl);

            JsonObject json = JsonParser.parseString(result).getAsJsonObject();

            if (json.has("data")) {
                JsonArray dataArray = json.getAsJsonArray("data");
                if (dataArray.size() > 0) {
                    JsonObject first = dataArray.get(0).getAsJsonObject();
                    if (first.has("url") && !first.get("url").isJsonNull()) {
                        return first.get("url").getAsString();
                    } else {
                        // URL 为空，检查是否有 fee 字段 (1: VIP, 4: Paid)
                        int fee = first.has("fee") ? first.get("fee").getAsInt() : 0;
                        if (fee == 1 || fee == 4) {
                            throw new RuntimeException("需要VIP权限或付费专辑");
                        } else {
                            throw new RuntimeException("可能是版权限制或暂时无法播放");
                        }
                    }
                }
            }
        } catch (Exception e) {
            System.err.println("获取网易云播放链接失败: " + e.getMessage());
        }
        return null;
    }

    /**
     * 获取 QQ 音乐播放链接
     */
    private String getQQPlayUrl(String songMid, String userId) {
        try {
            String apiUrl = API_BASE_URL + "/qq/song/url?id=" + songMid + "&userid="
                    + URLEncoder.encode(userId, StandardCharsets.UTF_8);
            String result = callApi(apiUrl);

            JsonObject json = JsonParser.parseString(result).getAsJsonObject();

            if (json.has("data")) {
                JsonElement data = json.get("data");
                if (data.isJsonPrimitive()) {
                    return data.getAsString();
                } else if (data.isJsonObject()) {
                    JsonObject dataObj = data.getAsJsonObject();
                    if (dataObj.has("url")) {
                        return dataObj.get("url").getAsString();
                    }
                }
            }
        } catch (Exception e) {
            System.err.println("获取 QQ 音乐播放链接失败: " + e.getMessage());
        }
        return null;
    }

    /**
     * 调用外部 API
     */
    private String callApi(String apiUrl) {
        try {
            URL url = new URL(apiUrl);
            HttpURLConnection conn = (HttpURLConnection) url.openConnection();

            conn.setRequestMethod("GET");
            conn.setConnectTimeout(CONNECT_TIMEOUT);
            conn.setReadTimeout(READ_TIMEOUT);
            conn.setRequestProperty("Accept", "application/json");

            int responseCode = conn.getResponseCode();
            InputStream inputStream = (responseCode >= 200 && responseCode < 300)
                    ? conn.getInputStream()
                    : conn.getErrorStream();

            BufferedReader reader = new BufferedReader(
                    new InputStreamReader(inputStream, StandardCharsets.UTF_8));
            StringBuilder response = new StringBuilder();
            String line;
            while ((line = reader.readLine()) != null) {
                response.append(line);
            }
            reader.close();
            conn.disconnect();

            return response.toString();

        } catch (Exception e) {
            System.err.println("API 调用失败: " + e.getMessage());
            return null;
        }
    }

    /**
     * 获取歌曲详细信息 (网易云/QQ 增强版)
     * 
     * 调用增强版详情 API 获取完整元数据：
     * - releaseYear: 发行年份
     * - coverUrl: 封面图片
     * - language: 语言
     * - company: 发行公司
     * - genre: 流派 (如有)
     */
    private JsonObject getSongDetail(String songId, String source) {
        try {
            String apiUrl;
            if ("netease".equals(source)) {
                // 使用增强版网易云详情 API
                apiUrl = API_BASE_URL + "/netease/song/detail/full?id=" + songId;
            } else if ("qq".equals(source)) {
                // 使用 QQ 音乐详情 API (通过 Python 代理)
                apiUrl = API_BASE_URL + "/qq/song/detail?mid=" + songId;
            } else {
                return null;
            }

            System.out.println("📋 [详情查询] 调用 " + source + " API: " + apiUrl);
            String result = callApi(apiUrl);
            if (result == null)
                return null;

            JsonObject json = JsonParser.parseString(result).getAsJsonObject();

            // 检查响应状态
            if (!json.has("code") || json.get("code").getAsInt() != 200 && json.get("code").getAsInt() != 0) {
                System.err.println("⚠️ 详情 API 返回错误: " + json);
                return null;
            }

            JsonObject data = json.has("data") ? json.getAsJsonObject("data") : null;
            if (data == null) {
                System.err.println("⚠️ 详情 API 返回数据为空");
                return null;
            }

            // 构建标准化的详情对象
            JsonObject details = new JsonObject();

            // 1. 发行年份
            if (data.has("releaseYear") && !data.get("releaseYear").isJsonNull()) {
                details.addProperty("releaseYear", data.get("releaseYear").getAsInt());
            } else if (data.has("publishTime") && !data.get("publishTime").isJsonNull()) {
                // 从时间戳解析年份
                long publishTime = data.get("publishTime").getAsLong();
                java.util.Calendar cal = java.util.Calendar.getInstance();
                cal.setTimeInMillis(publishTime);
                details.addProperty("releaseYear", cal.get(java.util.Calendar.YEAR));
            }

            // 2. 封面图片
            if (data.has("coverUrl") && !data.get("coverUrl").isJsonNull()) {
                String coverUrl = data.get("coverUrl").getAsString();
                if (coverUrl != null && !coverUrl.isEmpty()) {
                    details.addProperty("coverUrl", coverUrl);
                }
            }

            // 3. 语言
            if (data.has("language") && !data.get("language").isJsonNull()) {
                details.addProperty("language", data.get("language").getAsString());
            }

            // 4. 发行公司
            if (data.has("company") && !data.get("company").isJsonNull()) {
                details.addProperty("company", data.get("company").getAsString());
            }

            // 5. 流派/风格 (如有)
            if (data.has("genre") && !data.get("genre").isJsonNull()) {
                details.addProperty("genre", data.get("genre").getAsString());
                details.addProperty("genre", data.get("albumType").getAsString());
            }

            // 6. 时长 (Duration) - 解析并统一为秒
            int duration = 0;
            if (data.has("dt")) { // 网易云 (ms)
                duration = data.get("dt").getAsInt() / 1000;
            } else if (data.has("duration")) { // 网易云/通用 (ms or s?) 通常网易云 detail 是 dt
                duration = data.get("duration").getAsInt();
                // 简单判断: 如果数值巨大(>10000)认为是ms
                if (duration > 10000)
                    duration = duration / 1000;
            } else if (data.has("interval")) { // QQ (s)
                duration = data.get("interval").getAsInt();
            }
            if (duration > 0) {
                details.addProperty("duration", duration);
            }

            // 6. VIP 状态 (QQ 音乐)
            if (data.has("vip")) {
                details.addProperty("vip", data.get("vip").getAsBoolean());
            }

            // 7. 歌手信息 (用于后续处理)
            if (data.has("artists") && !data.get("artists").isJsonNull()) {
                details.addProperty("artists", data.get("artists").getAsString());
            }

            // 8. 专辑信息
            if (data.has("album") && !data.get("album").isJsonNull()) {
                details.addProperty("album", data.get("album").getAsString());
            } else if (data.has("albumName") && !data.get("albumName").isJsonNull()) {
                details.addProperty("album", data.get("albumName").getAsString());
            }

            System.out.println("✅ [详情获取成功] " + source + " | 字段数: " + details.size());
            return details;

        } catch (Exception e) {
            System.err.println("获取歌曲详情失败: " + e.getMessage());
            e.printStackTrace();
        }
        return null;
    }

    /**
     * 处理直接获取播放链接请求 (通过 ID 和 Source)
     */
    private void handleDirectRequest(String id, String source, String userId, PrintWriter out, JsonObject result) {
        try {
            JsonObject playInfo = null;

            if ("netease".equals(source)) {
                // 直接请求不含 title/artist，无法使用 QQ Fallback
                String url = getNeteasePlayUrl(id, "", "");
                if (url != null) {
                    playInfo = new JsonObject();
                    playInfo.addProperty("url", url);
                }
            } else if ("qq".equals(source)) {
                // QQ 音乐特殊处理，需要获取完整响应以判断 needLogin
                playInfo = getQQPlayUrlFull(id, userId);
            }

            if (playInfo != null) {
                // 检查 needLogin
                if (playInfo.has("needLogin") && playInfo.get("needLogin").getAsBoolean()) {
                    result.addProperty("success", true); // 请求成功，但只是需要登录
                    result.addProperty("needLogin", true);
                    result.addProperty("message", "需要登录 QQ 音乐账号");
                    result.addProperty("url", "");
                    result.addProperty("source", source);
                    result.addProperty("externalId", id);
                } else if (playInfo.has("url") && !playInfo.get("url").getAsString().isEmpty()) {
                    result.addProperty("success", true);
                    result.addProperty("url", playInfo.get("url").getAsString());
                    result.addProperty("source", source);
                    result.addProperty("externalId", id);
                    result.addProperty("cached", false);
                } else {
                    // 有响应但无 url，视为失败
                    result.addProperty("success", false);
                    result.addProperty("message", "未能获取播放链接");
                }
            } else {
                result.addProperty("success", false);
                result.addProperty("message", "未能获取播放链接");
            }

        } catch (Exception e) {
            e.printStackTrace();
            result.addProperty("success", false);
            result.addProperty("message", "服务器错误: " + e.getMessage());
        }
        out.print(gson.toJson(result));
    }

    /**
     * 获取 QQ 音乐完整播放信息 (包含 needLogin 状态)
     */
    private JsonObject getQQPlayUrlFull(String songMid, String userId) {
        try {
            String apiUrl = API_BASE_URL + "/qq/song/url?id=" + songMid + "&userid="
                    + URLEncoder.encode(userId, StandardCharsets.UTF_8);
            String result = callApi(apiUrl);
            JsonObject json = JsonParser.parseString(result).getAsJsonObject();

            if (json.has("data")) {
                // QQ API 代理返回的结构: { code: 0, data: { url: "...", needLogin: bool } }
                // 所以这里应该直接返回 json.get("data")
                return json.getAsJsonObject("data");
            }
        } catch (Exception e) {
            System.err.println("获取 QQ 音乐播放详情失败: " + e.getMessage());
        }
        return null;
    }
}
