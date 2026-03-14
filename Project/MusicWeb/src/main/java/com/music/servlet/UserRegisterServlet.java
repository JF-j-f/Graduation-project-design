package com.music.servlet;

import com.music.dao.*;
import com.music.javabean.*;
import com.music.service.RecommendationService;
import jakarta.servlet.*;
import jakarta.servlet.annotation.WebServlet;
import jakarta.servlet.http.*;
import java.io.*;

@WebServlet("/userRegister")
public class UserRegisterServlet extends HttpServlet {
    private static final long serialVersionUID = 1L;

    protected void doPost(HttpServletRequest request, HttpServletResponse response)
            throws ServletException, IOException {

        // 基本信息
        String username = request.getParameter("username");
        String password = request.getParameter("password");
        String email = request.getParameter("email");
        String nickname = request.getParameter("nickname");
        String phone = request.getParameter("phone");
        String gender = request.getParameter("gender");
        String city = request.getParameter("city");

        // 兴趣标签（冷启动用）
        String selectedGenres = request.getParameter("selectedGenres"); // 逗号分隔的 genre_ids
        String selectedArtists = request.getParameter("selectedArtists"); // 逗号分隔的歌手名

        UserDAO userDAO = new UserDAO();
        response.setContentType("text/html;charset=UTF-8");
        PrintWriter out = response.getWriter();

        // 验证输入
        if (username == null || username.trim().isEmpty() ||
                password == null || password.trim().isEmpty()) {
            out.println("<script>alert('用户名和密码不能为空！');window.location.href='register.jsp';</script>");
            return;
        }

        // 检查用户名是否已存在
        if (userDAO.isUsernameExist(username)) {
            out.println("<script>alert('用户名已存在！');window.location.href='register.jsp';</script>");
            return;
        }

        // 创建用户对象
        User user = new User();
        user.setUsername(username.trim());
        user.setPassword(password.trim());
        user.setEmail(email != null ? email.trim() : "");
        user.setNickname(nickname != null ? nickname.trim() : "");
        user.setPhone(phone != null ? phone.trim() : "");
        user.setGender(gender != null ? gender.trim() : "");
        user.setCity(city != null ? city.trim() : "");

        // 注册用户
        if (userDAO.registerUser(user)) {
            // 获取新注册用户的完整信息
            User registeredUser = userDAO.getUserByUsername(username);

            // 冷启动：保存用户偏好标签到 users 表，供 Python 推荐引擎读取
            if (registeredUser != null) {
                try {
                    /* 持久化偏好到 users 表 (v5.0.1) */
                    if ((selectedGenres != null && !selectedGenres.trim().isEmpty())
                            || (selectedArtists != null && !selectedArtists.trim().isEmpty())) {
                        userDAO.updatePreferences(registeredUser.getId(),
                                selectedGenres != null ? selectedGenres.trim() : "",
                                selectedArtists != null ? selectedArtists.trim() : "");
                    }

                    RecommendationService recService = new RecommendationService();
                    recService.initForNewUser(registeredUser.getId(), selectedGenres, selectedArtists);
                } catch (Exception e) {
                    // 冷启动失败不影响注册流程
                    System.err.println("Cold start recommendation failed: " + e.getMessage());
                }

                // 为新用户创建默认歌单 "我喜欢的音乐"
                try {
                    PlaylistDAO playlistDAO = new PlaylistDAO();
                    int playlistId = playlistDAO.createPlaylist("我喜欢的音乐", registeredUser.getId(), true);
                    if (playlistId > 0) {
                        System.out.println("🎵 [注册] 已为用户 " + registeredUser.getUsername() + " 创建默认歌单，ID=" + playlistId);
                    }
                } catch (Exception e) {
                    // 创建歌单失败不影响注册流程
                    System.err.println("Failed to create default playlist: " + e.getMessage());
                }
            }

            // 注册成功后自动登录
            HttpSession session = request.getSession();
            session.setAttribute("user", registeredUser);

            out.println("<script>alert('注册成功！我们已根据您的喜好为您准备了专属歌单 🎵');window.location.href='user.jsp';</script>");
        } else {
            out.println("<script>alert('注册失败，请重试！');window.location.href='register.jsp';</script>");
        }
    }

    protected void doGet(HttpServletRequest request, HttpServletResponse response)
            throws ServletException, IOException {
        doPost(request, response);
    }
}