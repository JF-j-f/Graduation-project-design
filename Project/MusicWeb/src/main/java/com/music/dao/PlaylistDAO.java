package com.music.dao;

import com.music.javabean.DBUtil;
import com.music.javabean.Playlist;
import com.music.javabean.Song;
import com.music.javabean.User;

import java.sql.*;
import java.util.ArrayList;
import java.util.List;

/**
 * 歌单数据访问对象
 * 提供歌单的增删改查操作
 */
public class PlaylistDAO {

    /**
     * 创建歌单
     * @param name 歌单名称
     * @param userId 用户ID
     * @param isDefault 是否为默认歌单
     * @return 创建的歌单ID，失败返回-1
     */
    public int createPlaylist(String name, int userId, boolean isDefault) {
        Connection conn = null;
        PreparedStatement pstmt = null;
        ResultSet rs = null;

        try {
            conn = DBUtil.getConnection();
            String sql = "INSERT INTO user_playlists (user_id, name, is_default) VALUES (?, ?, ?)";
            pstmt = conn.prepareStatement(sql, Statement.RETURN_GENERATED_KEYS);
            pstmt.setInt(1, userId);
            pstmt.setString(2, name);
            pstmt.setBoolean(3, isDefault);

            int result = pstmt.executeUpdate();
            System.out.println("🎵 [DEBUG] 创建歌单 - 用户ID: " + userId + ", 歌单名: " + name + ", 默认: " + isDefault);

            if (result > 0) {
                rs = pstmt.getGeneratedKeys();
                if (rs.next()) {
                    return rs.getInt(1);
                }
            }
            return -1;
        } catch (SQLException e) {
            System.err.println("❌ [ERROR] 创建歌单失败 - 用户ID: " + userId + ", 歌单名: " + name);
            System.err.println("错误信息: " + e.getMessage());
            e.printStackTrace();
            return -1;
        } finally {
            DBUtil.close(conn, pstmt, rs);
        }
    }

    /**
     * 获取用户的所有歌单
     * @param userId 用户ID
     * @return 歌单列表
     */
    public List<Playlist> getUserPlaylists(int userId) {
        Connection conn = null;
        PreparedStatement pstmt = null;
        ResultSet rs = null;
        List<Playlist> playlists = new ArrayList<>();

        try {
            conn = DBUtil.getConnection();
            String sql = "SELECT p.*, " +
                    "(SELECT COUNT(*) FROM playlist_songs WHERE playlist_id = p.id) as song_count " +
                    "FROM user_playlists p " +
                    "WHERE p.user_id = ? " +
                    "ORDER BY p.is_default DESC, p.create_time DESC";
            pstmt = conn.prepareStatement(sql);
            pstmt.setInt(1, userId);
            rs = pstmt.executeQuery();

            while (rs.next()) {
                Playlist playlist = new Playlist();
                playlist.setId(rs.getInt("id"));
                playlist.setUserId(rs.getInt("user_id"));
                playlist.setName(rs.getString("name"));
                playlist.setDescription(rs.getString("description"));
                playlist.setCoverImage(rs.getString("cover_image"));
                playlist.setDefault(rs.getBoolean("is_default"));
                playlist.setCreateTime(rs.getString("create_time"));
                playlist.setUpdateTime(rs.getString("update_time"));
                playlist.setSongCount(rs.getInt("song_count"));
                playlists.add(playlist);
            }

            System.out.println("🎵 [DEBUG] 获取用户歌单 - 用户ID: " + userId + ", 数量: " + playlists.size());
            return playlists;
        } catch (SQLException e) {
            System.err.println("❌ [ERROR] 获取用户歌单失败 - 用户ID: " + userId);
            System.err.println("错误信息: " + e.getMessage());
            e.printStackTrace();
            return playlists;
        } finally {
            DBUtil.close(conn, pstmt, rs);
        }
    }

    /**
     * 获取用户的默认歌单
     * @param userId 用户ID
     * @return 默认歌单，不存在返回null
     */
    public Playlist getDefaultPlaylist(int userId) {
        Connection conn = null;
        PreparedStatement pstmt = null;
        ResultSet rs = null;

        try {
            conn = DBUtil.getConnection();
            String sql = "SELECT p.*, " +
                    "(SELECT COUNT(*) FROM playlist_songs WHERE playlist_id = p.id) as song_count " +
                    "FROM user_playlists p " +
                    "WHERE p.user_id = ? AND p.is_default = TRUE";
            pstmt = conn.prepareStatement(sql);
            pstmt.setInt(1, userId);
            rs = pstmt.executeQuery();

            if (rs.next()) {
                Playlist playlist = new Playlist();
                playlist.setId(rs.getInt("id"));
                playlist.setUserId(rs.getInt("user_id"));
                playlist.setName(rs.getString("name"));
                playlist.setDescription(rs.getString("description"));
                playlist.setCoverImage(rs.getString("cover_image"));
                playlist.setDefault(rs.getBoolean("is_default"));
                playlist.setCreateTime(rs.getString("create_time"));
                playlist.setUpdateTime(rs.getString("update_time"));
                playlist.setSongCount(rs.getInt("song_count"));
                return playlist;
            }
            return null;
        } catch (SQLException e) {
            System.err.println("❌ [ERROR] 获取默认歌单失败 - 用户ID: " + userId);
            System.err.println("错误信息: " + e.getMessage());
            e.printStackTrace();
            return null;
        } finally {
            DBUtil.close(conn, pstmt, rs);
        }
    }

    /**
     * 根据ID获取歌单详情
     * @param playlistId 歌单ID
     * @return 歌单对象，不存在返回null
     */
    public Playlist getPlaylistById(int playlistId) {
        Connection conn = null;
        PreparedStatement pstmt = null;
        ResultSet rs = null;

        try {
            conn = DBUtil.getConnection();
            String sql = "SELECT p.*, " +
                    "(SELECT COUNT(*) FROM playlist_songs WHERE playlist_id = p.id) as song_count " +
                    "FROM user_playlists p WHERE p.id = ?";
            pstmt = conn.prepareStatement(sql);
            pstmt.setInt(1, playlistId);
            rs = pstmt.executeQuery();

            if (rs.next()) {
                Playlist playlist = new Playlist();
                playlist.setId(rs.getInt("id"));
                playlist.setUserId(rs.getInt("user_id"));
                playlist.setName(rs.getString("name"));
                playlist.setDescription(rs.getString("description"));
                playlist.setCoverImage(rs.getString("cover_image"));
                playlist.setDefault(rs.getBoolean("is_default"));
                playlist.setCreateTime(rs.getString("create_time"));
                playlist.setUpdateTime(rs.getString("update_time"));
                playlist.setSongCount(rs.getInt("song_count"));
                return playlist;
            }
            return null;
        } catch (SQLException e) {
            System.err.println("❌ [ERROR] 获取歌单详情失败 - 歌单ID: " + playlistId);
            System.err.println("错误信息: " + e.getMessage());
            e.printStackTrace();
            return null;
        } finally {
            DBUtil.close(conn, pstmt, rs);
        }
    }

    /**
     * 获取歌单中的所有歌曲
     * @param playlistId 歌单ID
     * @return 歌曲列表
     */
    public List<Song> getPlaylistSongs(int playlistId) {
        Connection conn = null;
        PreparedStatement pstmt = null;
        ResultSet rs = null;
        List<Song> songs = new ArrayList<>();

        try {
            conn = DBUtil.getConnection();
            String sql = "SELECT s.*, ps.add_time " +
                    "FROM playlist_songs ps " +
                    "JOIN songs s ON ps.song_id = s.id " +
                    "WHERE ps.playlist_id = ? " +
                    "ORDER BY ps.add_time DESC";
            pstmt = conn.prepareStatement(sql);
            pstmt.setInt(1, playlistId);
            rs = pstmt.executeQuery();

            SongDAO songDAO = new SongDAO();
            while (rs.next()) {
                Song song = songDAO.getSongById(rs.getInt("id"));
                if (song != null) {
                    songs.add(song);
                }
            }

            System.out.println("🎵 [DEBUG] 获取歌单歌曲 - 歌单ID: " + playlistId + ", 数量: " + songs.size());
            return songs;
        } catch (SQLException e) {
            System.err.println("❌ [ERROR] 获取歌单歌曲失败 - 歌单ID: " + playlistId);
            System.err.println("错误信息: " + e.getMessage());
            e.printStackTrace();
            return songs;
        } finally {
            DBUtil.close(conn, pstmt, rs);
        }
    }

    /**
     * 添加歌曲到歌单
     * @param playlistId 歌单ID
     * @param songId 歌曲ID
     * @return 是否成功
     */
    public boolean addSongToPlaylist(int playlistId, int songId) {
        Connection conn = null;
        PreparedStatement pstmt = null;

        try {
            conn = DBUtil.getConnection();
            String sql = "INSERT INTO playlist_songs (playlist_id, song_id) VALUES (?, ?)";
            pstmt = conn.prepareStatement(sql);
            pstmt.setInt(1, playlistId);
            pstmt.setInt(2, songId);

            int result = pstmt.executeUpdate();
            System.out.println("🎵 [DEBUG] 添加歌曲到歌单 - 歌单ID: " + playlistId + ", 歌曲ID: " + songId);

            return result > 0;
        } catch (SQLException e) {
            System.err.println("❌ [ERROR] 添加歌曲到歌单失败 - 歌单ID: " + playlistId + ", 歌曲ID: " + songId);
            System.err.println("错误信息: " + e.getMessage());
            e.printStackTrace();
            return false;
        } finally {
            DBUtil.close(conn, pstmt, null);
        }
    }

    /**
     * 从歌单移除歌曲
     * @param playlistId 歌单ID
     * @param songId 歌曲ID
     * @return 是否成功
     */
    public boolean removeSongFromPlaylist(int playlistId, int songId) {
        Connection conn = null;
        PreparedStatement pstmt = null;

        try {
            conn = DBUtil.getConnection();
            String sql = "DELETE FROM playlist_songs WHERE playlist_id = ? AND song_id = ?";
            pstmt = conn.prepareStatement(sql);
            pstmt.setInt(1, playlistId);
            pstmt.setInt(2, songId);

            int result = pstmt.executeUpdate();
            System.out.println("🎵 [DEBUG] 从歌单移除歌曲 - 歌单ID: " + playlistId + ", 歌曲ID: " + songId);

            return result > 0;
        } catch (SQLException e) {
            System.err.println("❌ [ERROR] 从歌单移除歌曲失败 - 歌单ID: " + playlistId + ", 歌曲ID: " + songId);
            System.err.println("错误信息: " + e.getMessage());
            e.printStackTrace();
            return false;
        } finally {
            DBUtil.close(conn, pstmt, null);
        }
    }

    /**
     * 更新歌单信息
     * @param playlistId 歌单ID
     * @param name 歌单名称
     * @param description 歌单描述
     * @return 是否成功
     */
    public boolean updatePlaylistInfo(int playlistId, String name, String description) {
        Connection conn = null;
        PreparedStatement pstmt = null;

        try {
            conn = DBUtil.getConnection();
            String sql = "UPDATE user_playlists SET name = ?, description = ? WHERE id = ?";
            pstmt = conn.prepareStatement(sql);
            pstmt.setString(1, name);
            pstmt.setString(2, description);
            pstmt.setInt(3, playlistId);

            int result = pstmt.executeUpdate();
            System.out.println("🎵 [DEBUG] 更新歌单信息 - 歌单ID: " + playlistId + ", 新名称: " + name);

            return result > 0;
        } catch (SQLException e) {
            System.err.println("❌ [ERROR] 更新歌单信息失败 - 歌单ID: " + playlistId);
            System.err.println("错误信息: " + e.getMessage());
            e.printStackTrace();
            return false;
        } finally {
            DBUtil.close(conn, pstmt, null);
        }
    }

    /**
     * 删除歌单
     * @param playlistId 歌单ID
     * @return 是否成功
     */
    public boolean deletePlaylist(int playlistId) {
        Connection conn = null;
        PreparedStatement pstmt = null;

        try {
            // 先检查是否为默认歌单
            Playlist playlist = getPlaylistById(playlistId);
            if (playlist != null && playlist.isDefault()) {
                System.err.println("❌ [ERROR] 默认歌单不可删除 - 歌单ID: " + playlistId);
                return false;
            }

            conn = DBUtil.getConnection();
            String sql = "DELETE FROM user_playlists WHERE id = ?";
            pstmt = conn.prepareStatement(sql);
            pstmt.setInt(1, playlistId);

            int result = pstmt.executeUpdate();
            System.out.println("🎵 [DEBUG] 删除歌单 - 歌单ID: " + playlistId);

            return result > 0;
        } catch (SQLException e) {
            System.err.println("❌ [ERROR] 删除歌单失败 - 歌单ID: " + playlistId);
            System.err.println("错误信息: " + e.getMessage());
            e.printStackTrace();
            return false;
        } finally {
            DBUtil.close(conn, pstmt, null);
        }
    }

    /**
     * 检查歌曲是否在歌单中
     * @param playlistId 歌单ID
     * @param songId 歌曲ID
     * @return 是否存在
     */
    public boolean isSongInPlaylist(int playlistId, int songId) {
        Connection conn = null;
        PreparedStatement pstmt = null;
        ResultSet rs = null;

        try {
            conn = DBUtil.getConnection();
            String sql = "SELECT id FROM playlist_songs WHERE playlist_id = ? AND song_id = ?";
            pstmt = conn.prepareStatement(sql);
            pstmt.setInt(1, playlistId);
            pstmt.setInt(2, songId);
            rs = pstmt.executeQuery();

            return rs.next();
        } catch (SQLException e) {
            System.err.println("❌ [ERROR] 检查歌曲是否在歌单中失败 - 歌单ID: " + playlistId + ", 歌曲ID: " + songId);
            System.err.println("错误信息: " + e.getMessage());
            e.printStackTrace();
            return false;
        } finally {
            DBUtil.close(conn, pstmt, rs);
        }
    }
}
