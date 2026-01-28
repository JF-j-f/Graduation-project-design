package com.music.servlet;

import com.music.javabean.DBUtil;
import jakarta.servlet.*;
import jakarta.servlet.annotation.WebServlet;
import jakarta.servlet.http.*;
import java.io.*;
import java.sql.*;

@WebServlet("/testDB")
public class TestDBServlet extends HttpServlet {
    private static final long serialVersionUID = 1L;

    protected void doGet(HttpServletRequest request, HttpServletResponse response)
            throws ServletException, IOException {

        response.setContentType("text/html;charset=UTF-8");
        PrintWriter out = response.getWriter();

        out.println("<!DOCTYPE html>");
        out.println("<html>");
        out.println("<head>");
        out.println("<title>数据库连接测试 - C3P0</title>");
        out.println("<style>");
        out.println("body { font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; }");
        out.println(".success { color: green; padding: 10px; background: #f0fff0; border: 1px solid green; margin: 10px 0; }");
        out.println(".error { color: red; padding: 10px; background: #fff0f0; border: 1px solid red; margin: 10px 0; }");
        out.println(".warning { color: orange; padding: 10px; background: #fff8f0; border: 1px solid orange; margin: 10px 0; }");
        out.println(".info { color: blue; padding: 10px; background: #f0f8ff; border: 1px solid blue; margin: 10px 0; }");
        out.println("pre { background: #f5f5f5; padding: 10px; border-radius: 5px; overflow-x: auto; }");
        out.println("</style>");
        out.println("</head>");
        out.println("<body>");
        out.println("<h1>MySQL数据库连接测试 (C3P0)</h1>");

        Connection conn = null;
        try {
            out.println("<div class='info'>📝 开始测试数据库连接...</div>");

            // 测试连接
            out.println("<h3>1. 获取数据库连接...</h3>");
            conn = DBUtil.getConnection();

            if (conn != null && !conn.isClosed()) {
                out.println("<div class='success'>✅ 数据库连接成功！</div>");

                // 测试数据库元数据
                out.println("<h3>2. 数据库信息...</h3>");
                DatabaseMetaData metaData = conn.getMetaData();
                out.println("<ul>");
                out.println("<li>数据库产品: " + metaData.getDatabaseProductName() + "</li>");
                out.println("<li>数据库版本: " + metaData.getDatabaseProductVersion() + "</li>");
                out.println("<li>驱动名称: " + metaData.getDriverName() + "</li>");
                out.println("<li>驱动版本: " + metaData.getDriverVersion() + "</li>");
                out.println("<li>URL: " + metaData.getURL() + "</li>");
                out.println("<li>用户名: " + metaData.getUserName() + "</li>");
                out.println("</ul>");

                // 测试查询
                out.println("<h3>3. 测试SQL查询...</h3>");
                testQuery(conn, out);

                // 测试表查询
                out.println("<h3>4. 数据库表列表...</h3>");
                testTables(conn, out);

            } else {
                out.println("<div class='error'>❌ 数据库连接失败：连接为null或已关闭</div>");
            }

        } catch (Exception e) {
            out.println("<div class='error'>❌ 数据库连接失败</div>");
            out.println("<h4>错误信息：</h4>");
            out.println("<pre>" + e.getMessage() + "</pre>");
            out.println("<h4>详细堆栈信息：</h4>");
            out.println("<pre>");
            e.printStackTrace(out);
            out.println("</pre>");
        } finally {
            // 关闭连接
            if (conn != null) {
                DBUtil.close(conn);
            }
        }

        out.println("<hr>");
        out.println("<h3>测试结果说明：</h3>");
        out.println("<ul>");
        out.println("<li><strong>数据库连接成功</strong>：C3P0连接池配置正确</li>");
        out.println("<li><strong>SQL查询测试</strong>：验证基本的SQL执行能力</li>");
        out.println("<li><strong>表列表</strong>：显示数据库中的现有表</li>");
        out.println("</ul>");

        out.println("<h3>下一步操作：</h3>");
        out.println("<ul>");
        out.println("<li><a href='index.jsp'>返回首页</a></li>");
        out.println("<li><a href='register.jsp'>用户注册测试</a></li>");
        out.println("<li><a href='#' onclick='location.reload()'>重新测试</a></li>");
        out.println("</ul>");

        out.println("</body>");
        out.println("</html>");
    }

    private void testQuery(Connection conn, PrintWriter out) throws SQLException {
        Statement stmt = null;
        ResultSet rs = null;
        try {
            stmt = conn.createStatement();

            // 使用反引号转义保留关键字，或者使用不同的列名
            String sql = "SELECT 1 as test_result, NOW() as current_time_value, VERSION() as mysql_version";
            out.println("<div class='info'>执行SQL: <code>" + sql + "</code></div>");

            rs = stmt.executeQuery(sql);

            if (rs.next()) {
                out.println("<div class='success'>✅ SQL查询测试成功</div>");
                out.println("<ul>");
                out.println("<li>测试结果: " + rs.getInt("test_result") + "</li>");
                out.println("<li>当前时间: " + rs.getString("current_time_value") + "</li>");
                out.println("<li>MySQL版本: " + rs.getString("mysql_version") + "</li>");
                out.println("</ul>");
            }
        } catch (SQLException e) {
            out.println("<div class='error'>❌ SQL查询测试失败: " + e.getMessage() + "</div>");

            // 备选方案：使用更简单的查询
            out.println("<div class='info'>🔄 尝试使用更简单的查询...</div>");
            try {
                if (rs != null) rs.close();
                if (stmt != null) stmt.close();

                stmt = conn.createStatement();
                String simpleSql = "SELECT 1 as test_result, VERSION() as mysql_version";
                out.println("<div class='info'>执行简化SQL: <code>" + simpleSql + "</code></div>");

                rs = stmt.executeQuery(simpleSql);

                if (rs.next()) {
                    out.println("<div class='success'>✅ 简化查询测试成功</div>");
                    out.println("<ul>");
                    out.println("<li>测试结果: " + rs.getInt("test_result") + "</li>");
                    out.println("<li>MySQL版本: " + rs.getString("mysql_version") + "</li>");
                    out.println("</ul>");
                }
            } catch (SQLException e2) {
                out.println("<div class='error'>❌ 简化查询也失败: " + e2.getMessage() + "</div>");
                throw e2;
            }
        } finally {
            if (rs != null) {
                try { rs.close(); } catch (SQLException e) { e.printStackTrace(); }
            }
            if (stmt != null) {
                try { stmt.close(); } catch (SQLException e) { e.printStackTrace(); }
            }
        }
    }

    private void testTables(Connection conn, PrintWriter out) throws SQLException {
        DatabaseMetaData metaData = conn.getMetaData();
        ResultSet tables = metaData.getTables(null, null, "%", new String[]{"TABLE"});

        out.println("<h4>数据库中的表：</h4>");
        boolean hasTables = false;

        while (tables.next()) {
            if (!hasTables) {
                out.println("<ul>");
                hasTables = true;
            }
            String tableName = tables.getString("TABLE_NAME");
            String tableType = tables.getString("TABLE_TYPE");
            String tableRemarks = tables.getString("REMARKS");
            out.println("<li>" + tableName + " (" + tableType + ")" +
                    (tableRemarks != null ? " - " + tableRemarks : "") + "</li>");
        }

        if (hasTables) {
            out.println("</ul>");
            out.println("<div class='success'>✅ 数据库表结构正常</div>");
        } else {
            out.println("<div class='warning'>⚠️ 没有找到任何表，可能需要创建表结构</div>");
            out.println("<h4>建议执行以下SQL创建表：</h4>");
            out.println("<pre>");
            out.println("CREATE TABLE users (\n" +
                    "    id INT PRIMARY KEY AUTO_INCREMENT,\n" +
                    "    username VARCHAR(50) NOT NULL UNIQUE,\n" +
                    "    password VARCHAR(100) NOT NULL,\n" +
                    "    email VARCHAR(100),\n" +
                    "    nickname VARCHAR(50),\n" +
                    "    phone VARCHAR(20),\n" +
                    "    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP\n" +
                    ");");
            out.println("</pre>");
        }
        tables.close();
    }
}