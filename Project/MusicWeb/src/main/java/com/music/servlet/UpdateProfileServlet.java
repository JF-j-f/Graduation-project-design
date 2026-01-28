package com.music.servlet;

import com.music.javabean.User;
import com.music.dao.UserDAO;
import jakarta.servlet.ServletException;
import jakarta.servlet.annotation.WebServlet;
import jakarta.servlet.http.HttpServlet;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import jakarta.servlet.http.HttpSession;
import java.io.IOException;

/**
 * 更新用户个人信息 Servlet
 */
@WebServlet("/updateProfile")
public class UpdateProfileServlet extends HttpServlet {

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

        User currentUser = (User) session.getAttribute("user");

        try {
            // 获取表单参数
            String nickname = request.getParameter("nickname");
            String email = request.getParameter("email");
            String phone = request.getParameter("phone");

            // 验证输入参数
            String errorMessage = validateInput(nickname, email, phone);
            if (errorMessage != null) {
                response.sendRedirect("settings.jsp?messageType=error&message=" +
                                  java.net.URLEncoder.encode(errorMessage, "UTF-8"));
                return;
            }

            // 创建用户对象用于更新
            User updatedUser = new User();
            updatedUser.setId(currentUser.getId());
            updatedUser.setNickname(nickname);
            updatedUser.setEmail(email);
            updatedUser.setPhone(phone);

            // 执行更新操作
            boolean success = userDAO.updateUser(updatedUser);

            if (success) {
                // 更新会话中的用户信息
                updatedUser.setUsername(currentUser.getUsername());
                updatedUser.setPassword(currentUser.getPassword());
                updatedUser.setCreateTime(currentUser.getCreateTime());
                session.setAttribute("user", updatedUser);

                // 记录操作日志
                System.out.println("✅ 用户信息更新成功 - 用户ID: " + currentUser.getId() +
                                 ", 昵称: " + nickname + ", 邮箱: " + email + ", 电话: " + phone);

                response.sendRedirect("settings.jsp?messageType=success&message=" +
                                  java.net.URLEncoder.encode("个人信息更新成功！", "UTF-8"));
            } else {
                System.err.println("❌ 用户信息更新失败 - 用户ID: " + currentUser.getId());
                response.sendRedirect("settings.jsp?messageType=error&message=" +
                                  java.net.URLEncoder.encode("更新失败，请稍后重试", "UTF-8"));
            }

        } catch (Exception e) {
            System.err.println("❌ 更新用户信息时发生异常: " + e.getMessage());
            e.printStackTrace();
            response.sendRedirect("settings.jsp?messageType=error&message=" +
                              java.net.URLEncoder.encode("系统错误，请稍后重试", "UTF-8"));
        }
    }

    /**
     * 验证输入参数
     * @param nickname 昵称
     * @param email 邮箱
     * @param phone 电话
     * @return 错误信息，如果验证通过则返回null
     */
    private String validateInput(String nickname, String email, String phone) {

        // 验证昵称
        if (nickname != null && !nickname.trim().isEmpty()) {
            nickname = nickname.trim();
            if (nickname.length() > 50) {
                return "昵称长度不能超过50个字符";
            }
            if (nickname.contains("<script>") || nickname.contains("javascript:")) {
                return "昵称包含非法字符";
            }
        }

        // 验证邮箱
        if (email != null && !email.trim().isEmpty()) {
            email = email.trim();
            if (!isValidEmail(email)) {
                return "请输入有效的邮箱地址";
            }
            if (email.length() > 100) {
                return "邮箱地址过长";
            }
        }

        // 验证手机号
        if (phone != null && !phone.trim().isEmpty()) {
            phone = phone.trim();
            if (!isValidPhone(phone)) {
                return "请输入有效的手机号码";
            }
        }

        return null; // 验证通过
    }

    /**
     * 验证邮箱格式
     * @param email 邮箱地址
     * @return 是否有效
     */
    private boolean isValidEmail(String email) {
        if (email == null || email.trim().isEmpty()) {
            return true; // 可选字段
        }

        String emailRegex = "^[a-zA-Z0-9_+&*-]+(?:\\.[a-zA-Z0-9_+&*-]+)*@(?:[a-zA-Z0-9-]+\\.)+[a-zA-Z]{2,7}$";
        return email.matches(emailRegex);
    }

    /**
     * 验证手机号格式
     * @param phone 手机号
     * @return 是否有效
     */
    private boolean isValidPhone(String phone) {
        if (phone == null || phone.trim().isEmpty()) {
            return true; // 可选字段
        }

        // 简单的中国手机号验证
        String phoneRegex = "^1[3-9]\\d{9}$";
        return phone.matches(phoneRegex);
    }

    @Override
    protected void doGet(HttpServletRequest request, HttpServletResponse response)
            throws ServletException, IOException {
        // GET 请求重定向到设置页面
        response.sendRedirect("settings.jsp");
    }
}