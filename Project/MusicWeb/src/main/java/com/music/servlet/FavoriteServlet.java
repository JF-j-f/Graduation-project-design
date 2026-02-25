package com.music.servlet;

import com.music.dao.*;
import com.music.javabean.*;
import jakarta.servlet.*;
import jakarta.servlet.annotation.WebServlet;
import jakarta.servlet.http.*;
import java.io.*;

/**
 * 收藏操作 Servlet
 * 统一收藏逻辑：❤️ 操作只写入默认歌单
 * 
 * v3.3.0 改造：移除对 FavoriteDAO 的依赖，只使用 PlaylistDAO
 */
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

        System.out.println("🎵 [收藏操作] Action: " + action + ", SongId: " + songIdStr);

        // 检查用户是否登录
        if (user == null) {
            out.println("<script>alert('请先登录！');window.location.href='index.jsp';</script>");
            return;
        }

        // 检查歌曲ID参数
        if (songIdStr == null || songIdStr.isEmpty()) {
            out.println("<script>alert('歌曲ID不能为空！');window.location.href='user.jsp';</script>");
            return;
        }

        try {
            int songId = Integer.parseInt(songIdStr);
            SongDAO songDAO = new SongDAO();
            PlaylistDAO playlistDAO = new PlaylistDAO();

            // 检查歌曲是否存在
            if (!songDAO.isSongExist(songId)) {
                out.println("<script>alert('歌曲不存在！');window.location.href='user.jsp';</script>");
                return;
            }

            // 获取用户的默认歌单
            Playlist defaultPlaylist = playlistDAO.getDefaultPlaylist(user.getId());
            if (defaultPlaylist == null) {
                // 如果没有默认歌单，创建一个
                int playlistId = playlistDAO.createPlaylist("我喜欢的音乐", user.getId(), true);
                if (playlistId > 0) {
                    defaultPlaylist = playlistDAO.getPlaylistById(playlistId);
                    System.out.println("🎵 [自动创建] 为用户 " + user.getId() + " 创建默认歌单，ID: " + playlistId);
                } else {
                    out.println("<script>alert('创建默认歌单失败，请重试！');window.location.href='user.jsp';</script>");
                    return;
                }
            }

            if ("add".equals(action)) {
                // 检查是否已经收藏（通过 PlaylistDAO 判断）
                if (playlistDAO.isFavorite(user.getId(), songId)) {
                    out.println("<script>alert('已经收藏过这首歌了！');window.location.href='user.jsp';</script>");
                    return;
                }

                // 添加到默认歌单
                if (playlistDAO.addSongToPlaylist(defaultPlaylist.getId(), songId)) {
                    // v3.3.0: 清除收藏缓存
                    RedisUtil.clearUserFavoritesCache(user.getId());
                    System.out.println("✅ [收藏成功] 用户: " + user.getId() + ", 歌曲: " + songId +
                            " → 默认歌单: " + defaultPlaylist.getName());
                    out.println("<script>alert('收藏成功！');window.location.href='user.jsp';</script>");
                } else {
                    out.println("<script>alert('收藏失败，请重试！');window.location.href='user.jsp';</script>");
                }

            } else if ("remove".equals(action)) {
                // 从默认歌单移除
                if (playlistDAO.removeSongFromPlaylist(defaultPlaylist.getId(), songId)) {
                    // v3.3.0: 清除收藏缓存
                    RedisUtil.clearUserFavoritesCache(user.getId());
                    System.out.println("✅ [取消收藏] 用户: " + user.getId() + ", 歌曲: " + songId +
                            " ← 默认歌单: " + defaultPlaylist.getName());
                    out.println("<script>alert('取消收藏成功！');window.location.href='user.jsp';</script>");
                } else {
                    out.println("<script>alert('取消收藏失败，请重试！');window.location.href='user.jsp';</script>");
                }
            } else {
                out.println("<script>alert('无效的操作！');window.location.href='user.jsp';</script>");
            }

        } catch (NumberFormatException e) {
            out.println("<script>alert('歌曲ID格式错误！');window.location.href='user.jsp';</script>");
        } catch (Exception e) {
            e.printStackTrace();
            out.println("<script>alert('操作失败：系统错误');window.location.href='user.jsp';</script>");
        }
    }

    protected void doGet(HttpServletRequest request, HttpServletResponse response)
            throws ServletException, IOException {
        doPost(request, response);
    }
}