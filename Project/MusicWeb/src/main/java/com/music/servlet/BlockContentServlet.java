package com.music.servlet;

import com.music.dao.RedisUtil;
import com.music.javabean.DBUtil;
import com.music.javabean.User;
import com.google.gson.Gson;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.google.gson.reflect.TypeToken;

import jakarta.servlet.ServletException;
import jakarta.servlet.annotation.WebServlet;
import jakarta.servlet.http.HttpServlet;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import jakarta.servlet.http.HttpSession;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.PrintWriter;
import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.List;

/**
 * 屏蔽管理 API
 *
 * GET    /api/blockContent              → 返回用户当前所有屏蔽项
 * POST   /api/blockContent              → 屏蔽流派/歌手 {type:"genre"/"artist", value:"摇滚"}
 * DELETE /api/blockContent?type=genre&value=摇滚 → 手动取消屏蔽
 */
@WebServlet("/api/blockContent")
public class BlockContentServlet extends HttpServlet {

    private static final Gson gson = new Gson();

    // ── 内部数据结构 ──────────────────────────────────────────
    private static class BlockItem {
        String type;
        String value;
        String blockedUntil;
        int blockCount;
        boolean isActive;

        BlockItem(String type, String value, String blockedUntil, int blockCount, boolean isActive) {
            this.type = type;
            this.value = value;
            this.blockedUntil = blockedUntil;
            this.blockCount = blockCount;
            this.isActive = isActive;
        }
    }

    // ── GET：返回当前屏蔽列表 ──────────────────────────────────
    @Override
    protected void doGet(HttpServletRequest request, HttpServletResponse response)
            throws ServletException, IOException {

        response.setContentType("application/json;charset=UTF-8");
        PrintWriter out = response.getWriter();

        int userId = getLoginUserId(request);
        if (userId < 0) {
            out.print("{\"success\":false,\"message\":\"未登录\"}");
            return;
        }

        try {
            List<BlockItem> blocks = getBlocks(userId);
            JsonObject result = new JsonObject();
            result.addProperty("success", true);
            result.add("blocks", gson.toJsonTree(blocks));
            out.print(gson.toJson(result));
        } catch (Exception e) {
            System.err.println("BlockContent GET 失败: " + e.getMessage());
            response.setStatus(HttpServletResponse.SC_INTERNAL_SERVER_ERROR);
            out.print("{\"success\":false,\"message\":\"服务器内部错误\"}");
        }
    }

    // ── POST：添加屏蔽 ────────────────────────────────────────
    @Override
    protected void doPost(HttpServletRequest request, HttpServletResponse response)
            throws ServletException, IOException {

        response.setContentType("application/json;charset=UTF-8");
        PrintWriter out = response.getWriter();

        int userId = getLoginUserId(request);
        if (userId < 0) {
            out.print("{\"success\":false,\"message\":\"未登录\"}");
            return;
        }

        // 解析请求体
        StringBuilder sb = new StringBuilder();
        try (BufferedReader reader = request.getReader()) {
            String line;
            while ((line = reader.readLine()) != null) sb.append(line);
        }

        JsonObject json;
        try {
            json = JsonParser.parseString(sb.toString()).getAsJsonObject();
        } catch (Exception e) {
            response.setStatus(HttpServletResponse.SC_BAD_REQUEST);
            out.print("{\"success\":false,\"message\":\"请求体格式错误\"}");
            return;
        }

        String type = getStr(json, "type");
        String value = getStr(json, "value");

        if (type == null || value == null || value.isEmpty()
                || (!"genre".equals(type) && !"artist".equals(type))) {
            response.setStatus(HttpServletResponse.SC_BAD_REQUEST);
            out.print("{\"success\":false,\"message\":\"参数错误：type 须为 genre/artist，value 不能为空\"}");
            return;
        }

        try {
            String result = addBlock(userId, type, value);
            RedisUtil.clearUserBlocksCache(userId);
            out.print("{\"success\":true,\"message\":\"" + result + "\"}");
        } catch (Exception e) {
            System.err.println("BlockContent POST 失败: " + e.getMessage());
            response.setStatus(HttpServletResponse.SC_INTERNAL_SERVER_ERROR);
            out.print("{\"success\":false,\"message\":\"服务器内部错误\"}");
        }
    }

    // ── DELETE：取消屏蔽 ──────────────────────────────────────
    @Override
    protected void doDelete(HttpServletRequest request, HttpServletResponse response)
            throws ServletException, IOException {

        response.setContentType("application/json;charset=UTF-8");
        PrintWriter out = response.getWriter();

        int userId = getLoginUserId(request);
        if (userId < 0) {
            out.print("{\"success\":false,\"message\":\"未登录\"}");
            return;
        }

        String type = request.getParameter("type");
        String value = request.getParameter("value");

        if (type == null || value == null || value.isEmpty()) {
            response.setStatus(HttpServletResponse.SC_BAD_REQUEST);
            out.print("{\"success\":false,\"message\":\"参数错误：需要 type 和 value\"}");
            return;
        }

        try {
            removeBlock(userId, type, value);
            RedisUtil.clearUserBlocksCache(userId);
            out.print("{\"success\":true,\"message\":\"已取消屏蔽\"}");
        } catch (Exception e) {
            System.err.println("BlockContent DELETE 失败: " + e.getMessage());
            response.setStatus(HttpServletResponse.SC_INTERNAL_SERVER_ERROR);
            out.print("{\"success\":false,\"message\":\"服务器内部错误\"}");
        }
    }

    // ── 业务逻辑：获取屏蔽列表（Redis 缓存优先） ──────────────
    private List<BlockItem> getBlocks(int userId) throws SQLException {
        // 优先读 Redis 缓存
        String cacheKey = RedisUtil.getUserBlocksKey(userId);
        List<BlockItem> cached = RedisUtil.getList(cacheKey,
                new TypeToken<List<BlockItem>>() {});
        if (cached != null) {
            return cached;
        }

        // 缓存未命中 → 查 DB
        List<BlockItem> blocks = new ArrayList<>();
        String sql = "SELECT block_type, block_value, blocked_until, block_count, is_active "
                   + "FROM user_content_blocks WHERE user_id = ? ORDER BY blocked_at DESC";
        try (Connection conn = DBUtil.getConnection();
             PreparedStatement ps = conn.prepareStatement(sql)) {
            ps.setInt(1, userId);
            ResultSet rs = ps.executeQuery();
            while (rs.next()) {
                blocks.add(new BlockItem(
                        rs.getString("block_type"),
                        rs.getString("block_value"),
                        rs.getString("blocked_until"),
                        rs.getInt("block_count"),
                        rs.getInt("is_active") == 1
                ));
            }
        }

        // 写入缓存（1 小时 TTL）
        RedisUtil.setList(cacheKey, blocks, RedisUtil.TTL_LONG);
        return blocks;
    }

    // ── 业务逻辑：添加屏蔽 ────────────────────────────────────
    private String addBlock(int userId, String type, String value) throws SQLException {
        // 查询是否已存在
        String selectSql = "SELECT id, block_count, is_active FROM user_content_blocks "
                         + "WHERE user_id = ? AND block_type = ? AND block_value = ?";
        try (Connection conn = DBUtil.getConnection();
             PreparedStatement ps = conn.prepareStatement(selectSql)) {
            ps.setInt(1, userId);
            ps.setString(2, type);
            ps.setString(3, value);
            ResultSet rs = ps.executeQuery();

            if (rs.next()) {
                int isActive = rs.getInt("is_active");
                if (isActive == 1) {
                    return "已在屏蔽中";
                }
                // 已过期 → 重新激活，block_count + 1
                int oldCount = rs.getInt("block_count");
                int newCount = oldCount + 1;
                int cooldownDays = 14 + (newCount - 1) * 7;
                String newUntil = LocalDate.now().plusDays(cooldownDays).toString();

                String updateSql = "UPDATE user_content_blocks "
                                 + "SET block_count = ?, blocked_until = ?, is_active = 1, "
                                 + "blocked_at = CURRENT_TIMESTAMP "
                                 + "WHERE id = ?";
                try (PreparedStatement ps2 = conn.prepareStatement(updateSql)) {
                    ps2.setInt(1, newCount);
                    ps2.setString(2, newUntil);
                    ps2.setInt(3, rs.getInt("id"));
                    ps2.executeUpdate();
                }
                System.out.println("🔄 [Block] 重新屏蔽 userId=" + userId + " " + type + "=" + value
                        + " count=" + newCount + " until=" + newUntil);
                return "已重新屏蔽（第" + newCount + "次，" + cooldownDays + "天）";
            }
        }

        // 不存在 → 新建
        int cooldownDays = 14;
        String until = LocalDate.now().plusDays(cooldownDays).toString();
        String insertSql = "INSERT INTO user_content_blocks "
                         + "(user_id, block_type, block_value, block_count, blocked_until) "
                         + "VALUES (?, ?, ?, 1, ?)";
        try (Connection conn = DBUtil.getConnection();
             PreparedStatement ps = conn.prepareStatement(insertSql)) {
            ps.setInt(1, userId);
            ps.setString(2, type);
            ps.setString(3, value);
            ps.setString(4, until);
            ps.executeUpdate();
        }
        System.out.println("🚫 [Block] 新增屏蔽 userId=" + userId + " " + type + "=" + value
                + " until=" + until);
        return "已屏蔽（14天）";
    }

    // ── 业务逻辑：取消屏蔽 ────────────────────────────────────
    private void removeBlock(int userId, String type, String value) throws SQLException {
        String sql = "DELETE FROM user_content_blocks "
                   + "WHERE user_id = ? AND block_type = ? AND block_value = ?";
        try (Connection conn = DBUtil.getConnection();
             PreparedStatement ps = conn.prepareStatement(sql)) {
            ps.setInt(1, userId);
            ps.setString(2, type);
            ps.setString(3, value);
            ps.executeUpdate();
        }
        System.out.println("✅ [Block] 取消屏蔽 userId=" + userId + " " + type + "=" + value);
    }

    // ── 工具方法 ──────────────────────────────────────────────
    private int getLoginUserId(HttpServletRequest request) {
        HttpSession session = request.getSession(false);
        if (session == null || session.getAttribute("user") == null) {
            return -1;
        }
        return ((User) session.getAttribute("user")).getId();
    }

    private String getStr(JsonObject json, String key) {
        try {
            return json.get(key).getAsString().trim();
        } catch (Exception e) {
            return null;
        }
    }
}
