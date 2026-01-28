package com.music.servlet;

import com.music.javabean.Song;
import jakarta.servlet.*;
import jakarta.servlet.annotation.WebServlet;
import jakarta.servlet.http.*;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;

import com.google.gson.*;

/**
 * 音频播放 Servlet
 * 改造为支持外部音乐源（网易云/QQ音乐）
 * 通过调用 Node.js API 服务获取播放链接并重定向
 */
@WebServlet("/audio")
public class AudioServlet extends HttpServlet {
    private static final long serialVersionUID = 1L;

    // Node.js API 服务地址
    private static final String API_BASE_URL = "http://localhost:3000";

    // HTTP 请求超时时间
    private static final int CONNECT_TIMEOUT = 5000;
    private static final int READ_TIMEOUT = 10000;

    @Override
    protected void doGet(HttpServletRequest request, HttpServletResponse response)
            throws ServletException, IOException {

        // 获取参数
        String source = request.getParameter("source"); // 音乐来源: netease/qq
        String externalId = request.getParameter("id"); // 外部歌曲ID

        // 参数验证
        if (source == null || externalId == null) {
            response.sendError(HttpServletResponse.SC_BAD_REQUEST,
                    "缺少必要参数: source 和 id");
            return;
        }

        try {
            // 根据来源获取播放链接
            String playUrl = null;

            if ("netease".equals(source)) {
                playUrl = getNeteasePlayUrl(externalId);
            } else if ("qq".equals(source)) {
                playUrl = getQQPlayUrl(externalId);
            } else {
                response.sendError(HttpServletResponse.SC_BAD_REQUEST,
                        "不支持的音乐源: " + source);
                return;
            }

            // 检查播放链接是否有效
            if (playUrl == null || playUrl.isEmpty()) {
                response.sendError(HttpServletResponse.SC_NOT_FOUND,
                        "无法获取播放链接，可能需要VIP或歌曲已下架");
                return;
            }

            // 重定向到播放链接
            response.sendRedirect(playUrl);

        } catch (Exception e) {
            e.printStackTrace();
            response.sendError(HttpServletResponse.SC_INTERNAL_SERVER_ERROR,
                    "获取播放链接失败: " + e.getMessage());
        }
    }

    /**
     * 获取网易云音乐播放链接
     * 
     * @param songId 网易云歌曲ID
     * @return 播放链接
     */
    private String getNeteasePlayUrl(String songId) {
        try {
            String apiUrl = API_BASE_URL + "/netease/song/url?id=" + songId;
            String result = callApi(apiUrl);

            JsonObject json = JsonParser.parseString(result).getAsJsonObject();

            if (json.has("data")) {
                JsonArray dataArray = json.getAsJsonArray("data");
                if (dataArray.size() > 0) {
                    JsonObject first = dataArray.get(0).getAsJsonObject();
                    if (first.has("url") && !first.get("url").isJsonNull()) {
                        return first.get("url").getAsString();
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
     * 
     * @param songMid QQ音乐歌曲MID
     * @return 播放链接
     */
    private String getQQPlayUrl(String songMid) {
        try {
            String apiUrl = API_BASE_URL + "/qq/song/url?id=" + songMid;
            String result = callApi(apiUrl);

            JsonObject json = JsonParser.parseString(result).getAsJsonObject();

            // 根据 QQ 音乐 API 返回格式解析
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
            System.err.println("获取QQ音乐播放链接失败: " + e.getMessage());
        }
        return null;
    }

    /**
     * 调用外部 API
     * 
     * @param apiUrl API 地址
     * @return 响应内容
     */
    private String callApi(String apiUrl) throws IOException {
        URL url = new URL(apiUrl);
        HttpURLConnection conn = (HttpURLConnection) url.openConnection();

        try {
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

            return response.toString();

        } finally {
            conn.disconnect();
        }
    }
}
