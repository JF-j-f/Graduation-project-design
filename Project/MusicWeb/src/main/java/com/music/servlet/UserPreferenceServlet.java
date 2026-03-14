package com.music.servlet;

import com.music.dao.UserDAO;
import com.music.javabean.User;
import com.google.gson.JsonArray;
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
import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.SQLException;
import java.time.LocalDate;
import java.util.Arrays;
import java.util.LinkedHashSet;
import java.util.Set;

import com.music.javabean.DBUtil;

/**
 * 用户偏好接口 (v4.0)
 *
 * GET  /api/userPreference → 返回当前用户 preferred_genres、preferred_artists
 * POST /api/userPreference → 接收 {satisfaction, genres[], artists[]}
 *       1. 写入 user_preference_feedback 表（同天覆盖）
 *       2. 合并去重后更新 users.preferred_genres / preferred_artists
 */
@WebServlet("/api/userPreference")
public class UserPreferenceServlet extends HttpServlet {

    // ── GET：返回当前偏好 ─────────────────────────────────────
    @Override
    protected void doGet(HttpServletRequest request, HttpServletResponse response)
            throws ServletException, IOException {

        response.setContentType("application/json;charset=UTF-8");
        PrintWriter out = response.getWriter();

        HttpSession session = request.getSession(false);
        if (session == null || session.getAttribute("user") == null) {
            out.print("{\"success\":false,\"message\":\"未登录\"}");
            return;
        }
        User user = (User) session.getAttribute("user");

        // 从 DB 刷新最新偏好（session 中的 user 对象可能是旧快照）
        UserDAO userDAO = new UserDAO();
        User fresh = userDAO.getUserById(user.getId());

        String genres  = fresh != null && fresh.getPreferredGenres()  != null ? fresh.getPreferredGenres()  : "";
        String artists = fresh != null && fresh.getPreferredArtists() != null ? fresh.getPreferredArtists() : "";

        out.print("{\"success\":true,"
                + "\"preferredGenres\":\"" + escapeJson(genres)  + "\","
                + "\"preferredArtists\":\"" + escapeJson(artists) + "\"}");
    }

    // ── POST：保存反馈 ────────────────────────────────────────
    @Override
    protected void doPost(HttpServletRequest request, HttpServletResponse response)
            throws ServletException, IOException {

        response.setContentType("application/json;charset=UTF-8");
        PrintWriter out = response.getWriter();

        HttpSession session = request.getSession(false);
        if (session == null || session.getAttribute("user") == null) {
            out.print("{\"success\":false,\"message\":\"未登录\"}");
            return;
        }
        User user = (User) session.getAttribute("user");
        int userId = user.getId();

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

        String satisfaction = getStr(json, "satisfaction", "neutral");
        String genresStr    = buildTokenString(json, "genres");
        String artistsStr   = buildTokenString(json, "artists");

        String today = LocalDate.now().toString(); // "YYYY-MM-DD"

        try {
            // ① 写入训练数据表（同一用户同一天：覆盖）
            insertOrUpdateFeedback(userId, today, satisfaction, genresStr, artistsStr);

            // ② 偏好更新策略：不满意 → 替换（清除旧偏好）；其他 → 追加合并
            if ("dissatisfied".equals(satisfaction)
                    && (!genresStr.isEmpty() || !artistsStr.isEmpty())) {
                replaceUserPreferences(userId, genresStr, artistsStr);
            } else {
                mergeUserPreferences(userId, genresStr, artistsStr);
            }

            // ③ 刷新 session 中的 user 对象
            UserDAO userDAO = new UserDAO();
            User fresh = userDAO.getUserById(userId);
            if (fresh != null) {
                session.setAttribute("user", fresh);
            }

            out.print("{\"success\":true}");
        } catch (Exception e) {
            System.err.println("❌ [ERROR] UserPreferenceServlet POST 失败: " + e.getMessage());
            e.printStackTrace();
            response.setStatus(HttpServletResponse.SC_INTERNAL_SERVER_ERROR);
            out.print("{\"success\":false,\"message\":\"服务器内部错误\"}");
        }
    }

    // ── 写入 user_preference_feedback（同天覆盖） ─────────────
    private void insertOrUpdateFeedback(int userId, String date,
                                         String satisfaction,
                                         String genres, String artists)
            throws SQLException {

        String sql = "INSERT INTO user_preference_feedback "
                   + "(user_id, feedback_date, satisfaction, genres_added, artists_added) "
                   + "VALUES (?, ?, ?, ?, ?) "
                   + "ON DUPLICATE KEY UPDATE "
                   + "satisfaction=VALUES(satisfaction), "
                   + "genres_added=VALUES(genres_added), "
                   + "artists_added=VALUES(artists_added)";

        try (Connection conn = DBUtil.getConnection();
             PreparedStatement ps = conn.prepareStatement(sql)) {
            ps.setInt(1, userId);
            ps.setString(2, date);
            ps.setString(3, satisfaction);
            ps.setString(4, genres.isEmpty() ? null : genres);
            ps.setString(5, artists.isEmpty() ? null : artists);
            ps.executeUpdate();
            System.out.println("✅ [UserPref] 反馈记录写入 userId=" + userId + ", satisfaction=" + satisfaction);
        }
    }

    // ── 合并偏好到 users 表（追加去重，不覆盖历史） ────────────
    private void mergeUserPreferences(int userId, String newGenres, String newArtists)
            throws SQLException {

        if (newGenres.isEmpty() && newArtists.isEmpty()) return;

        // 先读取现有值
        String existingGenres  = "";
        String existingArtists = "";
        String selectSql = "SELECT preferred_genres, preferred_artists FROM users WHERE id = ?";
        try (Connection conn = DBUtil.getConnection();
             PreparedStatement ps = conn.prepareStatement(selectSql)) {
            ps.setInt(1, userId);
            var rs = ps.executeQuery();
            if (rs.next()) {
                existingGenres  = rs.getString("preferred_genres")  != null ? rs.getString("preferred_genres")  : "";
                existingArtists = rs.getString("preferred_artists") != null ? rs.getString("preferred_artists") : "";
            }
        }

        String mergedGenres  = mergeTokens(existingGenres,  newGenres);
        String mergedArtists = mergeTokens(existingArtists, newArtists);

        String updateSql = "UPDATE users SET preferred_genres=?, preferred_artists=? WHERE id=?";
        try (Connection conn = DBUtil.getConnection();
             PreparedStatement ps = conn.prepareStatement(updateSql)) {
            ps.setString(1, mergedGenres.isEmpty()  ? null : mergedGenres);
            ps.setString(2, mergedArtists.isEmpty() ? null : mergedArtists);
            ps.setInt(3, userId);
            ps.executeUpdate();
            System.out.println("✅ [UserPref] 偏好更新 userId=" + userId
                    + ", genres=" + mergedGenres + ", artists=" + mergedArtists);
        }
    }

    // ── 不满意时直接替换偏好（清除旧偏好，只保留用户新填的） ────
    private void replaceUserPreferences(int userId, String genres, String artists)
            throws SQLException {

        String sql = "UPDATE users SET preferred_genres=?, preferred_artists=? WHERE id=?";
        try (Connection conn = DBUtil.getConnection();
             PreparedStatement ps = conn.prepareStatement(sql)) {
            ps.setString(1, genres.isEmpty() ? null : genres);
            ps.setString(2, artists.isEmpty() ? null : artists);
            ps.setInt(3, userId);
            ps.executeUpdate();
            System.out.println("🔄 [UserPref] 不满意→替换偏好 userId=" + userId
                    + ", genres=" + genres + ", artists=" + artists);
        }
    }

    // ── 工具方法 ──────────────────────────────────────────────

    /** 合并两个分号分隔的 token 列表，去重保序 */
    private String mergeTokens(String existing, String additional) {
        Set<String> set = new LinkedHashSet<>();
        if (existing != null && !existing.isEmpty()) {
            Arrays.stream(existing.split(";")).map(String::trim)
                  .filter(s -> !s.isEmpty()).forEach(set::add);
        }
        if (additional != null && !additional.isEmpty()) {
            Arrays.stream(additional.split(";")).map(String::trim)
                  .filter(s -> !s.isEmpty()).forEach(set::add);
        }
        return String.join(";", set);
    }

    /** 从 JsonObject 中读取字符串数组字段，拼接为分号分隔字符串 */
    private String buildTokenString(JsonObject json, String key) {
        if (!json.has(key)) return "";
        try {
            JsonArray arr = json.getAsJsonArray(key);
            StringBuilder sb = new StringBuilder();
            for (int i = 0; i < arr.size(); i++) {
                String val = arr.get(i).getAsString().trim();
                if (!val.isEmpty()) {
                    if (sb.length() > 0) sb.append(";");
                    sb.append(val);
                }
            }
            return sb.toString();
        } catch (Exception e) {
            return "";
        }
    }

    private String getStr(JsonObject json, String key, String def) {
        try { return json.get(key).getAsString(); } catch (Exception e) { return def; }
    }

    private String escapeJson(String s) {
        return s.replace("\\", "\\\\").replace("\"", "\\\"");
    }
}
