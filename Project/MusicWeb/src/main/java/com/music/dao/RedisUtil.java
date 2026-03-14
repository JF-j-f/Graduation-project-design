package com.music.dao;

import redis.clients.jedis.Jedis;
import redis.clients.jedis.JedisPool;
import redis.clients.jedis.JedisPoolConfig;
import com.google.gson.Gson;
import com.google.gson.reflect.TypeToken;
import java.lang.reflect.Type;
import java.util.List;

/**
 * Redis 工具类
 * 提供连接池管理和常用缓存操作
 * 
 * 功能：
 * 1. 连接池管理（自动重连）
 * 2. 字符串缓存（带 TTL）
 * 3. JSON 序列化存储对象/列表
 * 4. 优雅降级（Redis 不可用时返回 null，不影响主流程）
 */
public class RedisUtil {

    // Redis 配置
    private static final String REDIS_HOST = "localhost";
    private static final int REDIS_PORT = 6379;
    private static final int REDIS_TIMEOUT = 3000; // 连接超时 3 秒

    // 默认过期时间（秒）
    public static final int TTL_SHORT = 60 * 5; // 5 分钟
    public static final int TTL_MEDIUM = 60 * 30; // 30 分钟
    public static final int TTL_LONG = 60 * 60; // 1 小时
    public static final int TTL_DAY = 60 * 60 * 24; // 24 小时

    // 连接池（单例）
    private static JedisPool jedisPool = null;
    private static final Gson gson = new Gson();

    // Redis 是否可用的标志
    private static boolean redisAvailable = true;
    private static long lastCheckTime = 0;
    private static final long CHECK_INTERVAL = 60000; // 1 分钟后重试

    /**
     * 初始化连接池
     */
    static {
        try {
            JedisPoolConfig config = new JedisPoolConfig();
            config.setMaxTotal(50); // 最大连接数
            config.setMaxIdle(10); // 最大空闲连接
            config.setMinIdle(2); // 最小空闲连接
            config.setTestOnBorrow(true); // 获取连接时测试可用性
            config.setTestOnReturn(true); // 归还连接时测试可用性

            jedisPool = new JedisPool(config, REDIS_HOST, REDIS_PORT, REDIS_TIMEOUT);
            System.out.println("✅ Redis 连接池初始化成功");
        } catch (Exception e) {
            System.err.println("⚠️ Redis 连接池初始化失败: " + e.getMessage());
            redisAvailable = false;
        }
    }

    /**
     * 获取 Jedis 连接
     * 
     * @return Jedis 实例，如果不可用返回 null
     */
    private static Jedis getJedis() {
        // 如果 Redis 不可用，定期重试
        if (!redisAvailable) {
            long now = System.currentTimeMillis();
            if (now - lastCheckTime < CHECK_INTERVAL) {
                return null;
            }
            lastCheckTime = now;
        }

        try {
            if (jedisPool != null) {
                Jedis jedis = jedisPool.getResource();
                jedis.ping(); // 测试连接
                redisAvailable = true;
                return jedis;
            }
        } catch (Exception e) {
            System.err.println("⚠️ Redis 连接失败: " + e.getMessage());
            redisAvailable = false;
        }
        return null;
    }

    /**
     * 关闭 Jedis 连接（归还连接池）
     */
    private static void closeJedis(Jedis jedis) {
        if (jedis != null) {
            try {
                jedis.close();
            } catch (Exception e) {
                // 忽略关闭异常
            }
        }
    }

    // ============================================
    // 字符串操作
    // ============================================

    /**
     * 设置字符串值（带过期时间）
     * 
     * @param key        键
     * @param value      值
     * @param ttlSeconds 过期时间（秒）
     */
    public static void set(String key, String value, int ttlSeconds) {
        Jedis jedis = null;
        try {
            jedis = getJedis();
            if (jedis != null) {
                jedis.setex(key, ttlSeconds, value);
            }
        } catch (Exception e) {
            System.err.println("Redis SET 失败: " + e.getMessage());
        } finally {
            closeJedis(jedis);
        }
    }

    /**
     * 获取字符串值
     * 
     * @param key 键
     * @return 值，如果不存在或 Redis 不可用返回 null
     */
    public static String get(String key) {
        Jedis jedis = null;
        try {
            jedis = getJedis();
            if (jedis != null) {
                return jedis.get(key);
            }
        } catch (Exception e) {
            System.err.println("Redis GET 失败: " + e.getMessage());
        } finally {
            closeJedis(jedis);
        }
        return null;
    }

    /**
     * 删除键
     * 
     * @param key 键
     */
    public static void delete(String key) {
        Jedis jedis = null;
        try {
            jedis = getJedis();
            if (jedis != null) {
                jedis.del(key);
            }
        } catch (Exception e) {
            System.err.println("Redis DELETE 失败: " + e.getMessage());
        } finally {
            closeJedis(jedis);
        }
    }

    /**
     * 检查键是否存在
     * 
     * @param key 键
     * @return 存在返回 true
     */
    public static boolean exists(String key) {
        Jedis jedis = null;
        try {
            jedis = getJedis();
            if (jedis != null) {
                return jedis.exists(key);
            }
        } catch (Exception e) {
            System.err.println("Redis EXISTS 失败: " + e.getMessage());
        } finally {
            closeJedis(jedis);
        }
        return false;
    }

    // ============================================
    // JSON 对象操作
    // ============================================

    /**
     * 存储对象（JSON 序列化）
     * 
     * @param key        键
     * @param obj        对象
     * @param ttlSeconds 过期时间（秒）
     */
    public static void setObject(String key, Object obj, int ttlSeconds) {
        if (obj == null)
            return;
        String json = gson.toJson(obj);
        set(key, json, ttlSeconds);
    }

    /**
     * 获取对象（JSON 反序列化）
     * 
     * @param key   键
     * @param clazz 对象类型
     * @return 对象，如果不存在返回 null
     */
    public static <T> T getObject(String key, Class<T> clazz) {
        String json = get(key);
        if (json == null || json.isEmpty()) {
            return null;
        }
        try {
            return gson.fromJson(json, clazz);
        } catch (Exception e) {
            System.err.println("Redis JSON 解析失败: " + e.getMessage());
            return null;
        }
    }

    /**
     * 存储列表（JSON 序列化）
     * 
     * @param key        键
     * @param list       列表
     * @param ttlSeconds 过期时间（秒）
     */
    public static <T> void setList(String key, List<T> list, int ttlSeconds) {
        if (list == null)
            return;
        String json = gson.toJson(list);
        set(key, json, ttlSeconds);
    }

    /**
     * 获取列表（JSON 反序列化）
     * 
     * @param key       键
     * @param typeToken 列表类型标记
     * @return 列表，如果不存在返回 null
     */
    public static <T> List<T> getList(String key, TypeToken<List<T>> typeToken) {
        String json = get(key);
        if (json == null || json.isEmpty()) {
            return null;
        }
        try {
            Type type = typeToken.getType();
            return gson.fromJson(json, type);
        } catch (Exception e) {
            System.err.println("Redis JSON 列表解析失败: " + e.getMessage());
            return null;
        }
    }

    // ============================================
    // 缓存键常量
    // ============================================

    /** 热歌榜缓存键 */
    public static final String KEY_HOT_SONGS = "musicweb:hot_songs";

    /** 新歌榜缓存键 */
    public static final String KEY_NEW_SONGS = "musicweb:new_songs";

    /** 用户推荐缓存键前缀 */
    public static final String KEY_USER_RECOMMENDATIONS = "musicweb:user:%d:recommendations";

    /** 播放链接缓存键前缀 */
    public static final String KEY_PLAY_URL = "musicweb:play_url:%s:%s";

    /**
     * 生成用户推荐缓存键
     * 
     * @param userId 用户ID
     * @return 缓存键
     */
    public static String getUserRecommendationsKey(int userId) {
        return String.format(KEY_USER_RECOMMENDATIONS, userId);
    }

    /**
     * 生成播放链接缓存键
     * 
     * @param title  歌曲标题
     * @param artist 歌手
     * @return 缓存键
     */
    public static String getPlayUrlKey(String title, String artist) {
        // 移除特殊字符，避免键名问题
        String cleanTitle = title.replaceAll("[^\\w\\u4e00-\\u9fa5]", "");
        String cleanArtist = artist.replaceAll("[^\\w\\u4e00-\\u9fa5]", "");
        return String.format(KEY_PLAY_URL, cleanTitle, cleanArtist);
    }

    /** 播放历史缓存键前缀 */
    public static final String KEY_PLAY_HISTORY = "musicweb:play_history:user:%d:days:%d:page:%d";

    /** 播放历史总数缓存键前缀 */
    public static final String KEY_PLAY_HISTORY_COUNT = "musicweb:play_history_count:user:%d:days:%d";

    /**
     * 生成播放历史缓存键
     * 
     * @param userId 用户ID
     * @param days   时间范围（天数）
     * @param page   页码
     * @return 缓存键
     */
    public static String getPlayHistoryKey(int userId, int days, int page) {
        return String.format(KEY_PLAY_HISTORY, userId, days, page);
    }

    /**
     * 生成播放历史总数缓存键
     * 
     * @param userId 用户ID
     * @param days   时间范围（天数）
     * @return 缓存键
     */
    public static String getPlayHistoryCountKey(int userId, int days) {
        return String.format(KEY_PLAY_HISTORY_COUNT, userId, days);
    }

    /** 管理员页歌曲分页缓存键前缀 */
    public static final String KEY_ADMIN_SONGS_PAGE = "musicweb:admin:songs:page:%d";

    /** 管理员页歌曲总数缓存键 */
    public static final String KEY_ADMIN_SONGS_COUNT = "musicweb:admin:songs:count";

    /**
     * 生成管理员歌曲分页缓存键
     * 
     * @param page 页码
     * @return 缓存键
     */
    public static String getAdminSongsPageKey(int page) {
        return String.format(KEY_ADMIN_SONGS_PAGE, page);
    }

    /**
     * 清除管理员歌曲分页及总数缓存
     * 在歌曲被删除、添加或修改后调用
     */
    public static void clearAdminSongsCache() {
        Jedis jedis = null;
        try {
            jedis = getJedis();
            if (jedis != null) {
                jedis.del(KEY_ADMIN_SONGS_COUNT);
                // 保守清除前 200 页（生产环境中应避免使用 KEYS 导致阻塞）
                for (int i = 1; i <= 200; i++) {
                    jedis.del(getAdminSongsPageKey(i));
                }
                System.out.println("🗑️ [Redis] 已清除管理员后台歌曲列表缓存");
            }
        } catch (Exception e) {
            System.err.println("⚠️ 清除管理员后台歌曲缓存失败: " + e.getMessage());
        } finally {
            closeJedis(jedis);
        }
    }

    /** 用户屏蔽列表缓存键前缀 */
    public static final String KEY_USER_BLOCKS = "musicweb:user:%d:blocks";

    /**
     * 生成用户屏蔽列表缓存键
     *
     * @param userId 用户ID
     * @return 缓存键
     */
    public static String getUserBlocksKey(int userId) {
        return String.format(KEY_USER_BLOCKS, userId);
    }

    /**
     * 清除用户屏蔽列表缓存
     * 在用户添加/取消屏蔽时调用
     *
     * @param userId 用户ID
     */
    public static void clearUserBlocksCache(int userId) {
        delete(getUserBlocksKey(userId));
        System.out.println("🗑️ [Redis] 已清除用户 " + userId + " 的屏蔽列表缓存");
    }

    /** 用户收藏歌曲缓存键前缀 (v3.3.0) */
    public static final String KEY_USER_FAVORITES = "musicweb:user:%d:favorites";

    /** 用户收藏缓存 TTL：3分钟 */
    public static final int TTL_FAVORITES = 60 * 3;

    /**
     * 生成用户收藏歌曲缓存键
     * 
     * @param userId 用户ID
     * @return 缓存键
     */
    public static String getUserFavoritesKey(int userId) {
        return String.format(KEY_USER_FAVORITES, userId);
    }

    /**
     * 清除用户收藏缓存
     * 在用户收藏/取消收藏歌曲时调用
     * 
     * @param userId 用户ID
     */
    public static void clearUserFavoritesCache(int userId) {
        delete(getUserFavoritesKey(userId));
        System.out.println("🗑️ [Redis] 已清除用户 " + userId + " 的收藏缓存");
    }

    /**
     * 清除用户所有播放历史缓存
     * 在用户播放新歌曲时调用，确保下次查询获取最新数据
     * 
     * @param userId 用户ID
     */
    public static void clearUserPlayHistoryCache(int userId) {
        Jedis jedis = null;
        try {
            jedis = getJedis();
            if (jedis != null) {
                // 删除所有时间范围（7/30/90天）的缓存
                for (int days : new int[] { 7, 30, 90 }) {
                    // 删除前10页的缓存（通常用户不会翻那么多页）
                    for (int page = 1; page <= 10; page++) {
                        jedis.del(getPlayHistoryKey(userId, days, page));
                    }
                    // 删除总数缓存
                    jedis.del(getPlayHistoryCountKey(userId, days));
                }
                System.out.println("🗑️ [Redis] 已清除用户 " + userId + " 的播放历史缓存");
            }
        } catch (Exception e) {
            System.err.println("⚠️ 清除播放历史缓存失败: " + e.getMessage());
        } finally {
            closeJedis(jedis);
        }
    }

    /**
     * 检查 Redis 是否可用
     * 
     * @return true 表示可用
     */
    public static boolean isAvailable() {
        Jedis jedis = getJedis();
        boolean available = jedis != null;
        closeJedis(jedis);
        return available;
    }
}
