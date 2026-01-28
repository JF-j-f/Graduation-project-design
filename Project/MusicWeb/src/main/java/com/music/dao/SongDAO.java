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

            // 先删除 favorites 表中的相关记录
            String deleteFavoriteSql = "DELETE FROM favorites WHERE song_id = ?";
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
            // 假设有play_count字段，如果没有则按ID排序
            String sql = "SELECT s.*, IFNULL(f.favorite_count, 0) as favorite_count FROM songs s " +
                    "LEFT JOIN (SELECT song_id, COUNT(*) as favorite_count FROM favorites GROUP BY song_id) f ON s.id = f.song_id "
                    +
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
            String sql = "SELECT s.*, COUNT(f.id) as favorite_count FROM songs s " +
                    "LEFT JOIN favorites f ON s.id = f.song_id " +
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

    // 获取个性化推荐（从推荐池中随机抽取）
    public List<Song> getRecommendationsByRandom(int userId, int limit) {
        // 1. 先查缓存
        String cacheKey = RedisUtil.getUserRecommendationsKey(userId);
        List<Song> cachedSongs = RedisUtil.getList(cacheKey,
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
            // 关键 SQL：联合查询 recommendations 表，并随机排序
            // 如果 recommendations 表为空（冷启动），这会返回空列表
            String sql = "SELECT s.* FROM songs s " +
                    "JOIN recommendations r ON s.id = r.song_id " +
                    "WHERE r.user_id = ? " +
                    "ORDER BY RAND() LIMIT ?";

            pstmt = conn.prepareStatement(sql);
            pstmt.setInt(1, userId);
            pstmt.setInt(2, limit);

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
            // 如果推荐表里没数据（Python还没跑，或者新用户），回退到"新歌榜"
            if (songs.isEmpty()) {
                System.out.println("⚠️ 用户 " + userId + " 无个性化数据，降级为新歌榜");
                return getNewSongs(limit);
            }

            // 2. 写入缓存 (1小时)
            if (!songs.isEmpty()) {
                RedisUtil.setList(cacheKey, songs, RedisUtil.TTL_LONG);
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
     * 添加或更新外部歌曲信息
     * - 如果歌曲不存在：插入新记录
     * - 如果歌曲已存在：更新来源、封面、专辑、发行年份等缺失字段
     * 
     * @param title       歌曲标题
     * @param artist      歌手
     * @param album       专辑
     * @param duration    时长（秒）
     * @param source      来源（netease/qq）
     * @param coverImage  封面路径（本地路径如 img/cover_123.jpg）
     * @param releaseYear 发行年份（0 表示未知）
     * @param genre       曲风（格式：二次元；游戏）
     * @param language    语言（中文/英语/日语等）
     * @return 歌曲 ID（新插入或已存在的 ID），失败返回 -1
     */
    public int addOrUpdateFromExternal(String title, String artist, String album,
            int duration, String source,
            String coverImage, int releaseYear,
            String genre, String language) {
        // 1. 先查找是否已存在
        Song existing = findByTitleArtistAlbum(title, artist, album);

        if (existing != null) {
            // 2. 歌曲已存在，更新缺失字段
            return updateExistingSong(existing, source, coverImage, album, releaseYear, genre, language);
        } else {
            // 3. 歌曲不存在，插入新记录
            return insertNewExternalSong(title, artist, album, duration, source, coverImage, releaseYear, genre,
                    language);
        }
    }

    /**
     * 更新已存在歌曲的元数据
     * - 累积来源（如原有 netease，新增 qq，则变为 netease,qq）
     * - 补全空字段（album、cover_image、release_year）
     */
    private int updateExistingSong(Song existing, String newSource,
            String newCoverImage, String newAlbum, int newReleaseYear,
            String newGenre, String newLanguage) {
        Connection conn = null;
        PreparedStatement pstmt = null;

        try {
            conn = DBUtil.getConnection();

            // 构建动态更新语句
            StringBuilder sql = new StringBuilder("UPDATE songs SET ");
            List<Object> params = new ArrayList<>();
            boolean needComma = false;

            // 更新来源（累积）
            String currentFilePath = existing.getFilePath();
            if (newSource != null && !newSource.isEmpty()) {
                String updatedSource;
                if (currentFilePath == null || currentFilePath.isEmpty()) {
                    updatedSource = newSource;
                } else if (currentFilePath.contains(newSource)) {
                    // 已包含此来源，不重复添加
                    updatedSource = currentFilePath;
                } else {
                    // 累积来源
                    updatedSource = currentFilePath + "," + newSource;
                }
                sql.append("file_path = ?");
                params.add(updatedSource);
                needComma = true;
            }

            // 补全封面（如果当前为空或为默认值）
            String currentCover = existing.getCoverImage();
            if (newCoverImage != null && !newCoverImage.isEmpty() &&
                    (currentCover == null || currentCover.isEmpty() ||
                            currentCover.equals("img/cover.jpg"))) {
                if (needComma)
                    sql.append(", ");
                sql.append("cover_image = ?");
                params.add(newCoverImage);
                needComma = true;
            }

            // 补全专辑（如果当前为空）
            String currentAlbum = existing.getAlbum();
            if (newAlbum != null && !newAlbum.isEmpty() &&
                    (currentAlbum == null || currentAlbum.isEmpty())) {
                if (needComma)
                    sql.append(", ");
                sql.append("album = ?");
                params.add(newAlbum);
                needComma = true;
            }

            // 补全发行年份（如果当前为0或空）
            int currentYear = existing.getReleaseYear();
            if (newReleaseYear > 0 && currentYear == 0) {
                if (needComma)
                    sql.append(", ");
                sql.append("release_year = ?");
                params.add(newReleaseYear);
                needComma = true;
            }

            // 补全曲风（如果当前为空）
            String currentGenre = existing.getGenre();
            if (newGenre != null && !newGenre.isEmpty() &&
                    (currentGenre == null || currentGenre.isEmpty())) {
                if (needComma)
                    sql.append(", ");
                sql.append("genre = ?");
                params.add(newGenre);
                needComma = true;
            }

            // 补全语言（如果当前为空）
            String currentLanguage = existing.getLanguage();
            if (newLanguage != null && !newLanguage.isEmpty() &&
                    (currentLanguage == null || currentLanguage.isEmpty())) {
                if (needComma)
                    sql.append(", ");
                sql.append("language = ?");
                params.add(newLanguage);
            }

            // 如果没有需要更新的字段，直接返回
            if (params.isEmpty()) {
                System.out.println("📝 [更新歌曲] ID=" + existing.getId() + " 无需更新");
                return existing.getId();
            }

            sql.append(" WHERE id = ?");
            params.add(existing.getId());

            pstmt = conn.prepareStatement(sql.toString());
            for (int i = 0; i < params.size(); i++) {
                pstmt.setObject(i + 1, params.get(i));
            }

            int result = pstmt.executeUpdate();
            System.out.println("📝 [更新歌曲] ID=" + existing.getId() +
                    " 更新字段数=" + (params.size() - 1) + " 结果=" + (result > 0));

            return existing.getId();

        } catch (SQLException e) {
            System.err.println("❌ [ERROR] 更新歌曲失败: " + e.getMessage());
            e.printStackTrace();
            return existing.getId(); // 即使更新失败，仍返回已存在的 ID
        } finally {
            DBUtil.close(conn, pstmt, null);
        }
    }

    /**
     * 插入新的外部歌曲
     */
    private int insertNewExternalSong(String title, String artist, String album,
            int duration, String source,
            String coverImage, int releaseYear,
            String genre, String language) {
        Connection conn = null;
        PreparedStatement pstmt = null;
        ResultSet rs = null;

        try {
            conn = DBUtil.getConnection();
            String sql = "INSERT INTO songs (title, artist, album, duration, genre, release_year, file_path, cover_image, language) "
                    +
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)";
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