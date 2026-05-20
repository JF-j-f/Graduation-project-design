package com.music.util;

/**
 * 服务配置工具类。
 *
 * <p>本地开发和 Docker 部署使用不同的服务地址。这里统一从
 * System properties 与环境变量读取配置，避免业务代码散落硬编码地址。
 */
public final class ServiceConfig {

    private ServiceConfig() {
        // 工具类不允许实例化
    }

    /**
     * 读取配置值，优先级为 System properties、环境变量、默认值。
     *
     * @param key 配置键名
     * @param defaultValue 默认值
     * @return 最终配置值
     */
    public static String get(String key, String defaultValue) {
        String systemValue = System.getProperty(key);
        if (systemValue != null && !systemValue.trim().isEmpty()) {
            return systemValue.trim();
        }

        String envValue = System.getenv(key);
        if (envValue != null && !envValue.trim().isEmpty()) {
            return envValue.trim();
        }

        return defaultValue;
    }

    /**
     * 读取整数配置，解析失败时回退到默认值。
     *
     * @param key 配置键名
     * @param defaultValue 默认值
     * @return 整数配置值
     */
    public static int getInt(String key, int defaultValue) {
        String value = get(key, String.valueOf(defaultValue));
        try {
            return Integer.parseInt(value);
        } catch (NumberFormatException e) {
            System.err.println("⚠️ 配置 " + key + " 不是有效整数，使用默认值: " + defaultValue);
            return defaultValue;
        }
    }

    /**
     * 获取统一音乐 API 地址。
     *
     * @return Node.js 音乐 API 基础地址
     */
    public static String getMusicApiUrl() {
        return get("MUSIC_API_URL", "http://localhost:3000");
    }

    /**
     * 获取 QQ 元数据聚合 API 地址。
     *
     * @return Python QQ API 基础地址
     */
    public static String getQqApiUrl() {
        return get("QQ_API_URL", "http://127.0.0.1:8000");
    }

    /**
     * 获取 Redis 主机名。
     *
     * @return Redis 主机名
     */
    public static String getRedisHost() {
        return get("REDIS_HOST", "localhost");
    }

    /**
     * 获取 Redis 端口。
     *
     * @return Redis 端口
     */
    public static int getRedisPort() {
        return getInt("REDIS_PORT", 6379);
    }

    /**
     * 获取 MySQL JDBC 地址。
     *
     * <p>Docker 部署中 MySQL 主机名为 Compose 服务名，本地开发仍默认 localhost。
     *
     * @return JDBC 连接地址
     */
    public static String getJdbcUrl() {
        String explicitJdbcUrl = get("DB_JDBC_URL", "");
        if (!explicitJdbcUrl.isEmpty()) {
            return explicitJdbcUrl;
        }

        String host = get("DB_HOST", "localhost");
        int port = getInt("DB_PORT", 3306);
        String database = get("DB_NAME", "musicweb");
        return "jdbc:mysql://" + host + ":" + port + "/" + database
                + "?useUnicode=true&characterEncoding=UTF-8"
                + "&serverTimezone=Asia/Shanghai"
                + "&useSSL=false&allowPublicKeyRetrieval=true";
    }
}
