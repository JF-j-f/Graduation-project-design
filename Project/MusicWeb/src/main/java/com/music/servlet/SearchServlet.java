package com.music.servlet;

import com.music.javabean.User;
import com.music.javabean.Song;
import jakarta.servlet.ServletException;
import jakarta.servlet.annotation.WebServlet;
import jakarta.servlet.http.HttpServlet;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import jakarta.servlet.http.HttpSession;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import com.music.util.ServiceConfig;

import com.google.gson.*;

/**
 * 搜索 Servlet
 * 支持从网易云音乐和 QQ 音乐搜索歌曲
 */
@WebServlet("/search")
public class SearchServlet extends HttpServlet {
    private static final long serialVersionUID = 1L;

    // Node.js API 服务地址
    private static final String API_BASE_URL = ServiceConfig.getMusicApiUrl();

    // 默认搜索结果数量
    private static final int DEFAULT_LIMIT = 30;

    @Override
    protected void doGet(HttpServletRequest request, HttpServletResponse response)
            throws ServletException, IOException {

        // 设置编码
        request.setCharacterEncoding("UTF-8");
        response.setContentType("text/html;charset=UTF-8");

        // 检查用户是否登录
        HttpSession session = request.getSession();
        User user = (User) session.getAttribute("user");
        if (user == null) {
            response.sendRedirect("index.jsp");
            return;
        }

        // 获取搜索参数
        String keyword = request.getParameter("keyword");
        String source = request.getParameter("source"); // netease/qq/all

        if (keyword == null) {
            keyword = "";
        }
        keyword = keyword.trim();

        if (source == null || source.isEmpty()) {
            source = "netease"; // 默认使用网易云
        }

        System.out.println("🔍 [DEBUG] 外部搜索 - 用户: " + user.getUsername()
                + ", 关键词: " + keyword + ", 来源: " + source);

        // 执行外部搜索
        List<Song> searchResults = new ArrayList<>();

        if (!keyword.isEmpty()) {
            searchResults = searchExternalSongs(keyword, source, DEFAULT_LIMIT);
        }

        // 传递数据到JSP
        request.setAttribute("keyword", keyword);
        request.setAttribute("source", source);
        request.setAttribute("searchResults", searchResults);
        request.setAttribute("resultCount", searchResults.size());

        // 转发到搜索结果页面
        request.getRequestDispatcher("search.jsp").forward(request, response);
    }

    @Override
    protected void doPost(HttpServletRequest request, HttpServletResponse response)
            throws ServletException, IOException {
        doGet(request, response);
    }

    /**
     * 从外部音乐平台搜索歌曲
     * 
     * @param keyword 搜索关键词
     * @param source  音乐源 (netease/qq/all)
     * @param limit   返回数量
     * @return 歌曲列表
     */
    private List<Song> searchExternalSongs(String keyword, String source, int limit) {
        List<Song> songs = new ArrayList<>();

        if ("all".equals(source)) {
            // 聚合搜索：分别搜索网易云和QQ，然后交替合并
            List<Song> neteaseSongs = new ArrayList<>();
            List<Song> qqSongs = new ArrayList<>();

            try {
                neteaseSongs = searchExternalSongs(keyword, "netease", limit);
            } catch (Exception e) {
                System.err.println("⚠️ 网易云搜索失败: " + e.getMessage());
            }

            try {
                qqSongs = searchExternalSongs(keyword, "qq", limit);
            } catch (Exception e) {
                System.err.println("⚠️ QQ音乐搜索失败: " + e.getMessage());
            }

            System.out.println("🔍 [DEBUG] 聚合结果 - 网易云: " + neteaseSongs.size() + "首, QQ: " + qqSongs.size() + "首");

            // 交替合并结果
            int maxSize = Math.max(neteaseSongs.size(), qqSongs.size());
            for (int i = 0; i < maxSize; i++) {
                if (i < neteaseSongs.size())
                    songs.add(neteaseSongs.get(i));
                if (i < qqSongs.size())
                    songs.add(qqSongs.get(i));
            }
            return songs;
        }

        try {
            // 单源搜索
            String encodedKeyword = URLEncoder.encode(keyword, StandardCharsets.UTF_8.toString());
            String apiUrl;

            if ("netease".equals(source)) {
                apiUrl = API_BASE_URL + "/netease/search?keywords=" + encodedKeyword + "&limit=" + limit;
            } else {
                // 修复参数: server.js 需 keywords 和 limit
                apiUrl = API_BASE_URL + "/qq/search?keywords=" + encodedKeyword + "&limit=" + limit;
            }

            String result = callApi(apiUrl);
            if (result == null || result.isEmpty())
                return songs;

            JsonObject json = JsonParser.parseString(result).getAsJsonObject();

            if ("netease".equals(source)) {
                // 网易云音乐格式: { "result": { "songs": [...] } }
                if (json.has("result")) {
                    JsonObject resultObj = json.getAsJsonObject("result");
                    if (resultObj.has("songs")) {
                        JsonArray songsArray = resultObj.getAsJsonArray("songs");
                        for (JsonElement elem : songsArray) {
                            Song song = parseNeteaseSong(elem.getAsJsonObject());
                            if (song != null)
                                songs.add(song);
                        }
                    }
                }
            } else {
                // QQ 音乐格式: { "data": { "list": [...] } }
                if (json.has("data")) {
                    JsonElement dataElem = json.get("data");
                    JsonArray songsArray = null;

                    if (dataElem.isJsonArray()) {
                        // 新 Python API 格式: data 直接是数组
                        songsArray = dataElem.getAsJsonArray();
                    } else if (dataElem.isJsonObject()) {
                        // 旧格式或兼容格式: data.list
                        JsonObject dataObj = dataElem.getAsJsonObject();
                        if (dataObj.has("list")) {
                            songsArray = dataObj.getAsJsonArray("list");
                        }
                    }

                    if (songsArray != null) {
                        for (JsonElement elem : songsArray) {
                            Song song = parseQQSong(elem.getAsJsonObject());
                            if (song != null)
                                songs.add(song);
                        }
                    }
                }
            }

        } catch (Exception e) {
            System.err.println("外部搜索失败 [" + source + "]: " + e.getMessage());
            e.printStackTrace();
        }

        return songs;
    }

    /**
     * 解析网易云音乐歌曲
     */
    private Song parseNeteaseSong(JsonObject json) {
        try {
            Song song = new Song();
            song.setSource("netease");
            song.setExternalId(String.valueOf(json.get("id").getAsLong()));
            song.setTitle(json.get("name").getAsString());

            // 艺术家
            if (json.has("artists") && json.getAsJsonArray("artists").size() > 0) {
                StringBuilder artists = new StringBuilder();
                for (JsonElement artistElem : json.getAsJsonArray("artists")) {
                    if (artists.length() > 0)
                        artists.append(" / ");
                    artists.append(artistElem.getAsJsonObject().get("name").getAsString());
                }
                song.setArtist(artists.toString());
            }

            // 专辑
            if (json.has("album") && !json.get("album").isJsonNull()) {
                JsonObject album = json.getAsJsonObject("album");
                if (album.has("name")) {
                    song.setAlbum(album.get("name").getAsString());
                }
                if (album.has("picUrl")) {
                    song.setCoverUrl(album.get("picUrl").getAsString());
                }
            }

            // VIP检测 (网易云)
            // fee: 1 (VIP), 4 (付费专辑), 8 (低音质免费)
            if (json.has("fee")) {
                int fee = json.get("fee").getAsInt();
                if (fee == 1 || fee == 4) {
                    song.setVip(true);
                }
            }

            // 时长（毫秒转秒）
            if (json.has("duration")) {
                song.setDuration(json.get("duration").getAsInt() / 1000);
            }

            return song;
        } catch (

        Exception e) {
            System.err.println("解析网易云歌曲失败: " + e.getMessage());
            return null;
        }
    }

    /**
     * 解析 QQ 音乐歌曲
     */
    private Song parseQQSong(JsonObject json) {
        try {
            Song song = new Song();
            song.setSource("qq");

            // ID处理：优先使用 songmid，其次 mid
            if (json.has("songmid")) {
                song.setExternalId(json.get("songmid").getAsString());
            } else if (json.has("mid")) {
                song.setExternalId(json.get("mid").getAsString());
            } else {
                System.err.println("⚠️ [QQ解析] 缺少 songmid: " + json);
                return null;
            }

            // 歌名
            if (json.has("songname")) {
                song.setTitle(json.get("songname").getAsString());
            } else if (json.has("name")) {
                song.setTitle(json.get("name").getAsString());
            } else {
                song.setTitle("Unknown Song");
            }

            // 艺术家
            if (json.has("singer") && json.getAsJsonArray("singer").size() > 0) {
                StringBuilder singers = new StringBuilder();
                for (JsonElement singerElem : json.getAsJsonArray("singer")) {
                    if (singers.length() > 0)
                        singers.append(" / ");
                    singers.append(singerElem.getAsJsonObject().get("name").getAsString());
                }
                song.setArtist(singers.toString());
            } else {
                song.setArtist("Unknown Artist");
            }

            // 专辑
            if (json.has("albumname")) {
                song.setAlbum(json.get("albumname").getAsString());
            } else if (json.has("album") && json.getAsJsonObject("album").has("name")) {
                song.setAlbum(json.getAsJsonObject("album").get("name").getAsString());
            }

            // VIP检测 (QQ)
            // 优先检查 Node.js 注入的 vip 字段
            if (json.has("vip")) {
                song.setVip(json.get("vip").getAsBoolean());
            }
            // 其次检查原始 pay.pay_play 字段
            else if (json.has("pay") && json.getAsJsonObject("pay").has("pay_play")) {
                int payPlay = json.getAsJsonObject("pay").get("pay_play").getAsInt();
                if (payPlay == 1) {
                    song.setVip(true);
                }
            } else if (json.has("pay") && json.getAsJsonObject("pay").has("payplay")) {
                int payPlay = json.getAsJsonObject("pay").get("payplay").getAsInt();
                if (payPlay == 1) {
                    song.setVip(true);
                }
            }

            // 封面图片
            if (json.has("albummid")) {
                String albumMid = json.get("albummid").getAsString();
                song.setCoverUrl("https://y.qq.com/music/photo_new/T002R300x300M000" + albumMid + ".jpg");
            } else if (json.has("album") && json.getAsJsonObject("album").has("mid")) {
                String albumMid = json.getAsJsonObject("album").get("mid").getAsString();
                song.setCoverUrl("https://y.qq.com/music/photo_new/T002R300x300M000" + albumMid + ".jpg");
            }

            // 时长
            if (json.has("interval")) {
                song.setDuration(json.get("interval").getAsInt());
            }

            return song;
        } catch (Exception e) {
            System.err.println("⚠️ 解析QQ音乐歌曲异常: " + e.getMessage() + " | JSON: " + json);
            return null;
        }
    }

    /**
     * 调用外部 API
     */
    private String callApi(String apiUrl) throws IOException {
        URL url = new URL(apiUrl);
        HttpURLConnection conn = (HttpURLConnection) url.openConnection();

        try {
            conn.setRequestMethod("GET");
            conn.setConnectTimeout(5000);
            conn.setReadTimeout(10000);
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

            return response.toString();

        } finally {
            conn.disconnect();
        }
    }
}
