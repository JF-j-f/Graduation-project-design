package com.music.dao;

import com.music.javabean.*;
import com.google.gson.reflect.TypeToken;
import java.sql.*;
import java.util.ArrayList;
import java.util.List;

public class PlayHistoryDAO {

    // 添加播放历史记录
    // 播放新歌曲后会自动清除该用户的Redis缓存，确保下次查询获取最新数据
    public boolean addPlayHistory(int userId, int songId) {
        Connection conn = null;
        PreparedStatement pstmt = null;

        try {
            conn = DBUtil.getConnection();
            String sql = "INSERT INTO play_history (user_id, song_id, play_duration) VALUES (?, ?, 0)";
            pstmt = conn.prepareStatement(sql);
            pstmt.setInt(1, userId);
            pstmt.setInt(2, songId);

            int result = pstmt.executeUpdate();
            System.out.println("🎵 [DEBUG] 添加播放历史 - 用户ID: " + userId + ", 歌曲ID: " + songId + ", 结果: " + (result > 0));

            // 播放新歌后清除该用户的播放历史缓存，确保下次查询获取最新数据
            if (result > 0) {
                RedisUtil.clearUserPlayHistoryCache(userId);
            }

            return result > 0;
        } catch (SQLException e) {
            System.err.println("❌ [ERROR] 添加播放历史失败 - 用户ID: " + userId + ", 歌曲ID: " + songId);
            System.err.println("错误信息: " + e.getMessage());
            e.printStackTrace();
            return false;
        } finally {
            DBUtil.close(conn, pstmt, null);
        }
    }

    // 获取用户播放历史（带歌曲信息）
    public List<PlayHistory> getUserPlayHistory(int userId, int limit) {
        Connection conn = null;
        PreparedStatement pstmt = null;
        ResultSet rs = null;
        List<PlayHistory> historyList = new ArrayList<>();

        try {
            conn = DBUtil.getConnection();
            String sql = "SELECT ph.id, ph.user_id, ph.song_id, ph.play_time, ph.play_duration, " +
                    "s.title, s.artist, s.album, s.duration, s.genre, s.release_year, s.file_path, s.cover_image, s.language "
                    +
                    "FROM play_history ph " +
                    "JOIN songs s ON ph.song_id = s.id " +
                    "WHERE ph.user_id = ? " +
                    "ORDER BY ph.play_time DESC " +
                    "LIMIT ?";

            pstmt = conn.prepareStatement(sql);
            pstmt.setInt(1, userId);
            pstmt.setInt(2, limit);
            rs = pstmt.executeQuery();

            while (rs.next()) {
                PlayHistory history = new PlayHistory();
                history.setId(rs.getInt("id"));
                history.setUserId(rs.getInt("user_id"));
                history.setSongId(rs.getInt("song_id"));
                history.setPlayTime(rs.getString("play_time"));
                history.setPlayDuration(rs.getInt("play_duration"));

                // 构建关联的歌曲信息
                Song song = new Song();
                song.setId(rs.getInt("song_id"));
                song.setTitle(rs.getString("title"));
                song.setArtist(rs.getString("artist"));
                song.setAlbum(rs.getString("album"));
                song.setDuration(rs.getInt("duration"));
                song.setGenre(rs.getString("genre"));
                song.setReleaseYear(rs.getInt("release_year"));
                song.setFilePath(rs.getString("file_path"));
                song.setCoverImage(rs.getString("cover_image"));
                song.setLanguage(rs.getString("language"));

                history.setSong(song);
                historyList.add(history);
            }

            System.out.println("🎵 [DEBUG] 获取用户播放历史 - 用户ID: " + userId + ", 记录数: " + historyList.size());

            return historyList;
        } catch (SQLException e) {
            System.err.println("❌ [ERROR] 获取用户播放历史失败 - 用户ID: " + userId);
            System.err.println("错误信息: " + e.getMessage());
            e.printStackTrace();
            return historyList;
        } finally {
            DBUtil.close(conn, pstmt, rs);
        }
    }

    // 获取最近播放（默认20条）
    public List<PlayHistory> getRecentPlays(int userId) {
        return getUserPlayHistory(userId, 20);
    }

    // 获取播放历史总数
    public int getPlayHistoryCount(int userId) {
        Connection conn = null;
        PreparedStatement pstmt = null;
        ResultSet rs = null;

        try {
            conn = DBUtil.getConnection();
            String sql = "SELECT COUNT(*) as count FROM play_history WHERE user_id = ?";
            pstmt = conn.prepareStatement(sql);
            pstmt.setInt(1, userId);
            rs = pstmt.executeQuery();

            if (rs.next()) {
                int count = rs.getInt("count");
                System.out.println("🎵 [DEBUG] 获取播放历史总数 - 用户ID: " + userId + ", 总数: " + count);
                return count;
            }

            return 0;
        } catch (SQLException e) {
            System.err.println("❌ [ERROR] 获取播放历史总数失败 - 用户ID: " + userId);
            System.err.println("错误信息: " + e.getMessage());
            e.printStackTrace();
            return 0;
        } finally {
            DBUtil.close(conn, pstmt, rs);
        }
    }

    // 清空用户播放历史
    public boolean clearPlayHistory(int userId) {
        Connection conn = null;
        PreparedStatement pstmt = null;

        try {
            conn = DBUtil.getConnection();
            String sql = "DELETE FROM play_history WHERE user_id = ?";
            pstmt = conn.prepareStatement(sql);
            pstmt.setInt(1, userId);

            int result = pstmt.executeUpdate();
            System.out.println("🎵 [DEBUG] 清空播放历史 - 用户ID: " + userId + ", 删除记录数: " + result);

            return result > 0;
        } catch (SQLException e) {
            System.err.println("❌ [ERROR] 清空播放历史失败 - 用户ID: " + userId);
            System.err.println("错误信息: " + e.getMessage());
            e.printStackTrace();
            return false;
        } finally {
            DBUtil.close(conn, pstmt, null);
        }
    }

    // ============================================
    // v3.1.0 新增：按时间范围查询播放历史
    // ============================================

    /**
     * 按时间范围获取用户播放历史（带分页）
     * 使用Redis缓存加速查询，缓存有效期5分钟
     * 
     * @param userId   用户ID
     * @param days     时间范围（天数：7/30/90）
     * @param page     页码（从1开始）
     * @param pageSize 每页数量
     * @return 播放历史列表
     */
    public List<PlayHistory> getUserPlayHistoryByDays(int userId, int days, int page, int pageSize) {
        // 1. 尝试从Redis缓存读取
        String cacheKey = RedisUtil.getPlayHistoryKey(userId, days, page);
        List<PlayHistory> cachedList = RedisUtil.getList(cacheKey, new TypeToken<List<PlayHistory>>() {
        });
        if (cachedList != null) {
            System.out.println("✅ [Redis缓存命中] 播放历史 - userId=" + userId + ", days=" + days + ", page=" + page);
            return cachedList;
        }

        // 2. 缓存未命中，从数据库查询
        Connection conn = null;
        PreparedStatement pstmt = null;
        ResultSet rs = null;
        List<PlayHistory> historyList = new ArrayList<>();

        try {
            conn = DBUtil.getConnection();
            int offset = (page - 1) * pageSize;

            String sql = "SELECT ph.id, ph.user_id, ph.song_id, ph.play_time, ph.play_duration, " +
                    "s.title, s.artist, s.album, s.duration, s.genre, s.release_year, s.file_path, s.cover_image, s.language "
                    +
                    "FROM play_history ph " +
                    "JOIN songs s ON ph.song_id = s.id " +
                    "WHERE ph.user_id = ? AND ph.play_time >= DATE_SUB(NOW(), INTERVAL ? DAY) " +
                    "ORDER BY ph.play_time DESC " +
                    "LIMIT ? OFFSET ?";

            pstmt = conn.prepareStatement(sql);
            pstmt.setInt(1, userId);
            pstmt.setInt(2, days);
            pstmt.setInt(3, pageSize);
            pstmt.setInt(4, offset);
            rs = pstmt.executeQuery();

            while (rs.next()) {
                PlayHistory history = new PlayHistory();
                history.setId(rs.getInt("id"));
                history.setUserId(rs.getInt("user_id"));
                history.setSongId(rs.getInt("song_id"));
                history.setPlayTime(rs.getString("play_time"));
                history.setPlayDuration(rs.getInt("play_duration"));

                Song song = new Song();
                song.setId(rs.getInt("song_id"));
                song.setTitle(rs.getString("title"));
                song.setArtist(rs.getString("artist"));
                song.setAlbum(rs.getString("album"));
                song.setDuration(rs.getInt("duration"));
                song.setGenre(rs.getString("genre"));
                song.setReleaseYear(rs.getInt("release_year"));
                song.setFilePath(rs.getString("file_path"));
                song.setCoverImage(rs.getString("cover_image"));
                song.setLanguage(rs.getString("language"));

                history.setSong(song);
                historyList.add(history);
            }

            // 3. 将结果写入Redis缓存（TTL=5分钟）
            RedisUtil.setList(cacheKey, historyList, RedisUtil.TTL_SHORT);
            System.out.println("📦 [Redis缓存写入] 播放历史 - userId=" + userId + ", days=" + days + ", page=" + page
                    + ", count=" + historyList.size());

            return historyList;
        } catch (SQLException e) {
            System.err.println("❌ [ERROR] 按天数获取播放历史失败 - 用户ID: " + userId + ", days: " + days);
            e.printStackTrace();
            return historyList;
        } finally {
            DBUtil.close(conn, pstmt, rs);
        }
    }

    /**
     * 按时间范围获取播放历史总数
     * 使用Redis缓存加速查询，缓存有效期5分钟
     */
    public int getPlayHistoryCountByDays(int userId, int days) {
        // 1. 尝试从Redis缓存读取
        String cacheKey = RedisUtil.getPlayHistoryCountKey(userId, days);
        String cachedCount = RedisUtil.get(cacheKey);
        if (cachedCount != null) {
            try {
                int count = Integer.parseInt(cachedCount);
                System.out.println("✅ [Redis缓存命中] 播放历史总数 - userId=" + userId + ", days=" + days + ", count=" + count);
                return count;
            } catch (NumberFormatException e) {
                // 缓存数据格式错误，忽略并从数据库重新查询
            }
        }

        // 2. 缓存未命中，从数据库查询
        Connection conn = null;
        PreparedStatement pstmt = null;
        ResultSet rs = null;

        try {
            conn = DBUtil.getConnection();
            String sql = "SELECT COUNT(*) as count FROM play_history " +
                    "WHERE user_id = ? AND play_time >= DATE_SUB(NOW(), INTERVAL ? DAY)";
            pstmt = conn.prepareStatement(sql);
            pstmt.setInt(1, userId);
            pstmt.setInt(2, days);
            rs = pstmt.executeQuery();

            if (rs.next()) {
                int count = rs.getInt("count");
                // 3. 将结果写入Redis缓存（TTL=5分钟）
                RedisUtil.set(cacheKey, String.valueOf(count), RedisUtil.TTL_SHORT);
                System.out.println("📦 [Redis缓存写入] 播放历史总数 - userId=" + userId + ", days=" + days + ", count=" + count);
                return count;
            }
            return 0;
        } catch (SQLException e) {
            System.err.println("❌ [ERROR] 获取播放历史总数失败 - 用户ID: " + userId + ", days: " + days);
            e.printStackTrace();
            return 0;
        } finally {
            DBUtil.close(conn, pstmt, rs);
        }
    }
}
