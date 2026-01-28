package com.music.service;

import com.music.javabean.DBUtil;
import java.sql.*;
import java.util.*;

/**
 * 推荐服务类
 * 负责冷启动推荐和个性化推荐的生成
 */
public class RecommendationService {

    /**
     * 为新用户生成冷启动推荐
     * 基于用户选择的流派和歌手标签，从热门歌曲中生成初始推荐列表
     * 
     * @param userId          新用户ID
     * @param selectedGenres  逗号分隔的 genre_ids（如 "465,921,1259"）
     * @param selectedArtists 逗号分隔的歌手名（如 "周杰伦,林俊杰"）
     */
    public void initForNewUser(int userId, String selectedGenres, String selectedArtists) {
        Connection conn = null;
        PreparedStatement pstmt = null;
        ResultSet rs = null;

        try {
            conn = DBUtil.getConnection();

            // 收集候选歌曲ID
            Set<Integer> candidateSongIds = new LinkedHashSet<>();

            // 1. 根据 genre_ids 查找热门歌曲
            if (selectedGenres != null && !selectedGenres.trim().isEmpty()) {
                String[] genres = selectedGenres.split(",");
                for (String genreId : genres) {
                    genreId = genreId.trim();
                    if (!genreId.isEmpty()) {
                        findSongsByGenre(conn, genreId, candidateSongIds, 30);
                    }
                }
            }

            // 2. 根据歌手名查找热门歌曲
            if (selectedArtists != null && !selectedArtists.trim().isEmpty()) {
                String[] artists = selectedArtists.split(",");
                for (String artist : artists) {
                    artist = artist.trim();
                    if (!artist.isEmpty()) {
                        findSongsByArtist(conn, artist, candidateSongIds, 20);
                    }
                }
            }

            // 3. 如果没有选择任何标签，使用全局热门歌曲
            if (candidateSongIds.isEmpty()) {
                findGlobalHotSongs(conn, candidateSongIds, 50);
            }

            // 4. 从候选集中随机采样 20 首，保证多样性
            List<Integer> songList = new ArrayList<>(candidateSongIds);
            Collections.shuffle(songList);
            List<Integer> finalSongs = songList.subList(0, Math.min(20, songList.size()));

            // 5. 写入 recommendations 表
            saveRecommendations(conn, userId, finalSongs);

            System.out.println("Cold start: Generated " + finalSongs.size() + " recommendations for user " + userId);

        } catch (SQLException e) {
            e.printStackTrace();
        } finally {
            DBUtil.close(conn, pstmt, rs);
        }
    }

    /**
     * 根据 genre_id 查找热门歌曲
     */
    private void findSongsByGenre(Connection conn, String genreId, Set<Integer> songIds, int limit)
            throws SQLException {
        String sql = "SELECT id FROM songs WHERE genre_ids LIKE ? AND popularity > 0 ORDER BY popularity DESC LIMIT ?";
        try (PreparedStatement pstmt = conn.prepareStatement(sql)) {
            pstmt.setString(1, "%" + genreId + "%");
            pstmt.setInt(2, limit);
            try (ResultSet rs = pstmt.executeQuery()) {
                while (rs.next()) {
                    songIds.add(rs.getInt("id"));
                }
            }
        }
    }

    /**
     * 根据歌手名查找热门歌曲
     */
    private void findSongsByArtist(Connection conn, String artist, Set<Integer> songIds, int limit)
            throws SQLException {
        String sql = "SELECT id FROM songs WHERE artist LIKE ? ORDER BY popularity DESC LIMIT ?";
        try (PreparedStatement pstmt = conn.prepareStatement(sql)) {
            pstmt.setString(1, "%" + artist + "%");
            pstmt.setInt(2, limit);
            try (ResultSet rs = pstmt.executeQuery()) {
                while (rs.next()) {
                    songIds.add(rs.getInt("id"));
                }
            }
        }
    }

    /**
     * 查找全局热门歌曲（无标签时的兜底策略）
     */
    private void findGlobalHotSongs(Connection conn, Set<Integer> songIds, int limit) throws SQLException {
        String sql = "SELECT id FROM songs WHERE popularity > 0 ORDER BY popularity DESC LIMIT ?";
        try (PreparedStatement pstmt = conn.prepareStatement(sql)) {
            pstmt.setInt(1, limit);
            try (ResultSet rs = pstmt.executeQuery()) {
                while (rs.next()) {
                    songIds.add(rs.getInt("id"));
                }
            }
        }
    }

    /**
     * 保存推荐结果到数据库
     */
    private void saveRecommendations(Connection conn, int userId, List<Integer> songIds) throws SQLException {
        // 先删除该用户的旧推荐（如果有）
        String deleteSql = "DELETE FROM recommendations WHERE user_id = ? AND source_type = 'cold_start'";
        try (PreparedStatement pstmt = conn.prepareStatement(deleteSql)) {
            pstmt.setInt(1, userId);
            pstmt.executeUpdate();
        }

        // 批量插入新推荐
        String insertSql = "INSERT INTO recommendations (user_id, song_id, score, source_type) VALUES (?, ?, ?, 'cold_start')";
        try (PreparedStatement pstmt = conn.prepareStatement(insertSql)) {
            double score = 1.0;
            for (Integer songId : songIds) {
                pstmt.setInt(1, userId);
                pstmt.setInt(2, songId);
                pstmt.setDouble(3, score);
                pstmt.addBatch();
                score -= 0.01; // 递减分数以保持排序
            }
            pstmt.executeBatch();
        }
    }
}
