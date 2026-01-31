package com.music.servlet;

import com.music.dao.PlaylistDAO;
import com.music.javabean.Playlist;
import com.music.javabean.User;
import com.google.gson.Gson;
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
import java.util.ArrayList;

/**
 * 获取用户歌单列表API
 * 返回标准 JSON 格式 {code: 0, data: [...]}
 */
@WebServlet("/api/userPlaylists")
public class UserPlaylistsServlet extends HttpServlet {
    private static final long serialVersionUID = 1L;

    @Override
    protected void doGet(HttpServletRequest request, HttpServletResponse response)
            throws ServletException, IOException {

        response.setContentType("application/json;charset=UTF-8");
        PrintWriter out = response.getWriter();
        Gson gson = new Gson();
        Map<String, Object> result = new HashMap<>();

        HttpSession session = request.getSession();
        User user = (User) session.getAttribute("user");

        if (user == null) {
            result.put("code", -1);
            result.put("message", "用户未登录");
            out.println(gson.toJson(result));
            return;
        }

        try {
            PlaylistDAO playlistDAO = new PlaylistDAO();
            List<Playlist> playlists = playlistDAO.getUserPlaylists(user.getId());

            /* 转换为前端需要的格式 */
            List<Map<String, Object>> playlistData = new ArrayList<>();
            for (Playlist p : playlists) {
                Map<String, Object> item = new HashMap<>();
                item.put("id", p.getId());
                item.put("name", p.getName());
                item.put("description", p.getDescription() != null ? p.getDescription() : "");
                item.put("songCount", p.getSongCount());
                item.put("isDefault", p.isDefault());
                item.put("coverImage", p.getDisplayCover());
                playlistData.add(item);
            }

            result.put("code", 0);
            result.put("data", playlistData);
        } catch (Exception e) {
            result.put("code", -1);
            result.put("message", "获取歌单失败: " + e.getMessage());
            e.printStackTrace();
        }

        out.println(gson.toJson(result));
    }
}
