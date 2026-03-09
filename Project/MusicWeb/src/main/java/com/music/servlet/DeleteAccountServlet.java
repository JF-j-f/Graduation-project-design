package com.music.servlet;

import com.music.dao.UserDAO;
import com.music.dao.PlaylistDAO;
import com.music.javabean.Playlist;
import jakarta.servlet.ServletException;
import jakarta.servlet.annotation.WebServlet;
import jakarta.servlet.http.HttpServlet;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import jakarta.servlet.http.HttpSession;
import java.io.IOException;

/**
 * 注销账户 Servlet
 */
@WebServlet("/deleteAccount")
public class DeleteAccountServlet extends HttpServlet {

    private UserDAO userDAO = new UserDAO();
    private PlaylistDAO playlistDAO = new PlaylistDAO();

    @Override
    protected void doPost(HttpServletRequest request, HttpServletResponse response)
            throws ServletException, IOException {

        // 设置请求编码
        request.setCharacterEncoding("UTF-8");

        // 获取当前用户会话
        HttpSession session = request.getSession(false);
        if (session == null || session.getAttribute("user") == null) {
            response.sendRedirect("jsp/index.jsp");
            return;
        }

        com.music.javabean.User currentUser = (com.music.javabean.User) session.getAttribute("user");
        int userId = currentUser.getId();
        String username = currentUser.getUsername();

        try {
            // 获取确认密码
            String passwordConfirm = request.getParameter("passwordConfirm");
            if (passwordConfirm == null || passwordConfirm.trim().isEmpty()) {
                response.sendRedirect("jsp/settings.jsp?messageType=error&message=" +
                        java.net.URLEncoder.encode("请输入密码确认操作", "UTF-8"));
                return;
            }

            // 验证用户密码
            if (!userDAO.validatePassword(userId, passwordConfirm)) {
                System.err.println("❌ 注销账户失败 - 密码错误 - 用户ID: " + userId);
                response.sendRedirect("jsp/settings.jsp?messageType=error&message=" +
                        java.net.URLEncoder.encode("密码错误，无法确认您的身份", "UTF-8"));
                return;
            }

            // 开始注销账户流程
            boolean deleteSuccess = false;
            boolean favoriteCleanupSuccess = false;

            // 1. 先删除用户的收藏记录
            try {
                // 获取用户收藏数量用于日志（通过默认歌单统计）
                Playlist defaultPlaylist = playlistDAO.getDefaultPlaylist(userId);
                int favoriteCount = defaultPlaylist != null ? defaultPlaylist.getSongCount() : 0;

                // 数据库的外键约束会自动删除相关的歌单和收藏记录
                favoriteCleanupSuccess = true;

                System.out.println("🗑️ [DEBUG] 用户收藏清理 - 用户ID: " + userId +
                        ", 收藏数量: " + favoriteCount);

            } catch (Exception e) {
                System.err.println("❌ [ERROR] 清理用户收藏失败 - 用户ID: " + userId +
                        ", 错误: " + e.getMessage());
                e.printStackTrace();
            }

            // 2. 删除用户账户
            try {
                deleteSuccess = userDAO.deleteUser(userId);

                if (deleteSuccess) {
                    System.out.println("🗑️ [SUCCESS] 用户账户删除成功 - 用户ID: " + userId +
                            ", 用户名: " + username);
                } else {
                    System.err.println("❌ [ERROR] 用户账户删除失败 - 用户ID: " + userId);
                }

            } catch (Exception e) {
                System.err.println("❌ [ERROR] 删除用户账户时发生异常 - 用户ID: " + userId +
                        ", 错误: " + e.getMessage());
                e.printStackTrace();
            }

            if (deleteSuccess && favoriteCleanupSuccess) {
                // 注销成功，清除会话
                session.invalidate();

                // 记录完整的注销日志
                System.out.println("✅ [SUCCESS] 账户注销完成 - 用户ID: " + userId +
                        ", 用户名: " + username + ", 时间: " + new java.util.Date());

                // 重定向到首页，显示成功消息
                response.sendRedirect("jsp/index.jsp?messageType=success&message=" +
                        java.net.URLEncoder.encode("您的账户已成功注销，感谢您的使用！", "UTF-8"));
            } else {
                // 注销失败
                System.err.println("❌ [ERROR] 账户注销失败 - 用户ID: " + userId +
                        ", 删除结果: " + deleteSuccess +
                        ", 收藏清理: " + favoriteCleanupSuccess);

                String errorMsg = "账户注销失败";
                if (!deleteSuccess) {
                    errorMsg += "，无法删除用户账户";
                } else if (!favoriteCleanupSuccess) {
                    errorMsg += "，无法清理用户数据";
                }
                errorMsg += "，请稍后重试或联系管理员";

                response.sendRedirect("jsp/settings.jsp?messageType=error&message=" +
                        java.net.URLEncoder.encode(errorMsg, "UTF-8"));
            }

        } catch (Exception e) {
            System.err.println("❌ [FATAL] 注销账户时发生严重异常 - 用户ID: " + userId +
                    ", 错误: " + e.getMessage());
            e.printStackTrace();

            response.sendRedirect("jsp/settings.jsp?messageType=error&message=" +
                    java.net.URLEncoder.encode("系统错误，无法完成注销操作，请稍后重试", "UTF-8"));
        }
    }

    @Override
    protected void doGet(HttpServletRequest request, HttpServletResponse response)
            throws ServletException, IOException {
        // GET 请求重定向到设置页面
        response.sendRedirect("jsp/settings.jsp");
    }

    /**
     * 验证注销前的安全检查
     * 
     * @param userId   用户ID
     * @param password 密码
     * @return 安全检查结果
     */
    private boolean performSecurityCheck(int userId, String password) {
        try {
            // 验证密码
            if (!userDAO.validatePassword(userId, password)) {
                return false;
            }

            // 可以添加其他安全检查，如：
            // - 检查账户是否已被锁定
            // - 检查是否有未完成的订单/交易
            // - 检查是否为管理员账户（可能需要特殊处理）

            return true;

        } catch (Exception e) {
            System.err.println("❌ [ERROR] 安全检查失败 - 用户ID: " + userId +
                    ", 错误: " + e.getMessage());
            return false;
        }
    }

    /**
     * 记录注销操作日志
     * 
     * @param userId   用户ID
     * @param username 用户名
     * @param success  是否成功
     * @param reason   原因/错误信息
     */
    private void logDeletionAttempt(int userId, String username, boolean success, String reason) {
        String status = success ? "SUCCESS" : "FAILED";
        String timestamp = new java.text.SimpleDateFormat("yyyy-MM-dd HH:mm:ss")
                .format(new java.util.Date());

        String logMessage = String.format("[%s] [DELETE_ACCOUNT] User: %s (ID: %d) - Status: %s - %s",
                timestamp, username, userId, status, reason);

        if (success) {
            System.out.println(logMessage);
        } else {
            System.err.println(logMessage);
        }
    }
}