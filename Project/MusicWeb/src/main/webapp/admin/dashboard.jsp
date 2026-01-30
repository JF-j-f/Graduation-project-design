<%@ page contentType="text/html;charset=UTF-8" language="java" %>
<%@ page import="java.util.Map" %>
<%
    // 检查用户是否登录
    if (session.getAttribute("user") == null) {
        response.sendRedirect("../jsp/index.jsp");
        return;
    }
%>
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>管理员后台 - 音乐网站</title>
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

        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 1.5rem;
            margin-bottom: 2rem;
        }

        .stat-card {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 2rem;
            border-radius: 12px;
            text-align: center;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
        }

        .stat-card.users { background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); }
        .stat-card.songs { background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); }
        .stat-card.favorites { background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%); }
        .stat-card.new { background: linear-gradient(135deg, #fa709a 0%, #fee140 100%); }

        .stat-number {
            font-size: 3rem;
            font-weight: bold;
            margin-bottom: 0.5rem;
        }

        .stat-label {
            font-size: 1.1rem;
            opacity: 0.9;
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

        .user-info span {
            margin-right: 1rem;
        }

        .logout-btn {
            background: #dc3545;
            color: white;
            padding: 0.5rem 1rem;
            border: none;
            border-radius: 6px;
            text-decoration: none;
            transition: background 0.3s ease;
        }

        .logout-btn:hover {
            background: #c82333;
            color: white;
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
            <button class="sidebar-item active" onclick="window.location.href='admin?action=dashboard'">
                📊 仪表板
            </button>
            <button class="sidebar-item" onclick="window.location.href='admin?action=users'">
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
            <h1 class="page-title">📊 数据统计仪表板</h1>

            <%
                Map<String, Integer> stats = (Map<String, Integer>) request.getAttribute("stats");
                if (stats != null) {
            %>
            <div class="stats-grid">
                <div class="stat-card users">
                    <div class="stat-number"><%= stats.getOrDefault("totalUsers", 0) %></div>
                    <div class="stat-label">总用户数</div>
                </div>

                <div class="stat-card songs">
                    <div class="stat-number"><%= stats.getOrDefault("totalSongs", 0) %></div>
                    <div class="stat-label">总歌曲数</div>
                </div>

                <div class="stat-card favorites">
                    <div class="stat-number"><%= stats.getOrDefault("totalFavorites", 0) %></div>
                    <div class="stat-label">总收藏数</div>
                </div>

                <div class="stat-card new">
                    <div class="stat-number"><%= stats.getOrDefault("newUsers", 0) %></div>
                    <div class="stat-label">7日新用户</div>
                </div>
            </div>

            <div class="stats-grid">
                <div class="stat-card new">
                    <div class="stat-number"><%= stats.getOrDefault("newFavorites", 0) %></div>
                    <div class="stat-label">7日新收藏</div>
                </div>
            </div>
            <%
                } else {
            %>
            <div class="alert alert-error">
                <span class="alert-icon">❌</span>
                <span>无法加载统计数据</span>
            </div>
            <%
                }
            %>

            <!-- 快速操作 -->
            <div style="margin-top: 3rem;">
                <h2 style="margin-bottom: 1.5rem; color: #2c3e50;">🚀 快速操作</h2>
                <div class="stats-grid">
                    <button class="sidebar-item" style="font-size: 1.1rem; padding: 1.5rem;" onclick="window.location.href='admin?action=users'">
                        👥 查看所有用户
                    </button>
                    <button class="sidebar-item" style="font-size: 1.1rem; padding: 1.5rem;" onclick="window.location.href='admin?action=songs'">
                        🎵 查看所有歌曲
                    </button>
                    <button class="sidebar-item" style="font-size: 1.1rem; padding: 1.5rem;" onclick="window.location.href='admin?action=favorites'">
                        ❤️ 查看收藏记录
                    </button>
                </div>
            </div>
        </div>
    </div>

    <script src="../js/app.js"></script>
</body>
</html>