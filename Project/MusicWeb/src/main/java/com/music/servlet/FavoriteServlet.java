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

            // === 核心修复：外部歌曲自动入库 ===
            // 当 songId=0 时（搜索结果中的外部歌曲尚未入库），
            // 通过前端传来的元数据自动入库后再操作
            if (songId == 0) {
                String songTitle = request.getParameter("songTitle");
                String songArtist = request.getParameter("songArtist");
                String songAlbum = request.getParameter("songAlbum");
                String songSource = request.getParameter("songSource");
                String songCoverUrl = request.getParameter("songCoverUrl");
                String songDurationStr = request.getParameter("songDuration");

                if (songTitle == null || songTitle.isEmpty() || songArtist == null || songArtist.isEmpty()) {
                    out.println("<script>alert('歌曲信息不完整！');window.location.href='user.jsp';</script>");
                    return;
                }

                int songDuration = 0;
                try {
                    songDuration = Integer.parseInt(songDurationStr);
                } catch (Exception ignored) {
                }

                // 调用已有的 addOrUpdateFromExternal 方法：
                // 内部先按 title+artist 查库，已存在则返回已有ID，不存在则插入新记录
                songId = songDAO.addOrUpdateFromExternal(
                        songTitle, songArtist,
                        songAlbum != null ? songAlbum : "",
                        songDuration,
                        songSource != null ? songSource : "",
                        songCoverUrl != null ? songCoverUrl : "",
                        0, "", "");

                if (songId <= 0) {
                    out.println("<script>alert('歌曲信息同步失败！');window.location.href='user.jsp';</script>");
                    return;
                }
                System.out.println("🎵 [自动入库] 外部歌曲已入库 - 标题: " + songTitle +
                        ", 歌手: " + songArtist + ", 新ID: " + songId);
            }

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