package com.music.servlet;

import com.music.dao.AdminDAO;
import com.music.dao.AppealDAO;
import com.music.dao.UserDAO;
import com.music.dao.SongDAO;
import com.music.javabean.User;
import com.music.javabean.Song;
import com.music.javabean.Favorite;
import com.music.javabean.Appeal;
import com.music.util.EmailUtil;

import jakarta.servlet.ServletException;
import jakarta.servlet.annotation.WebServlet;
import jakarta.servlet.http.HttpServlet;
import java.util.List;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import jakarta.servlet.http.HttpSession;
import java.io.IOException;
import java.util.List;
import java.util.Map;

/**
 * 管理员后台控制器
 */
@WebServlet("/admin")
public class AdminServlet extends HttpServlet {
    private AdminDAO adminDAO;

    @Override
    public void init() throws ServletException {
        adminDAO = new AdminDAO();
    }

    @Override
    protected void doGet(HttpServletRequest request, HttpServletResponse response)
            throws ServletException, IOException {

        // 设置响应编码
        request.setCharacterEncoding("UTF-8");
        response.setContentType("text/html;charset=UTF-8");

        // 检查用户是否登录
        HttpSession session = request.getSession(false);
        if (session == null || session.getAttribute("user") == null) {
            response.sendRedirect("index.jsp?message=请先登录&messageType=error");
            return;
        }

        // 获取当前用户
        User currentUser = (User) session.getAttribute("user");

        // 检查是否为管理员
        if (!adminDAO.isAdmin(currentUser.getUsername())) {
            response.sendRedirect("user.jsp?message=权限不足&messageType=error");
            return;
        }

        // 获取请求参数
        String action = request.getParameter("action");
        if (action == null) {
            action = "dashboard";
        }

        try {
            switch (action) {
                case "dashboard":
                    showDashboard(request, response);
                    break;
                case "users":
                    showUsers(request, response);
                    break;
                case "userDetails":
                    showUserDetails(request, response);
                    break;
                case "freezeUser":
                    freezeUser(request, response);
                    break;
                case "unfreezeUser":
                    unfreezeUser(request, response);
                    break;
                case "deleteUser":
                    deleteUser(request, response);
                    break;
                case "songs":
                    showSongs(request, response);
                    break;
                case "addSong":
                    addSong(request, response);
                    return;
                case "deleteSong":
                    deleteSong(request, response);
                    return;
                case "favorites":
                    showFavorites(request, response);
                    break;
                case "appeals":
                    showAppeals(request, response);
                    break;
                case "getAppealDetail":
                    getAppealDetail(request, response);
                    return;
                case "approveAppeal":
                    approveAppeal(request, response);
                    break;
                case "rejectAppeal":
                    rejectAppeal(request, response);
                    break;
                default:
                    showDashboard(request, response);
                    break;
            }
        } catch (Exception e) {
            System.err.println("管理员后台操作失败: " + e.getMessage());
            e.printStackTrace();
            request.setAttribute("error", "系统错误，请稍后重试");
            request.getRequestDispatcher("/admin/admin.jsp").forward(request, response);
        }
    }

    /**
     * 显示仪表板
     */
    private void showDashboard(HttpServletRequest request, HttpServletResponse response)
            throws ServletException, IOException {

        Map<String, Integer> stats = adminDAO.getDatabaseStats();
        request.setAttribute("stats", stats);
        request.getRequestDispatcher("/admin/dashboard.jsp").forward(request, response);
    }

    /**
     * 显示用户列表
     */
    private void showUsers(HttpServletRequest request, HttpServletResponse response)
            throws ServletException, IOException {

        List<User> users = adminDAO.getAllUsers();
        request.setAttribute("users", users);
        request.getRequestDispatcher("/admin/users.jsp").forward(request, response);
    }

    /**
     * 显示歌曲列表
     */
    private void showSongs(HttpServletRequest request, HttpServletResponse response)
            throws ServletException, IOException {

        List<Song> songs = adminDAO.getAllSongs();
        request.setAttribute("songs", songs);
        request.getRequestDispatcher("/admin/songs.jsp").forward(request, response);
    }

    /**
     * 显示收藏记录
     */
    private void showFavorites(HttpServletRequest request, HttpServletResponse response)
            throws ServletException, IOException {

        List<Favorite> favorites = adminDAO.getAllFavorites();
        request.setAttribute("favorites", favorites);
        request.getRequestDispatcher("/admin/favorites.jsp").forward(request, response);
    }

    /**
     * 显示用户详情
     */
    private void showUserDetails(HttpServletRequest request, HttpServletResponse response)
            throws ServletException, IOException {

        String userIdStr = request.getParameter("userId");
        if (userIdStr == null || userIdStr.trim().isEmpty()) {
            response.sendRedirect("admin?action=users&message=用户ID不能为空&messageType=error");
            return;
        }

        try {
            int userId = Integer.parseInt(userIdStr);
            User user = adminDAO.getUserById(userId);
            if (user == null) {
                response.sendRedirect("admin?action=users&message=用户不存在&messageType=error");
                return;
            }

            request.setAttribute("user", user);
            request.getRequestDispatcher("/admin/userDetails.jsp").forward(request, response);
        } catch (NumberFormatException e) {
            response.sendRedirect("admin?action=users&message=用户ID格式错误&messageType=error");
        }
    }

    /**
     * 冻结用户
     */
    private void freezeUser(HttpServletRequest request, HttpServletResponse response)
            throws ServletException, IOException {
        try {
            String userIdStr = request.getParameter("userId");
            String frozenUntil = request.getParameter("frozenUntil");
            String reason = request.getParameter("reason");

            if (userIdStr == null || frozenUntil == null || reason == null) {
                response.setStatus(HttpServletResponse.SC_BAD_REQUEST);
                return;
            }

            int userId = Integer.parseInt(userIdStr);
            boolean success = adminDAO.freezeUser(userId, frozenUntil, reason);
            if (success) {
                response.setStatus(HttpServletResponse.SC_OK);
            } else {
                response.setStatus(HttpServletResponse.SC_INTERNAL_SERVER_ERROR);
            }
        } catch (Exception e) {
            response.setStatus(HttpServletResponse.SC_INTERNAL_SERVER_ERROR);
        }
    }

    /**
     * 解冻用户
     */
    private void unfreezeUser(HttpServletRequest request, HttpServletResponse response)
            throws ServletException, IOException {
        try {
            String userIdStr = request.getParameter("userId");

            if (userIdStr == null) {
                response.setStatus(HttpServletResponse.SC_BAD_REQUEST);
                return;
            }

            int userId = Integer.parseInt(userIdStr);
            boolean success = adminDAO.unfreezeUser(userId);
            if (success) {
                response.setStatus(HttpServletResponse.SC_OK);
            } else {
                response.setStatus(HttpServletResponse.SC_INTERNAL_SERVER_ERROR);
            }
        } catch (Exception e) {
            response.setStatus(HttpServletResponse.SC_INTERNAL_SERVER_ERROR);
        }
    }

    /**
     * 删除用户
     */
    private void deleteUser(HttpServletRequest request, HttpServletResponse response)
            throws ServletException, IOException {
        try {
            String userIdStr = request.getParameter("userId");

            if (userIdStr == null) {
                response.setStatus(HttpServletResponse.SC_BAD_REQUEST);
                return;
            }

            int userId = Integer.parseInt(userIdStr);
            boolean success = adminDAO.deleteUser(userId);
            if (success) {
                response.setStatus(HttpServletResponse.SC_OK);
            } else {
                response.setStatus(HttpServletResponse.SC_INTERNAL_SERVER_ERROR);
            }
        } catch (Exception e) {
            response.setStatus(HttpServletResponse.SC_INTERNAL_SERVER_ERROR);
        }
    }

    private void showAppeals(HttpServletRequest request, HttpServletResponse response)
            throws ServletException, IOException {
        AppealDAO appealDAO = new AppealDAO();
        List<Appeal> appeals = appealDAO.getAllAppeals();
        request.setAttribute("appeals", appeals);
        request.getRequestDispatcher("/admin/appeals.jsp").forward(request, response);
    }

    private void approveAppeal(HttpServletRequest request, HttpServletResponse response)
            throws ServletException, IOException {
        try {
            String idParam = request.getParameter("id");
            if (idParam == null) {
                response.setStatus(HttpServletResponse.SC_BAD_REQUEST);
                return;
            }

            int appealId = Integer.parseInt(idParam);
            AppealDAO appealDAO = new AppealDAO();
            Appeal appeal = appealDAO.getAppealById(appealId);

            if (appeal != null) {
                String adminReply = request.getParameter("reply");
                if (adminReply == null || adminReply.trim().isEmpty()) {
                    adminReply = "您的申诉已通过审核，账号已恢复正常。";
                }

                if (appealDAO.approveAppeal(appealId, adminReply)) {
                    AdminDAO adminDAO = new AdminDAO();
                    UserDAO userDAO = new UserDAO();

                    if ("frozen".equals(appeal.getAppealType())) {
                        adminDAO.unfreezeUser(appeal.getUserId());
                    } else if ("deleted".equals(appeal.getAppealType())) {
                        User user = userDAO.getUserById(appeal.getUserId());
                        if (user != null) {
                            adminDAO.unfreezeUser(appeal.getUserId());
                        }
                    }

                    response.setStatus(HttpServletResponse.SC_OK);

                    // 异步发送邮件
                    final String finalReply = adminReply;
                    final String username = appeal.getUsername();
                    final String email = appeal.getContactEmail();
                    new Thread(() -> {
                        String emailContent = "<h2>申诉审批通知</h2>" +
                                "<p>尊敬的用户 " + username + "：</p>" +
                                "<p>您的账号申诉已通过审核。</p>" +
                                "<p><strong>管理员回复：</strong>" + finalReply + "</p>" +
                                "<p>您现在可以正常登录系统了。</p>" +
                                "<p><a href='http://localhost:8082/musicweb_war_exploded/index.jsp'>点击这里登录</a></p>";
                        EmailUtil.sendEmail(email, "账号申诉审批通知", emailContent);
                    }).start();
                } else {
                    response.setStatus(HttpServletResponse.SC_INTERNAL_SERVER_ERROR);
                }
            } else {
                response.setStatus(HttpServletResponse.SC_NOT_FOUND);
            }
        } catch (Exception e) {
            response.setStatus(HttpServletResponse.SC_INTERNAL_SERVER_ERROR);
        }
    }

    private void rejectAppeal(HttpServletRequest request, HttpServletResponse response)
            throws ServletException, IOException {
        try {
            String idParam = request.getParameter("id");
            if (idParam == null) {
                response.setStatus(HttpServletResponse.SC_BAD_REQUEST);
                return;
            }

            int appealId = Integer.parseInt(idParam);
            String adminReply = request.getParameter("reply");

            if (adminReply == null || adminReply.trim().isEmpty()) {
                adminReply = "您的申诉未通过审核。";
            }

            AppealDAO appealDAO = new AppealDAO();
            Appeal appeal = appealDAO.getAppealById(appealId);

            if (appeal != null && appealDAO.rejectAppeal(appealId, adminReply)) {
                response.setStatus(HttpServletResponse.SC_OK);

                // 异步发送邮件
                final String finalReply = adminReply;
                final String username = appeal.getUsername();
                final String email = appeal.getContactEmail();
                new Thread(() -> {
                    String emailContent = "<h2>申诉审批通知</h2>" +
                            "<p>尊敬的用户 " + username + "：</p>" +
                            "<p>很抱歉，您的账号申诉未通过审核。</p>" +
                            "<p><strong>管理员回复：</strong>" + finalReply + "</p>";
                    EmailUtil.sendEmail(email, "账号申诉审批通知", emailContent);
                }).start();
            } else {
                response.setStatus(HttpServletResponse.SC_INTERNAL_SERVER_ERROR);
            }
        } catch (Exception e) {
            response.setStatus(HttpServletResponse.SC_INTERNAL_SERVER_ERROR);
        }
    }

    private void addSong(HttpServletRequest request, HttpServletResponse response)
            throws ServletException, IOException {
        try {
            String title = request.getParameter("title");
            String artist = request.getParameter("artist");
            String album = request.getParameter("album");
            String durationStr = request.getParameter("duration");
            String genre = request.getParameter("genre");
            String releaseYearStr = request.getParameter("releaseYear");
            String filePath = request.getParameter("filePath");
            String coverImage = request.getParameter("coverImage");

            if (title == null || title.trim().isEmpty() || artist == null || artist.trim().isEmpty()) {
                response.setStatus(HttpServletResponse.SC_BAD_REQUEST);
                return;
            }

            Song song = new Song();
            song.setTitle(title);
            song.setArtist(artist);
            song.setAlbum(album);
            song.setDuration(durationStr != null && !durationStr.trim().isEmpty() ? Integer.parseInt(durationStr) : 0);
            song.setGenre(genre);
            song.setReleaseYear(releaseYearStr != null && !releaseYearStr.trim().isEmpty() ? Integer.parseInt(releaseYearStr) : 0);
            song.setFilePath(filePath);
            song.setCoverImage(coverImage);

            SongDAO songDAO = new SongDAO();
            if (songDAO.addSong(song)) {
                response.setStatus(HttpServletResponse.SC_OK);
            } else {
                response.setStatus(HttpServletResponse.SC_INTERNAL_SERVER_ERROR);
            }
        } catch (Exception e) {
            System.err.println("添加歌曲失败: " + e.getMessage());
            e.printStackTrace();
            response.setStatus(HttpServletResponse.SC_INTERNAL_SERVER_ERROR);
        }
    }

    private void deleteSong(HttpServletRequest request, HttpServletResponse response)
            throws ServletException, IOException {
        try {
            String songIdStr = request.getParameter("songId");
            if (songIdStr == null || songIdStr.trim().isEmpty()) {
                response.setStatus(HttpServletResponse.SC_BAD_REQUEST);
                return;
            }

            int songId = Integer.parseInt(songIdStr);
            SongDAO songDAO = new SongDAO();
            if (songDAO.deleteSong(songId)) {
                response.setStatus(HttpServletResponse.SC_OK);
            } else {
                response.setStatus(HttpServletResponse.SC_INTERNAL_SERVER_ERROR);
            }
        } catch (Exception e) {
            System.err.println("删除歌曲失败: " + e.getMessage());
            e.printStackTrace();
            response.setStatus(HttpServletResponse.SC_INTERNAL_SERVER_ERROR);
        }
    }

    /**
     * 获取申诉详情
     */
    private void getAppealDetail(HttpServletRequest request, HttpServletResponse response)
            throws ServletException, IOException {
        try {
            String idParam = request.getParameter("id");
            if (idParam == null) {
                response.setStatus(HttpServletResponse.SC_BAD_REQUEST);
                return;
            }

            int appealId = Integer.parseInt(idParam);
            AppealDAO appealDAO = new AppealDAO();
            Appeal appeal = appealDAO.getAppealById(appealId);

            if (appeal != null) {
                // 返回JSON格式数据
                response.setContentType("application/json");
                response.setCharacterEncoding("UTF-8");
                String json = String.format(
                    "{\"reason\": \"%s\", \"adminReply\": \"%s\"}",
                    appeal.getReason() != null ? appeal.getReason().replace("\"", "\\\"").replace("\n", "\\n").replace("\r", "") : "",
                    appeal.getAdminReply() != null ? appeal.getAdminReply().replace("\"", "\\\"").replace("\n", "\\n").replace("\r", "") : ""
                );
                response.getWriter().write(json);
            } else {
                response.setStatus(HttpServletResponse.SC_NOT_FOUND);
            }
        } catch (NumberFormatException e) {
            response.setStatus(HttpServletResponse.SC_BAD_REQUEST);
        } catch (Exception e) {
            response.setStatus(HttpServletResponse.SC_INTERNAL_SERVER_ERROR);
        }
    }

    @Override
    protected void doPost(HttpServletRequest request, HttpServletResponse response)
            throws ServletException, IOException {

        doGet(request, response);
    }
}