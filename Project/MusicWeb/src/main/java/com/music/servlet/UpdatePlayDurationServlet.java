package com.music.servlet;

import com.music.dao.PlayHistoryDAO;
import com.music.javabean.User;
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
 * 更新播放时长 Servlet (v4.0)
 *
 * 功能：接收前端在切歌/歌曲结束时上报的实际收听时长，
 *       更新 play_history 表中该用户最近一条记录的 play_duration。
 *
 * 请求：POST /api/updatePlayDuration
 * 请求体 JSON：{ "songId": 123, "playDuration": 85 }
 * 响应 JSON：{ "success": true } 或 { "success": false, "message": "..." }
 */
@WebServlet("/api/updatePlayDuration")
public class UpdatePlayDurationServlet extends HttpServlet {

    @Override
    protected void doPost(HttpServletRequest request, HttpServletResponse response)
            throws ServletException, IOException {

        response.setContentType("application/json;charset=UTF-8");
        PrintWriter out = response.getWriter();

        // 1. 校验登录状态
        HttpSession session = request.getSession(false);
        if (session == null || session.getAttribute("user") == null) {
            out.print("{\"success\":false,\"message\":\"未登录\"}");
            return;
        }
        User user = (User) session.getAttribute("user");
        int userId = user.getId();

        // 2. 解析请求体
        StringBuilder sb = new StringBuilder();
        try (BufferedReader reader = request.getReader()) {
            String line;
            while ((line = reader.readLine()) != null) {
                sb.append(line);
            }
        }

        JsonObject json;
        try {
            json = JsonParser.parseString(sb.toString()).getAsJsonObject();
        } catch (Exception e) {
            response.setStatus(HttpServletResponse.SC_BAD_REQUEST);
            out.print("{\"success\":false,\"message\":\"请求体格式错误\"}");
            return;
        }

        // 3. 提取并校验参数
        int songId;
        int playDuration;
        try {
            songId       = json.get("songId").getAsInt();
            playDuration = json.get("playDuration").getAsInt();
        } catch (Exception e) {
            response.setStatus(HttpServletResponse.SC_BAD_REQUEST);
            out.print("{\"success\":false,\"message\":\"参数缺失或格式错误\"}");
            return;
        }

        if (songId <= 0 || playDuration < 1) {
            // songId 无效或时长极短（< 1 秒），忽略
            out.print("{\"success\":true,\"message\":\"已忽略\"}");
            return;
        }

        // 4. 更新数据库
        PlayHistoryDAO dao = new PlayHistoryDAO();
        boolean ok = dao.updatePlayDuration(userId, songId, playDuration);

        if (ok) {
            out.print("{\"success\":true}");
        } else {
            // 找不到对应记录（可能 3 秒上报还未到达），静默成功
            out.print("{\"success\":true,\"message\":\"未找到对应记录，已忽略\"}");
        }
    }
}
