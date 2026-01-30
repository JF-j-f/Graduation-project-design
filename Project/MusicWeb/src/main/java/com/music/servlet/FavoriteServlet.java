package com.music.servlet;

import com.music.dao.*;
import com.music.javabean.*;
import jakarta.servlet.*;
import jakarta.servlet.annotation.WebServlet;
import jakarta.servlet.http.*;
import java.io.*;

@WebServlet("/favorite")
public class FavoriteServlet extends HttpServlet {
    private static final long serialVersionUID = 1L;

    protected void doPost(HttpServletRequest request, HttpServletResponse response)
            throws ServletException, IOException {

        String action = request.getParameter("action");
        String songIdStr = request.getParameter("songId");

        HttpSession session = request.getSession();
        User user = (User) session.getAttribute("user");

        response.setContentType("text/html;charset=UTF-8");
        PrintWriter out = response.getWriter();

        System.out.println("收藏操作 - Action: " + action + ", SongId: " + songIdStr);

        // 检查用户是否登录
        if (user == null) {
            out.println("<script>alert('请先登录！');window.location.href='jsp/index.jsp';</script>");
            return;
        }

        // 检查歌曲ID参数
        if (songIdStr == null || songIdStr.isEmpty()) {
            out.println("<script>alert('歌曲ID不能为空！');window.location.href='jsp/user.jsp';</script>");
            return;
        }

        try {
            int songId = Integer.parseInt(songIdStr);
            FavoriteDAO favoriteDAO = new FavoriteDAO();
            SongDAO songDAO = new SongDAO();

            // 检查歌曲是否存在
            if (!songDAO.isSongExist(songId)) {
                out.println("<script>alert('歌曲不存在！');window.location.href='jsp/user.jsp';</script>");
                return;
            }

            if ("add".equals(action)) {
                // 检查是否已经收藏
                if (favoriteDAO.isFavorite(user.getId(), songId)) {
                    out.println("<script>alert('已经收藏过这首歌了！');window.location.href='jsp/user.jsp';</script>");
                    return;
                }

                // 添加收藏
                if (favoriteDAO.addFavorite(user.getId(), songId)) {
                    out.println("<script>alert('收藏成功！');window.location.href='jsp/user.jsp';</script>");
                } else {
                    out.println("<script>alert('收藏失败，请重试！');window.location.href='jsp/user.jsp';</script>");
                }

            } else if ("remove".equals(action)) {
                // 取消收藏
                if (favoriteDAO.removeFavorite(user.getId(), songId)) {
                    out.println("<script>alert('取消收藏成功！');window.location.href='jsp/user.jsp';</script>");
                } else {
                    out.println("<script>alert('取消收藏失败，请重试！');window.location.href='jsp/user.jsp';</script>");
                }
            } else {
                out.println("<script>alert('无效的操作！');window.location.href='jsp/user.jsp';</script>");
            }

        } catch (NumberFormatException e) {
            out.println("<script>alert('歌曲ID格式错误！');window.location.href='jsp/user.jsp';</script>");
        } catch (Exception e) {
            e.printStackTrace();
            out.println("<script>alert('操作失败：系统错误');window.location.href='jsp/user.jsp';</script>");
        }
    }

    protected void doGet(HttpServletRequest request, HttpServletResponse response)
            throws ServletException, IOException {
        doPost(request, response);
    }
}