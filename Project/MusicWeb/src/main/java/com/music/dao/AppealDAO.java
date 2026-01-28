package com.music.dao;

import com.music.javabean.*;
import java.sql.*;
import java.util.ArrayList;
import java.util.List;

public class AppealDAO {

    public boolean createAppeal(Appeal appeal) {
        String sql = "INSERT INTO appeals (username, user_id, appeal_type, reason, contact_email) VALUES (?, ?, ?, ?, ?)";

        try (Connection conn = DBUtil.getConnection();
             PreparedStatement pstmt = conn.prepareStatement(sql)) {

            pstmt.setString(1, appeal.getUsername());
            if (appeal.getUserId() != null) {
                pstmt.setInt(2, appeal.getUserId());
            } else {
                pstmt.setNull(2, Types.INTEGER);
            }
            pstmt.setString(3, appeal.getAppealType());
            pstmt.setString(4, appeal.getReason());
            pstmt.setString(5, appeal.getContactEmail());

            return pstmt.executeUpdate() > 0;
        } catch (SQLException e) {
            e.printStackTrace();
            return false;
        }
    }

    public List<Appeal> getAllAppeals() {
        List<Appeal> appeals = new ArrayList<>();
        String sql = "SELECT * FROM appeals ORDER BY create_time DESC";

        try (Connection conn = DBUtil.getConnection();
             PreparedStatement pstmt = conn.prepareStatement(sql);
             ResultSet rs = pstmt.executeQuery()) {

            while (rs.next()) {
                appeals.add(extractAppeal(rs));
            }
        } catch (SQLException e) {
            e.printStackTrace();
        }

        return appeals;
    }

    public List<Appeal> getPendingAppeals() {
        List<Appeal> appeals = new ArrayList<>();
        String sql = "SELECT * FROM appeals WHERE status = 'pending' ORDER BY create_time DESC";

        try (Connection conn = DBUtil.getConnection();
             PreparedStatement pstmt = conn.prepareStatement(sql);
             ResultSet rs = pstmt.executeQuery()) {

            while (rs.next()) {
                appeals.add(extractAppeal(rs));
            }
        } catch (SQLException e) {
            e.printStackTrace();
        }

        return appeals;
    }

    public Appeal getAppealById(int id) {
        String sql = "SELECT * FROM appeals WHERE id = ?";

        try (Connection conn = DBUtil.getConnection();
             PreparedStatement pstmt = conn.prepareStatement(sql)) {

            pstmt.setInt(1, id);
            ResultSet rs = pstmt.executeQuery();

            if (rs.next()) {
                return extractAppeal(rs);
            }
        } catch (SQLException e) {
            e.printStackTrace();
        }

        return null;
    }

    public boolean approveAppeal(int appealId, String adminReply) {
        String sql = "UPDATE appeals SET status = 'approved', admin_reply = ? WHERE id = ?";

        try (Connection conn = DBUtil.getConnection();
             PreparedStatement pstmt = conn.prepareStatement(sql)) {

            pstmt.setString(1, adminReply);
            pstmt.setInt(2, appealId);

            return pstmt.executeUpdate() > 0;
        } catch (SQLException e) {
            e.printStackTrace();
            return false;
        }
    }

    public boolean rejectAppeal(int appealId, String adminReply) {
        String sql = "UPDATE appeals SET status = 'rejected', admin_reply = ? WHERE id = ?";

        try (Connection conn = DBUtil.getConnection();
             PreparedStatement pstmt = conn.prepareStatement(sql)) {

            pstmt.setString(1, adminReply);
            pstmt.setInt(2, appealId);

            return pstmt.executeUpdate() > 0;
        } catch (SQLException e) {
            e.printStackTrace();
            return false;
        }
    }

    private Appeal extractAppeal(ResultSet rs) throws SQLException {
        Appeal appeal = new Appeal();
        appeal.setId(rs.getInt("id"));
        appeal.setUsername(rs.getString("username"));
        appeal.setUserId(rs.getObject("user_id", Integer.class));
        appeal.setAppealType(rs.getString("appeal_type"));
        appeal.setReason(rs.getString("reason"));
        appeal.setContactEmail(rs.getString("contact_email"));
        appeal.setStatus(rs.getString("status"));
        appeal.setAdminReply(rs.getString("admin_reply"));
        appeal.setCreateTime(rs.getString("create_time"));
        appeal.setUpdateTime(rs.getString("update_time"));
        return appeal;
    }
}
