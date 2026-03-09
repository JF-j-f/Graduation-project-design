<%@ page contentType="text/html;charset=UTF-8" language="java" %>
    <%@ page import="java.util.List" %>
        <%@ page import="com.music.javabean.User" %>
            <% List<User> users = (List<User>) request.getAttribute("users");
                    if (users == null) {
                    response.sendRedirect(request.getContextPath() + "/admin?action=dashboard");
                    return;
                    }
                    %>
                    <!DOCTYPE html>
                    <html lang="zh-CN">

                    <head>
                        <meta charset="UTF-8">
                        <meta name="viewport" content="width=device-width, initial-scale=1.0">
                        <title>用户信息管理 - MusicWeb Admin</title>
                        <link rel="stylesheet" href="${pageContext.request.contextPath}/css/admin/admin.css">
                    </head>

                    <body class="admin-page">

                        <div class="admin-sidebar">
                            <div class="sidebar-logo">
                                Music<span>Web</span>
                            </div>
                            <div class="sidebar-menu">
                                <a href="${pageContext.request.contextPath}/admin?action=dashboard"
                                    class="sidebar-item">
                                    <span class="sidebar-item-icon">📊</span> 仪表盘
                                </a>
                                <a href="${pageContext.request.contextPath}/admin?action=users"
                                    class="sidebar-item active">
                                    <span class="sidebar-item-icon">👥</span> 用户信息管理
                                </a>
                                <a href="${pageContext.request.contextPath}/admin?action=songs" class="sidebar-item">
                                    <span class="sidebar-item-icon">🎵</span> 歌曲管理
                                </a>
                                <a href="${pageContext.request.contextPath}/admin?action=playlists"
                                    class="sidebar-item">
                                    <span class="sidebar-item-icon">📋</span> 歌单管理
                                </a>
                                <a href="${pageContext.request.contextPath}/admin?action=appeals" class="sidebar-item">
                                    <span class="sidebar-item-icon">📝</span> 申诉管理
                                </a>
                            </div>
                        </div>

                        <div class="admin-wrapper">
                            <header class="admin-header">
                                <div class="user-info">
                                    <span class="admin-badge">SYSTEM ADMIN</span>
                                    <span style="font-weight: 500;">Admin</span>
                                        <a href="${pageContext.request.contextPath}/admin?action=dashboard"
                                            class="btn btn-sm btn-light">返回仪表盘</a>
                                    <a href="${pageContext.request.contextPath}/logout"
                                        class="btn btn-sm btn-danger">注销登出</a>
                                </div>
                            </header>

                            <div class="admin-content">
                                <h1 class="page-title">
                                    <span style="margin-right:10px; color:var(--primary);">👥</span> 用户信息管理
                                </h1>

                                <div class="card">
                                    <div class="card-header"
                                        style="display:flex; justify-content:space-between; align-items:center;">
                                        <h3 class="card-title">用户列表</h3>
                                        <div class="search-input">
                                            <span style="color:var(--text-muted); margin-left:10px;">🔍</span>
                                            <input type="text" id="userSearch" placeholder="输入用户名、邮箱或标识码..."
                                                style="border:none; outline:none; background:transparent; padding:8px; width:250px;">
                                        </div>
                                    </div>

                                    <div class="card-body" style="padding: 0;">
                                        <div class="table-container">
                                            <table class="table" id="usersTable">
                                                <thead>
                                                    <tr>
                                                        <th style="padding-left: 1rem;">UID 标识</th>
                                                        <th>账号 / 昵称</th>
                                                        <th>联系方式</th>
                                                        <th>创建时间</th>
                                                        <th style="text-align: right; padding-right: 1rem;">操作</th>
                                                    </tr>
                                                </thead>
                                                <tbody>
                                                    <% if (users.isEmpty()) { %>
                                                        <tr>
                                                            <td colspan="5"
                                                                style="text-align:center; padding: 40px; color: var(--text-muted);">
                                                                暂无用户数据
                                                            </td>
                                                        </tr>
                                                        <% } else { for (User user : users) { %>
                                                            <tr class="user-row">
                                                                <td style="padding-left: 1rem;">
                                                                    <span class="badge badge-light-dark">#<%=
                                                                            user.getId() %></span>
                                                                </td>
                                                                <td>
                                                                    <div
                                                                        style="font-weight: 500; font-size: 1.05rem; color: var(--text-main); margin-bottom: 4px;">
                                                                        <%= user.getUsername() %>
                                                                    </div>
                                                                    <div
                                                                        style="font-size: 0.85rem; color: var(--text-muted);">
                                                                        <%= (user.getNickname() !=null &&
                                                                            !user.getNickname().trim().isEmpty()) ?
                                                                            user.getNickname() : "未设置" %>
                                                                    </div>
                                                                </td>
                                                                <td>
                                                                    <% if (user.getEmail() !=null &&
                                                                        !user.getEmail().trim().isEmpty()) { %>
                                                                        <div
                                                                            style="color:var(--text-main); margin-bottom:4px; font-size:0.95rem;">
                                                                            ✉️ <%= user.getEmail() %>
                                                                        </div>
                                                                        <% } else { %>
                                                                            <div
                                                                                style="color:var(--text-muted); font-size:0.85rem; margin-bottom:4px;">
                                                                                🚫 未绑定邮箱
                                                                            </div>
                                                                            <% } %>

                                                                                <% if (user.getPhone() !=null &&
                                                                                    !user.getPhone().trim().isEmpty()) {
                                                                                    %>
                                                                                    <div
                                                                                        style="font-size: 0.95rem; color: var(--text-main);">
                                                                                        📱 <%= user.getPhone() %>
                                                                                    </div>
                                                                                    <% } else { %>
                                                                                        <div
                                                                                            style="color:var(--text-muted); font-size: 0.85rem;">
                                                                                            🚫 未绑定手机
                                                                                        </div>
                                                                                        <% } %>
                                                                </td>
                                                                <td>
                                                                    <span class="badge badge-light-primary">
                                                                        <%= user.getCreateTime() !=null ?
                                                                            user.getCreateTime().substring(0, 10) : "未知"
                                                                            %>
                                                                    </span>
                                                                </td>
                                                                <td style="text-align: right; padding-right: 1rem;">
                                                                    <a href="${pageContext.request.contextPath}/admin?action=userDetails&userId=<%= user.getId() %>"
                                                                        class="btn btn-sm btn-light">
                                                                        查看详情
                                                                    </a>
                                                                </td>
                                                            </tr>
                                                            <% } } %>
                                                </tbody>
                                            </table>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                        <script>
                            document.getElementById('userSearch').addEventListener('input', function (e) {
                                const term = e.target.value.toLowerCase();
                                const rows = document.querySelectorAll('.user-row');
                                rows.forEach(row => {
                                    const text = row.textContent.toLowerCase();
                                    row.style.display = text.includes(term) ? '' : 'none';
                                });
                            });
                        </script>
                    </body>

                    </html>