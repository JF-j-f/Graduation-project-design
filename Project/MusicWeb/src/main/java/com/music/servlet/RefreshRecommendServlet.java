package com.music.servlet;

import com.music.dao.SongDAO;
import com.music.dao.PlaylistDAO;
import com.music.javabean.Song;
import com.music.javabean.User;
import jakarta.servlet.ServletException;
import jakarta.servlet.annotation.WebServlet;
import jakarta.servlet.http.HttpServlet;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import jakarta.servlet.http.HttpSession;

import java.io.IOException;
import java.io.PrintWriter;
import java.util.List;

@WebServlet("/api/refreshRecommend")
public class RefreshRecommendServlet extends HttpServlet {

    @Override
    protected void doGet(HttpServletRequest request, HttpServletResponse response)
            throws ServletException, IOException {
        // 1. 设置响应类型为 JSON
        response.setContentType("application/json");
        response.setCharacterEncoding("UTF-8");
        PrintWriter out = response.getWriter();

        // 2. 检查登录状态
        HttpSession session = request.getSession();
        User user = (User) session.getAttribute("user");

        if (user == null) {
            response.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
            out.print("{\"error\": \"User not logged in\"}");
            return;
        }

        // 3. 接收和解析 offset 参数（基于得分高低流转所需）
        int offset = 0;
        String offsetStr = request.getParameter("offset");
        if (offsetStr != null && !offsetStr.isEmpty()) {
            try {
                offset = Integer.parseInt(offsetStr);
            } catch (NumberFormatException e) {
                // 忽略解析错误，保持 0
            }
        }

        // 4. 获取推荐数据
        SongDAO songDAO = new SongDAO();
        PlaylistDAO playlistDAO = new PlaylistDAO(); // v3.3.0: 统一使用 PlaylistDAO 判断收藏

        // 获取对应 offset 下的 5 首依 score 排序的推荐
        List<Song> songs = songDAO.getRecommendationsByScore(user.getId(), 5, offset);

        // 4. 手动构建 JSON (避免引入 Jackson 等库，保持轻量)
        StringBuilder json = new StringBuilder("[");
        for (int i = 0; i < songs.size(); i++) {
            Song s = songs.get(i);
            boolean isFavorited = playlistDAO.isFavorite(user.getId(), s.getId()); // 基于默认歌单判断

            json.append("{")
                    .append("\"id\":").append(s.getId()).append(",")
                    .append("\"title\":\"").append(escapeJson(s.getTitle())).append("\",")
                    .append("\"artist\":\"").append(escapeJson(s.getArtist())).append("\",")
                    .append("\"album\":\"").append(escapeJson(s.getAlbum())).append("\",")
                    .append("\"coverImage\":\"").append(s.getCoverImage() != null ? s.getCoverImage() : "")
                    .append("\",")
                    .append("\"duration\":").append(s.getDuration()).append(",")
                    .append("\"isFavorited\":").append(isFavorited)
                    .append("}");

            if (i < songs.size() - 1) {
                json.append(",");
            }
        }
        json.append("]");

        out.print(json.toString());
        out.flush();
    }

    // 简单的 JSON 转义辅助方法
    private String escapeJson(String input) {
        if (input == null)
            return "";
        return input.replace("\\", "\\\\")
                .replace("\"", "\\\"")
                .replace("\n", "\\n")
                .replace("\r", "\\r");
    }
}