package com.music.dao;

import com.music.javabean.DBUtil;
import com.music.javabean.User;
import com.music.javabean.Song;
import com.music.javabean.Favorite;

import java.sql.*;
import java.util.ArrayList;
import java.util.List;

/**
 * 管理员数据访问对象
 * 提供查询所有数据的功能，严格防止SQL注入
 */
public class AdminDAO {

    /**
     * 获取所有用户信息
     */
    public List<User> getAllUsers() {
        List<User> users = new ArrayList<>();
        String sql = "SELECT id, username, email, nickname, phone, status, frozen_until, frozen_reason, create_time FROM users ORDER BY create_time DESC";

        try (Connection conn = DBUtil.getConnection();
                PreparedStatement pstmt = conn.prepareStatement(sql);
                ResultSet rs = pstmt.executeQuery()) {

            while (rs.next()) {
                User user = new User();
                user.setId(rs.getInt("id"));
                user.setUsername(rs.getString("username"));
                user.setEmail(rs.getString("email"));
                user.setNickname(rs.getString("nickname"));
                user.setPhone(rs.getString("phone"));
                user.setStatus(rs.getString("status"));
                user.setFrozenUntil(rs.getString("frozen_until"));
                user.setFrozenReason(rs.getString("frozen_reason"));
                user.setCreateTime(rs.getString("create_time"));
                users.add(user);
            }
        } catch (SQLException e) {
            System.err.println("获取用户列表失败: " + e.getMessage());
            e.printStackTrace();
        }

        return users;
    }

    /**
     * 根据ID获取用户信息
     */
    public User getUserById(int userId) {
        User user = null;
        String sql = "SELECT id, username, email, nickname, phone, status, frozen_until, frozen_reason, create_time FROM users WHERE id = ?";

        try (Connection conn = DBUtil.getConnection();
                PreparedStatement pstmt = conn.prepareStatement(sql)) {

            pstmt.setInt(1, userId);
            try (ResultSet rs = pstmt.executeQuery()) {
                if (rs.next()) {
                    user = new User();
                    user.setId(rs.getInt("id"));
                    user.setUsername(rs.getString("username"));
                    user.setEmail(rs.getString("email"));
                    user.setNickname(rs.getString("nickname"));
                    user.setPhone(rs.getString("phone"));
                    user.setStatus(rs.getString("status"));
                    user.setFrozenUntil(rs.getString("frozen_until"));
                    user.setFrozenReason(rs.getString("frozen_reason"));
                    user.setCreateTime(rs.getString("create_time"));
                }
            }
        } catch (SQLException e) {
            System.err.println("获取用户信息失败: " + e.getMessage());
            e.printStackTrace();
        }

        return user;
    }

    /**
     * 冻结用户账号
     */
    public boolean freezeUser(int userId, String frozenUntil, String reason) {
        String sql = "UPDATE users SET status = 'frozen', frozen_until = ?, frozen_reason = ? WHERE id = ?";

        try (Connection conn = DBUtil.getConnection();
                PreparedStatement pstmt = conn.prepareStatement(sql)) {

            pstmt.setString(1, frozenUntil);
            pstmt.setString(2, reason);
            pstmt.setInt(3, userId);

            int affectedRows = pstmt.executeUpdate();
            return affectedRows > 0;
        } catch (SQLException e) {
            System.err.println("冻结用户失败: " + e.getMessage());
            e.printStackTrace();
            return false;
        }
    }

    /**
     * 解冻用户账号
     */
    public boolean unfreezeUser(int userId) {
        String sql = "UPDATE users SET status = 'active', frozen_until = NULL, frozen_reason = NULL WHERE id = ?";

        try (Connection conn = DBUtil.getConnection();
                PreparedStatement pstmt = conn.prepareStatement(sql)) {

            pstmt.setInt(1, userId);

            int affectedRows = pstmt.executeUpdate();
            return affectedRows > 0;
        } catch (SQLException e) {
            System.err.println("解冻用户失败: " + e.getMessage());
            e.printStackTrace();
            return false;
        }
    }

    /**
     * 删除用户账号（软删除，记录删除时间）
     */
    public boolean deleteUser(int userId) {
        String sql = "UPDATE users SET status = 'deleted', deleted_at = NOW() WHERE id = ?";

        try (Connection conn = DBUtil.getConnection();
                PreparedStatement pstmt = conn.prepareStatement(sql)) {

            pstmt.setInt(1, userId);

            int affectedRows = pstmt.executeUpdate();
            return affectedRows > 0;
        } catch (SQLException e) {
            System.err.println("删除用户失败: " + e.getMessage());
            e.printStackTrace();
            return false;
        }
    }

    /**
     * 获取所有歌曲信息
     */
    public List<Song> getAllSongs() {
        List<Song> songs = new ArrayList<>();
        String sql = "SELECT id, title, artist, album, duration, genre, release_year, file_path, cover_image, language FROM songs ORDER BY id";

        try (Connection conn = DBUtil.getConnection();
                PreparedStatement pstmt = conn.prepareStatement(sql);
                ResultSet rs = pstmt.executeQuery()) {

            while (rs.next()) {
                Song song = new Song();
                song.setId(rs.getInt("id"));
                song.setTitle(rs.getString("title"));
                song.setArtist(rs.getString("artist"));
                song.setAlbum(rs.getString("album"));
                song.setDuration(rs.getInt("duration"));
                song.setGenre(rs.getString("genre"));
                song.setReleaseYear(rs.getInt("release_year"));
                song.setFilePath(rs.getString("file_path"));
                song.setCoverImage(rs.getString("cover_image"));
                song.setLanguage(rs.getString("language"));
                songs.add(song);
            }
        } catch (SQLException e) {
            System.err.println("获取歌曲列表失败: " + e.getMessage());
            e.printStackTrace();
        }

        return songs;
    }

    /**
     * 获取所有收藏记录
     */
    public List<Favorite> getAllFavorites() {
        List<Favorite> favorites = new ArrayList<>();
        String sql = "SELECT f.id, f.user_id, f.song_id, f.create_time, u.username as user_name, s.title as song_title "
                +
                "FROM favorites f " +
                "JOIN users u ON f.user_id = u.id " +
                "JOIN songs s ON f.song_id = s.id " +
                "ORDER BY f.create_time DESC";

        try (Connection conn = DBUtil.getConnection();
                PreparedStatement pstmt = conn.prepareStatement(sql);
                ResultSet rs = pstmt.executeQuery()) {

            while (rs.next()) {
                Favorite favorite = new Favorite();
                favorite.setId(rs.getInt("id"));
                favorite.setUserId(rs.getInt("user_id"));
                favorite.setSongId(rs.getInt("song_id"));
                favorite.setCreateTime(rs.getString("create_time"));

                // 设置关联的用户名和歌曲标题
                User user = new User();
                user.setUsername(rs.getString("user_name"));
                favorite.setUser(user);

                Song song = new Song();
                song.setTitle(rs.getString("song_title"));
                favorite.setSong(song);

                favorites.add(favorite);
            }
        } catch (SQLException e) {
            System.err.println("获取收藏记录失败: " + e.getMessage());
            e.printStackTrace();
        }

        return favorites;
    }

    /**
     * 获取数据库统计信息
     */
    public java.util.Map<String, Integer> getDatabaseStats() {
        java.util.Map<String, Integer> stats = new java.util.HashMap<>();

        String[] queries = {
                "SELECT COUNT(*) FROM users",
                "SELECT COUNT(*) FROM songs",
                "SELECT COUNT(*) FROM favorites",
                "SELECT COUNT(*) FROM users WHERE create_time >= DATE_SUB(NOW(), INTERVAL 7 DAY)",
                "SELECT COUNT(*) FROM favorites WHERE create_time >= DATE_SUB(NOW(), INTERVAL 7 DAY)"
        };

        String[] keys = { "totalUsers", "totalSongs", "totalFavorites", "newUsers", "newFavorites" };

        try (Connection conn = DBUtil.getConnection()) {
            for (int i = 0; i < queries.length; i++) {
                try (PreparedStatement pstmt = conn.prepareStatement(queries[i]);
                        ResultSet rs = pstmt.executeQuery()) {
                    if (rs.next()) {
                        stats.put(keys[i], rs.getInt(1));
                    }
                }
            }
        } catch (SQLException e) {
            System.err.println("获取统计信息失败: " + e.getMessage());
            e.printStackTrace();
        }

        return stats;
    }

    /**
     * 检查用户是否为管理员
     */
    public boolean isAdmin(String username) {
        if (username == null || username.trim().isEmpty()) {
            return false;
        }

        String sql = "SELECT COUNT(*) FROM users WHERE username = ? AND username = 'admin'";

        try (Connection conn = DBUtil.getConnection();
                PreparedStatement pstmt = conn.prepareStatement(sql)) {

            pstmt.setString(1, username.trim());

            try (ResultSet rs = pstmt.executeQuery()) {
                return rs.next() && rs.getInt(1) > 0;
            }
        } catch (SQLException e) {
            System.err.println("检查管理员权限失败: " + e.getMessage());
            e.printStackTrace();
            return false;
        }
    }
}