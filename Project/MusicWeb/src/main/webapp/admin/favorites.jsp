<%@ page contentType="text/html;charset=UTF-8" language="java" %>
    <%@ page import="com.music.javabean.Favorite, java.util.List" %>
        <% // 检查用户是否登录 if (session.getAttribute("user")==null) { response.sendRedirect("../jsp/index.jsp"); return; } %>
            <!DOCTYPE html>
            <html lang="zh-CN">

            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>收藏管理 - 管理员后台</title>
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

                    .favorites-table {
                        width: 100%;
                        border-collapse: collapse;
                        margin-top: 1rem;
                        background: white;
                        border-radius: 8px;
                        overflow: hidden;
                        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
                    }

                    .favorites-table th {
                        background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%);
                        color: white;
                        padding: 1rem;
                        text-align: left;
                        font-weight: 600;
                    }

                    .favorites-table td {
                        padding: 1rem;
                        border-bottom: 1px solid #e9ecef;
                    }

                    .favorites-table tr:hover {
                        background: #f8f9fa;
                    }

                    .favorites-table tr:nth-child(even) {
                        background: #f8f9fa;
                    }

                    .favorites-table tr:nth-child(even):hover {
                        background: #e9ecef;
                    }

                    .favorite-id {
                        font-weight: bold;
                        color: #38f9d7;
                    }

                    .user-name {
                        color: #007bff;
                        font-weight: 500;
                    }

                    .song-title {
                        color: #e83e8c;
                        font-weight: 500;
                    }

                    .favorite-actions {
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

                    .btn-delete {
                        background: #dc3545;
                        color: white;
                    }

                    .btn-delete:hover {
                        background: #c82333;
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
                        border-color: #38f9d7;
                    }

                    .favorite-stats {
                        display: flex;
                        gap: 2rem;
                        margin-bottom: 2rem;
                        flex-wrap: wrap;
                    }

                    .stat-item {
                        background: #f8f9fa;
                        padding: 1rem 1.5rem;
                        border-radius: 6px;
                        border-left: 4px solid #38f9d7;
                        min-width: 150px;
                    }

                    .stat-number {
                        font-size: 1.5rem;
                        font-weight: bold;
                        color: #38f9d7;
                    }

                    .stat-label {
                        color: #6c757d;
                        font-size: 0.9rem;
                    }

                    .time-stamp {
                        color: #6c757d;
                        font-size: 0.9rem;
                        white-space: nowrap;
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

                        .favorites-table {
                            font-size: 0.875rem;
                        }

                        .favorites-table th,
                        .favorites-table td {
                            padding: 0.5rem;
                        }

                        .favorite-stats {
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
                        <button class="sidebar-item" onclick="window.location.href='admin?action=songs'">
                            🎵 音乐管理
                        </button>
                        <button class="sidebar-item active" onclick="window.location.href='admin?action=favorites'">
                            ❤️ 收藏管理
                        </button>
                        <button class="sidebar-item" onclick="window.location.href='admin?action=appeals'">
                            📝 申诉管理
                        </button>
                    </div>

                    <!-- 主要内容区域 -->
                    <div class="admin-content">
                        <h1 class="page-title">❤️ 收藏管理</h1>

                        <!-- 收藏统计 -->
                        <div class="favorite-stats">
                            <div class="stat-item">
                                <div class="stat-number">
                                    <% List<Favorite> favorites = (List<Favorite>) request.getAttribute("favorites");
                                            out.print(favorites != null ? favorites.size() : 0);
                                            %>
                                </div>
                                <div class="stat-label">总收藏记录</div>
                            </div>
                        </div>

                        <!-- 搜索栏 -->
                        <div class="search-bar">
                            <input type="text" class="search-input" placeholder="搜索用户名、歌曲名..." id="favoriteSearch">
                            <button class="btn btn-primary" onclick="searchFavorites()">🔍 搜索</button>
                            <button class="btn btn-secondary" onclick="resetSearch()">🔄 重置</button>
                            <button class="btn btn-danger" onclick="showBulkDeleteConfirm()">🗑️ 批量删除</button>
                        </div>

                        <!-- 收藏记录表格 -->
                        <div style="overflow-x: auto;">
                            <table class="favorites-table" id="favoritesTable">
                                <thead>
                                    <tr>
                                        <th>
                                            <input type="checkbox" id="selectAll" onchange="toggleSelectAll()">
                                            <span style="margin-left: 0.5rem;">收藏ID</span>
                                        </th>
                                        <th>用户名</th>
                                        <th>歌曲名</th>
                                        <th>收藏时间</th>
                                        <th>操作</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <% if (favorites !=null && !favorites.isEmpty()) { for (Favorite favorite :
                                        favorites) { %>
                                        <tr>
                                            <td>
                                                <input type="checkbox" class="favorite-checkbox"
                                                    value="<%= favorite.getId() %>" onchange="updateSelectAll()">
                                                <span class="favorite-id" style="margin-left: 0.5rem;">#<%=
                                                        favorite.getId() %></span>
                                            </td>
                                            <td>
                                                <span class="user-name">
                                                    <%= favorite.getUser() !=null ? favorite.getUser().getUsername()
                                                        : "未知用户" %>
                                                </span>
                                            </td>
                                            <td>
                                                <span class="song-title">
                                                    <%= favorite.getSong() !=null ? favorite.getSong().getTitle()
                                                        : "未知歌曲" %>
                                                </span>
                                            </td>
                                            <td>
                                                <span class="time-stamp">
                                                    <%= favorite.getCreateTime() !=null ?
                                                        favorite.getCreateTime().substring(0, 16) : "未知时间" %>
                                                </span>
                                            </td>
                                            <td>
                                                <div class="favorite-actions">
                                                    <button class="btn-small btn-view"
                                                        onclick="viewFavoriteDetails(<%= favorite.getId() %>)">
                                                        👁️ 详情
                                                    </button>
                                                    <button class="btn-small btn-delete"
                                                        onclick="deleteFavorite(<%= favorite.getId() %>)">
                                                        🗑️ 删除
                                                    </button>
                                                </div>
                                            </td>
                                        </tr>
                                        <% } } else { %>
                                            <tr>
                                                <td colspan="5"
                                                    style="text-align: center; padding: 2rem; color: #6c757d;">
                                                    暂无收藏记录
                                                </td>
                                            </tr>
                                            <% } %>
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>

                <script>
                    // 搜索收藏记录功能
                    function searchFavorites() {
                        const searchTerm = document.getElementById('favoriteSearch').value.toLowerCase();
                        const rows = document.querySelectorAll('#favoritesTable tbody tr');

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
                        document.getElementById('favoriteSearch').value = '';
                        const rows = document.querySelectorAll('#favoritesTable tbody tr');
                        rows.forEach(row => {
                            row.style.display = '';
                        });
                    }

                    // 全选/取消全选
                    function toggleSelectAll() {
                        const selectAll = document.getElementById('selectAll');
                        const checkboxes = document.querySelectorAll('.favorite-checkbox');

                        checkboxes.forEach(checkbox => {
                            checkbox.checked = selectAll.checked;
                        });
                    }

                    // 更新全选状态
                    function updateSelectAll() {
                        const selectAll = document.getElementById('selectAll');
                        const checkboxes = document.querySelectorAll('.favorite-checkbox');
                        const checkedBoxes = document.querySelectorAll('.favorite-checkbox:checked');

                        selectAll.checked = checkboxes.length === checkedBoxes.length && checkboxes.length > 0;
                        selectAll.indeterminate = checkedBoxes.length > 0 && checkedBoxes.length < checkboxes.length;
                    }

                    // 查看收藏详情
                    function viewFavoriteDetails(favoriteId) {
                        alert(`查看收藏记录ID: ${favoriteId} 的详细信息\n\n注意：实际项目中这里应该显示详细的收藏信息弹窗或跳转到详情页面`);
                    }

                    // 删除单个收藏记录
                    function deleteFavorite(favoriteId) {
                        if (confirm('确定要删除这条收藏记录吗？\n\n注意：实际项目中这里应该发送删除请求到服务器')) {
                            showNotification(`收藏记录 ${favoriteId} 已删除（演示）`);
                            // 实际项目中应该发送AJAX请求到服务器
                            setTimeout(() => {
                                const row = document.querySelector(`input[value="${favoriteId}"]`).closest('tr');
                                if (row) {
                                    row.remove();
                                }
                            }, 1000);
                        }
                    }

                    // 批量删除确认
                    function showBulkDeleteConfirm() {
                        const selectedBoxes = document.querySelectorAll('.favorite-checkbox:checked');
                        if (selectedBoxes.length === 0) {
                            alert('请先选择要删除的记录');
                            return;
                        }

                        if (confirm(`确定要删除选中的 ${selectedBoxes.length} 条收藏记录吗？\n\n注意：此操作不可恢复！`)) {
                            showNotification(`已删除 ${selectedBoxes.length} 条记录（演示）`);
                            // 实际项目中应该发送批量删除请求到服务器

                            // 演示：直接移除选中的行
                            setTimeout(() => {
                                selectedBoxes.forEach(checkbox => {
                                    const row = checkbox.closest('tr');
                                    if (row) {
                                        row.remove();
                                    }
                                });
                                document.getElementById('selectAll').checked = false;
                            }, 1000);
                        }
                    }

                    // 实时搜索
                    document.getElementById('favoriteSearch').addEventListener('input', searchFavorites);

                    // 表格排序功能
                    function sortTable(columnIndex) {
                        const table = document.getElementById('favoritesTable');
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
                    document.querySelectorAll('.favorites-table th').forEach((th, index) => {
                        if (index > 0 && index < 4) { // 除了复选框列和操作列
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
                background: linear-gradient(135deg, #43e97b, #38f9d7);
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

                <script src="../js/app.js"></script>
            </body>

            </html>