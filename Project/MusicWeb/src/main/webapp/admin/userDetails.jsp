<%@ page contentType="text/html;charset=UTF-8" language="java" %>
    <%@ page import="java.util.List" %>
        <%@ page import="com.music.javabean.User" %>
            <%@ page import="com.music.javabean.Playlist" %>
                <% User user=(User) request.getAttribute("user"); if (user==null) {
                    response.sendRedirect(request.getContextPath() + "/admin?action=users" ); return; } List<Playlist>
                    playlists = (List<Playlist>) request.getAttribute("playlists");
                        int playlistCount = (playlists != null) ? playlists.size() : 0;
                        Integer playlistSongCount = (Integer) request.getAttribute("playlistSongCount");
                        int songCount = (playlistSongCount != null) ? playlistSongCount : 0;
                        Integer favCount = (Integer) request.getAttribute("favoriteCount");
                        int favoriteCount = (favCount != null) ? favCount : 0;
                        Integer dur = (Integer) request.getAttribute("playDuration");
                        int playDuration = (dur != null) ? dur : 0;
                        int hours = playDuration / 3600;
                        int minutes = (playDuration % 3600) / 60;
                        String durationStr = (hours > 0) ? (hours + "小时" + minutes + "分钟") : (minutes + "分钟");
                        String status = user.getStatus();
                        if (status == null) status = "active";
                        String statusText = "正常";
                        String statusClass = "badge-success";
                        if ("frozen".equals(status)) { statusText = "已冻结"; statusClass = "badge-warning"; }
                        else if ("deleted".equals(status)) { statusText = "已删除"; statusClass = "badge-danger"; }
                        String message = request.getParameter("message");
                        String messageType = request.getParameter("messageType");
                        %>
                        <!DOCTYPE html>
                        <html lang="zh-CN">

                        <head>
                            <meta charset="UTF-8">
                            <meta name="viewport" content="width=device-width, initial-scale=1.0">
                            <title>用户详情 - MusicWeb Admin</title>
                            <link rel="stylesheet" href="${pageContext.request.contextPath}/css/admin/admin.css">
                            <link rel="stylesheet" href="${pageContext.request.contextPath}/css/admin/userDetails.css">
                        </head>

                        <body class="admin-page">
                            <div class="admin-sidebar">
                                <div class="sidebar-logo">Music<span>Web</span></div>
                                <div class="sidebar-menu">
                                    <a href="${pageContext.request.contextPath}/admin?action=dashboard"
                                        class="sidebar-item"><span class="sidebar-item-icon">&#x1F4CA;</span> 仪表盘</a>
                                    <a href="${pageContext.request.contextPath}/admin?action=users"
                                        class="sidebar-item active"><span class="sidebar-item-icon">&#x1F465;</span>
                                        用户管理</a>
                                    <a href="${pageContext.request.contextPath}/admin?action=songs"
                                        class="sidebar-item"><span class="sidebar-item-icon">&#x1F3B5;</span> 歌曲管理</a>
                                    <a href="${pageContext.request.contextPath}/admin?action=playlists"
                                        class="sidebar-item"><span class="sidebar-item-icon">&#x1F4CB;</span> 歌单管理</a>
                                    <a href="${pageContext.request.contextPath}/admin?action=appeals"
                                        class="sidebar-item"><span class="sidebar-item-icon">&#x1F4DD;</span> 申诉管理</a>
                                </div>
                            </div>
                            <div class="admin-wrapper">
                                <header class="admin-header">
                                    <div class="user-info">
                                        <span class="admin-badge">SYSTEM ADMIN</span>
                                        <span style="font-weight:500;">Admin</span>
                                        <a href="${pageContext.request.contextPath}/admin?action=dashboard"
                                            class="btn btn-sm btn-light">返回仪表盘</a>
                                        <a href="${pageContext.request.contextPath}/logout"
                                            class="btn btn-sm btn-danger">注销登出</a>
                                    </div>
                                </header>
                                <div class="admin-content">
                                    <div style="margin-bottom:10px;">
                                        <a href="${pageContext.request.contextPath}/admin?action=users"
                                            class="btn btn-sm btn-light" style="text-decoration:none;">&#x2190;
                                            返回用户列表</a>
                                    </div>
                                    <div class="detail-header">
                                        <h1>&#x1F464; 用户详情</h1>
                                        <span class="status-badge <%= statusClass %>">
                                            <%= statusText %>
                                        </span>
                                        <span style="color:var(--text-muted);font-size:0.85rem;">UID #<%= user.getId()
                                                %></span>
                                    </div>
                                    <% if (message !=null && !message.isEmpty()) { %>
                                        <div class="alert alert-<%= " success".equals(messageType) ? "success" : "error"
                                            %>"><%= message %>
                                        </div>
                                        <% } %>
                                            <% if ("deleted".equals(status)) { %>
                                                <div class="alert-deleted">&#x26A0;&#xFE0F; 该账号已被标记为删除状态。<% if
                                                        (user.getDeletedAt() !=null) { %>删除时间：<%= user.getDeletedAt() %>
                                                            ，30天后将被系统自动永久清除。<% } %>
                                                </div>
                                                <% } %>
                                                    <div class="info-grid">
                                                        <div class="info-card">
                                                            <h3>&#x1F4CB; 基本信息</h3>
                                                            <div class="info-row">
                                                                <span class="info-label">昵称</span>
                                                                <span class="info-value">
                                                                    <% String nick=user.getNickname(); out.print((nick
                                                                        !=null && !nick.trim().isEmpty()) ? nick : "未设置"
                                                                        ); %>
                                                                </span>
                                                            </div>
                                                            <div class="info-row">
                                                                <span class="info-label">登录账号</span>
                                                                <span class="info-value">
                                                                    <%= user.getUsername() %>
                                                                </span>
                                                            </div>
                                                            <div class="info-row">
                                                                <span class="info-label">邮箱</span>
                                                                <% String email=user.getEmail(); boolean
                                                                    noEmail=(email==null || email.trim().isEmpty());
                                                                    String emailClass=noEmail ? "info-value muted"
                                                                    : "info-value" ; String emailText=noEmail ? "未绑定" :
                                                                    email; %>
                                                                    <span class="<%= emailClass %>">
                                                                        <%= emailText %>
                                                                    </span>
                                                            </div>
                                                            <div class="info-row">
                                                                <span class="info-label">手机号</span>
                                                                <% String phone=user.getPhone(); boolean
                                                                    noPhone=(phone==null || phone.trim().isEmpty());
                                                                    String phoneClass=noPhone ? "info-value muted"
                                                                    : "info-value" ; String phoneText=noPhone ? "未绑定" :
                                                                    phone; %>
                                                                    <span class="<%= phoneClass %>">
                                                                        <%= phoneText %>
                                                                    </span>
                                                            </div>
                                                            <div class="tag-row">
                                                                <span class="info-label">偏好流派</span>
                                                                <div class="tag-container">
                                                                    <% String genres=user.getPreferredGenres(); 
                                                                       if (genres !=null && !genres.trim().isEmpty()) {
                                                                           String[] genreArr=genres.split("[,，]"); 
                                                                           for (String g : genreArr) { 
                                                                               String trimmed=g.trim();
                                                                               if (!trimmed.isEmpty()) { 
                                                                    %>
                                                                        <span class="tag tag-genre"><%= trimmed %></span>
                                                                    <% 
                                                                               }
                                                                           }
                                                                       } else { 
                                                                    %>
                                                                        <span class="info-value muted">未设置</span>
                                                                    <% 
                                                                       }
                                                                    %>
                                                                </div>
                                                            </div>
                                                            <div class="tag-row"><span class="info-label">偏好艺术家</span>
                                                                <div class="tag-container">
                                                                    <% String artists=user.getPreferredArtists(); if
                                                                        (artists !=null && !artists.trim().isEmpty()) {
                                                                        String[] artistArr=artists.split("[,，]"); for
                                                                        (String a : artistArr) { String
                                                                        trimmedA=a.trim(); if (!trimmedA.isEmpty()) { %>
                                                                        <span class="tag tag-artist">
                                                                            <%= trimmedA %>
                                                                        </span>
                                                                        <% } } } else { %><span
                                                                                class="info-value muted">未设置</span>
                                                                            <% } %>
                                                                </div>
                                                            </div>
                                                        </div>
                                                        <div class="info-card">
                                                            <h3>&#x1F4CA; 使用数据</h3>
                                                            <div class="info-row"><span
                                                                    class="info-label">注册时间</span><span
                                                                    class="info-value">
                                                                    <%= user.getCreateTime() !=null ?
                                                                        user.getCreateTime() : "未知" %>
                                                                </span></div>
                                                            <div class="info-row"><span
                                                                    class="info-label">累计听歌时长</span><span
                                                                    class="info-value">
                                                                    <%= durationStr %>
                                                                </span></div>
                                                            <div class="info-row"><span
                                                                    class="info-label">歌单数</span><span
                                                                    class="info-value"><span class="stat-number">
                                                                        <%= playlistCount %>
                                                                    </span> 个</span></div>
                                                            <div class="info-row"><span
                                                                    class="info-label">歌单歌曲总数</span><span
                                                                    class="info-value"><span class="stat-number">
                                                                        <%= songCount %>
                                                                    </span> 首</span></div>
                                                            <div class="info-row"><span
                                                                    class="info-label">收藏歌曲数</span><span
                                                                    class="info-value"><span class="stat-number">
                                                                        <%= favoriteCount %>
                                                                    </span> 首</span></div>
                                                        </div>
                                                    </div>
                                                    <div class="action-card">
                                                        <h3>&#x2699;&#xFE0F; 账号操作</h3>
                                                        <% if ("frozen".equals(status)) { %>
                                                            <div class="frozen-info">&#x1F512; 该账号当前处于冻结状态。<% if
                                                                    (user.getFrozenUntil() !=null) { %>冻结截止：<%=
                                                                        user.getFrozenUntil() %>
                                                                        <% } %>
                                                                            <% if (user.getFrozenReason() !=null &&
                                                                                !user.getFrozenReason().trim().isEmpty())
                                                                                { %><br>封禁原因：<%= user.getFrozenReason()
                                                                                    %>
                                                                                    <% } %>
                                                            </div>
                                                            <% } %>
                                                                <div class="action-buttons">
                                                                    <% if ("active".equals(status)) { %>
                                                                        <button type="button" class="btn btn-freeze" onclick="document.getElementById('freezeModal').style.display='flex'">&#x1F512; 冻结账号</button>
                                                                        <button type="button" class="btn btn-delete-action"
                                                                            onclick="deleteUserAccount(<%= user.getId() %>, '<%= user.getUsername() %>')">&#x1F5D1;&#xFE0F;
                                                                            删除账号</button>
                                                                        <% } else if ("frozen".equals(status)) { %>
                                                                            <a href="${pageContext.request.contextPath}/admin?action=unfreezeUser&userId=<%= user.getId() %>"
                                                                                class="btn btn-unfreeze"
                                                                                onclick="return confirm('确认要解除用户 <%= user.getUsername() %> 的冻结状态吗？');">&#x1F513;
                                                                                解除冻结</a>
                                                                            <% } else if ("deleted".equals(status)) { %>
                                                                                <a href="${pageContext.request.contextPath}/admin?action=unfreezeUser&userId=<%= user.getId() %>"
                                                                                    class="btn btn-restore"
                                                                                    onclick="return confirm('确认要恢复用户 <%= user.getUsername() %> 的账号吗？');">&#x267B;&#xFE0F;
                                                                                    恢复账号</a>
                                                                                <% } %>
                                                                </div>
                                                    </div>
                                </div>
                            </div>

                            <!-- 冻结账号模态框 -->
                            <div id="freezeModal" class="modal" style="display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.5); z-index:1000; align-items:center; justify-content:center;">
                                <div style="background:#fff; padding:25px; border-radius:8px; width:400px; max-width:90%;">
                                    <h2 style="margin-top:0;">🔒 冻结账号</h2>
                                    <form action="${pageContext.request.contextPath}/admin" method="post">
                                        <input type="hidden" name="action" value="freezeUser">
                                        <input type="hidden" name="userId" value="<%= user.getId() %>">
                                        <div style="margin-bottom:15px;">
                                            <label style="display:block; margin-bottom:5px;">冻结截止时间 (必填) *</label>
                                            <input type="datetime-local" name="frozenUntil" required style="width:100%; padding:8px; box-sizing:border-box;">
                                        </div>
                                        <div style="margin-bottom:20px;">
                                            <label style="display:block; margin-bottom:5px;">封禁原因 (必填) *</label>
                                            <input type="text" name="reason" placeholder="如: 涉嫌违规操作..." required style="width:100%; padding:8px; box-sizing:border-box;">
                                        </div>
                                        <div style="text-align:right;">
                                            <button type="button" class="btn btn-sm btn-light" onclick="document.getElementById('freezeModal').style.display='none'">取消</button>
                                            <button type="submit" class="btn btn-freeze" style="margin-left:10px;">确定冻结</button>
                                        </div>
                                    </form>
                                </div>
                            </div>
                            <script>
                                function deleteUserAccount(userId, username) {
                                    if (confirm('确认要删除用户 ' + username + ' 吗？删除后30天内可恢复。')) {
                                        fetch('${pageContext.request.contextPath}/admin?action=deleteUser&userId=' + userId)
                                        .then(function(r) {
                                            if (r.ok) {
                                                alert('账号已移入保护期等待30天后彻底清除！');
                                                window.location.reload();
                                            } else {
                                                alert('系统返回异常');
                                            }
                                        })
                                        .catch(function(e) {
                                            alert('请求失败');
                                        });
                                    }
                                }
                            </script>
                        </body>

                        </html>