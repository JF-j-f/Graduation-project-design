<%@ page contentType="text/html;charset=UTF-8" language="java" %>
    <%@ page import="com.music.javabean.User" %>
        <% // 检查用户是否登录 if (session.getAttribute("user")==null) { response.sendRedirect("../jsp/index.jsp"); return; }
            User user=(User) request.getAttribute("user"); if (user==null) {
            response.sendRedirect("admin?action=users&message=用户不存在&messageType=error"); return; } // 获取消息参数 String
            message=request.getParameter("message"); String messageType=request.getParameter("messageType"); String
            successMsg=null; String errorMsg=null; if (message !=null && !message.isEmpty()) { if
            ("success".equals(messageType)) { successMsg=message; } else { errorMsg=message; } } %>
            <!DOCTYPE html>
            <html lang="zh-CN">

            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>用户详情 - 管理员后台</title>
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

                    .user-details-grid {
                        display: grid;
                        grid-template-columns: 1fr 1fr;
                        gap: 2rem;
                        margin-bottom: 2rem;
                    }

                    .user-info-card {
                        background: #f8f9fa;
                        border-radius: 8px;
                        padding: 1.5rem;
                        border-left: 4px solid #007bff;
                    }

                    .user-actions-card {
                        background: #f8f9fa;
                        border-radius: 8px;
                        padding: 1.5rem;
                        border-left: 4px solid #dc3545;
                    }

                    .info-item {
                        margin-bottom: 1rem;
                        padding-bottom: 1rem;
                        border-bottom: 1px solid #dee2e6;
                    }

                    .info-label {
                        font-weight: 600;
                        color: #495057;
                        margin-bottom: 0.25rem;
                    }

                    .info-value {
                        color: #212529;
                        font-size: 1.1rem;
                    }

                    .status-badge {
                        display: inline-block;
                        padding: 0.25rem 0.75rem;
                        border-radius: 20px;
                        font-size: 0.875rem;
                        font-weight: 600;
                    }

                    .status-active {
                        background: #d4edda;
                        color: #155724;
                    }

                    .status-frozen {
                        background: #fff3cd;
                        color: #856404;
                    }

                    .status-deleted {
                        background: #f8d7da;
                        color: #721c24;
                    }

                    .action-section {
                        margin-bottom: 2rem;
                    }

                    .action-title {
                        font-size: 1.25rem;
                        margin-bottom: 1rem;
                        color: #495057;
                        border-bottom: 2px solid #dee2e6;
                        padding-bottom: 0.5rem;
                    }

                    .freeze-form {
                        background: #fff3cd;
                        border: 1px solid #ffeaa7;
                        border-radius: 6px;
                        padding: 1.5rem;
                        margin-bottom: 1rem;
                    }

                    .form-group {
                        margin-bottom: 1rem;
                    }

                    .form-label {
                        display: block;
                        margin-bottom: 0.5rem;
                        font-weight: 600;
                        color: #495057;
                    }

                    .form-input {
                        width: 100%;
                        padding: 0.75rem;
                        border: 1px solid #ced4da;
                        border-radius: 4px;
                        font-size: 1rem;
                    }

                    .form-input:focus {
                        outline: none;
                        border-color: #007bff;
                        box-shadow: 0 0 0 2px rgba(0, 123, 255, 0.25);
                    }

                    .btn-danger {
                        background: #dc3545;
                        color: white;
                        border: none;
                        padding: 0.75rem 1.5rem;
                        border-radius: 4px;
                        cursor: pointer;
                        font-size: 1rem;
                        transition: background 0.3s ease;
                    }

                    .btn-danger:hover {
                        background: #c82333;
                    }

                    .btn-warning {
                        background: #ffc107;
                        color: #212529;
                        border: none;
                        padding: 0.75rem 1.5rem;
                        border-radius: 4px;
                        cursor: pointer;
                        font-size: 1rem;
                        transition: background 0.3s ease;
                    }

                    .btn-warning:hover {
                        background: #e0a800;
                    }

                    .btn-success {
                        background: #28a745;
                        color: white;
                        border: none;
                        padding: 0.75rem 1.5rem;
                        border-radius: 4px;
                        cursor: pointer;
                        font-size: 1rem;
                        transition: background 0.3s ease;
                    }

                    .btn-success:hover {
                        background: #218838;
                    }

                    .back-link {
                        display: inline-block;
                        margin-bottom: 2rem;
                        color: #007bff;
                        text-decoration: none;
                        font-weight: 600;
                    }

                    .back-link:hover {
                        text-decoration: underline;
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

                        .user-details-grid {
                            grid-template-columns: 1fr;
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
                        <a href="admin?action=users" class="back-link">← 返回用户列表</a>
                        <h1 class="page-title">👤 用户详情</h1>

                        <!-- 消息提示 -->
                        <% if (successMsg !=null) { %>
                            <div class="alert alert-success">
                                <span class="alert-icon">✅</span>
                                <span>
                                    <%= successMsg %>
                                </span>
                                <button type="button" class="alert-close"
                                    onclick="this.parentElement.style.display='none'">&times;</button>
                            </div>
                            <% } %>

                                <% if (errorMsg !=null) { %>
                                    <div class="alert alert-error">
                                        <span class="alert-icon">❌</span>
                                        <span>
                                            <%= errorMsg %>
                                        </span>
                                        <button type="button" class="alert-close"
                                            onclick="this.parentElement.style.display='none'">&times;</button>
                                    </div>
                                    <% } %>

                                        <div class="user-details-grid">
                                            <!-- 用户信息 -->
                                            <div class="user-info-card">
                                                <h2 style="margin-bottom: 1.5rem; color: #495057;">基本信息</h2>

                                                <div class="info-item">
                                                    <div class="info-label">用户ID</div>
                                                    <div class="info-value">#<%= user.getId() %>
                                                    </div>
                                                </div>

                                                <div class="info-item">
                                                    <div class="info-label">用户名</div>
                                                    <div class="info-value">
                                                        <%= user.getUsername() %>
                                                    </div>
                                                </div>

                                                <div class="info-item">
                                                    <div class="info-label">昵称</div>
                                                    <div class="info-value">
                                                        <%= user.getNickname() !=null ? user.getNickname() : "未设置" %>
                                                    </div>
                                                </div>

                                                <div class="info-item">
                                                    <div class="info-label">邮箱</div>
                                                    <div class="info-value">
                                                        <%= user.getEmail() !=null ? user.getEmail() : "未设置" %>
                                                    </div>
                                                </div>

                                                <div class="info-item">
                                                    <div class="info-label">手机号</div>
                                                    <div class="info-value">
                                                        <%= user.getPhone() !=null ? user.getPhone() : "未设置" %>
                                                    </div>
                                                </div>

                                                <div class="info-item">
                                                    <div class="info-label">注册时间</div>
                                                    <div class="info-value">
                                                        <%= user.getCreateTime() !=null ?
                                                            user.getCreateTime().substring(0, 16) : "未知" %>
                                                    </div>
                                                </div>

                                                <div class="info-item">
                                                    <div class="info-label">账号状态</div>
                                                    <div class="info-value">
                                                        <% String status=user.getStatus(); String statusText="" ; String
                                                            statusClass="" ; if ("active".equals(status)) {
                                                            statusText="正常" ; statusClass="status-active" ; } else if
                                                            ("frozen".equals(status)) { statusText="已冻结" ;
                                                            statusClass="status-frozen" ; } else if
                                                            ("deleted".equals(status)) { statusText="已删除" ;
                                                            statusClass="status-deleted" ; } else { statusText="未知" ;
                                                            statusClass="status-active" ; } %>
                                                            <span class="status-badge <%= statusClass %>">
                                                                <%= statusText %>
                                                            </span>
                                                    </div>
                                                </div>

                                                <% if ("frozen".equals(user.getStatus())) { %>
                                                    <div class="info-item">
                                                        <div class="info-label">冻结截止时间</div>
                                                        <div class="info-value">
                                                            <%= user.getFrozenUntil() !=null ?
                                                                user.getFrozenUntil().substring(0, 16) : "未知" %>
                                                        </div>
                                                    </div>

                                                    <div class="info-item">
                                                        <div class="info-label">冻结原因</div>
                                                        <div class="info-value">
                                                            <%= user.getFrozenReason() !=null ? user.getFrozenReason()
                                                                : "未说明" %>
                                                        </div>
                                                    </div>
                                                    <% } %>
                                            </div>

                                            <!-- 管理操作 -->
                                            <div class="user-actions-card">
                                                <h2 style="margin-bottom: 1.5rem; color: #495057;">管理操作</h2>

                                                <% if ("active".equals(user.getStatus())) { %>
                                                    <!-- 冻结操作 -->
                                                    <div class="action-section">
                                                        <h3 class="action-title">❄️ 冻结账号</h3>
                                                        <form id="freezeForm">
                                                            <input type="hidden" name="userId"
                                                                value="<%= user.getId() %>">

                                                            <div class="form-group">
                                                                <label class="form-label">冻结截止时间</label>
                                                                <input type="datetime-local" name="frozenUntil"
                                                                    class="form-input" required>
                                                            </div>

                                                            <div class="form-group">
                                                                <label class="form-label">冻结原因</label>
                                                                <textarea name="reason" class="form-input" rows="3"
                                                                    placeholder="请输入冻结原因..." required></textarea>
                                                            </div>

                                                            <button type="button" class="btn-warning"
                                                                style="width: 100%;"
                                                                onclick="submitFreeze()">确认冻结</button>
                                                        </form>
                                                    </div>
                                                    <% } else if ("frozen".equals(user.getStatus())) { %>
                                                        <!-- 解冻操作 -->
                                                        <div class="action-section">
                                                            <h3 class="action-title">🔥 解冻账号</h3>
                                                            <button type="button" class="btn-success"
                                                                style="width: 100%;"
                                                                onclick="submitUnfreeze(<%= user.getId() %>)">立即解冻</button>
                                                        </div>
                                                        <% } %>

                                                            <!-- 删除操作 -->
                                                            <div class="action-section">
                                                                <h3 class="action-title">🗑️ 删除账号</h3>
                                                                <p style="margin-bottom: 1rem; color: #6c757d;">
                                                                    删除操作将软删除用户账号，用户将无法登录但数据仍保留在数据库中。
                                                                </p>
                                                                <button type="button" class="btn-danger"
                                                                    style="width: 100%;"
                                                                    onclick="submitDelete('<%= user.getUsername() %>')">删除用户</button>
                                                            </div>
                                            </div>
                                        </div>
                    </div>
                </div>

                <script>
                    const contextPath = '${pageContext.request.contextPath}';
                    const userId = <%= user.getId() %>;

                    function submitFreeze() {
                        const form = document.getElementById('freezeForm');
                        const formData = new FormData(form);
                        const params = new URLSearchParams(formData);

                        fetch(contextPath + '/admin?action=freezeUser', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                            body: params
                        }).then(response => {
                            if (response.ok) {
                                window.location.href = contextPath + '/admin?action=userDetails&userId=' + userId;
                            } else {
                                alert('冻结失败');
                            }
                        }).catch(() => {
                            alert('冻结失败');
                        });
                    }

                    function submitUnfreeze(userId) {
                        if (confirm('确定要解冻该用户吗？')) {
                            fetch(contextPath + '/admin?action=unfreezeUser&userId=' + userId, {
                                method: 'POST'
                            }).then(response => {
                                if (response.ok) {
                                    window.location.href = contextPath + '/admin?action=userDetails&userId=' + userId;
                                } else {
                                    alert('解冻失败');
                                }
                            }).catch(() => {
                                alert('解冻失败');
                            });
                        }
                    }

                    function submitDelete(username) {
                        if (confirm('确定要删除用户 ' + username + ' 吗？此操作不可逆!')) {
                            fetch(contextPath + '/admin?action=deleteUser&userId=' + userId, {
                                method: 'POST'
                            }).then(response => {
                                if (response.ok) {
                                    window.location.href = contextPath + '/admin?action=userDetails&userId=' + userId;
                                } else {
                                    alert('删除失败');
                                }
                            }).catch(() => {
                                alert('删除失败');
                            });
                        }
                    }
                </script>
                <script src="../js/app.js"></script>
            </body>

            </html>