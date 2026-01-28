<%@ page contentType="text/html;charset=UTF-8" language="java" %>
<%@ page import="com.music.javabean.User, java.util.List" %>
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
    <title>用户管理 - 管理员后台</title>
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

        .users-table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 1rem;
            background: white;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        }

        .users-table th {
            background: #007bff;
            color: white;
            padding: 1rem;
            text-align: left;
            font-weight: 600;
        }

        .users-table td {
            padding: 1rem;
            border-bottom: 1px solid #e9ecef;
        }

        .users-table tr:hover {
            background: #f8f9fa;
        }

        .users-table tr:nth-child(even) {
            background: #f8f9fa;
        }

        .users-table tr:nth-child(even):hover {
            background: #e9ecef;
        }

        .user-id {
            font-weight: bold;
            color: #007bff;
        }

        .user-actions {
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
            border-color: #007bff;
        }

        .user-stats {
            display: flex;
            gap: 2rem;
            margin-bottom: 2rem;
        }

        .stat-item {
            background: #f8f9fa;
            padding: 1rem 1.5rem;
            border-radius: 6px;
            border-left: 4px solid #007bff;
        }

        .stat-number {
            font-size: 1.5rem;
            font-weight: bold;
            color: #007bff;
        }

        .stat-label {
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

            .users-table {
                font-size: 0.875rem;
            }

            .users-table th,
            .users-table td {
                padding: 0.5rem;
            }

            .user-stats {
                flex-direction: column;
                gap: 1rem;
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
            <button class="sidebar-item active" onclick="window.location.href='admin?action=users'">
                👥 用户管理
            </button>
            <button class="sidebar-item" onclick="window.location.href='admin?action=songs'">
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
            <h1 class="page-title">👥 用户管理</h1>

            <!-- 用户统计 -->
            <div class="user-stats">
                <div class="stat-item">
                    <div class="stat-number">
                        <%
                            List<User> users = (List<User>) request.getAttribute("users");
                            out.print(users != null ? users.size() : 0);
                        %>
                    </div>
                    <div class="stat-label">总用户数</div>
                </div>
            </div>

            <!-- 搜索栏 -->
            <div class="search-bar">
                <input type="text" class="search-input" placeholder="搜索用户名、昵称或邮箱..." id="userSearch">
                <button class="btn btn-primary" onclick="searchUsers()">🔍 搜索</button>
                <button class="btn btn-secondary" onclick="resetSearch()">🔄 重置</button>
            </div>

            <!-- 用户表格 -->
            <div style="overflow-x: auto;">
                <table class="users-table" id="usersTable">
                    <thead>
                        <tr>
                            <th>用户ID</th>
                            <th>用户名</th>
                            <th>昵称</th>
                            <th>邮箱</th>
                            <th>手机号</th>
                            <th>注册时间</th>
                            <th>操作</th>
                        </tr>
                    </thead>
                    <tbody>
                        <%
                            if (users != null && !users.isEmpty()) {
                                for (User user : users) {
                        %>
                        <tr>
                            <td class="user-id">#<%= user.getId() %></td>
                            <td><%= user.getUsername() %></td>
                            <td><%= user.getNickname() != null ? user.getNickname() : "未设置" %></td>
                            <td><%= user.getEmail() != null ? user.getEmail() : "未设置" %></td>
                            <td><%= user.getPhone() != null ? user.getPhone() : "未设置" %></td>
                            <td><%= user.getCreateTime() != null ? user.getCreateTime().substring(0, 16) : "未知" %></td>
                            <td>
                                <div class="user-actions">
                                    <a href="admin?action=userDetails&userId=<%= user.getId() %>" class="btn-small btn-view">
                                        👁️ 查看
                                    </a>
                                </div>
                            </td>
                        </tr>
                        <%
                                }
                            } else {
                        %>
                        <tr>
                            <td colspan="7" style="text-align: center; padding: 2rem; color: #6c757d;">
                                暂无用户数据
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
        // 搜索用户功能
        function searchUsers() {
            const searchTerm = document.getElementById('userSearch').value.toLowerCase();
            const rows = document.querySelectorAll('#usersTable tbody tr');

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
            document.getElementById('userSearch').value = '';
            const rows = document.querySelectorAll('#usersTable tbody tr');
            rows.forEach(row => {
                row.style.display = '';
            });
        }

        // 查看用户详情
        function viewUserDetails(userId) {
            alert(`查看用户ID: ${userId} 的详细信息\n\n注意：实际项目中这里应该显示详细的用户信息弹窗或跳转到详情页面`);
        }

        // 实时搜索
        document.getElementById('userSearch').addEventListener('input', searchUsers);

        // 表格排序功能
        function sortTable(columnIndex) {
            const table = document.getElementById('usersTable');
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
        document.querySelectorAll('.users-table th').forEach((th, index) => {
            if (index < 6) { // 除了操作列
                th.style.cursor = 'pointer';
                th.title = '点击排序';
                th.addEventListener('click', () => sortTable(index));
            }
        });
    </script>

    <script src="../js/app.js"></script>
</body>
</html>