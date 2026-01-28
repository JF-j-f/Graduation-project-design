package com.music.servlet;

import com.music.dao.PlaylistDAO;
import com.music.dao.SongDAO;
import com.music.javabean.Playlist;
import com.music.javabean.Song;
import com.music.javabean.User;
import jakarta.servlet.ServletException;
import jakarta.servlet.annotation.WebServlet;
import jakarta.servlet.http.HttpServlet;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import jakarta.servlet.http.HttpSession;

import java.io.IOException;
import java.io.PrintWriter;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * 歌单管理控制器
 * 处理歌单的增删改查操作
 */
@WebServlet("/playlist")
public class PlaylistServlet extends HttpServlet {
    private static final long serialVersionUID = 1L;

    @Override
    protected void doGet(HttpServletRequest request, HttpServletResponse response)
            throws ServletException, IOException {

        String action = request.getParameter("action");
        HttpSession session = request.getSession();
        User user = (User) session.getAttribute("user");

        // 检查用户是否登录
        if (user == null) {
            response.sendRedirect("index.jsp");
            return;
        }

        PlaylistDAO playlistDAO = new PlaylistDAO();

        if ("view".equals(action)) {
            // 查看歌单详情
            viewPlaylist(request, response, user, playlistDAO);
        } else if ("list".equals(action)) {
            // 获取用户歌单列表（JSON）
            getPlaylistList(response, user, playlistDAO);
        } else {
            response.sendError(HttpServletResponse.SC_BAD_REQUEST, "无效的操作");
        }
    }

    @Override
    protected void doPost(HttpServletRequest request, HttpServletResponse response)
            throws ServletException, IOException {

        String action = request.getParameter("action");
        HttpSession session = request.getSession();
        User user = (User) session.getAttribute("user");

        // 设置JSON响应
        response.setContentType("application/json;charset=UTF-8");
        response.setCharacterEncoding("UTF-8");
        PrintWriter out = response.getWriter();

        // 检查用户是否登录
        if (user == null) {
            out.println("{\"success\": false, \"message\": \"请先登录\"}");
            return;
        }

        PlaylistDAO playlistDAO = new PlaylistDAO();
        Map<String, Object> result = new HashMap<>();

        try {
            if ("create".equals(action)) {
                // 创建歌单
                String name = request.getParameter("name");
                String description = request.getParameter("description");

                if (name == null || name.trim().isEmpty()) {
                    result.put("success", false);
                    result.put("message", "歌单名称不能为空");
                } else {
                    int playlistId = playlistDAO.createPlaylist(name.trim(), user.getId(), false);
                    if (playlistId > 0) {
                        result.put("success", true);
                        result.put("message", "歌单创建成功");
                        result.put("playlistId", playlistId);
                    } else {
                        result.put("success", false);
                        result.put("message", "歌单创建失败");
                    }
                }

            } else if ("addSong".equals(action)) {
                // 添加歌曲到歌单
                int playlistId = Integer.parseInt(request.getParameter("playlistId"));
                int songId = Integer.parseInt(request.getParameter("songId"));

                // 检查歌单是否属于当前用户
                Playlist playlist = playlistDAO.getPlaylistById(playlistId);
                if (playlist == null || playlist.getUserId() != user.getId()) {
                    result.put("success", false);
                    result.put("message", "歌单不存在");
                } else if (playlistDAO.isSongInPlaylist(playlistId, songId)) {
                    result.put("success", false);
                    result.put("message", "歌曲已在歌单中");
                } else {
                    if (playlistDAO.addSongToPlaylist(playlistId, songId)) {
                        result.put("success", true);
                        result.put("message", "添加成功");
                    } else {
                        result.put("success", false);
                        result.put("message", "添加失败");
                    }
                }

            } else if ("removeSong".equals(action)) {
                // 从歌单移除歌曲
                int playlistId = Integer.parseInt(request.getParameter("playlistId"));
                int songId = Integer.parseInt(request.getParameter("songId"));

                // 检查歌单是否属于当前用户
                Playlist playlist = playlistDAO.getPlaylistById(playlistId);
                if (playlist == null || playlist.getUserId() != user.getId()) {
                    result.put("success", false);
                    result.put("message", "歌单不存在");
                } else {
                    if (playlistDAO.removeSongFromPlaylist(playlistId, songId)) {
                        result.put("success", true);
                        result.put("message", "移除成功");
                    } else {
                        result.put("success", false);
                        result.put("message", "移除失败");
                    }
                }

            } else if ("update".equals(action)) {
                // 更新歌单信息
                int playlistId = Integer.parseInt(request.getParameter("playlistId"));
                String name = request.getParameter("name");
                String description = request.getParameter("description");

                // 检查歌单是否属于当前用户
                Playlist playlist = playlistDAO.getPlaylistById(playlistId);
                if (playlist == null || playlist.getUserId() != user.getId()) {
                    result.put("success", false);
                    result.put("message", "歌单不存在");
                } else if (name == null || name.trim().isEmpty()) {
                    result.put("success", false);
                    result.put("message", "歌单名称不能为空");
                } else {
                    if (playlistDAO.updatePlaylistInfo(playlistId, name.trim(), description)) {
                        result.put("success", true);
                        result.put("message", "更新成功");
                    } else {
                        result.put("success", false);
                        result.put("message", "更新失败");
                    }
                }

            } else if ("delete".equals(action)) {
                // 删除歌单
                int playlistId = Integer.parseInt(request.getParameter("playlistId"));

                // 检查歌单是否属于当前用户
                Playlist playlist = playlistDAO.getPlaylistById(playlistId);
                if (playlist == null || playlist.getUserId() != user.getId()) {
                    result.put("success", false);
                    result.put("message", "歌单不存在");
                } else if (playlist.isDefault()) {
                    result.put("success", false);
                    result.put("message", "默认歌单不可删除");
                } else {
                    if (playlistDAO.deletePlaylist(playlistId)) {
                        result.put("success", true);
                        result.put("message", "删除成功");
                    } else {
                        result.put("success", false);
                        result.put("message", "删除失败");
                    }
                }

            } else {
                result.put("success", false);
                result.put("message", "无效的操作");
            }

        } catch (NumberFormatException e) {
            result.put("success", false);
            result.put("message", "参数格式错误");
            e.printStackTrace();
        } catch (Exception e) {
            result.put("success", false);
            result.put("message", "系统错误");
            e.printStackTrace();
        }

        // 输出JSON结果
        out.println("{\"success\": " + result.get("success") + ", \"message\": \"" + result.get("message") + "\"}");
    }

    /**
     * 查看歌单详情
     */
    private void viewPlaylist(HttpServletRequest request, HttpServletResponse response,
                             User user, PlaylistDAO playlistDAO) throws ServletException, IOException {
        try {
            int playlistId = Integer.parseInt(request.getParameter("id"));
            Playlist playlist = playlistDAO.getPlaylistById(playlistId);

            // 检查歌单是否存在
            if (playlist == null) {
                response.sendError(HttpServletResponse.SC_NOT_FOUND, "歌单不存在");
                return;
            }

            // 检查歌单是否属于当前用户
            if (playlist.getUserId() != user.getId()) {
                response.sendError(HttpServletResponse.SC_FORBIDDEN, "无权访问");
                return;
            }

            // 获取歌单中的歌曲
            List<Song> songs = playlistDAO.getPlaylistSongs(playlistId);
            playlist.setSongs(songs);

            // 传递数据到JSP页面
            request.setAttribute("playlist", playlist);
            request.getRequestDispatcher("playlist.jsp").forward(request, response);

        } catch (NumberFormatException e) {
            response.sendError(HttpServletResponse.SC_BAD_REQUEST, "歌单ID格式错误");
        }
    }

    /**
     * 获取用户歌单列表（JSON格式）
     */
    private void getPlaylistList(HttpServletResponse response, User user, PlaylistDAO playlistDAO)
            throws IOException {
        List<Playlist> playlists = playlistDAO.getUserPlaylists(user.getId());

        StringBuilder json = new StringBuilder();
        json.append("[");
        for (int i = 0; i < playlists.size(); i++) {
            Playlist p = playlists.get(i);
            if (i > 0) json.append(",");
            json.append("{");
            json.append("\"id\":").append(p.getId()).append(",");
            json.append("\"name\":\"").append(escapeJson(p.getName())).append("\",");
            json.append("\"description\":\"").append(escapeJson(p.getDescription() != null ? p.getDescription() : "")).append("\",");
            json.append("\"songCount\":").append(p.getSongCount()).append(",");
            json.append("\"isDefault\":").append(p.isDefault()).append(",");
            json.append("\"coverImage\":\"").append(escapeJson(p.getDisplayCover())).append("\"");
            json.append("}");
        }
        json.append("]");

        response.setContentType("application/json;charset=UTF-8");
        PrintWriter out = response.getWriter();
        out.println(json.toString());
    }

    /**
     * 转义JSON特殊字符
     */
    private String escapeJson(String str) {
        if (str == null) return "";
        return str.replace("\\", "\\\\")
                .replace("\"", "\\\"")
                .replace("\n", "\\n")
                .replace("\r", "\\r")
                .replace("\t", "\\t");
    }
}
