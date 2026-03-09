package com.music.dao;

import com.music.javabean.DBUtil;
import com.music.javabean.User;
import com.music.javabean.Song;
import com.music.javabean.Playlist;
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
        String sql = "SELECT id, username, email, nickname, phone, status, frozen_until, frozen_reason, deleted_at, create_time, preferred_genres, preferred_artists FROM users WHERE username != 'admin' ORDER BY create_time DESC";

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
                user.setDeletedAt(rs.getString("deleted_at"));
                user.setCreateTime(rs.getString("create_time"));
                user.setPreferredGenres(rs.getString("preferred_genres"));
                user.setPreferredArtists(rs.getString("preferred_artists"));
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
        String sql = "SELECT id, username, email, nickname, phone, status, frozen_until, frozen_reason, deleted_at, create_time, preferred_genres, preferred_artists FROM users WHERE id = ?";

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
                    user.setDeletedAt(rs.getString("deleted_at"));
                    user.setCreateTime(rs.getString("create_time"));
                    user.setPreferredGenres(rs.getString("preferred_genres"));
                    user.setPreferredArtists(rs.getString("preferred_artists"));
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
        String sql = "UPDATE users SET status = 'active', frozen_until = NULL, frozen_reason = NULL, deleted_at = NULL WHERE id = ?";

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
     * 更新歌曲信息（管理员专用）
     */
    public boolean updateSongAdmin(Song song) {
        String sql = "UPDATE songs SET title = ?, artist = ?, album = ?, duration = ?, genre = ?, release_year = ? WHERE id = ?";
        try (Connection conn = DBUtil.getConnection();
                PreparedStatement pstmt = conn.prepareStatement(sql)) {
            pstmt.setString(1, song.getTitle());
            pstmt.setString(2, song.getArtist());
            pstmt.setString(3, song.getAlbum());
            pstmt.setInt(4, song.getDuration());
            pstmt.setString(5, song.getGenre());
            pstmt.setInt(6, song.getReleaseYear());
            pstmt.setInt(7, song.getId());
            int affectedRows = pstmt.executeUpdate();
            if (affectedRows > 0) {
                com.music.dao.RedisUtil.clearAdminSongsCache();
                return true;
            }
            return false;
        } catch (SQLException e) {
            System.err.println("更新歌曲失败: " + e.getMessage());
            e.printStackTrace();
            return false;
        }
    }

    /**
     * 获取指定歌单的所有歌曲（管理员专用）
     */
    public List<Song> getPlaylistSongsForAdmin(int playlistId) {
        List<Song> songs = new ArrayList<>();
        String sql = "SELECT s.* FROM songs s JOIN playlist_songs ps ON s.id = ps.song_id WHERE ps.playlist_id = ? ORDER BY ps.add_time DESC";
        try (Connection conn = DBUtil.getConnection();
                PreparedStatement pstmt = conn.prepareStatement(sql)) {
            pstmt.setInt(1, playlistId);
            try (ResultSet rs = pstmt.executeQuery()) {
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
            }
        } catch (SQLException e) {
            System.err.println("获取歌单歌曲失败: " + e.getMessage());
            e.printStackTrace();
        }
        return songs;
    }

    /**
     * 删除歌单（管理员专用），仅允许删除非默认歌单
     */
    public boolean deletePlaylistAdmin(int playlistId) {
        String sql = "DELETE FROM user_playlists WHERE id = ? AND is_default = FALSE";
        try (Connection conn = DBUtil.getConnection();
                PreparedStatement pstmt = conn.prepareStatement(sql)) {
            pstmt.setInt(1, playlistId);
            return pstmt.executeUpdate() > 0;
        } catch (SQLException e) {
            System.err.println("删除歌单失败: " + e.getMessage());
            e.printStackTrace();
            return false;
        }
    }

    /**
     * 获取所有收藏记录
     */
    public List<Favorite> getAllFavorites() {
        List<Favorite> favorites = new ArrayList<>();
        String sql = "SELECT ps.id, up.user_id, ps.song_id, ps.add_time as create_time, u.username as user_name, s.title as song_title "
                +
                "FROM playlist_songs ps " +
                "JOIN user_playlists up ON ps.playlist_id = up.id AND up.is_default = TRUE " +
                "JOIN users u ON up.user_id = u.id " +
                "JOIN songs s ON ps.song_id = s.id " +
                "ORDER BY ps.add_time DESC";

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
                "SELECT COUNT(ps.id) FROM playlist_songs ps JOIN user_playlists up ON ps.playlist_id = up.id AND up.is_default = TRUE",
                "SELECT COUNT(*) FROM users WHERE create_time >= DATE_SUB(NOW(), INTERVAL 7 DAY)",
                "SELECT COUNT(ps.id) FROM playlist_songs ps JOIN user_playlists up ON ps.playlist_id = up.id AND up.is_default = TRUE WHERE ps.add_time >= DATE_SUB(NOW(), INTERVAL 7 DAY)"
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
     * 获取所有歌单（携带创建者用户名和歌曲数）
     * 联查 user_playlists, users, playlist_songs 表
     */
    public List<Playlist> getAllPlaylistsWithUser() {
        List<Playlist> playlists = new ArrayList<>();
        String sql = "SELECT p.*, u.username, " +
                "(SELECT COUNT(*) FROM playlist_songs ps WHERE ps.playlist_id = p.id) AS song_count " +
                "FROM user_playlists p " +
                "LEFT JOIN users u ON p.user_id = u.id " +
                "WHERE u.username != 'admin' OR u.username IS NULL " +
                "ORDER BY p.create_time DESC";

        try (Connection conn = DBUtil.getConnection();
                PreparedStatement pstmt = conn.prepareStatement(sql);
                ResultSet rs = pstmt.executeQuery()) {

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

                User user = new User();
                user.setUsername(rs.getString("username"));
                playlist.setUser(user);

                playlists.add(playlist);
            }
        } catch (SQLException e) {
            System.err.println("获取歌单列表失败: " + e.getMessage());
            e.printStackTrace();
        }

        return playlists;
    }

    /**
     * 获取指定用户的全部歌单
     */
    public List<Playlist> getUserPlaylists(int userId) {
        List<Playlist> playlists = new ArrayList<>();
        String sql = "SELECT * FROM user_playlists WHERE user_id = ? ORDER BY create_time DESC";

        try (Connection conn = DBUtil.getConnection();
                PreparedStatement pstmt = conn.prepareStatement(sql)) {

            pstmt.setInt(1, userId);
            try (ResultSet rs = pstmt.executeQuery()) {
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
                    playlists.add(playlist);
                }
            }
        } catch (SQLException e) {
            System.err.println("获取用户歌单失败: " + e.getMessage());
            e.printStackTrace();
        }

        return playlists;
    }

    /**
     * 获取指定用户所有歌单内的歌曲总数
     * 联查 user_playlists 和 playlist_songs 表统计
     */
    public int getUserTotalPlaylistSongCount(int userId) {
        int count = 0;
        String sql = "SELECT COUNT(ps.song_id) FROM playlist_songs ps " +
                "JOIN user_playlists p ON ps.playlist_id = p.id " +
                "WHERE p.user_id = ?";

        try (Connection conn = DBUtil.getConnection();
                PreparedStatement pstmt = conn.prepareStatement(sql)) {

            pstmt.setInt(1, userId);
            try (ResultSet rs = pstmt.executeQuery()) {
                if (rs.next()) {
                    count = rs.getInt(1);
                }
            }
        } catch (SQLException e) {
            System.err.println("获取用户歌单歌曲总数失败: " + e.getMessage());
            e.printStackTrace();
        }

        return count;
    }

    /**
     * 获取指定用户的收藏曲目数量
     */
    public int getUserFavoriteCount(int userId) {
        int count = 0;
        String sql = "SELECT COUNT(ps.id) FROM playlist_songs ps " +
                "JOIN user_playlists up ON ps.playlist_id = up.id " +
                "WHERE up.user_id = ? AND up.is_default = TRUE";

        try (Connection conn = DBUtil.getConnection();
                PreparedStatement pstmt = conn.prepareStatement(sql)) {

            pstmt.setInt(1, userId);
            try (ResultSet rs = pstmt.executeQuery()) {
                if (rs.next()) {
                    count = rs.getInt(1);
                }
            }
        } catch (SQLException e) {
            System.err.println("获取用户收藏数失败: " + e.getMessage());
            e.printStackTrace();
        }

        return count;
    }

    /**
     * 获取指定用户的累计听歌时长（秒）
     * 从 play_history 表的 play_duration 字段求和
     */
    public int getUserPlayDuration(int userId) {
        int duration = 0;
        String sql = "SELECT COALESCE(SUM(s.duration), 0) FROM play_history ph JOIN songs s ON ph.song_id = s.id WHERE ph.user_id = ?";

        try (Connection conn = DBUtil.getConnection();
                PreparedStatement pstmt = conn.prepareStatement(sql)) {

            pstmt.setInt(1, userId);
            try (ResultSet rs = pstmt.executeQuery()) {
                if (rs.next()) {
                    duration = rs.getInt(1);
                }
            }
        } catch (SQLException e) {
            System.err.println("获取用户听歌时长失败: " + e.getMessage());
            e.printStackTrace();
        }

        return duration;
    }

    /**
     * 物理删除所有软删除超过指定天数的用户及其关联数据
     * 【重要】使用事务保证级联删除的原子性
     *
     * @param days 删除阈值天数（30天）
     */
    public void hardDeleteExpiredUsers(int days) {
        String findSql = "SELECT id FROM users WHERE status = 'deleted' AND deleted_at IS NOT NULL AND DATEDIFF(NOW(), deleted_at) >= ?";

        try (Connection conn = DBUtil.getConnection()) {
            conn.setAutoCommit(false);

            try {
                /* 第一步：查找所有超期的待销毁用户ID */
                List<Integer> expiredUserIds = new ArrayList<>();
                try (PreparedStatement pstmt = conn.prepareStatement(findSql)) {
                    pstmt.setInt(1, days);
                    try (ResultSet rs = pstmt.executeQuery()) {
                        while (rs.next()) {
                            expiredUserIds.add(rs.getInt("id"));
                        }
                    }
                }

                if (expiredUserIds.isEmpty()) {
                    conn.commit();
                    return;
                }

                System.out.println("[自动清理] 发现 " + expiredUserIds.size() + " 个已过期用户，开始级联删除...");

                /* 第二步：对每个过期用户执行级联删除 */
                String[] cascadeQueries = {
                        "DELETE FROM playlist_songs WHERE playlist_id IN (SELECT id FROM user_playlists WHERE user_id = ?)",
                        "DELETE FROM user_playlists WHERE user_id = ?",
                        "DELETE FROM favorites WHERE user_id = ?",
                        "DELETE FROM play_history WHERE user_id = ?",
                        "DELETE FROM recommendation_feedback WHERE user_id = ?",
                        "DELETE FROM recommendations WHERE user_id = ?",
                        "DELETE FROM users WHERE id = ?"
                };

                for (int userId : expiredUserIds) {
                    for (String cascadeSql : cascadeQueries) {
                        try (PreparedStatement pstmt = conn.prepareStatement(cascadeSql)) {
                            pstmt.setInt(1, userId);
                            pstmt.executeUpdate();
                        }
                    }
                    System.out.println("[自动清理] 用户ID=" + userId + " 已被永久删除。");
                }

                conn.commit();
            } catch (SQLException e) {
                conn.rollback();
                System.err.println("级联删除过期用户失败，已回滚: " + e.getMessage());
                e.printStackTrace();
            } finally {
                conn.setAutoCommit(true);
            }
        } catch (SQLException e) {
            System.err.println("获取数据库连接失败: " + e.getMessage());
            e.printStackTrace();
        }
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

    /**
     * 获取指定页的歌曲列表（支持分页，并使用 Redis 缓存。带搜索条件时不走缓存）
     */
    public List<Song> getSongsByPage(int page, int pageSize, String searchQuery) {
        boolean isSearch = searchQuery != null && !searchQuery.trim().isEmpty();

        if (!isSearch) {
            String cacheKey = RedisUtil.getAdminSongsPageKey(page);
            List<Song> cachedList = RedisUtil.getList(cacheKey, new com.google.gson.reflect.TypeToken<List<Song>>() {});
            if (cachedList != null) {
                System.out.println("✅ [Redis缓存命中] 管理员后台歌曲列表 - page=" + page);
                return cachedList;
            }
        }

        List<Song> songs = new ArrayList<>();
        String sql;
        if (isSearch) {
            sql = "SELECT id, title, artist, album, duration, genre, release_year, file_path, cover_image, language FROM songs WHERE title LIKE ? OR artist LIKE ? OR album LIKE ? ORDER BY id LIMIT ? OFFSET ?";
        } else {
            sql = "SELECT id, title, artist, album, duration, genre, release_year, file_path, cover_image, language FROM songs ORDER BY id LIMIT ? OFFSET ?";
        }
        
        try (Connection conn = DBUtil.getConnection();
             PreparedStatement pstmt = conn.prepareStatement(sql)) {
            
            int paramIndex = 1;
            if (isSearch) {
                String likePattern = "%" + searchQuery.trim() + "%";
                pstmt.setString(paramIndex++, likePattern);
                pstmt.setString(paramIndex++, likePattern);
                pstmt.setString(paramIndex++, likePattern);
            }
            pstmt.setInt(paramIndex++, pageSize);
            pstmt.setInt(paramIndex++, (page - 1) * pageSize);
            
            try (ResultSet rs = pstmt.executeQuery()) {
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
            }
            
            if (!isSearch) {
                String cacheKey = RedisUtil.getAdminSongsPageKey(page);
                RedisUtil.setList(cacheKey, songs, RedisUtil.TTL_MEDIUM);
                System.out.println("📦 [Redis缓存写入] 管理员后台歌曲列表 - page=" + page + ", count=" + songs.size());
            }

        } catch (SQLException e) {
            System.err.println("获取分页歌曲列表失败: " + e.getMessage());
            e.printStackTrace();
        }

        return songs;
    }

    /**
     * 获取歌曲总数（使用 Redis 缓存。带搜索条件时不走缓存）
     */
    public int getTotalSongsCount(String searchQuery) {
        boolean isSearch = searchQuery != null && !searchQuery.trim().isEmpty();

        if (!isSearch) {
            String cacheKey = RedisUtil.KEY_ADMIN_SONGS_COUNT;
            String cachedCount = RedisUtil.get(cacheKey);
            if (cachedCount != null) {
                try {
                    return Integer.parseInt(cachedCount);
                } catch (NumberFormatException e) {
                    // Ignore parse errors
                }
            }
        }

        int count = 0;
        String sql;
        if (isSearch) {
            sql = "SELECT COUNT(*) FROM songs WHERE title LIKE ? OR artist LIKE ? OR album LIKE ?";
        } else {
            sql = "SELECT COUNT(*) FROM songs";
        }

        try (Connection conn = DBUtil.getConnection();
             PreparedStatement pstmt = conn.prepareStatement(sql)) {
            
            if (isSearch) {
                String likePattern = "%" + searchQuery.trim() + "%";
                pstmt.setString(1, likePattern);
                pstmt.setString(2, likePattern);
                pstmt.setString(3, likePattern);
            }

            try (ResultSet rs = pstmt.executeQuery()) {
                if (rs.next()) {
                    count = rs.getInt(1);
                }
            }

            if (!isSearch) {
                RedisUtil.set(RedisUtil.KEY_ADMIN_SONGS_COUNT, String.valueOf(count), RedisUtil.TTL_MEDIUM);
            }
        } catch (SQLException e) {
            System.err.println("获取歌曲总数失败: " + e.getMessage());
            e.printStackTrace();
        }
        return count;
    }
}