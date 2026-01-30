package com.music.servlet;

import jakarta.servlet.*;
import jakarta.servlet.annotation.WebServlet;
import jakarta.servlet.http.*;
import java.io.*;

@WebServlet("/logout")
public class LogoutServlet extends HttpServlet {
    private static final long serialVersionUID = 1L;

    protected void doGet(HttpServletRequest request, HttpServletResponse response)
            throws ServletException, IOException {

        HttpSession session = request.getSession();

        // 记录退出日志
        Object userObj = session.getAttribute("user");
        if (userObj != null) {
            System.out.println("用户退出: " + userObj.toString());
        }

        // 销毁session
        session.invalidate();

        // 重定向到首页
        response.sendRedirect("jsp/index.jsp");
    }

    protected void doPost(HttpServletRequest request, HttpServletResponse response)
            throws ServletException, IOException {
        doGet(request, response);
    }
}