package com.music.servlet;

import com.music.dao.*;
import com.music.javabean.*;
import jakarta.servlet.*;
import jakarta.servlet.annotation.WebServlet;
import jakarta.servlet.http.*;
import java.io.*;

@WebServlet("/appeal")
public class AppealServlet extends HttpServlet {

    protected void doPost(HttpServletRequest request, HttpServletResponse response)
            throws ServletException, IOException {

        request.setCharacterEncoding("UTF-8");
        response.setContentType("text/html;charset=UTF-8");

        String username = request.getParameter("username");
        String password = request.getParameter("password");
        String appealType = request.getParameter("appealType");
        String reason = request.getParameter("reason");
        String contactEmail = request.getParameter("contactEmail");

        PrintWriter out = response.getWriter();

        if (username == null || password == null || appealType == null ||
            reason == null || contactEmail == null ||
            username.trim().isEmpty() || password.trim().isEmpty() ||
            reason.trim().isEmpty() || contactEmail.trim().isEmpty()) {
            out.println("<script>alert('所有字段都必须填写！');history.back();</script>");
            return;
        }

        UserDAO userDAO = new UserDAO();
        User userStatus = userDAO.getUserStatusInfo(username, password);

        if (userStatus == null) {
            out.println("<script>alert('用户名或密码错误！');history.back();</script>");
            return;
        }

        Appeal appeal = new Appeal();
        appeal.setUsername(username);
        appeal.setUserId(userStatus.getId());
        appeal.setAppealType(appealType);
        appeal.setReason(reason);
        appeal.setContactEmail(contactEmail);

        AppealDAO appealDAO = new AppealDAO();
        if (appealDAO.createAppeal(appeal)) {
            out.println("<script>alert('申诉提交成功！我们会尽快处理您的申诉。');window.location.href='index.jsp';</script>");
        } else {
            out.println("<script>alert('申诉提交失败，请稍后重试！');history.back();</script>");
        }
    }

    protected void doGet(HttpServletRequest request, HttpServletResponse response)
            throws ServletException, IOException {
        doPost(request, response);
    }
}
