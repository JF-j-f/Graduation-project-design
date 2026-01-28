package com.music.servlet;

import com.music.dao.SongDAO;
import com.music.dao.FavoriteDAO;
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

        // 3. 【关键修复】清除用户推荐缓存，确保每次刷新获取新数据
        String cacheKey = com.music.dao.RedisUtil.getUserRecommendationsKey(user.getId());
        com.music.dao.RedisUtil.delete(cacheKey);
        System.out.println("🔄 [刷新推荐] 已清除用户 " + user.getId() + " 的推荐缓存");

        // 4. 获取推荐数据
        SongDAO songDAO = new SongDAO();
        FavoriteDAO favoriteDAO = new FavoriteDAO();

        // 获取 5 首随机推荐
        List<Song> songs = songDAO.getRecommendationsByRandom(user.getId(), 5);

        // 4. 手动构建 JSON (避免引入 Jackson 等库，保持轻量)
        StringBuilder json = new StringBuilder("[");
        for (int i = 0; i < songs.size(); i++) {
            Song s = songs.get(i);
            boolean isFavorited = favoriteDAO.isFavorite(user.getId(), s.getId());

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