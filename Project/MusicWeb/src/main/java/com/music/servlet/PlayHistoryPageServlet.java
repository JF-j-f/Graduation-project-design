package com.music.servlet;

import com.music.dao.PlayHistoryDAO;
import com.music.javabean.PlayHistory;
import com.music.javabean.User;
import com.google.gson.Gson;
import com.google.gson.JsonObject;

import jakarta.servlet.ServletException;
import jakarta.servlet.annotation.WebServlet;
import jakarta.servlet.http.HttpServlet;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import jakarta.servlet.http.HttpSession;

import java.io.IOException;
import java.io.PrintWriter;
import java.util.List;

/**
 * 播放历史分页查询 Servlet
 * 
 * 支持按时间范围（7天/30天/90天）和分页查询
 * 
 * 请求：GET /api/playHistoryPage
 * 参数：
 * - days: 7, 30, or 90 (时间范围)
 * - page: 页码 (从1开始)
 * - pageSize: 每页数量 (默认25)
 * 
 * 响应：
 * {
 * "code": 0,
 * "data": {
 * "items": [...],
 * "totalItems": 123,
 * "totalPages": 5,
 * "currentPage": 1
 * }
 * }
 * 
 * @version v3.1.0
 */
@WebServlet("/api/playHistoryPage")
public class PlayHistoryPageServlet extends HttpServlet {

    private static final Gson gson = new Gson();

    @Override
    protected void doGet(HttpServletRequest request, HttpServletResponse response)
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
                result.addProperty("code", -1);
                result.addProperty("message", "用户未登录");
                out.print(gson.toJson(result));
                return;
            }

            // 2. 解析参数
            int days = parseIntParam(request, "days", 7);
            int page = parseIntParam(request, "page", 1);
            int pageSize = parseIntParam(request, "pageSize", 25);

            // 验证参数
            if (days != 7 && days != 30 && days != 90) {
                days = 7;
            }
            if (page < 1)
                page = 1;
            if (pageSize < 1 || pageSize > 100)
                pageSize = 25;

            // 3. 查询播放历史
            PlayHistoryDAO dao = new PlayHistoryDAO();
            List<PlayHistory> items = dao.getUserPlayHistoryByDays(user.getId(), days, page, pageSize);
            int totalItems = dao.getPlayHistoryCountByDays(user.getId(), days);
            int totalPages = (int) Math.ceil((double) totalItems / pageSize);

            // 4. 构建响应
            result.addProperty("code", 0);

            JsonObject data = new JsonObject();
            data.add("items", gson.toJsonTree(items));
            data.addProperty("totalItems", totalItems);
            data.addProperty("totalPages", totalPages);
            data.addProperty("currentPage", page);
            data.addProperty("pageSize", pageSize);
            data.addProperty("days", days);

            result.add("data", data);

            System.out.println("📋 [播放历史分页] userId=" + user.getId() +
                    ", days=" + days + ", page=" + page + "/" + totalPages +
                    ", items=" + items.size() + "/" + totalItems);

        } catch (Exception e) {
            e.printStackTrace();
            result.addProperty("code", -1);
            result.addProperty("message", "服务器错误: " + e.getMessage());
        }

        out.print(gson.toJson(result));
    }

    private int parseIntParam(HttpServletRequest request, String name, int defaultValue) {
        String value = request.getParameter(name);
        if (value != null && !value.isEmpty()) {
            try {
                return Integer.parseInt(value);
            } catch (NumberFormatException e) {
                return defaultValue;
            }
        }
        return defaultValue;
    }
}
