package com.music.servlet;

import com.music.dao.PlaylistDAO;
import com.music.javabean.Playlist;
import com.music.javabean.Song;
import com.music.javabean.User;
import com.google.gson.Gson;
import com.google.gson.JsonObject;

import jakarta.servlet.ServletException;
import jakarta.servlet.annotation.WebServlet;
import jakarta.servlet.http.HttpServlet;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import jakarta.servlet.http.HttpSession;

import java.io.IOException;
import java.io.PrintWriter;
import java.util.Comparator;
import java.util.List;
import java.util.stream.Collectors;

/**
 * 歌单歌曲分页查询 Servlet
 * 
 * 支持分页和多字段排序
 * 
 * 请求：GET /api/playlistSongsPage
 * 参数：
 * - playlistId: 歌单ID (必需)
 * - page: 页码 (从1开始，默认1)
 * - pageSize: 每页数量 (默认25)
 * - sortBy: 排序字段 (artist/time/album/year/playCount，默认time)
 * - order: 排序方向 (asc/desc，默认desc)
 * 
 * 响应：
 * {
 * "code": 0,
 * "data": {
 * "items": [...],
 * "totalItems": 123,
 * "totalPages": 5,
 * "currentPage": 1,
 * "playlistName": "我喜欢的音乐"
 * }
 * }
 * 
 * @version v3.2.5
 */
@WebServlet("/api/playlistSongsPage")
public class PlaylistSongsPageServlet extends HttpServlet {

    private static final Gson gson = new Gson();

    @Override
    protected void doGet(HttpServletRequest request, HttpServletResponse response)
            throws ServletException, IOException {

        response.setContentType("application/json;charset=UTF-8");
        PrintWriter out = response.getWriter();
        JsonObject result = new JsonObject();

        try {
            // 1. 检查登录状态
            HttpSession session = request.getSession();
            User user = (User) session.getAttribute("user");

            if (user == null) {
                response.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
                result.addProperty("code", -1);
                result.addProperty("message", "用户未登录");
                out.print(gson.toJson(result));
                return;
            }

            // 2. 解析参数
            int playlistId = parseIntParam(request, "playlistId", -1);
            int page = parseIntParam(request, "page", 1);
            int pageSize = parseIntParam(request, "pageSize", 25);
            String sortBy = request.getParameter("sortBy");
            String order = request.getParameter("order");

            // 验证必需参数
            if (playlistId < 0) {
                result.addProperty("code", -1);
                result.addProperty("message", "缺少歌单ID");
                out.print(gson.toJson(result));
                return;
            }

            // 参数默认值
            if (sortBy == null || sortBy.isEmpty()) {
                sortBy = "time";
            }
            if (order == null || order.isEmpty()) {
                order = "desc";
            }
            if (page < 1)
                page = 1;
            if (pageSize < 1 || pageSize > 100)
                pageSize = 25;

            // 3. 获取歌单信息
            PlaylistDAO playlistDAO = new PlaylistDAO();
            Playlist playlist = playlistDAO.getPlaylistById(playlistId);

            if (playlist == null) {
                result.addProperty("code", -1);
                result.addProperty("message", "歌单不存在");
                out.print(gson.toJson(result));
                return;
            }

            // 检查歌单所有权
            if (playlist.getUserId() != user.getId()) {
                result.addProperty("code", -1);
                result.addProperty("message", "无权访问此歌单");
                out.print(gson.toJson(result));
                return;
            }

            // 4. 获取所有歌曲 (由 DAO 返回)
            List<Song> allSongs = playlistDAO.getPlaylistSongs(playlistId);
            System.out.println("✅ [DEBUG] Step 4: 获取到 " + allSongs.size() + " 首歌曲");

            // 5. 排序
            final String finalSortBy = sortBy;
            final boolean isAsc = "asc".equalsIgnoreCase(order);

            Comparator<Song> comparator = getComparator(finalSortBy);
            if (!isAsc) {
                comparator = comparator.reversed();
            }
            allSongs.sort(comparator);

            // 6. 分页
            int totalItems = allSongs.size();
            int totalPages = (int) Math.ceil((double) totalItems / pageSize);
            int start = (page - 1) * pageSize;
            int end = Math.min(start + pageSize, totalItems);

            List<Song> pagedSongs = (start < totalItems)
                    ? allSongs.subList(start, end)
                    : List.of();
            System.out.println("✅ [DEBUG] Step 6: 分页完成, 当前页 " + pagedSongs.size() + " 首");

            // 7. [修复] 批量填充收藏状态
            if (!pagedSongs.isEmpty()) {
                System.out.println("⏳ [DEBUG] Step 7: 开始批量查询收藏状态...");
                com.music.dao.FavoriteDAO favoriteDAO = new com.music.dao.FavoriteDAO();
                List<Integer> songIds = pagedSongs.stream().map(Song::getId).collect(Collectors.toList());
                List<Integer> favoritedIds = favoriteDAO.getFavoritedSongIds(user.getId(), songIds);
                System.out.println("✅ [DEBUG] Step 7: 批量查询结束, 命中 " + favoritedIds.size() + " 首");

                for (Song song : pagedSongs) {
                    if (favoritedIds.contains(song.getId())) {
                        song.setFavorited(true);
                    }
                }
            }

            // 7. 构建响应
            result.addProperty("code", 0);

            JsonObject data = new JsonObject();
            data.add("items", gson.toJsonTree(pagedSongs));
            data.addProperty("totalItems", totalItems);
            data.addProperty("totalPages", totalPages);
            data.addProperty("currentPage", page);
            data.addProperty("pageSize", pageSize);
            data.addProperty("sortBy", sortBy);
            data.addProperty("order", order);
            data.addProperty("playlistName", playlist.getName());
            data.addProperty("playlistId", playlistId);

            result.add("data", data);

            System.out.println("📋 [歌单分页] userId=" + user.getId() +
                    ", playlistId=" + playlistId +
                    ", page=" + page + "/" + totalPages +
                    ", sortBy=" + sortBy + " " + order +
                    ", items=" + pagedSongs.size() + "/" + totalItems);

        } catch (Exception e) {
            e.printStackTrace();
            result.addProperty("code", -1);
            result.addProperty("message", "服务器错误: " + e.getMessage());
        }

        out.print(gson.toJson(result));
    }

    /**
     * 根据排序字段获取比较器
     */
    private Comparator<Song> getComparator(String sortBy) {
        switch (sortBy.toLowerCase()) {
            case "artist":
                return Comparator.comparing(
                        s -> s.getArtist() != null ? s.getArtist() : "",
                        String.CASE_INSENSITIVE_ORDER);
            case "album":
                return Comparator.comparing(
                        s -> s.getAlbum() != null ? s.getAlbum() : "",
                        String.CASE_INSENSITIVE_ORDER);
            case "year":
                return Comparator.comparingInt(Song::getReleaseYear);
            case "playcount":
                // 播放次数暂不支持（Song 类中未实现），默认按 ID 排序
                return Comparator.comparingInt(Song::getId);
            case "time":
            default:
                // 默认按添加时间排序（歌曲ID作为代理，ID越大越新）
                return Comparator.comparingInt(Song::getId);
        }
    }

    private int parseIntParam(HttpServletRequest request, String name, int defaultValue) {
        String value = request.getParameter(name);
        if (value != null && !value.isEmpty()) {
            try {
                return Integer.parseInt(value);
            } catch (NumberFormatException e) {
                return defaultValue;
            }
        }
        return defaultValue;
    }
}
