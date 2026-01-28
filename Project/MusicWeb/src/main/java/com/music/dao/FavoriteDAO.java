package com.music.dao;

import com.music.javabean.*;
import java.sql.*;
import java.util.ArrayList;
import java.util.List;

public class FavoriteDAO {

    // 添加收藏
    public boolean addFavorite(int userId, int songId) {
        Connection conn = null;
        PreparedStatement pstmt = null;

        try {
            conn = DBUtil.getConnection();
            String sql = "INSERT INTO favorites (user_id, song_id) VALUES (?, ?)";
            pstmt = conn.prepareStatement(sql);
            pstmt.setInt(1, userId);
            pstmt.setInt(2, songId);

            int result = pstmt.executeUpdate();
            System.out.println("🎵 [DEBUG] 添加收藏 - 用户ID: " + userId + ", 歌曲ID: " + songId + ", 结果: " + (result > 0));

            return result > 0;
        } catch (SQLException e) {
            System.err.println("❌ [ERROR] 添加收藏失败 - 用户ID: " + userId + ", 歌曲ID: " + songId);
            System.err.println("错误信息: " + e.getMessage());
            e.printStackTrace();
            return false;
        } finally {
            DBUtil.close(conn, pstmt, null);
        }
    }

    // 取消收藏
    public boolean removeFavorite(int userId, int songId) {
        Connection conn = null;
        PreparedStatement pstmt = null;

        try {
            conn = DBUtil.getConnection();
            String sql = "DELETE FROM favorites WHERE user_id = ? AND song_id = ?";
            pstmt = conn.prepareStatement(sql);
            pstmt.setInt(1, userId);
            pstmt.setInt(2, songId);

            int result = pstmt.executeUpdate();
            System.out.println("🎵 [DEBUG] 取消收藏 - 用户ID: " + userId + ", 歌曲ID: " + songId + ", 结果: " + (result > 0));

            return result > 0;
        } catch (SQLException e) {
            System.err.println("❌ [ERROR] 取消收藏失败 - 用户ID: " + userId + ", 歌曲ID: " + songId);
            System.err.println("错误信息: " + e.getMessage());
            e.printStackTrace();
            return false;
        } finally {
            DBUtil.close(conn, pstmt, null);
        }
    }

    // 检查是否已收藏
    public boolean isFavorite(int userId, int songId) {
        Connection conn = null;
        PreparedStatement pstmt = null;
        ResultSet rs = null;

        try {
            conn = DBUtil.getConnection();
            String sql = "SELECT id FROM favorites WHERE user_id = ? AND song_id = ?";
            pstmt = conn.prepareStatement(sql);
            pstmt.setInt(1, userId);
            pstmt.setInt(2, songId);
            rs = pstmt.executeQuery();

            boolean exists = rs.next();
            System.out.println("🎵 [DEBUG] 检查收藏状态 - 用户ID: " + userId + ", 歌曲ID: " + songId + ", 已收藏: " + exists);

            return exists;
        } catch (SQLException e) {
            System.err.println("❌ [ERROR] 检查收藏状态失败 - 用户ID: " + userId + ", 歌曲ID: " + songId);
            System.err.println("错误信息: " + e.getMessage());
            e.printStackTrace();
            return false;
        } finally {
            DBUtil.close(conn, pstmt, rs);
        }
    }

    // 获取用户的收藏列表
    public List<Favorite> getUserFavorites(int userId) {
        Connection conn = null;
        PreparedStatement pstmt = null;
        ResultSet rs = null;
        List<Favorite> favorites = new ArrayList<>();

        try {
            conn = DBUtil.getConnection();
            String sql = "SELECT f.*, s.title, s.artist, s.album, s.duration, s.cover_image " +
                    "FROM favorites f JOIN songs s ON f.song_id = s.id " +
                    "WHERE f.user_id = ? ORDER BY f.create_time DESC";
            pstmt = conn.prepareStatement(sql);
            pstmt.setInt(1, userId);
            rs = pstmt.executeQuery();

            while (rs.next()) {
                Favorite favorite = new Favorite();
                favorite.setId(rs.getInt("id"));
                favorite.setUserId(rs.getInt("user_id"));
                favorite.setSongId(rs.getInt("song_id"));
                favorite.setCreateTime(rs.getString("create_time"));

                Song song = new Song();
                song.setId(rs.getInt("song_id"));
                song.setTitle(rs.getString("title"));
                song.setArtist(rs.getString("artist"));
                song.setAlbum(rs.getString("album"));
                song.setDuration(rs.getInt("duration"));
                song.setCoverImage(rs.getString("cover_image"));

                favorite.setSong(song);
                favorites.add(favorite);
            }

            System.out.println("🎵 [DEBUG] 获取用户收藏列表 - 用户ID: " + userId + ", 收藏数量: " + favorites.size());

        } catch (SQLException e) {
            System.err.println("❌ [ERROR] 获取用户收藏列表失败 - 用户ID: " + userId);
            System.err.println("错误信息: " + e.getMessage());
            e.printStackTrace();
        } finally {
            DBUtil.close(conn, pstmt, rs);
        }

        return favorites;
    }

    // 获取用户收藏数量
    public int getFavoriteCount(int userId) {
        Connection conn = null;
        PreparedStatement pstmt = null;
        ResultSet rs = null;
        int count = 0;

        try {
            conn = DBUtil.getConnection();
            String sql = "SELECT COUNT(*) FROM favorites WHERE user_id = ?";
            pstmt = conn.prepareStatement(sql);
            pstmt.setInt(1, userId);
            rs = pstmt.executeQuery();

            if (rs.next()) {
                count = rs.getInt(1);
            }

            System.out.println("🎵 [DEBUG] 获取用户收藏数量 - 用户ID: " + userId + ", 数量: " + count);

        } catch (SQLException e) {
            System.err.println("❌ [ERROR] 获取用户收藏数量失败 - 用户ID: " + userId);
            System.err.println("错误信息: " + e.getMessage());
            e.printStackTrace();
        } finally {
            DBUtil.close(conn, pstmt, rs);
        }

        return count;
    }

    // 检查歌曲是否存在（在收藏之前验证）
    public boolean isSongExist(int songId) {
        Connection conn = null;
        PreparedStatement pstmt = null;
        ResultSet rs = null;

        try {
            conn = DBUtil.getConnection();
            String sql = "SELECT id FROM songs WHERE id = ?";
            pstmt = conn.prepareStatement(sql);
            pstmt.setInt(1, songId);
            rs = pstmt.executeQuery();

            boolean exists = rs.next();
            System.out.println("🎵 [DEBUG] 检查歌曲是否存在 - 歌曲ID: " + songId + ", 存在: " + exists);

            return exists;
        } catch (SQLException e) {
            System.err.println("❌ [ERROR] 检查歌曲是否存在失败 - 歌曲ID: " + songId);
            System.err.println("错误信息: " + e.getMessage());
            e.printStackTrace();
            return false;
        } finally {
            DBUtil.close(conn, pstmt, rs);
        }
    }
}