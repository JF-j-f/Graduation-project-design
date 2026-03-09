<%@ page contentType="text/html;charset=UTF-8" language="java" %>
    <%@ page import="java.util.Map" %>
        <%@ page import="java.util.HashMap" %>
            <% Map<String, Integer> statsMap = (Map<String, Integer>) request.getAttribute("stats");
                    if (statsMap == null) {
                    statsMap = new HashMap<>();
                        }
                        %>
                        <!DOCTYPE html>
                        <html lang="zh-CN">

                        <head>
                            <meta charset="UTF-8">
                            <meta name="viewport" content="width=device-width, initial-scale=1.0">
                            <title>仪表盘 - MusicWeb Admin</title>
                            <link rel="stylesheet" href="${pageContext.request.contextPath}/css/admin/admin.css">
                        </head>

                        <body class="admin-page">

                            <div class="admin-sidebar">
                                <div class="sidebar-logo">
                                    Music<span>Web</span>
                                </div>
                                <div class="sidebar-menu">
                                    <a href="${pageContext.request.contextPath}/admin?action=dashboard"
                                        class="sidebar-item active">
                                        <span class="sidebar-item-icon">📊</span> 仪表盘
                                    </a>
                                    <a href="${pageContext.request.contextPath}/admin?action=users"
                                        class="sidebar-item">
                                        <span class="sidebar-item-icon">👥</span> 用户信息管理
                                    </a>
                                    <a href="${pageContext.request.contextPath}/admin?action=songs"
                                        class="sidebar-item">
                                        <span class="sidebar-item-icon">🎵</span> 歌曲管理
                                    </a>
                                    <a href="${pageContext.request.contextPath}/admin?action=playlists"
                                        class="sidebar-item">
                                        <span class="sidebar-item-icon">📋</span> 歌单管理
                                    </a>
                                    <a href="${pageContext.request.contextPath}/admin?action=appeals"
                                        class="sidebar-item">
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
                                        <span style="margin-right:10px; color:var(--primary);">📊</span> 数据概览
                                    </h1>

                                    <div class="dashboard-grid">
                                        <!-- 统计卡片 1 -->
                                        <div class="stat-widget">
                                            <div class="stat-icon primary">👥</div>
                                            <div class="stat-info">
                                                <div class="stat-title">总注册用户</div>
                                                <div class="stat-value">
                                                    <%= statsMap.getOrDefault("totalUsers", 0) %>
                                                </div>
                                            </div>
                                        </div>

                                        <!-- 统计卡片 2 -->
                                        <div class="stat-widget">
                                            <div class="stat-icon warning">🎵</div>
                                            <div class="stat-info">
                                                <div class="stat-title">歌曲总数</div>
                                                <div class="stat-value">
                                                    <%= statsMap.getOrDefault("totalSongs", 0) %>
                                                </div>
                                            </div>
                                        </div>

                                        <!-- 统计卡片 3 -->
                                        <div class="stat-widget">
                                            <div class="stat-icon danger">❤️</div>
                                            <div class="stat-info">
                                                <div class="stat-title">收藏总数</div>
                                                <div class="stat-value">
                                                    <%= statsMap.getOrDefault("totalFavorites", 0) %>
                                                </div>
                                            </div>
                                        </div>

                                        <!-- 统计卡片 4 -->
                                        <div class="stat-widget">
                                            <div class="stat-icon success">🚀</div>
                                            <div class="stat-info">
                                                <div class="stat-title">近7日新增用户</div>
                                                <div class="stat-value">
                                                    <%= statsMap.getOrDefault("newUsers", 0) %>
                                                </div>
                                            </div>
                                        </div>
                                    </div>

                                    <!-- 快捷执行区 -->
                                    <div class="card">
                                        <div class="card-header">
                                            <h3 class="card-title">快捷操作</h3>
                                        </div>
                                        <div class="card-body">
                                            <div style="display:flex; gap:15px; flex-wrap:wrap;">
                                                <a href="${pageContext.request.contextPath}/admin?action=users"
                                                    class="btn btn-primary">
                                                    👥 用户管理
                                                </a>
                                                <a href="${pageContext.request.contextPath}/admin?action=songs"
                                                    class="btn btn-outline"
                                                    style="border: 1px solid var(--border-color); color: var(--text-main); background: transparent; padding: 0.5rem 1.2rem; border-radius: 6px; font-weight: 500; cursor: pointer; text-decoration: none;">
                                                    🎵 歌曲管理
                                                </a>
                                                <a href="${pageContext.request.contextPath}/admin?action=playlists"
                                                    class="btn btn-light">
                                                    📋 歌单管理
                                                </a>
                                            </div>
                                        </div>
                                    </div>

                                </div>
                            </div>
                        </body>

                        </html>