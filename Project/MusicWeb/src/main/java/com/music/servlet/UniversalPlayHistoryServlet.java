package com.music.servlet;

import com.music.dao.SongDAO;
import com.music.dao.PlayHistoryDAO;
import com.music.javabean.User;
import com.music.util.CoverDownloadUtil;
import com.google.gson.Gson;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;

import jakarta.servlet.ServletException;
import jakarta.servlet.annotation.WebServlet;
import jakarta.servlet.http.HttpServlet;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import jakarta.servlet.http.HttpSession;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.PrintWriter;

/**
 * 通用播放历史记录 Servlet
 * 
 * 功能：
 * 1. 接收前端播放 3 秒后发送的歌曲信息
 * 2. 自动添加/更新 songs 表中的记录
 * 3. 下载封面图片到本地
 * 4. 记录播放历史到 play_history 表
 * 
 * 请求：POST /api/universalPlayHistory
 * 请求体：{
 * "songId": 123, // 可选，本地歌曲 ID
 * "title": "歌曲名",
 * "artist": "歌手",
 * "album": "专辑",
 * "duration": 240,
 * "source": "netease", // 来源：netease/qq/local
 * "externalId": "123456",
 * "coverUrl": "https://..."
 * }
 * 
 * @version v3.1.0
 */
@WebServlet("/api/universalPlayHistory")
public class UniversalPlayHistoryServlet extends HttpServlet {

    private static final Gson gson = new Gson();

    @Override
    protected void doPost(HttpServletRequest request, HttpServletResponse response)
            throws ServletException, IOException {

        response.setContentType("application/json;charset=UTF-8");
        PrintWriter out = response.getWriter();
        JsonObject result = new JsonObject();

        try {
            // 1. 检查登录状态
            HttpSession session = request.getSession();
            User user = (User) session.getAttribute("user");

            if (user == null) {
                response.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
                result.addProperty("success", false);
                result.addProperty("message", "用户未登录");
                out.print(gson.toJson(result));
                return;
            }

            // 2. 解析请求体
            StringBuilder sb = new StringBuilder();
            try (BufferedReader reader = request.getReader()) {
                String line;
                while ((line = reader.readLine()) != null) {
                    sb.append(line);
                }
            }

            JsonObject body = JsonParser.parseString(sb.toString()).getAsJsonObject();

            // 3. 提取歌曲信息
            Integer songId = body.has("songId") && !body.get("songId").isJsonNull()
                    ? body.get("songId").getAsInt()
                    : null;
            String title = getJsonString(body, "title");
            String artist = getJsonString(body, "artist");
            String album = getJsonString(body, "album");
            int duration = body.has("duration") ? body.get("duration").getAsInt() : 0;
            String source = getJsonString(body, "source");
            String coverUrl = getJsonString(body, "coverUrl");
            int releaseYear = body.has("releaseYear") ? body.get("releaseYear").getAsInt() : 0;
            String genre = getJsonString(body, "genre");
            String language = getJsonString(body, "language");

            // 4. 验证必要字段
            if (title == null || title.isEmpty()) {
                result.addProperty("success", false);
                result.addProperty("message", "缺少歌曲标题");
                out.print(gson.toJson(result));
                return;
            }

            // 4.5 对于外部歌曲，如果缺少元数据，调用增强详情 API 获取
            String externalId = getJsonString(body, "externalId");
            if (source != null && !"local".equals(source) && externalId != null && !externalId.isEmpty()) {
                // 检查是否缺少关键元数据
                boolean needsEnhancement = (releaseYear == 0 || genre == null || language == null || coverUrl == null
                        || coverUrl.isEmpty());

                if (needsEnhancement) {
                    System.out.println("📡 [元数据增强] 尝试从 API 获取完整信息: " + source + " / " + externalId);
                    JsonObject enhancedData = fetchEnhancedMetadata(source, externalId);

                    if (enhancedData != null) {
                        // 用增强数据填充缺失字段
                        if (releaseYear == 0 && enhancedData.has("releaseYear")
                                && !enhancedData.get("releaseYear").isJsonNull()) {
                            releaseYear = enhancedData.get("releaseYear").getAsInt();
                            System.out.println("   ➤ releaseYear: " + releaseYear);
                        }
                        if (genre == null && enhancedData.has("genre") && !enhancedData.get("genre").isJsonNull()) {
                            genre = enhancedData.get("genre").getAsString();
                            System.out.println("   ➤ genre: " + genre);
                        }
                        if (language == null && enhancedData.has("language")
                                && !enhancedData.get("language").isJsonNull()) {
                            language = enhancedData.get("language").getAsString();
                            System.out.println("   ➤ language: " + language);
                        }
                        if ((coverUrl == null || coverUrl.isEmpty()) && enhancedData.has("coverUrl")
                                && !enhancedData.get("coverUrl").isJsonNull()) {
                            coverUrl = enhancedData.get("coverUrl").getAsString();
                            System.out.println("   ➤ coverUrl: "
                                    + (coverUrl != null ? coverUrl.substring(0, Math.min(50, coverUrl.length())) + "..."
                                            : "null"));
                        }
                        if ((album == null || album.isEmpty()) && enhancedData.has("album")
                                && !enhancedData.get("album").isJsonNull()) {
                            album = enhancedData.get("album").getAsString();
                            System.out.println("   ➤ album: " + album);
                        }
                    }
                }
            }

            System.out.println("🎵 [通用播放历史] 收到请求: " + title + " - " + artist +
                    " (source=" + source + ", songId=" + songId + ")");

            SongDAO songDAO = new SongDAO();
            PlayHistoryDAO playHistoryDAO = new PlayHistoryDAO();

            int finalSongId;

            // 5. 处理歌曲记录
            if (songId != null && songId > 0 && songDAO.isSongExist(songId)) {
                // 本地歌曲，直接使用
                finalSongId = songId;
                System.out.println("📝 [本地歌曲] 使用现有 ID=" + songId);

                // 如果有外部信息，尝试更新
                if (source != null && !source.equals("local")) {
                    String localCover = downloadCover(coverUrl, songId, request);
                    songDAO.addOrUpdateFromExternal(title, artist, album,
                            duration, source, localCover, releaseYear, genre, language);
                }
            } else {
                // 外部歌曲，需要添加或更新
                String localCover = null;

                // 先尝试下载封面（需要先获取一个临时 ID 用于命名）
                // 由于此时还没有 ID，我们先用时间戳临时命名
                if (coverUrl != null && !coverUrl.isEmpty()) {
                    // 先查找是否已存在
                    var existing = songDAO.findByTitleArtistAlbum(title, artist, album);
                    if (existing != null) {
                        localCover = downloadCover(coverUrl, existing.getId(), request);
                    }
                    // 如果不存在，先插入再下载（见下方逻辑）
                }

                // 添加或更新歌曲
                finalSongId = songDAO.addOrUpdateFromExternal(
                        title, artist, album, duration, source, localCover, releaseYear, genre, language);

                // 如果是新插入的歌曲且封面未下载，现在下载
                if (localCover == null && coverUrl != null && !coverUrl.isEmpty() && finalSongId > 0) {
                    localCover = downloadCover(coverUrl, finalSongId, request);
                    if (localCover != null) {
                        // 更新封面路径
                        songDAO.addOrUpdateFromExternal(
                                title, artist, album, duration, source, localCover, releaseYear, genre, language);
                    }
                }
            }

            // 6. 记录播放历史
            if (finalSongId > 0) {
                boolean historyAdded = playHistoryDAO.addPlayHistory(user.getId(), finalSongId);
                result.addProperty("success", true);
                result.addProperty("songId", finalSongId);
                result.addProperty("historyRecorded", historyAdded);
                System.out.println("✅ [播放历史] 记录成功: userId=" + user.getId() + ", songId=" + finalSongId);
            } else {
                result.addProperty("success", false);
                result.addProperty("message", "无法处理歌曲信息");
            }

        } catch (Exception e) {
            e.printStackTrace();
            result.addProperty("success", false);
            result.addProperty("message", "服务器错误: " + e.getMessage());
        }

        out.print(gson.toJson(result));
    }

    /**
     * 安全获取 JSON 字符串字段
     */
    private String getJsonString(JsonObject obj, String key) {
        if (obj.has(key) && !obj.get(key).isJsonNull()) {
            return obj.get(key).getAsString();
        }
        return null;
    }

    /**
     * 下载封面到本地
     */
    private String downloadCover(String coverUrl, int songId, HttpServletRequest request) {
        if (coverUrl == null || coverUrl.isEmpty() || songId <= 0) {
            return null;
        }

        String webappPath = request.getServletContext().getRealPath("/");
        return CoverDownloadUtil.downloadCover(coverUrl, songId, webappPath);
    }

    /**
     * 从增强详情 API 获取完整元数据
     * 
     * @param source     音乐来源 (netease/qq)
     * @param externalId 外部歌曲 ID
     * @return 包含 releaseYear, coverUrl, language, genre 等字段的 JsonObject
     */
    private JsonObject fetchEnhancedMetadata(String source, String externalId) {
        try {
            String apiUrl;
            if ("netease".equals(source)) {
                apiUrl = "http://localhost:3000/netease/song/detail/full?id=" + externalId;
            } else if ("qq".equals(source)) {
                apiUrl = "http://localhost:3000/qq/song/detail?mid=" + externalId;
            } else {
                return null;
            }

            // 调用 API
            java.net.URL url = new java.net.URL(apiUrl);
            java.net.HttpURLConnection conn = (java.net.HttpURLConnection) url.openConnection();
            conn.setRequestMethod("GET");
            conn.setConnectTimeout(5000);
            conn.setReadTimeout(10000);

            int responseCode = conn.getResponseCode();
            if (responseCode != 200) {
                System.err.println("⚠️ [元数据增强] API 返回非 200: " + responseCode);
                return null;
            }

            // 读取响应
            StringBuilder sb = new StringBuilder();
            try (java.io.BufferedReader reader = new java.io.BufferedReader(
                    new java.io.InputStreamReader(conn.getInputStream(), "UTF-8"))) {
                String line;
                while ((line = reader.readLine()) != null) {
                    sb.append(line);
                }
            }

            JsonObject json = JsonParser.parseString(sb.toString()).getAsJsonObject();

            // 检查响应状态
            if (!json.has("code")) {
                return null;
            }
            int code = json.get("code").getAsInt();
            if (code != 200 && code != 0) {
                System.err.println("⚠️ [元数据增强] API 业务错误: code=" + code);
                return null;
            }

            // 返回 data 对象
            if (json.has("data") && !json.get("data").isJsonNull()) {
                System.out.println("✅ [元数据增强] 成功获取增强数据");
                return json.getAsJsonObject("data");
            }

            return null;

        } catch (Exception e) {
            System.err.println("⚠️ [元数据增强] 调用 API 失败: " + e.getMessage());
            return null;
        }
    }
}
