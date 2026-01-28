package com.music.servlet;

import com.music.dao.PlayHistoryDAO;
import com.music.javabean.PlayHistory;
import com.music.javabean.User;
import jakarta.servlet.*;
import jakarta.servlet.annotation.WebServlet;
import jakarta.servlet.http.*;
import java.io.*;
import java.util.List;

@WebServlet("/playHistory")
public class PlayHistoryServlet extends HttpServlet {
    private static final long serialVersionUID = 1L;

    protected void doPost(HttpServletRequest request, HttpServletResponse response)
            throws ServletException, IOException {

        String action = request.getParameter("action");
        HttpSession session = request.getSession();
        User user = (User) session.getAttribute("user");

        response.setContentType("text/html;charset=UTF-8");

        // 检查用户是否登录
        if (user == null) {
            response.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
            response.getWriter().write("未登录");
            return;
        }

        PlayHistoryDAO playHistoryDAO = new PlayHistoryDAO();

        if ("add".equals(action)) {
            // 添加播放历史
            String songIdStr = request.getParameter("songId");

            if (songIdStr == null || songIdStr.isEmpty()) {
                response.setStatus(HttpServletResponse.SC_BAD_REQUEST);
                response.getWriter().write("缺少歌曲ID");
                return;
            }

            try {
                int songId = Integer.parseInt(songIdStr);

                if (playHistoryDAO.addPlayHistory(user.getId(), songId)) {
                    response.setStatus(HttpServletResponse.SC_OK);
                    response.getWriter().write("添加成功");
                } else {
                    response.setStatus(HttpServletResponse.SC_INTERNAL_SERVER_ERROR);
                    response.getWriter().write("添加失败");
                }

            } catch (NumberFormatException e) {
                response.setStatus(HttpServletResponse.SC_BAD_REQUEST);
                response.getWriter().write("歌曲ID格式错误");
            }

        } else if ("clear".equals(action)) {
            // 清空播放历史
            if (playHistoryDAO.clearPlayHistory(user.getId())) {
                response.setStatus(HttpServletResponse.SC_OK);
                response.getWriter().write("清空成功");
            } else {
                response.setStatus(HttpServletResponse.SC_INTERNAL_SERVER_ERROR);
                response.getWriter().write("清空失败");
            }

        } else {
            response.setStatus(HttpServletResponse.SC_BAD_REQUEST);
            response.getWriter().write("无效的操作");
        }
    }

    protected void doGet(HttpServletRequest request, HttpServletResponse response)
            throws ServletException, IOException {

        String action = request.getParameter("action");
        HttpSession session = request.getSession();
        User user = (User) session.getAttribute("user");

        response.setContentType("application/json;charset=UTF-8");
        PrintWriter out = response.getWriter();

        // 检查用户是否登录
        if (user == null) {
            response.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
            out.write("{\"error\": \"未登录\"}");
            return;
        }

        PlayHistoryDAO playHistoryDAO = new PlayHistoryDAO();

        if ("list".equals(action) || "recent".equals(action)) {
            // 获取播放历史列表
            String limitStr = request.getParameter("limit");
            int limit = 20; // 默认20条

            if (limitStr != null && !limitStr.isEmpty()) {
                try {
                    limit = Integer.parseInt(limitStr);
                } catch (NumberFormatException e) {
                    // 使用默认值
                }
            }

            List<PlayHistory> historyList = playHistoryDAO.getUserPlayHistory(user.getId(), limit);

            // 构建JSON响应
            StringBuilder json = new StringBuilder();
            json.append("{\"success\": true, \"data\": [");

            for (int i = 0; i < historyList.size(); i++) {
                PlayHistory history = historyList.get(i);
                if (i > 0) json.append(",");

                json.append("{")
                    .append("\"id\": ").append(history.getId()).append(",")
                    .append("\"songId\": ").append(history.getSongId()).append(",")
                    .append("\"playTime\": \"").append(history.getPlayTime()).append("\",")
                    .append("\"song\": {")
                        .append("\"id\": ").append(history.getSong().getId()).append(",")
                        .append("\"title\": \"").append(escapeJson(history.getSong().getTitle())).append("\",")
                        .append("\"artist\": \"").append(escapeJson(history.getSong().getArtist())).append("\",")
                        .append("\"album\": \"").append(escapeJson(history.getSong().getAlbum())).append("\",")
                        .append("\"duration\": ").append(history.getSong().getDuration())
                    .append("}")
                    .append("}");
            }

            json.append("]}");
            out.write(json.toString());

        } else if ("count".equals(action)) {
            // 获取播放历史总数
            int count = playHistoryDAO.getPlayHistoryCount(user.getId());
            out.write("{\"success\": true, \"count\": " + count + "}");

        } else {
            response.setStatus(HttpServletResponse.SC_BAD_REQUEST);
            out.write("{\"error\": \"无效的操作\"}");
        }
    }

    // 转义JSON字符串中的特殊字符
    private String escapeJson(String str) {
        if (str == null) return "";
        return str.replace("\\", "\\\\")
                  .replace("\"", "\\\"")
                  .replace("\n", "\\n")
                  .replace("\r", "\\r")
                  .replace("\t", "\\t");
    }
}
