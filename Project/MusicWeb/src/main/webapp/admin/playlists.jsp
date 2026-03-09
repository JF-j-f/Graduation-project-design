<%@ page contentType="text/html;charset=UTF-8" language="java" %>
    <%@ page import="java.util.List" %>
        <%@ page import="com.music.javabean.Playlist" %>
            <% List<Playlist> playlists = (List<Playlist>) request.getAttribute("playlists");
                    if (playlists == null) {
                    response.sendRedirect(request.getContextPath() + "/admin?action=dashboard");
                    return;
                    }
                    %>
                    <!DOCTYPE html>
                    <html lang="zh-CN">

                    <head>
                        <meta charset="UTF-8">
                        <meta name="viewport" content="width=device-width, initial-scale=1.0">
                        <title>歌单管理 - MusicWeb Admin</title>
                        <link rel="stylesheet" href="${pageContext.request.contextPath}/css/admin/admin.css">
                        <style>
                            .cover-img {
                                width: 40px;
                                height: 40px;
                                border-radius: 6px;
                                object-fit: cover;
                                box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
                            }
                        </style>
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
                                <a href="${pageContext.request.contextPath}/admin?action=users" class="sidebar-item">
                                    <span class="sidebar-item-icon">👥</span> 用户信息管理
                                </a>
                                <a href="${pageContext.request.contextPath}/admin?action=songs" class="sidebar-item">
                                    <span class="sidebar-item-icon">🎵</span> 歌曲管理
                                </a>
                                <a href="${pageContext.request.contextPath}/admin?action=playlists"
                                    class="sidebar-item active">
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
                                    <span style="margin-right:10px; color:var(--primary);">📋</span> 歌单管理
                                </h1>

                                <div class="card">
                                    <div class="card-header"
                                        style="display:flex; justify-content:space-between; align-items:center;">
                                        <h3 class="card-title">全部歌单</h3>
                                        <div class="search-input">
                                            <span style="color:var(--text-muted); margin-left:10px;">🔍</span>
                                            <input type="text" id="playlistSearch" placeholder="搜索歌单名、创建者账号..."
                                                style="border:none; outline:none; background:transparent; padding:8px; width:250px;">
                                        </div>
                                    </div>

                                    <div class="card-body" style="padding: 0;">
                                        <div class="table-container">
                                            <table class="table" id="playlistsTable">
                                                <thead>
                                                    <tr>
                                                        <th style="padding-left: 1rem;">PID / 封面</th>
                                                        <th>歌单名称</th>
                                                        <th>创建者</th>
                                                        <th>歌曲数</th>
                                                        <th>创建时间</th>
                                                        <th style="text-align: right; padding-right: 1rem;">操作</th>
                                                    </tr>
                                                </thead>
                                                <tbody>
                                                    <% if (playlists.isEmpty()) { %>
                                                        <tr>
                                                            <td colspan="6"
                                                                style="text-align:center; padding: 40px; color: var(--text-muted);">
                                                                暂无歌单数据
                                                            </td>
                                                        </tr>
                                                        <% } else { for (Playlist playlist : playlists) { %>
                                                            <tr class="playlist-row">
                                                                <td style="padding-left: 1rem;">
                                                                    <div
                                                                        style="display: flex; align-items: center; gap: 12px;">
                                                                        <span class="badge badge-light-dark">#<%=
                                                                                playlist.getId() %></span>
                                                                        <% if (playlist.getCoverImage() !=null &&
                                                                            !playlist.getCoverImage().trim().isEmpty())
                                                                            { %>
                                                                            <img src="${pageContext.request.contextPath}/<%= playlist.getCoverImage() %>"
                                                                                class="cover-img"
                                                                                onerror="this.src='${pageContext.request.contextPath}/images/default_cover.png'">
                                                                            <% } else { %>
                                                                                <div class="cover-img"
                                                                                    style="background:#e9ecef; display:flex; align-items:center; justify-content:center; color:#adb5bd; font-size: 0.8rem;">
                                                                                    无图</div>
                                                                                <% } %>
                                                                    </div>
                                                                </td>
                                                                <td>
                                                                    <div
                                                                        style="font-weight: 500; font-size: 1.05rem; color: var(--text-main); margin-bottom: 4px;">
                                                                        <%= playlist.getName() %>
                                                                            <% if (playlist.isDefault()) { %>
                                                                                <span class="badge badge-light-danger"
                                                                                    style="margin-left:8px; font-size:0.7em; padding: 2px 6px;">默认</span>
                                                                                <% } %>
                                                                    </div>
                                                                    <div
                                                                        style="font-size: 0.85rem; color: var(--text-muted); max-width: 200px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
                                                                        <%= (playlist.getDescription() !=null &&
                                                                            !playlist.getDescription().isEmpty()) ?
                                                                            playlist.getDescription() : "暂无描述" %>
                                                                    </div>
                                                                </td>
                                                                <td>
                                                                    <div
                                                                        style="color:var(--text-main); font-size:0.95rem;">
                                                                        👤 <%= playlist.getUser() !=null ?
                                                                            playlist.getUser().getUsername() : "未知系统" %>
                                                                    </div>
                                                                </td>
                                                                <td>
                                                                    <span class="badge badge-light-primary">
                                                                        🎵 <%= playlist.getSongCount() %> 首
                                                                    </span>
                                                                </td>
                                                                <td>
                                                                    <div
                                                                        style="color:var(--text-muted); font-size: 0.9rem;">
                                                                        <%= playlist.getCreateTime() !=null ?
                                                                            playlist.getCreateTime().substring(0, 10)
                                                                            : "未知" %>
                                                                    </div>
                                                                </td>
                                                                <td style="text-align: right; padding-right: 1rem;">
                                                                    <button class="btn btn-sm btn-light"
                                                                        onclick="loadPlaylistSongs(<%= playlist.getId() %>, '<%= playlist.getName().replace("'", "\\'") %>')">
                                                                        查看内容
                                                                    </button>
                                                                    <% if (!playlist.isDefault()) { %>
                                                                        <a href="${pageContext.request.contextPath}/admin?action=deletePlaylist&id=<%= playlist.getId() %>"
                                                                            class="btn btn-sm btn-danger"
                                                                            style="margin-left: 5px;"
                                                                            onclick="return confirm('确认要删除这个歌单吗？此操作不可撤销。');">
                                                                            删除
                                                                        </a>
                                                                        <% } %>
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
                            const contextPath = '${pageContext.request.contextPath}';

                            /* 搜索过滤 */
                            document.getElementById('playlistSearch').addEventListener('input', function (e) {
                                const term = e.target.value.toLowerCase();
                                const rows = document.querySelectorAll('.playlist-row');
                                rows.forEach(row => {
                                    const text = row.textContent.toLowerCase();
                                    row.style.display = text.includes(term) ? '' : 'none';
                                });
                            });

                            /* 加载歌单内容到模态框 */
                            function loadPlaylistSongs(playlistId, playlistName) {
                                document.getElementById('modalPlaylistName').textContent = playlistName;
                                document.getElementById('songListBody').innerHTML = '<tr><td colspan="4" style="text-align:center; padding:20px; color:var(--text-muted);">正在加载...</td></tr>';
                                document.getElementById('playlistSongsModal').classList.add('show');

                                fetch(contextPath + '/admin?action=getPlaylistSongs&playlistId=' + playlistId)
                                    .then(resp => {
                                        if (resp.ok) return resp.json();
                                        throw new Error('加载失败');
                                    })
                                    .then(data => {
                                        const tbody = document.getElementById('songListBody');
                                        if (!data || data.length === 0) {
                                            tbody.innerHTML = '<tr><td colspan="4" style="text-align:center; padding:20px; color:var(--text-muted);">该歌单暂无歌曲</td></tr>';
                                            return;
                                        }
                                        let html = '';
                                        data.forEach((song, i) => {
                                            let dur = '';
                                            if (song.duration && song.duration > 0) {
                                                dur = Math.floor(song.duration / 60) + ':' + String(song.duration % 60).padStart(2, '0');
                                            } else { dur = '-'; }
                                            html += '<tr>' +
                                                '<td style="padding-left:1rem;">' + (i + 1) + '</td>' +
                                                '<td style="font-weight:500;">' + (song.title || '未知') + '</td>' +
                                                '<td>' + (song.artist || '未知') + '</td>' +
                                                '<td style="color:var(--text-muted);">' + dur + '</td>' +
                                                '</tr>';
                                        });
                                        tbody.innerHTML = html;
                                    })
                                    .catch(err => {
                                        document.getElementById('songListBody').innerHTML = '<tr><td colspan="4" style="text-align:center; padding:20px; color:#dc3545;">加载失败：' + err.message + '</td></tr>';
                                    });
                            }

                            function closePlaylistModal() {
                                document.getElementById('playlistSongsModal').classList.remove('show');
                            }
                        </script>

                        <!-- 歌单内容模态框 -->
                        <div id="playlistSongsModal"
                            style="display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.6); z-index:1000; align-items:center; justify-content:center;">
                            <div
                                style="background:#ffffff; border:1px solid var(--border-color); border-radius:10px; max-width:650px; width:92%; max-height:80vh; overflow-y:auto; padding:24px; color:var(--text-main);">
                                <div
                                    style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px;">
                                    <h3 style="margin:0; font-size:1.1rem;">🎵 <span id="modalPlaylistName"></span> -
                                        歌曲列表</h3>
                                    <button class="btn btn-sm btn-light" onclick="closePlaylistModal()">关闭</button>
                                </div>
                                <div class="table-container">
                                    <table class="table" style="margin:0;">
                                        <thead>
                                            <tr>
                                                <th style="padding-left:1rem;">#</th>
                                                <th>歌曲名称</th>
                                                <th>艺术家</th>
                                                <th>时长</th>
                                            </tr>
                                        </thead>
                                        <tbody id="songListBody"></tbody>
                                    </table>
                                </div>
                            </div>
                        </div>

                        <style>
                            #playlistSongsModal.show {
                                display: flex !important;
                            }
                        </style>
                    </body>

                    </html>