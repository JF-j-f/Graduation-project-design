package com.music.servlet;

import com.music.dao.*;
import com.music.javabean.*;
import jakarta.servlet.*;
import jakarta.servlet.annotation.WebServlet;
import jakarta.servlet.http.*;
import java.io.*;

@WebServlet("/userLogin")
public class UserLoginServlet extends HttpServlet {
    private static final long serialVersionUID = 1L;

    protected void doPost(HttpServletRequest request, HttpServletResponse response)
            throws ServletException, IOException {

        // 设置编码
        request.setCharacterEncoding("UTF-8");
        response.setContentType("text/html;charset=UTF-8");

        String username = request.getParameter("username");
        String password = request.getParameter("password");

        // 输入验证
        if (username == null || username.trim().isEmpty() ||
                password == null || password.trim().isEmpty()) {
            PrintWriter out = response.getWriter();
            out.println("<script>alert('用户名和密码不能为空！');window.location.href='index.jsp';</script>");
            return;
        }

        UserDAO userDAO = new UserDAO();
        AdminDAO adminDAO = new AdminDAO();
        PrintWriter out = response.getWriter();

        // 获取用户状态信息
        User userStatus = userDAO.getUserStatusInfo(username, password);

        if (userStatus == null) {
            // 用户不存在或密码错误
            out.println("<script>alert('用户名或密码错误！');window.location.href='index.jsp';</script>");
        } else {
            String status = userStatus.getStatus();

            if ("active".equals(status)) {
                // 账号正常，登录成功
                HttpSession session = request.getSession();
                User user = userDAO.getUserByUsername(username);
                session.setAttribute("user", user);

                // 检查是否为管理员
                boolean isAdmin = adminDAO.isAdmin(username);

                if (isAdmin) {
                    // 管理员登录，跳转到后台
                    out.println("<script>alert('管理员登录成功！');window.location.href='admin';</script>");
                } else {
                    // 普通用户登录，跳转到用户页面
                    out.println("<script>alert('登录成功！');window.location.href='user.jsp';</script>");
                }
            } else if ("frozen".equals(status)) {
                // 账号被冻结，重定向到状态页面
                String frozenReason = userStatus.getFrozenReason();
                String frozenUntil = userStatus.getFrozenUntil();
                response.sendRedirect("accountStatus.jsp?status=frozen&username=" + username +
                        "&reason=" + java.net.URLEncoder.encode(frozenReason != null ? frozenReason : "无", "UTF-8") +
                        "&until=" + java.net.URLEncoder.encode(frozenUntil != null ? frozenUntil : "未知", "UTF-8"));
                return;
            } else if ("deleted".equals(status)) {
                // 账号已被删除，重定向到状态页面
                response.sendRedirect("accountStatus.jsp?status=deleted&username=" + username);
                return;
            } else {
                // 未知状态
                out.println("<script>alert('账号状态异常，请联系管理员！');window.location.href='index.jsp';</script>");
            }
        }
    }

    protected void doGet(HttpServletRequest request, HttpServletResponse response)
            throws ServletException, IOException {
        doPost(request, response);
    }
}