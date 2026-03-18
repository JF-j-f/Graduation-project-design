package com.music.dao;

import com.music.javabean.*;
import java.sql.*;
import java.util.*;

public class SongDAO {

    // 检查歌曲是否存在
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

            return rs.next();
        } catch (SQLException e) {
            e.printStackTrace();
            return false;
        } finally {
            DBUtil.close(conn, pstmt, rs);
        }
    }

    // 获取所有歌曲
    public List<Song> getAllSongs() {
        Connection conn = null;
        PreparedStatement pstmt = null;
        ResultSet rs = null;
        List<Song> songs = new ArrayList<>();

        try {
            conn = DBUtil.getConnection();
            String sql = "SELECT * FROM songs ORDER BY id";
            pstmt = conn.prepareStatement(sql);
            rs = pstmt.executeQuery();

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
            e.printStackTrace();
        } finally {
            DBUtil.close(conn, pstmt, rs);
        }

        return songs;
    }

    // 根据ID获取歌曲
    public Song getSongById(int songId) {
        Connection conn = null;
        PreparedStatement pstmt = null;
        ResultSet rs = null;
        Song song = null;

        try {
            conn = DBUtil.getConnection();
            String sql = "SELECT * FROM songs WHERE id = ?";
            pstmt = conn.prepareStatement(sql);
            pstmt.setInt(1, songId);
            rs = pstmt.executeQuery();

            if (rs.next()) {
                song = new Song();
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
            }
        } catch (SQLException e) {
            e.printStackTrace();
        } finally {
            DBUtil.close(conn, pstmt, rs);
        }

        return song;
    }

    // 添加歌曲（管理员功能）
    public boolean addSong(Song song) {
        Connection conn = null;
        PreparedStatement pstmt = null;

        try {
            conn = DBUtil.getConnection();
            String sql = "INSERT INTO songs (title, artist, album, duration, genre, release_year, file_path, cover_image) VALUES (?, ?, ?, ?, ?, ?, ?, ?)";
            pstmt = conn.prepareStatement(sql);
            pstmt.setString(1, song.getTitle());
            pstmt.setString(2, song.getArtist());
            pstmt.setString(3, song.getAlbum());
            pstmt.setInt(4, song.getDuration());
            pstmt.setString(5, song.getGenre());
            pstmt.setInt(6, song.getReleaseYear());
            pstmt.setString(7, song.getFilePath());
            pstmt.setString(8, song.getCoverImage());

            return pstmt.executeUpdate() > 0;
        } catch (SQLException e) {
            e.printStackTrace();
            return false;
        } finally {
            DBUtil.close(conn, pstmt, null);
        }
    }

    // 删除歌曲
    public boolean deleteSong(int songId) {
        Connection conn = null;
        PreparedStatement pstmt = null;
        try {
            conn = DBUtil.getConnection();
            conn.setAutoCommit(false);

            // 先删除 playlist_songs 表中的相关记录（已废弃 favorites 表）
            String deleteFavoriteSql = "DELETE FROM playlist_songs WHERE song_id = ?";
            pstmt = conn.prepareStatement(deleteFavoriteSql);
            pstmt.setInt(1, songId);
            pstmt.executeUpdate();
            pstmt.close();

            // 再删除歌曲
            String deleteSongSql = "DELETE FROM songs WHERE id = ?";
            pstmt = conn.prepareStatement(deleteSongSql);
            pstmt.setInt(1, songId);
            int result = pstmt.executeUpdate();

            conn.commit();
            return result > 0;
        } catch (SQLException e) {
            try {
                if (conn != null)
                    conn.rollback();
            } catch (SQLException ex) {
                ex.printStackTrace();
            }
            e.printStackTrace();
            return false;
        } finally {
            try {
                if (conn != null)
                    conn.setAutoCommit(true);
            } catch (SQLException e) {
                e.printStackTrace();
            }
            DBUtil.close(conn, pstmt, null);
        }
    }

    // 获取热歌榜（按播放次数或默认排序）
    public List<Song> getHotSongs(int limit) {
        // 1. 先查缓存
        List<Song> cachedSongs = RedisUtil.getList(RedisUtil.KEY_HOT_SONGS,
                new com.google.gson.reflect.TypeToken<List<Song>>() {
                });
        if (cachedSongs != null && !cachedSongs.isEmpty()) {
            return cachedSongs.size() > limit ? cachedSongs.subList(0, limit) : cachedSongs;
        }

        Connection conn = null;
        PreparedStatement pstmt = null;
        ResultSet rs = null;
        List<Song> songs = new ArrayList<>();

        try {
            conn = DBUtil.getConnection();
            // 按收藏次数排序（数据来源：playlist_songs 默认歌单）
            String sql = "SELECT s.*, IFNULL(f.favorite_count, 0) as favorite_count FROM songs s " +
                    "LEFT JOIN (SELECT ps.song_id, COUNT(*) as favorite_count " +
                    "FROM playlist_songs ps JOIN user_playlists up ON ps.playlist_id = up.id " +
                    "WHERE up.is_default = TRUE GROUP BY ps.song_id) f ON s.id = f.song_id " +
                    "ORDER BY favorite_count DESC, s.id DESC LIMIT ?";
            pstmt = conn.prepareStatement(sql);
            pstmt.setInt(1, limit);
            rs = pstmt.executeQuery();

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

            // 2. 写入缓存 (30分钟)
            if (!songs.isEmpty()) {
                RedisUtil.setList(RedisUtil.KEY_HOT_SONGS, songs, RedisUtil.TTL_MEDIUM);
            }

        } catch (SQLException e) {
            e.printStackTrace();
        } finally {
            DBUtil.close(conn, pstmt, rs);
        }

        return songs;
    }

    // 获取新歌榜（按发布时间排序）
    public List<Song> getNewSongs(int limit) {
        // 1. 先查缓存
        List<Song> cachedSongs = RedisUtil.getList(RedisUtil.KEY_NEW_SONGS,
                new com.google.gson.reflect.TypeToken<List<Song>>() {
                });
        if (cachedSongs != null && !cachedSongs.isEmpty()) {
            return cachedSongs.size() > limit ? cachedSongs.subList(0, limit) : cachedSongs;
        }

        Connection conn = null;
        PreparedStatement pstmt = null;
        ResultSet rs = null;
        List<Song> songs = new ArrayList<>();

        try {
            conn = DBUtil.getConnection();
            String sql = "SELECT * FROM songs ORDER BY release_year DESC, id DESC LIMIT ?";
            pstmt = conn.prepareStatement(sql);
            pstmt.setInt(1, limit);
            rs = pstmt.executeQuery();

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

            // 2. 写入缓存 (30分钟)
            if (!songs.isEmpty()) {
                RedisUtil.setList(RedisUtil.KEY_NEW_SONGS, songs, RedisUtil.TTL_MEDIUM);
            }

        } catch (SQLException e) {
            e.printStackTrace();
        } finally {
            DBUtil.close(conn, pstmt, rs);
        }

        return songs;
    }

    // 获取收藏榜（按收藏次数排序）
    public List<Song> getFavoriteSongs(int limit) {
        Connection conn = null;
        PreparedStatement pstmt = null;
        ResultSet rs = null;
        List<Song> songs = new ArrayList<>();

        try {
            conn = DBUtil.getConnection();
            String sql = "SELECT s.*, COUNT(ps.id) as favorite_count FROM songs s " +
                    "LEFT JOIN playlist_songs ps ON s.id = ps.song_id " +
                    "LEFT JOIN user_playlists up ON ps.playlist_id = up.id AND up.is_default = TRUE " +
                    "GROUP BY s.id " +
                    "ORDER BY favorite_count DESC, s.id DESC " +
                    "LIMIT ?";
            pstmt = conn.prepareStatement(sql);
            pstmt.setInt(1, limit);
            rs = pstmt.executeQuery();

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
            e.printStackTrace();
        } finally {
            DBUtil.close(conn, pstmt, rs);
        }

        return songs;
    }

    // 搜索歌曲（支持标题、艺术家、专辑、类型模糊匹配）
    public List<Song> searchSongs(String keyword) {
        Connection conn = null;
        PreparedStatement pstmt = null;
        ResultSet rs = null;
        List<Song> songs = new ArrayList<>();

        try {
            conn = DBUtil.getConnection();
            String sql = "SELECT * FROM songs WHERE " +
                    "title LIKE ? OR artist LIKE ? OR album LIKE ? OR genre LIKE ? " +
                    "ORDER BY release_year DESC, id DESC";
            pstmt = conn.prepareStatement(sql);

            String searchPattern = "%" + keyword + "%";
            pstmt.setString(1, searchPattern);
            pstmt.setString(2, searchPattern);
            pstmt.setString(3, searchPattern);
            pstmt.setString(4, searchPattern);

            rs = pstmt.executeQuery();

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

            System.out.println("🔍 [DEBUG] 搜索歌曲 - 关键词: " + keyword + ", 结果数: " + songs.size());

        } catch (SQLException e) {
            System.err.println("❌ [ERROR] 搜索歌曲失败 - 关键词: " + keyword);
            System.err.println("错误信息: " + e.getMessage());
            e.printStackTrace();
        } finally {
            DBUtil.close(conn, pstmt, rs);
        }

        return songs;
    }

    // 搜索歌曲（支持标题、艺术家、专辑、类型模糊匹配 + 高级筛选）
    public List<Song> searchSongsWithFilters(String keyword, String genre, String artist, Integer yearFrom,
            Integer yearTo) {
        Connection conn = null;
        PreparedStatement pstmt = null;
        ResultSet rs = null;
        List<Song> songs = new ArrayList<>();

        try {
            conn = DBUtil.getConnection();

            // 动态构建SQL查询
            StringBuilder sql = new StringBuilder("SELECT * FROM songs WHERE 1=1");
            List<Object> params = new ArrayList<>();

            // 关键词搜索（如果提供）
            if (keyword != null && !keyword.trim().isEmpty()) {
                sql.append(" AND (title LIKE ? OR artist LIKE ? OR album LIKE ? OR genre LIKE ?)");
                String searchPattern = "%" + keyword.trim() + "%";
                params.add(searchPattern);
                params.add(searchPattern);
                params.add(searchPattern);
                params.add(searchPattern);
            }

            // 风格筛选（精确匹配）
            if (genre != null && !genre.trim().isEmpty()) {
                sql.append(" AND genre = ?");
                params.add(genre.trim());
            }

            // 艺术家筛选（模糊匹配）
            if (artist != null && !artist.trim().isEmpty()) {
                sql.append(" AND artist LIKE ?");
                params.add("%" + artist.trim() + "%");
            }

            // 年份范围筛选
            if (yearFrom != null) {
                sql.append(" AND release_year >= ?");
                params.add(yearFrom);
            }
            if (yearTo != null) {
                sql.append(" AND release_year <= ?");
                params.add(yearTo);
            }

            sql.append(" ORDER BY release_year DESC, id DESC");

            pstmt = conn.prepareStatement(sql.toString());

            // 设置参数
            for (int i = 0; i < params.size(); i++) {
                pstmt.setObject(i + 1, params.get(i));
            }

            rs = pstmt.executeQuery();

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

            System.out.println("🔍 [DEBUG] 搜索歌曲（带筛选） - 关键词: " + keyword +
                    ", 风格: " + genre +
                    ", 艺术家: " + artist +
                    ", 年份: " + yearFrom + "~" + yearTo +
                    ", 结果数: " + songs.size());

        } catch (SQLException e) {
            System.err.println("❌ [ERROR] 搜索歌曲失败（带筛选）");
            System.err.println("错误信息: " + e.getMessage());
            e.printStackTrace();
        } finally {
            DBUtil.close(conn, pstmt, rs);
        }

        return songs;
    }

    // 新增：获取个性化推荐（按照 score 得分从高到低，支持游标分页）
    public List<Song> getRecommendationsByScore(int userId, int limit, int offset) {
        // 由于存在 offset 轮询机制，为了保证前端严格按序拿到数据，暂不使用 Redis 整体缓存，而是直接走 MySQL 拿最准确的 TOP
        Connection conn = null;
        PreparedStatement pstmt = null;
        ResultSet rs = null;
        List<Song> songs = new ArrayList<>();

        try {
            conn = DBUtil.getConnection();
            String sql = "SELECT s.* FROM songs s " +
                    "JOIN recommendations r ON s.id = r.song_id " +
                    "WHERE r.user_id = ? " +
                    "ORDER BY r.score DESC " +
                    "LIMIT ? OFFSET ?";

            pstmt = conn.prepareStatement(sql);
            pstmt.setInt(1, userId);
            pstmt.setInt(2, limit);
            pstmt.setInt(3, offset);

            rs = pstmt.executeQuery();

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

            // 【兜底策略】
            // 如果取出的数据为空（新用户或 Python 未跑），回退到"新歌榜"
            if (songs.isEmpty() && offset == 0) {
                System.out.println("⚠️ 用户 " + userId + " 无个性化数据，降级为新歌榜");
                return getNewSongs(limit);
            }

        } catch (SQLException e) {
            e.printStackTrace();
        } finally {
            DBUtil.close(conn, pstmt, rs);
        }

        return songs;
    }

    // ============================================
    // v3.1.0 新增：外部歌曲处理方法
    // ============================================

    /**
     * 根据标题+歌手+专辑查找歌曲
     * 用于判断外部歌曲是否已存在于数据库中
     * 
     * @param title  歌曲标题
     * @param artist 歌手
     * @param album  专辑（可为空，空时只匹配标题和歌手）
     * @return 匹配的歌曲，未找到返回 null
     */
    public Song findByTitleArtistAlbum(String title, String artist, String album) {
        Connection conn = null;
        PreparedStatement pstmt = null;
        ResultSet rs = null;
        Song song = null;

        try {
            conn = DBUtil.getConnection();
            String sql;

            if (album != null && !album.trim().isEmpty()) {
                // 完整匹配：标题 + 歌手 + 专辑
                sql = "SELECT * FROM songs WHERE title = ? AND artist = ? AND album = ? LIMIT 1";
                pstmt = conn.prepareStatement(sql);
                pstmt.setString(1, title);
                pstmt.setString(2, artist);
                pstmt.setString(3, album);
            } else {
                // 部分匹配：标题 + 歌手
                sql = "SELECT * FROM songs WHERE title = ? AND artist = ? LIMIT 1";
                pstmt = conn.prepareStatement(sql);
                pstmt.setString(1, title);
                pstmt.setString(2, artist);
            }

            rs = pstmt.executeQuery();

            if (rs.next()) {
                song = new Song();
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
            }

            System.out.println("🔍 [查找歌曲] " + title + " - " + artist +
                    (album != null ? " (" + album + ")" : "") +
                    " => " + (song != null ? "找到 ID=" + song.getId() : "未找到"));

        } catch (SQLException e) {
            System.err.println("❌ [ERROR] 查找歌曲失败: " + e.getMessage());
            e.printStackTrace();
        } finally {
            DBUtil.close(conn, pstmt, rs);
        }

        return song;
    }

    /**
     * 智能歌手交集匹配
     * 
     * 处理不同音乐源歌手格式不一致的问题，例如：
     * - 数据库：`VISION SOUND`
     * - 传入：`jixwang / VISION SOUND`
     * 
     * 匹配逻辑：
     * 1. 按 title 查找所有候选歌曲
     * 2. 将传入的 artist 按分隔符（" / "、"/"）分割成列表
     * 3. 检查候选歌曲的 artist 是否与列表有交集
     * 
     * @param title  歌曲标题
     * @param artist 传入的歌手名称（可能包含多个歌手）
     * @return 匹配的歌曲，未找到返回 null
     */
    public Song findByTitleAndArtistIntersection(String title, String artist) {
        if (title == null || title.isEmpty() || artist == null || artist.isEmpty()) {
            return null;
        }

        Connection conn = null;
        PreparedStatement pstmt = null;
        ResultSet rs = null;
        Song bestMatch = null;

        try {
            conn = DBUtil.getConnection();
            // 按 title 查找所有候选歌曲
            String sql = "SELECT * FROM songs WHERE title = ?";
            pstmt = conn.prepareStatement(sql);
            pstmt.setString(1, title);
            rs = pstmt.executeQuery();

            // 将传入的 artist 按分隔符分割成列表（支持多种格式）
            java.util.Set<String> inputArtists = new java.util.HashSet<>();
            for (String a : artist.split("\\s*/\\s*|\\s*,\\s*|\\s*&\\s*")) {
                String trimmed = a.trim().toLowerCase();
                if (!trimmed.isEmpty()) {
                    inputArtists.add(trimmed);
                }
            }

            while (rs.next()) {
                String dbArtist = rs.getString("artist");
                if (dbArtist == null || dbArtist.isEmpty()) {
                    continue;
                }

                // 将数据库的 artist 也分割成列表
                java.util.Set<String> dbArtists = new java.util.HashSet<>();
                for (String a : dbArtist.split("\\s*/\\s*|\\s*,\\s*|\\s*&\\s*")) {
                    String trimmed = a.trim().toLowerCase();
                    if (!trimmed.isEmpty()) {
                        dbArtists.add(trimmed);
                    }
                }

                // 检查是否有交集
                java.util.Set<String> intersection = new java.util.HashSet<>(inputArtists);
                intersection.retainAll(dbArtists);

                if (!intersection.isEmpty()) {
                    // 找到匹配，构建 Song 对象
                    bestMatch = new Song();
                    bestMatch.setId(rs.getInt("id"));
                    bestMatch.setTitle(rs.getString("title"));
                    bestMatch.setArtist(dbArtist);
                    bestMatch.setAlbum(rs.getString("album"));
                    bestMatch.setDuration(rs.getInt("duration"));
                    bestMatch.setGenre(rs.getString("genre"));
                    bestMatch.setReleaseYear(rs.getInt("release_year"));
                    bestMatch.setFilePath(rs.getString("file_path"));
                    bestMatch.setCoverImage(rs.getString("cover_image"));
                    bestMatch.setLanguage(rs.getString("language"));

                    System.out.println("🔍 [智能匹配] " + title + " | 传入: '" + artist + "' ↔ 数据库: '" + dbArtist +
                            "' | 交集: " + intersection + " => 找到 ID=" + bestMatch.getId());
                    break; // 找到第一个匹配就返回
                }
            }

            if (bestMatch == null) {
                System.out.println("🔍 [智能匹配] " + title + " | '" + artist + "' => 未找到交集匹配");
            }

        } catch (SQLException e) {
            System.err.println("❌ [ERROR] 智能歌手匹配失败: " + e.getMessage());
            e.printStackTrace();
        } finally {
            DBUtil.close(conn, pstmt, rs);
        }

        return bestMatch;
    }

    /**
     * 添加或更新外部歌曲信息
     * - 如果歌曲不存在：插入新记录
     * - 如果歌曲已存在：强制更新元数据（Album, Duration, Source, Cover, Year, Genre, Language）
     * 
     * 匹配策略（两阶段）：
     * 1. 精确匹配：title + artist + album
     * 2. 智能匹配：title + 歌手交集（处理不同来源歌手格式不一致问题）
     * 
     * @param title       歌曲标题
     * @param artist      歌手
     * @param album       专辑
     * @param duration    时长（秒）
     * @param source      来源（netease/qq）
     * @param coverImage  封面路径
     * @param releaseYear 发行年份
     * @param genre       曲风
     * @param language    语言
     * @return 歌曲 ID
     */
    public int addOrUpdateFromExternal(String title, String artist, String album,
            int duration, String source,
            String coverImage, int releaseYear,
            String genre, String language) {
        // Step 1: 精确匹配 (title + artist + album)
        Song existing = findByTitleArtistAlbum(title, artist, album);

        // Step 2: 若精确匹配失败，尝试智能歌手交集匹配 (处理歌手格式不一致问题)
        if (existing == null) {
            existing = findByTitleAndArtistIntersection(title, artist);
        }

        if (existing != null) {
            // 3. 歌曲已存在，强制更新元数据
            return updateExistingSong(existing, source, coverImage, album, releaseYear, genre, language, duration);
        } else {
            // 4. 歌曲不存在，插入新记录
            return insertNewExternalSong(title, artist, album, duration, source, coverImage, releaseYear, genre,
                    language);
        }
    }

    /**
     * 累积来源标识
     * 
     * 将新来源追加到现有来源字符串中，用 ";" 分隔
     * 不会添加重复的来源
     * 
     * @param currentSources 当前来源字符串（如 "qq" 或 "netease;qq"）
     * @param newSource      新来源（如 "netease"）
     * @return 更新后的来源字符串
     */
    private String accumulateSource(String currentSources, String newSource) {
        if (newSource == null || newSource.isEmpty()) {
            return currentSources != null ? currentSources : "";
        }

        if (currentSources == null || currentSources.isEmpty()) {
            return newSource;
        }

        // 检查是否已包含该来源
        java.util.Set<String> sources = new java.util.LinkedHashSet<>();
        for (String s : currentSources.split(";")) {
            String trimmed = s.trim();
            if (!trimmed.isEmpty()) {
                sources.add(trimmed);
            }
        }

        // 添加新来源
        sources.add(newSource.trim());

        // 重新组合成字符串
        return String.join(";", sources);
    }

    /**
     * 智能合并元数据值（策略 C：子集判断合并）
     * 
     * 逻辑：
     * - 如果新值的所有标签都是旧值的子集 → 不更新，返回旧值
     * - 如果旧值的所有标签都是新值的子集 → 更新为新值
     * - 否则（有新内容）→ 合并两者
     * 
     * 用 ";" 作为分隔符
     * 
     * @param currentValue 当前值（如 "二次元;国产流行;日本流行"）
     * @param newValue     新值（如 "二次元"）
     * @return 合并后的值
     */
    private String mergeMetadataValues(String currentValue, String newValue) {
        // 如果新值为空，保持当前值
        if (newValue == null || newValue.isEmpty()) {
            return currentValue;
        }

        // 如果当前值为空，使用新值
        if (currentValue == null || currentValue.isEmpty()) {
            return newValue;
        }

        // 解析标签集合（支持多种分隔符："; " / ";" / ", " / "," / "；" / "，"）
        java.util.Set<String> currentTags = new java.util.LinkedHashSet<>();
        for (String tag : currentValue.split("[;,；，]\\s*")) {
            String trimmed = tag.trim();
            if (!trimmed.isEmpty()) {
                currentTags.add(trimmed);
            }
        }

        java.util.Set<String> newTags = new java.util.LinkedHashSet<>();
        for (String tag : newValue.split("[;,；，]\\s*")) {
            String trimmed = tag.trim();
            if (!trimmed.isEmpty()) {
                newTags.add(trimmed);
            }
        }

        // 判断子集关系
        boolean newIsSubsetOfCurrent = currentTags.containsAll(newTags);
        boolean currentIsSubsetOfNew = newTags.containsAll(currentTags);

        if (newIsSubsetOfCurrent) {
            // 新值是旧值的子集 → 保持旧值（标准化格式防止重复）
            return String.join(";", currentTags);
        } else if (currentIsSubsetOfNew) {
            // 旧值是新值的子集 → 使用新值（标准化为 ; 分隔）
            return String.join(";", newTags);
        } else {
            // 两者都有独有内容 → 合并
            java.util.Set<String> merged = new java.util.LinkedHashSet<>(currentTags);
            merged.addAll(newTags);
            return String.join(";", merged);
        }
    }

    /**
     * 强制更新已存在歌曲的元数据
     * 策略：只要新值有效且与旧值不同，立即覆盖（来源累积）
     */
    private int updateExistingSong(Song existing, String newSource,
            String newCoverImage, String newAlbum, int newReleaseYear,
            String newGenre, String newLanguage, int newDuration) {
        Connection conn = null;
        PreparedStatement pstmt = null;

        try {
            conn = DBUtil.getConnection();

            // 构建动态更新语句
            StringBuilder sql = new StringBuilder("UPDATE songs SET ");
            List<Object> params = new ArrayList<>();
            boolean needComma = false;

            // 1. 来源标识 (file_path) - 累积多来源，用 ";" 分隔
            // 存储所有可用的流媒体源 (如 "netease;qq")
            String currentFilePath = existing.getFilePath();
            if (newSource != null && !newSource.isEmpty()) {
                String updatedFilePath = accumulateSource(currentFilePath, newSource);
                if (!updatedFilePath.equals(currentFilePath)) {
                    sql.append("file_path = ?");
                    params.add(updatedFilePath);
                    needComma = true;
                }
            }

            // 2. 封面 (cover_image) - 强制覆盖
            String currentCover = existing.getCoverImage();
            if (newCoverImage != null && !newCoverImage.isEmpty() && !newCoverImage.equals(currentCover)) {
                if (needComma)
                    sql.append(", ");
                sql.append("cover_image = ?");
                params.add(newCoverImage);
                needComma = true;
            }

            // 3. 专辑 (album) - 强制覆盖
            String currentAlbum = existing.getAlbum();
            if (newAlbum != null && !newAlbum.isEmpty() && !newAlbum.equals(currentAlbum)) {
                if (needComma)
                    sql.append(", ");
                sql.append("album = ?");
                params.add(newAlbum);
                needComma = true;
            }

            // 4. 发行年份 (release_year) - 强制覆盖
            int currentYear = existing.getReleaseYear();
            if (newReleaseYear > 0 && newReleaseYear != currentYear) {
                if (needComma)
                    sql.append(", ");
                sql.append("release_year = ?");
                params.add(newReleaseYear);
                needComma = true;
            }

            // 5. 曲风 (genre) - 智能合并（策略 C：子集判断）
            String currentGenre = existing.getGenre();
            if (newGenre != null && !newGenre.isEmpty()) {
                String mergedGenre = mergeMetadataValues(currentGenre, newGenre);
                if (!mergedGenre.equals(currentGenre)) {
                    if (needComma)
                        sql.append(", ");
                    sql.append("genre = ?");
                    params.add(mergedGenre);
                    needComma = true;
                }
            }

            // 6. 语言 (language) - 智能合并（策略 C：子集判断）
            String currentLanguage = existing.getLanguage();
            if (newLanguage != null && !newLanguage.isEmpty()) {
                String mergedLanguage = mergeMetadataValues(currentLanguage, newLanguage);
                if (!mergedLanguage.equals(currentLanguage)) {
                    if (needComma)
                        sql.append(", ");
                    sql.append("language = ?");
                    params.add(mergedLanguage);
                    needComma = true;
                }
            }

            // 7. 时长 (duration) - 强制覆盖
            int currentDuration = existing.getDuration();
            if (newDuration > 0 && newDuration != currentDuration) {
                if (needComma)
                    sql.append(", ");
                sql.append("duration = ?");
                params.add(newDuration);
            }

            // 如果没有需要更新的字段，直接返回
            if (params.isEmpty()) {
                System.out.println("📝 [Skip] Song ID=" + existing.getId() + " data identical, skipped.");
                return existing.getId();
            }

            sql.append(" WHERE id = ?");
            params.add(existing.getId());

            pstmt = conn.prepareStatement(sql.toString());
            for (int i = 0; i < params.size(); i++) {
                pstmt.setObject(i + 1, params.get(i));
            }

            int result = pstmt.executeUpdate();
            System.out.println("📝 [Update] Song ID=" + existing.getId() +
                    " Updated fields=" + (params.size() - 1) + " Success=" + (result > 0));

            return existing.getId();

        } catch (SQLException e) {
            System.err.println("❌ [ERROR] Song update failed: " + e.getMessage());
            e.printStackTrace();
            return existing.getId();
        } finally {
            DBUtil.close(conn, pstmt, null);
        }
    }

    /**
     * 插入新的外部歌曲
     */
    /** 语言 → ISO-3166 发行国推断表（50+ 条目） */
    private static final java.util.Map<String, String> LANG_TO_COUNTRY;
    static {
        java.util.Map<String, String> m = new java.util.HashMap<>();
        m.put("国语", "TW"); m.put("普通话", "CN"); m.put("粤语", "HK");
        m.put("英语", "US"); m.put("日语", "JP"); m.put("韩语", "KR");
        m.put("法语", "FR"); m.put("西班牙语", "ES"); m.put("葡萄牙语", "BR");
        m.put("德语", "DE"); m.put("意大利语", "IT"); m.put("俄语", "RU");
        m.put("泰语", "TH"); m.put("越南语", "VN"); m.put("印尼语", "ID");
        m.put("马来语", "MY"); m.put("印地语", "IN"); m.put("阿拉伯语", "SA");
        m.put("土耳其语", "TR"); m.put("菲律宾语", "PH"); m.put("蒙古语", "MN");
        m.put("Chinese", "CN"); m.put("Mandarin", "TW"); m.put("Cantonese", "HK");
        m.put("English", "US"); m.put("Japanese", "JP"); m.put("Korean", "KR");
        m.put("French", "FR"); m.put("Spanish", "ES"); m.put("Portuguese", "BR");
        m.put("German", "DE"); m.put("Italian", "IT"); m.put("Russian", "RU");
        m.put("Thai", "TH"); m.put("Vietnamese", "VN"); m.put("Indonesian", "ID");
        m.put("Hindi", "IN"); m.put("Arabic", "SA"); m.put("Turkish", "TR");
        LANG_TO_COUNTRY = java.util.Collections.unmodifiableMap(m);
    }

    private String inferOriginCountry(String language) {
        if (language == null || language.isEmpty()) return "XX";
        // 多值分隔（取第一个）
        String first = language.split("[;,；，]")[0].trim();
        return LANG_TO_COUNTRY.getOrDefault(first, "XX");
    }

    private int insertNewExternalSong(String title, String artist, String album,
            int duration, String source,
            String coverImage, int releaseYear,
            String genre, String language) {
        Connection conn = null;
        PreparedStatement pstmt = null;
        ResultSet rs = null;

        String originCountry = inferOriginCountry(language);

        try {
            conn = DBUtil.getConnection();
            String sql = "INSERT INTO songs (title, artist, album, duration, genre, release_year, file_path, cover_image, language, origin_country) "
                    +
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)";
            pstmt = conn.prepareStatement(sql, Statement.RETURN_GENERATED_KEYS);
            pstmt.setString(1, title);
            pstmt.setString(2, artist);
            pstmt.setString(3, album != null ? album : "");
            pstmt.setInt(4, duration);
            pstmt.setString(5, genre != null ? genre : "");
            pstmt.setInt(6, releaseYear);
            pstmt.setString(7, source != null ? source : "");
            pstmt.setString(8, coverImage != null ? coverImage : "img/cover.jpg");
            pstmt.setString(9, language != null ? language : "");
            pstmt.setString(10, originCountry);

            int result = pstmt.executeUpdate();

            if (result > 0) {
                rs = pstmt.getGeneratedKeys();
                if (rs.next()) {
                    int newId = rs.getInt(1);
                    System.out.println("✅ [新增歌曲] ID=" + newId + " " + title + " - " + artist);
                    return newId;
                }
            }

            return -1;

        } catch (SQLException e) {
            System.err.println("❌ [ERROR] 插入歌曲失败: " + e.getMessage());
            e.printStackTrace();
            return -1;
        } finally {
            DBUtil.close(conn, pstmt, rs);
        }
    }

}