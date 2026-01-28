<%@ page contentType="text/html;charset=UTF-8" language="java" %>
<%@ page import="com.music.javabean.Song, java.util.List" %>
<%
    // 检查用户是否登录
    if (session.getAttribute("user") == null) {
        response.sendRedirect("../index.jsp");
        return;
    }
%>
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>音乐管理 - 管理员后台</title>
    <link rel="stylesheet" href="../css/style.css">
    <style>
        .admin-header {
            background: linear-gradient(135deg, #2c3e50 0%, #34495e 100%);
            color: white;
            padding: 1rem 0;
        }

        .admin-container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 2rem;
        }

        .admin-sidebar {
            width: 250px;
            background: #f8f9fa;
            min-height: calc(100vh - 200px);
            border-radius: 8px;
            padding: 1.5rem;
            position: fixed;
            left: 20px;
            top: 120px;
        }

        .admin-content {
            margin-left: 290px;
            background: white;
            border-radius: 8px;
            padding: 2rem;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }

        .sidebar-item {
            display: block;
            padding: 1rem;
            margin-bottom: 0.5rem;
            border-radius: 6px;
            text-decoration: none;
            color: #333;
            transition: all 0.3s ease;
            border: none;
            background: none;
            width: 100%;
            text-align: left;
            cursor: pointer;
            font-size: 1rem;
        }

        .sidebar-item:hover {
            background: #e9ecef;
            color: #007bff;
        }

        .sidebar-item.active {
            background: #007bff;
            color: white;
        }

        .page-title {
            font-size: 2rem;
            margin-bottom: 2rem;
            color: #2c3e50;
            border-bottom: 3px solid #007bff;
            padding-bottom: 0.5rem;
        }

        .admin-badge {
            background: #dc3545;
            color: white;
            padding: 0.25rem 0.75rem;
            border-radius: 20px;
            font-size: 0.8rem;
            margin-left: 1rem;
        }

        .songs-table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 1rem;
            background: white;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        }

        .songs-table th {
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            color: white;
            padding: 1rem;
            text-align: left;
            font-weight: 600;
        }

        .songs-table td {
            padding: 1rem;
            border-bottom: 1px solid #e9ecef;
        }

        .songs-table tr:hover {
            background: #f8f9fa;
        }

        .songs-table tr:nth-child(even) {
            background: #f8f9fa;
        }

        .songs-table tr:nth-child(even):hover {
            background: #e9ecef;
        }

        .song-id {
            font-weight: bold;
            color: #f5576c;
        }

        .song-actions {
            display: flex;
            gap: 0.5rem;
        }

        .btn-small {
            padding: 0.25rem 0.75rem;
            font-size: 0.875rem;
            border: none;
            border-radius: 4px;
            text-decoration: none;
            cursor: pointer;
            transition: background 0.3s ease;
        }

        .btn-view {
            background: #28a745;
            color: white;
        }

        .btn-view:hover {
            background: #218838;
        }

        .btn-play {
            background: #007bff;
            color: white;
        }

        .btn-play:hover {
            background: #0056b3;
        }

        .search-bar {
            display: flex;
            gap: 1rem;
            margin-bottom: 2rem;
            align-items: center;
        }

        .search-input {
            flex: 1;
            padding: 0.75rem;
            border: 2px solid #e9ecef;
            border-radius: 6px;
            font-size: 1rem;
        }

        .search-input:focus {
            outline: none;
            border-color: #f5576c;
        }

        .song-stats {
            display: flex;
            gap: 2rem;
            margin-bottom: 2rem;
            flex-wrap: wrap;
        }

        .stat-item {
            background: #f8f9fa;
            padding: 1rem 1.5rem;
            border-radius: 6px;
            border-left: 4px solid #f5576c;
            min-width: 150px;
        }

        .stat-number {
            font-size: 1.5rem;
            font-weight: bold;
            color: #f5576c;
        }

        .stat-label {
            color: #6c757d;
            font-size: 0.9rem;
        }

        .genre-tag {
            background: #e9ecef;
            padding: 0.25rem 0.75rem;
            border-radius: 12px;
            font-size: 0.875rem;
            color: #495057;
        }

        .duration {
            color: #6c757d;
            font-size: 0.9rem;
        }

        @media (max-width: 768px) {
            .admin-sidebar {
                position: static;
                width: 100%;
                margin-bottom: 2rem;
            }

            .admin-content {
                margin-left: 0;
            }

            .admin-container {
                padding: 1rem;
            }

            .songs-table {
                font-size: 0.875rem;
            }

            .songs-table th,
            .songs-table td {
                padding: 0.5rem;
            }

            .song-stats {
                flex-direction: column;
                gap: 1rem;
            }

            .search-bar {
                flex-direction: column;
                align-items: stretch;
            }
        }
    </style>
</head>
<body class="admin-page">
    <script>
        const contextPath = '${pageContext.request.contextPath}';
    </script>
    <!-- 管理员头部导航 -->
    <header class="admin-header">
        <div class="nav-container">
            <a href="admin" class="logo" style="color: white;">🔧 管理员后台</a>
            <div class="user-info">
                <span>👤 管理员</span>
                <span class="admin-badge">ADMIN</span>
                <a href="admin?action=dashboard" class="logout-btn" style="background: #28a745;">返回前台</a>
                <a href="${pageContext.request.contextPath}/logout" class="logout-btn">退出登录</a>
            </div>
        </div>
    </header>

    <div class="admin-container">
        <!-- 侧边栏 -->
        <div class="admin-sidebar">
            <button class="sidebar-item" onclick="window.location.href='admin?action=dashboard'">
                📊 仪表板
            </button>
            <button class="sidebar-item" onclick="window.location.href='admin?action=users'">
                👥 用户管理
            </button>
            <button class="sidebar-item active" onclick="window.location.href='admin?action=songs'">
                🎵 音乐管理
            </button>
            <button class="sidebar-item" onclick="window.location.href='admin?action=favorites'">
                ❤️ 收藏管理
            </button>
            <button class="sidebar-item" onclick="window.location.href='admin?action=appeals'">
                📝 申诉管理
            </button>
        </div>

        <!-- 主要内容区域 -->
        <div class="admin-content">
            <h1 class="page-title">🎵 音乐管理</h1>

            <!-- 消息提示 -->
            <%
                String message = request.getParameter("message");
                String messageType = request.getParameter("messageType");
                if (message != null && !message.isEmpty()) {
                    String bgColor = "success".equals(messageType) ? "#d4edda" : "#f8d7da";
                    String textColor = "success".equals(messageType) ? "#155724" : "#721c24";
                    String borderColor = "success".equals(messageType) ? "#c3e6cb" : "#f5c6cb";
            %>
            <div style="background-color: <%= bgColor %>; color: <%= textColor %>; border: 1px solid <%= borderColor %>; padding: 1rem; border-radius: 4px; margin-bottom: 1.5rem;">
                <%= message %>
            </div>
            <%
                }
            %>

            <!-- 歌曲统计 -->
            <div class="song-stats">
                <div class="stat-item">
                    <div class="stat-number">
                        <%
                            List<Song> songs = (List<Song>) request.getAttribute("songs");
                            out.print(songs != null ? songs.size() : 0);
                        %>
                    </div>
                    <div class="stat-label">总歌曲数</div>
                </div>
            </div>

            <!-- 操作按钮 -->
            <div style="margin-bottom: 1.5rem;">
                <button onclick="showAddModal()" class="btn-primary" style="padding: 0.75rem 1.5rem; font-size: 1rem;">
                    ➕ 新增歌曲
                </button>
            </div>

            <!-- 搜索栏 -->
            <div class="search-bar">
                <input type="text" class="search-input" placeholder="搜索歌曲名、艺术家或专辑..." id="songSearch">
                <button class="btn btn-primary" onclick="searchSongs()">🔍 搜索</button>
                <button class="btn btn-secondary" onclick="resetSearch()">🔄 重置</button>
            </div>

            <!-- 歌曲表格 -->
            <div style="overflow-x: auto;">
                <table class="songs-table" id="songsTable">
                    <thead>
                        <tr>
                            <th>歌曲ID</th>
                            <th>歌曲名称</th>
                            <th>艺术家</th>
                            <th>专辑</th>
                            <th>时长</th>
                            <th>类型</th>
                            <th>发行年份</th>
                            <th>操作</th>
                        </tr>
                    </thead>
                    <tbody>
                        <%
                            if (songs != null && !songs.isEmpty()) {
                                for (Song song : songs) {
                        %>
                        <tr>
                            <td class="song-id">#<%= song.getId() %></td>
                            <td><strong><%= song.getTitle() %></strong></td>
                            <td><%= song.getArtist() %></td>
                            <td><%= song.getAlbum() != null ? song.getAlbum() : "未知专辑" %></td>
                            <td>
                                <%
                                    if (song.getDuration() > 0) {
                                        int minutes = song.getDuration() / 60;
                                        int seconds = song.getDuration() % 60;
                                        out.print(String.format("%d:%02d", minutes, seconds));
                                    } else {
                                        out.print("未知");
                                    }
                                %>
                            </td>
                            <td>
                                <span class="genre-tag">
                                    <%= song.getGenre() != null ? song.getGenre() : "未分类" %>
                                </span>
                            </td>
                            <td>
                                <%= song.getReleaseYear() > 0 ? song.getReleaseYear() : "未知" %>
                            </td>
                            <td>
                                <div class="song-actions">
                                    <button class="btn-small btn-play" onclick="playSong(<%= song.getId() %>, '<%= song.getTitle() %>')">
                                        ▶️ 播放
                                    </button>
                                    <button class="btn-small btn-view" onclick="viewSongDetails(<%= song.getId() %>)">
                                        👁️ 详情
                                    </button>
                                    <button class="btn-small btn-danger" onclick="deleteSong(<%= song.getId() %>, '<%= song.getTitle() %>')">
                                        🗑️ 删除
                                    </button>
                                </div>
                            </td>
                        </tr>
                        <%
                                }
                            } else {
                        %>
                        <tr>
                            <td colspan="8" style="text-align: center; padding: 2rem; color: #6c757d;">
                                暂无歌曲数据
                            </td>
                        </tr>
                        <%
                            }
                        %>
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <script>
        // 搜索歌曲功能
        function searchSongs() {
            const searchTerm = document.getElementById('songSearch').value.toLowerCase();
            const rows = document.querySelectorAll('#songsTable tbody tr');

            rows.forEach(row => {
                const text = row.textContent.toLowerCase();
                if (text.includes(searchTerm)) {
                    row.style.display = '';
                } else {
                    row.style.display = 'none';
                }
            });
        }

        // 重置搜索
        function resetSearch() {
            document.getElementById('songSearch').value = '';
            const rows = document.querySelectorAll('#songsTable tbody tr');
            rows.forEach(row => {
                row.style.display = '';
            });
        }

        // 播放歌曲
        function playSong(songId, songTitle) {
            // 这里可以添加实际的播放逻辑
            showNotification(`正在播放: ${songTitle} (ID: ${songId})`);
        }

        // 查看歌曲详情
        function viewSongDetails(songId) {
            alert(`查看歌曲ID: ${songId} 的详细信息\n\n注意：实际项目中这里应该显示详细的歌曲信息弹窗或跳转到详情页面`);
        }

        // 删除歌曲
        function deleteSong(songId, songTitle) {
            if (!songId) {
                alert('歌曲ID无效');
                return;
            }
            if (confirm(`确定要删除歌曲 "${songTitle}" 吗？此操作不可逆！`)) {
                fetch(contextPath + '/admin?action=deleteSong&songId=' + songId)
                    .then(() => {
                        window.location.href = contextPath + '/admin?action=songs';
                    })
                    .catch(() => {
                        alert('删除歌曲失败');
                    });
            }
        }

        // 显示新增歌曲模态框
        function showAddModal() {
            document.getElementById('addModal').classList.add('show');
        }

        // 关闭新增歌曲模态框
        function closeAddModal() {
            document.getElementById('addModal').classList.remove('show');
            document.getElementById('addSongForm').reset();
        }

        // 提交新增歌曲
        function submitAddSong() {
            const form = document.getElementById('addSongForm');
            const formData = new FormData(form);
            const params = new URLSearchParams(formData);

            fetch(contextPath + '/admin?action=addSong', {
                method: 'POST',
                headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                body: params
            }).then(response => {
                if (response.ok) {
                    window.location.href = contextPath + '/admin?action=songs';
                } else {
                    alert('添加歌曲失败');
                }
            }).catch(error => {
                console.error('Error:', error);
                alert('添加歌曲失败');
            });
        }

        // 实时搜索
        document.getElementById('songSearch').addEventListener('input', searchSongs);

        // 表格排序功能
        function sortTable(columnIndex) {
            const table = document.getElementById('songsTable');
            const tbody = table.querySelector('tbody');
            const rows = Array.from(tbody.querySelectorAll('tr'));

            rows.sort((a, b) => {
                const aText = a.children[columnIndex].textContent.trim();
                const bText = b.children[columnIndex].textContent.trim();
                return aText.localeCompare(bText);
            });

            rows.forEach(row => tbody.appendChild(row));
        }

        // 为表头添加点击排序
        document.querySelectorAll('.songs-table th').forEach((th, index) => {
            if (index < 7) { // 除了操作列
                th.style.cursor = 'pointer';
                th.title = '点击排序';
                th.addEventListener('click', () => sortTable(index));
            }
        });

        // 显示通知函数
        function showNotification(message) {
            // 创建通知元素
            const notification = document.createElement('div');
            notification.style.cssText = `
                position: fixed;
                top: 20px;
                right: 20px;
                background: linear-gradient(135deg, #667eea, #764ba2);
                color: white;
                padding: 1rem 1.5rem;
                border-radius: 8px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.15);
                z-index: 1000;
                font-size: 0.9rem;
                animation: slideIn 0.3s ease;
            `;
            notification.textContent = message;

            document.body.appendChild(notification);

            // 3秒后移除
            setTimeout(() => {
                notification.style.animation = 'slideOut 0.3s ease';
                setTimeout(() => {
                    if (notification.parentNode) {
                        notification.parentNode.removeChild(notification);
                    }
                }, 300);
            }, 3000);
        }

        // 添加动画样式
        const style = document.createElement('style');
        style.textContent = `
            @keyframes slideIn {
                from { transform: translateX(100%); opacity: 0; }
                to { transform: translateX(0); opacity: 1; }
            }
            @keyframes slideOut {
                from { transform: translateX(0); opacity: 1; }
                to { transform: translateX(100%); opacity: 0; }
            }
        `;
        document.head.appendChild(style);
    </script>

    <!-- 新增歌曲模态框 -->
    <div id="addModal" class="modal">
        <div class="modal-content">
            <h2>➕ 新增歌曲</h2>
            <form id="addSongForm">
                <div class="form-group">
                    <label>歌曲名称 *</label>
                    <input type="text" name="title" required>
                </div>
                <div class="form-group">
                    <label>艺术家 *</label>
                    <input type="text" name="artist" required>
                </div>
                <div class="form-group">
                    <label>专辑</label>
                    <input type="text" name="album">
                </div>
                <div class="form-group">
                    <label>时长（秒）</label>
                    <input type="number" name="duration" min="0">
                </div>
                <div class="form-group">
                    <label>类型</label>
                    <input type="text" name="genre">
                </div>
                <div class="form-group">
                    <label>发行年份</label>
                    <input type="number" name="releaseYear" min="1900" max="2100">
                </div>
                <div class="form-group">
                    <label>文件路径</label>
                    <input type="text" name="filePath">
                </div>
                <div class="form-group">
                    <label>封面图片路径</label>
                    <input type="text" name="coverImage">
                </div>
                <div class="modal-actions">
                    <button type="button" class="btn-primary" onclick="submitAddSong()">提交</button>
                    <button type="button" class="btn-secondary" onclick="closeAddModal()">取消</button>
                </div>
            </form>
        </div>
    </div>

    <style>
        .modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.5);
            z-index: 1000;
            align-items: center;
            justify-content: center;
        }

        .modal.show {
            display: flex;
        }

        .modal-content {
            background: white;
            padding: 2rem;
            border-radius: 8px;
            max-width: 500px;
            width: 90%;
            max-height: 80vh;
            overflow-y: auto;
        }

        .modal-content h2 {
            margin-bottom: 1.5rem;
            color: #2c3e50;
        }

        .form-group {
            margin-bottom: 1rem;
        }

        .form-group label {
            display: block;
            margin-bottom: 0.5rem;
            font-weight: 500;
            color: #333;
        }

        .form-group input {
            width: 100%;
            padding: 0.75rem;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 1rem;
        }

        .modal-actions {
            display: flex;
            gap: 1rem;
            margin-top: 1.5rem;
        }

        .modal-actions button {
            flex: 1;
            padding: 0.75rem;
            font-size: 1rem;
        }
    </style>

    <script src="../js/app.js"></script>
</body>
</html>