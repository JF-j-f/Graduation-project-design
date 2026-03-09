<%@ page contentType="text/html;charset=UTF-8" language="java" %>
    <%@ page import="com.music.javabean.Song, java.util.List" %>
        <% if (session.getAttribute("user")==null) { response.sendRedirect("../jsp/index.jsp"); return; } 
                List<Song> songs = (List<Song>) request.getAttribute("songs");
                Integer currentPage = (Integer) request.getAttribute("currentPage");
                if (currentPage == null) currentPage = 1;
                Integer totalPages = (Integer) request.getAttribute("totalPages");
                if (totalPages == null) totalPages = 1;
                Integer totalCount = (Integer) request.getAttribute("totalCount");
                if (totalCount == null) totalCount = 0;
                String message = request.getParameter("message");
                String messageType = request.getParameter("messageType");
                %>
                <!DOCTYPE html>
                <html lang="zh-CN">

                <head>
                    <meta charset="UTF-8">
                    <meta name="viewport" content="width=device-width, initial-scale=1.0">
                    <title>歌曲管理 - MusicWeb Admin</title>
                    <link rel="stylesheet" href="${pageContext.request.contextPath}/css/admin/admin.css">
                    <link rel="stylesheet" href="${pageContext.request.contextPath}/css/admin/songs.css">
                </head>

                <body class="admin-page">
                    <script>var contextPath = '${pageContext.request.contextPath}';</script>
                    <div class="admin-sidebar">
                        <div class="sidebar-logo">Music<span>Web</span></div>
                        <div class="sidebar-menu">
                            <a href="${pageContext.request.contextPath}/admin?action=dashboard"
                                class="sidebar-item"><span class="sidebar-item-icon">&#x1F4CA;</span> 仪表盘</a>
                            <a href="${pageContext.request.contextPath}/admin?action=users" class="sidebar-item"><span
                                    class="sidebar-item-icon">&#x1F465;</span> 用户管理</a>
                            <a href="${pageContext.request.contextPath}/admin?action=songs"
                                class="sidebar-item active"><span class="sidebar-item-icon">&#x1F3B5;</span> 歌曲管理</a>
                            <a href="${pageContext.request.contextPath}/admin?action=playlists"
                                class="sidebar-item"><span class="sidebar-item-icon">&#x1F4CB;</span> 歌单管理</a>
                            <a href="${pageContext.request.contextPath}/admin?action=appeals" class="sidebar-item"><span
                                    class="sidebar-item-icon">&#x1F4DD;</span> 申诉管理</a>
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
                            <h1 class="page-title"><span
                                    style="margin-right:10px;color:var(--primary);">&#x1F3B5;</span> 歌曲管理</h1>
                            <% if (message !=null && !message.isEmpty()) { %>
                                <div style="background:<%= " success".equals(messageType) ? "#d4edda" : "#f8d7da" %>
                                    ;color:<%= "success" .equals(messageType) ? "#155724" : "#721c24" %>;border:1px
                                        solid <%= "success" .equals(messageType) ? "#c3e6cb" : "#f5c6cb" %>;padding:12px
                                            18px;border-radius:6px;margin-bottom:16px;"><%= message %>
                                </div>
                                <% } %>
                                    <div class="song-stats">
                                        <div class="stat-box">
                                            <div class="stat-num">
                                                <%= request.getAttribute("totalCount") != null ? request.getAttribute("totalCount") : 0 %>
                                            </div>
                                            <div class="stat-lbl">歌曲总数</div>
                                        </div>
                                    </div>
                                    <div class="toolbar">
                                        <form action="${pageContext.request.contextPath}/admin" method="GET" style="display: flex; gap: 12px; align-items: center; width: 100%; flex-wrap: wrap; margin: 0;">
                                            <input type="hidden" name="action" value="songs">
                                            <input type="text" id="songSearch" name="search" placeholder="搜索歌曲名、艺术家或专辑..." value="<%= request.getParameter("search") != null ? request.getParameter("search").replace("\"", "&quot;") : "" %>">
                                            <button type="submit" class="btn btn-primary">&#x1F50D; 搜索</button>
                                            <button type="button" class="btn btn-sm btn-light" onclick="window.location.href='${pageContext.request.contextPath}/admin?action=songs'">&#x1F504; 重置</button>
                                            <button type="button" class="btn btn-primary" onclick="showModal('addModal')">&#x2795; 新增歌曲</button>
                                        </form>
                                    </div>
                                    <div class="card">
                                        <div class="card-body" style="padding:0;">
                                            <div class="table-container">
                                                <table class="table" id="songsTable">
                                                    <thead>
                                                        <tr>
                                                            <th style="padding-left:1rem;">ID</th>
                                                            <th>歌曲名称</th>
                                                            <th>艺术家</th>
                                                            <th>专辑</th>
                                                            <th>时长</th>
                                                            <th>类型</th>
                                                            <th>发行年份</th>
                                                            <th style="text-align:right;padding-right:1rem;">操作</th>
                                                        </tr>
                                                    </thead>
                                                    <tbody>
                                                        <% if (songs !=null && !songs.isEmpty()) { for (Song song :
                                                            songs) { String safeTitle=song.getTitle() !=null ?
                                                            song.getTitle().replace("'", "\\'" ).replace("\"", "&quot;"
                                                            ) : "" ; String safeArtist=song.getArtist() !=null ?
                                                            song.getArtist().replace("'", "\\'" ).replace("\"", "&quot;"
                                                            ) : "" ; String safeAlbum=song.getAlbum() !=null ?
                                                            song.getAlbum().replace("'", "\\'" ).replace("\"", "&quot;"
                                                            ) : "" ; String safeGenre=song.getGenre() !=null ?
                                                            song.getGenre().replace("'", "\\'" ).replace("\"", "&quot;"
                                                            ) : "" ; %>
                                                            <tr class="song-row">
                                                                <td style="padding-left:1rem;"><span
                                                                        class="badge badge-light-dark">#<%= song.getId()
                                                                            %></span></td>
                                                                <td style="font-weight:500;">
                                                                    <%= song.getTitle() %>
                                                                </td>
                                                                <td>
                                                                    <%= song.getArtist() %>
                                                                </td>
                                                                <td>
                                                                    <%= song.getAlbum() !=null ? song.getAlbum()
                                                                        : "未知专辑" %>
                                                                </td>
                                                                <td><span class="duration-text">
                                                                        <% if (song.getDuration()> 0) { int m =
                                                                            song.getDuration() / 60; int s =
                                                                            song.getDuration() % 60;
                                                                            out.print(String.format("%d:%02d", m, s)); }
                                                                            else { out.print("未知"); } %>
                                                                    </span></td>
                                                                <td><span class="genre-tag">
                                                                        <%= song.getGenre() !=null ? song.getGenre()
                                                                            : "未分类" %>
                                                                    </span></td>
                                                                <td>
                                                                    <%= song.getReleaseYear()> 0 ? song.getReleaseYear()
                                                                        : "未知" %>
                                                                </td>
                                                                <td style="text-align:right;padding-right:1rem;">
                                                                    <button class="btn btn-sm btn-light"
                                                                        onclick="openEditModal(<%= song.getId() %>, '<%= safeTitle %>', '<%= safeArtist %>', '<%= safeAlbum %>', <%= song.getDuration() %>, '<%= safeGenre %>', <%= song.getReleaseYear() %>)">&#x270F;&#xFE0F;
                                                                        编辑</button>
                                                                    <button class="btn btn-sm btn-danger"
                                                                        style="margin-left:4px;"
                                                                        onclick="deleteSong(<%= song.getId() %>, '<%= safeTitle %>')">&#x1F5D1;&#xFE0F;
                                                                        删除</button>
                                                                </td>
                                                            </tr>
                                                            <% } } else { %>
                                                                <tr>
                                                                    <td colspan="8"
                                                                        style="text-align:center;padding:40px;color:var(--text-muted);">
                                                                        暂无歌曲数据</td>
                                                                </tr>
                                                                <% } %>
                                                    </tbody>
                                                </table>
                                            </div>
                                            <!-- 分页组件 -->
                                            <div class="pagination" style="padding:15px; display:flex; justify-content:center; align-items:center; border-top:1px solid var(--border-color); background:var(--card-bg);">
                                               <span style="margin-right:15px;color:var(--text-muted);font-size:0.9rem;">共 <%= totalCount %> 首，当前第 <%= currentPage %> / <%= totalPages %> 页</span>
                                               <% String searchParam = request.getParameter("search") != null && !request.getParameter("search").trim().isEmpty() ? "&search=" + java.net.URLEncoder.encode(request.getParameter("search").trim(), "UTF-8") : ""; %>
                                               <button class="btn btn-sm btn-light" onclick="goToPage(<%= currentPage - 1 %>)" <%= currentPage <= 1 ? "disabled" : "" %>>上页</button>
                                               <button class="btn btn-sm btn-light" onclick="goToPage(<%= currentPage + 1 %>)" <%= currentPage >= totalPages ? "disabled" : "" %>>下页</button>
                                               <span style="margin-left:15px;">
                                                   跳至 <input type="number" id="pageInput" min="1" max="<%= totalPages %>" style="width:60px; text-align:center; border:1px solid #ccc; border-radius:4px; padding:4px;" value="<%= currentPage %>"> 页
                                                   <button class="btn btn-sm btn-primary" onclick="jumpToPage()" style="margin-left:5px;">GO</button>
                                               </span>
                                            </div>
                                            <script>
                                                function goToPage(page) {
                                                    if (page < 1 || page > <%= totalPages %>) return;
                                                    window.location.href = contextPath + '/admin?action=songs&page=' + page + '<%= searchParam %>';
                                                }
                                                function jumpToPage() {
                                                    var p = document.getElementById('pageInput').value;
                                                    if (p) { goToPage(parseInt(p)); }
                                                }
                                            </script>
                                        </div>
                                    </div>
                        </div>
                    </div>
                    <div id="addModal" class="modal">
                        <div class="modal-content">
                            <h2>&#x2795; 新增歌曲</h2>
                            <form id="addSongForm" onsubmit="submitAddSong(event)">
                                <div class="form-group"><label>歌曲名称 *</label><input type="text" name="title" required>
                                </div>
                                <div class="form-group"><label>艺术家 *</label><input type="text" name="artist" required>
                                </div>
                                <div class="form-group"><label>专辑</label><input type="text" name="album"></div>
                                <div class="form-group"><label>时长（秒）</label><input type="number" name="duration"
                                        min="0"></div>
                                <div class="form-group"><label>类型</label><input type="text" name="genre"></div>
                                <div class="form-group"><label>发行年份</label><input type="number" name="releaseYear"
                                        min="1900" max="2100"></div>
                                <div class="form-group"><label>文件路径</label><input type="text" name="filePath"></div>
                                <div class="form-group"><label>封面图片路径</label><input type="text" name="coverImage"></div>
                                <div class="modal-actions">
                                    <button type="submit" class="btn btn-primary">提交</button>
                                    <button type="button" class="btn btn-sm btn-light"
                                        onclick="hideModal('addModal')">取消</button>
                                </div>
                            </form>
                        </div>
                    </div>
                    <div id="editModal" class="modal">
                        <div class="modal-content">
                            <h2>&#x270F;&#xFE0F; 编辑歌曲</h2>
                            <form id="editSongForm" onsubmit="submitEditSong(event)">
                                <input type="hidden" name="id" id="editSongId">
                                <div class="form-group"><label>歌曲名称 *</label><input type="text" name="title"
                                        id="editTitle" required></div>
                                <div class="form-group"><label>艺术家 *</label><input type="text" name="artist"
                                        id="editArtist" required></div>
                                <div class="form-group"><label>专辑</label><input type="text" name="album" id="editAlbum">
                                </div>
                                <div class="form-group"><label>时长（秒）</label><input type="number" name="duration"
                                        id="editDuration" min="0"></div>
                                <div class="form-group"><label>类型</label><input type="text" name="genre" id="editGenre">
                                </div>
                                <div class="form-group"><label>发行年份</label><input type="number" name="releaseYear"
                                        id="editReleaseYear" min="1900" max="2100"></div>
                                <div class="modal-actions">
                                    <button type="submit" class="btn btn-primary">保存修改</button>
                                    <button type="button" class="btn btn-sm btn-light"
                                        onclick="hideModal('editModal')">取消</button>
                                </div>
                            </form>
                        </div>
                    </div>
                    <script>
                        function showModal(id) { document.getElementById(id).classList.add('show'); }
                        function hideModal(id) { document.getElementById(id).classList.remove('show'); }
                        function submitAddSong(e) {
                            e.preventDefault();
                            var form = document.getElementById('addSongForm');
                            var params = new URLSearchParams(new FormData(form));
                            fetch(contextPath + '/admin?action=addSong', { method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, body: params }).then(function (r) { if (r.ok) window.location.href = contextPath + '/admin?action=songs'; else alert('添加歌曲失败'); }).catch(function () { alert('添加歌曲失败'); });
                        }
                        function openEditModal(id, title, artist, album, duration, genre, releaseYear) {
                            document.getElementById('editSongId').value = id;
                            document.getElementById('editTitle').value = title;
                            document.getElementById('editArtist').value = artist;
                            document.getElementById('editAlbum').value = album;
                            document.getElementById('editDuration').value = duration > 0 ? duration : '';
                            document.getElementById('editGenre').value = genre;
                            document.getElementById('editReleaseYear').value = releaseYear > 0 ? releaseYear : '';
                            showModal('editModal');
                        }
                        function submitEditSong(e) {
                            e.preventDefault();
                            var form = document.getElementById('editSongForm');
                            var params = new URLSearchParams(new FormData(form));
                            fetch(contextPath + '/admin?action=editSong', { method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, body: params }).then(function (r) { if (r.ok) window.location.href = contextPath + '/admin?action=songs'; else alert('修改歌曲失败'); }).catch(function () { alert('修改歌曲失败'); });
                        }
                        function deleteSong(songId, songTitle) {
                            if (confirm('确定要删除歌曲「' + songTitle + '」吗？此操作不可逆！')) {
                                fetch(contextPath + '/admin?action=deleteSong&songId=' + songId).then(function () { window.location.href = contextPath + '/admin?action=songs'; }).catch(function () { alert('删除歌曲失败'); });
                            }
                        }
                    </script>
                </body>

                </html>