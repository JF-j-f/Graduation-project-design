package com.music.servlet;

import com.music.dao.UserDAO;
import jakarta.servlet.ServletException;
import jakarta.servlet.annotation.WebServlet;
import jakarta.servlet.http.HttpServlet;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import jakarta.servlet.http.HttpSession;
import java.io.IOException;

/**
 * 修改密码 Servlet
 */
@WebServlet("/changePassword")
public class ChangePasswordServlet extends HttpServlet {

    private UserDAO userDAO = new UserDAO();

    @Override
    protected void doPost(HttpServletRequest request, HttpServletResponse response)
            throws ServletException, IOException {

        // 设置请求编码
        request.setCharacterEncoding("UTF-8");

        // 获取当前用户会话
        HttpSession session = request.getSession(false);
        if (session == null || session.getAttribute("user") == null) {
            response.sendRedirect("index.jsp");
            return;
        }

        com.music.javabean.User currentUser = (com.music.javabean.User) session.getAttribute("user");
        int userId = currentUser.getId();

        try {
            // 获取表单参数
            String currentPassword = request.getParameter("currentPassword");
            String newPassword = request.getParameter("newPassword");
            String confirmPassword = request.getParameter("confirmPassword");

            // 验证输入参数
            String errorMessage = validatePasswordInput(currentPassword, newPassword, confirmPassword);
            if (errorMessage != null) {
                response.sendRedirect("settings.jsp?messageType=error&message=" +
                                  java.net.URLEncoder.encode(errorMessage, "UTF-8"));
                return;
            }

            // 验证当前密码
            if (!userDAO.validatePassword(userId, currentPassword)) {
                System.err.println("❌ 密码修改失败 - 当前密码错误 - 用户ID: " + userId);
                response.sendRedirect("settings.jsp?messageType=error&message=" +
                                  java.net.URLEncoder.encode("当前密码错误", "UTF-8"));
                return;
            }

            // 执行密码修改
            boolean success = userDAO.changePassword(userId, newPassword);

            if (success) {
                // 更新会话中的用户密码
                currentUser.setPassword(newPassword);
                session.setAttribute("user", currentUser);

                // 记录操作日志
                System.out.println("✅ 密码修改成功 - 用户ID: " + userId);

                response.sendRedirect("settings.jsp?messageType=success&message=" +
                                  java.net.URLEncoder.encode("密码修改成功！", "UTF-8"));
            } else {
                System.err.println("❌ 密码修改失败 - 用户ID: " + userId);
                response.sendRedirect("settings.jsp?messageType=error&message=" +
                                  java.net.URLEncoder.encode("密码修改失败，请稍后重试", "UTF-8"));
            }

        } catch (Exception e) {
            System.err.println("❌ 修改密码时发生异常: " + e.getMessage());
            e.printStackTrace();
            response.sendRedirect("settings.jsp?messageType=error&message=" +
                              java.net.URLEncoder.encode("系统错误，请稍后重试", "UTF-8"));
        }
    }

    /**
     * 验证密码输入
     * @param currentPassword 当前密码
     * @param newPassword 新密码
     * @param confirmPassword 确认密码
     * @return 错误信息，如果验证通过则返回null
     */
    private String validatePasswordInput(String currentPassword, String newPassword, String confirmPassword) {

        // 验证当前密码
        if (currentPassword == null || currentPassword.trim().isEmpty()) {
            return "请输入当前密码";
        }

        // 验证新密码
        if (newPassword == null || newPassword.trim().isEmpty()) {
            return "请输入新密码";
        }

        if (newPassword.length() < 6) {
            return "新密码长度不能少于6位";
        }

        if (newPassword.length() > 20) {
            return "新密码长度不能超过20位";
        }

        // 验证密码强度
        if (!isPasswordStrong(newPassword)) {
            return "新密码强度较弱，请包含字母、数字或特殊字符";
        }

        // 验证新密码不能与当前密码相同
        if (currentPassword.equals(newPassword)) {
            return "新密码不能与当前密码相同";
        }

        // 验证确认密码
        if (confirmPassword == null || confirmPassword.trim().isEmpty()) {
            return "请确认新密码";
        }

        if (!newPassword.equals(confirmPassword)) {
            return "两次输入的密码不一致";
        }

        return null; // 验证通过
    }

    /**
     * 检查密码强度
     * @param password 密码
     * @return 是否符合强度要求
     */
    private boolean isPasswordStrong(String password) {
        // 至少包含两种不同类型的字符
        boolean hasLetter = false;
        boolean hasDigit = false;
        boolean hasSpecial = false;

        for (char c : password.toCharArray()) {
            if (Character.isLetter(c)) {
                hasLetter = true;
            } else if (Character.isDigit(c)) {
                hasDigit = true;
            } else {
                hasSpecial = true;
            }
        }

        // 至少包含两种字符类型
        return (hasLetter && hasDigit) || (hasLetter && hasSpecial) || (hasDigit && hasSpecial);
    }

    @Override
    protected void doGet(HttpServletRequest request, HttpServletResponse response)
            throws ServletException, IOException {
        // GET 请求重定向到设置页面
        response.sendRedirect("settings.jsp");
    }
}