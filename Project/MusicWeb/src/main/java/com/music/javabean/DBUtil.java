package com.music.javabean;

import java.sql.*;
import javax.sql.DataSource;
import com.mchange.v2.c3p0.ComboPooledDataSource;
import com.music.util.ServiceConfig;

public class DBUtil {
    private static DataSource dataSource;

    static {
        try {
            // 使用命名的配置，对应 c3p0-config.xml 中的 named-config
            ComboPooledDataSource cpds = new ComboPooledDataSource("musicweb");
            // 数据库用户名/密码由 SecretsLoader 启动时注入到 System.properties，此处编程式覆盖
            // 这样做的原因：c3p0 XML 不支持 ${...} 占位符，只能通过 API 设置
            String dbUser = ServiceConfig.get("DB_USER", "");
            String dbPassword = ServiceConfig.get("DB_PASSWORD", "");
            if (dbUser != null && !dbUser.isEmpty()) {
                cpds.setUser(dbUser);
            }
            if (dbPassword != null && !dbPassword.isEmpty()) {
                cpds.setPassword(dbPassword);
            }
            cpds.setJdbcUrl(ServiceConfig.getJdbcUrl());
            dataSource = cpds;
            System.out.println("✅ C3P0连接池初始化成功");
        } catch (Exception e) {
            System.err.println("❌ C3P0连接池初始化失败: " + e.getMessage());
            e.printStackTrace();
        }
    }

    public static Connection getConnection() throws SQLException {
        Connection conn = dataSource.getConnection();
        System.out.println("✅ 从连接池获取连接成功");
        return conn;
    }

    public static void close(Connection conn, PreparedStatement pstmt, ResultSet rs) {
        try {
            if (rs != null) {
                rs.close();
                System.out.println("✅ ResultSet已关闭");
            }
            if (pstmt != null) {
                pstmt.close();
                System.out.println("✅ PreparedStatement已关闭");
            }
            if (conn != null) {
                conn.close(); // 注意：这里实际上是归还连接到连接池，不是真正关闭
                System.out.println("✅ Connection已归还到连接池");
            }
        } catch (SQLException e) {
            System.err.println("❌ 关闭数据库资源时出错: " + e.getMessage());
            e.printStackTrace();
        }
    }

    public static void close(Connection conn, PreparedStatement pstmt) {
        close(conn, pstmt, null);
    }

    public static void close(Connection conn) {
        close(conn, null, null);
    }

    // 获取连接池状态信息（用于调试）
    public static void printPoolStatus() {
        if (dataSource instanceof ComboPooledDataSource) {
            ComboPooledDataSource cpds = (ComboPooledDataSource) dataSource;
            try {
                System.out.println("=== C3P0连接池状态 ===");
                System.out.println("连接数: " + cpds.getNumConnections());
                System.out.println("忙碌连接: " + cpds.getNumBusyConnections());
                System.out.println("空闲连接: " + cpds.getNumIdleConnections());
                System.out.println("=== ============= ===");
            } catch (SQLException e) {
                System.err.println("获取连接池状态失败: " + e.getMessage());
            }
        }
    }
}
