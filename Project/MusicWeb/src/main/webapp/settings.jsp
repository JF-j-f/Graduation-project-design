<%@ page contentType="text/html;charset=UTF-8" language="java" %>
    <%@ page import="com.music.javabean.*" %>
        <% // 检查用户是否登录 User user=(User) session.getAttribute("user"); if (user==null) {
            response.sendRedirect("index.jsp"); return; } // 获取消息参数 String message=request.getParameter("message");
            String messageType=request.getParameter("messageType"); // success, error String successMsg=null; String
            errorMsg=null; if (message !=null && !message.isEmpty()) { if ("success".equals(messageType)) {
            successMsg=message; } else { errorMsg=message; } } %>
            <!DOCTYPE html>
            <html lang="zh-CN">

            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>设置 - 音乐网站</title>
                <link rel="stylesheet" href="${pageContext.request.contextPath}/css/style.css">
                <link rel="stylesheet" href="${pageContext.request.contextPath}/css/settings.css">
            </head>

            <body class="settings-page">
                <!-- 头部导航 -->
                <header class="header">
                    <div class="nav-container">
                        <a href="user.jsp" class="logo">MusicWeb</a>
                        <nav class="nav-links">
                            <a href="user.jsp" class="nav-link">首页</a>
                            <a href="user.jsp#discover" class="nav-link">发现</a>
                            <a href="user.jsp#charts" class="nav-link">排行榜</a>
                            <a href="user.jsp#favorites" class="nav-link">我的收藏</a>
                        </nav>
                        <div class="user-info">
                            <div class="user-avatar">
                                <%= user.getNickname() !=null && !user.getNickname().trim().isEmpty() ?
                                    user.getNickname().charAt(0) : user.getUsername().charAt(0) %>
                            </div>
                            <span>欢迎, <%= user.getNickname() !=null && !user.getNickname().trim().isEmpty() ?
                                    user.getNickname() : user.getUsername() %></span>
                            <a href="logout" class="btn btn-outline" style="margin-right: 0.5rem;">退出</a>
                            <a href="settings.jsp" class="btn btn-secondary">⚙️ 设置</a>
                        </div>
                    </div>
                </header>

                <!-- 主要内容 -->
                <main class="main-container">
                    <!-- 页面标题 -->
                    <div class="page-header">
                        <h1>账户设置</h1>
                        <p>管理您的个人信息和账户安全</p>
                    </div>

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

                                    <div class="settings-container">
                                        <!-- 左侧导航 -->
                                        <div class="settings-sidebar">
                                            <div class="sidebar-item active" data-tab="profile">
                                                <span class="sidebar-icon">👤</span>
                                                <span class="sidebar-text">个人信息</span>
                                            </div>
                                            <div class="sidebar-item" data-tab="security">
                                                <span class="sidebar-icon">🔒</span>
                                                <span class="sidebar-text">账户安全</span>
                                            </div>
                                            <div class="sidebar-item" data-tab="account">
                                                <span class="sidebar-icon">⚙️</span>
                                                <span class="sidebar-text">账户管理</span>
                                            </div>
                                        </div>

                                        <!-- 右侧内容 -->
                                        <div class="settings-content">
                                            <!-- 个人信息标签页 -->
                                            <div class="tab-content active" id="profile-tab">
                                                <div class="content-header">
                                                    <h2>个人信息</h2>
                                                    <p>更新您的基本信息</p>
                                                </div>

                                                <form id="profileForm" action="updateProfile" method="post"
                                                    class="settings-form">
                                                    <div class="form-section">
                                                        <h3>基本信息</h3>

                                                        <div class="form-row">
                                                            <div class="form-group">
                                                                <label for="username">用户名</label>
                                                                <input type="text" id="username" name="username"
                                                                    value="<%= user.getUsername() %>" readonly
                                                                    class="form-input readonly">
                                                                <small class="form-help">用户名创建后不能修改</small>
                                                            </div>

                                                            <div class="form-group">
                                                                <label for="nickname">昵称</label>
                                                                <input type="text" id="nickname" name="nickname"
                                                                    value="<%= user.getNickname() != null ? user.getNickname() : "" %>"
                                                                    class="form-input" placeholder="请输入昵称">
                                                            </div>
                                                        </div>

                                                        <div class="form-row">
                                                            <div class="form-group">
                                                                <label for="email">邮箱地址</label>
                                                                <input type="email" id="email" name="email"
                                                                    value="<%= user.getEmail() != null ? user.getEmail() : "" %>"
                                                                    class="form-input" placeholder="请输入邮箱地址">
                                                            </div>

                                                            <div class="form-group">
                                                                <label for="phone">手机号码</label>
                                                                <input type="tel" id="phone" name="phone"
                                                                    value="<%= user.getPhone() != null ? user.getPhone() : "" %>"
                                                                    class="form-input" placeholder="请输入手机号码">
                                                            </div>
                                                        </div>
                                                    </div>

                                                    <div class="form-actions">
                                                        <button type="submit" class="btn btn-primary">保存更改</button>
                                                        <button type="button" class="btn btn-secondary"
                                                            onclick="resetForm()">重置</button>
                                                    </div>
                                                </form>
                                            </div>

                                            <!-- 账户安全标签页 -->
                                            <div class="tab-content" id="security-tab">
                                                <div class="content-header">
                                                    <h2>账户安全</h2>
                                                    <p>保护您的账户安全</p>
                                                </div>

                                                <form id="passwordForm" action="changePassword" method="post"
                                                    class="settings-form">
                                                    <div class="form-section">
                                                        <h3>修改密码</h3>

                                                        <div class="form-group">
                                                            <label for="currentPassword">当前密码</label>
                                                            <input type="password" id="currentPassword"
                                                                name="currentPassword" class="form-input"
                                                                placeholder="请输入当前密码" required>
                                                        </div>

                                                        <div class="form-row">
                                                            <div class="form-group">
                                                                <label for="newPassword">新密码</label>
                                                                <input type="password" id="newPassword"
                                                                    name="newPassword" class="form-input"
                                                                    placeholder="请输入新密码" required>
                                                                <div class="password-strength">
                                                                    <div class="strength-bar">
                                                                        <div class="strength-fill"></div>
                                                                    </div>
                                                                    <span class="strength-text">密码强度：弱</span>
                                                                </div>
                                                            </div>

                                                            <div class="form-group">
                                                                <label for="confirmPassword">确认新密码</label>
                                                                <input type="password" id="confirmPassword"
                                                                    name="confirmPassword" class="form-input"
                                                                    placeholder="请再次输入新密码" required>
                                                            </div>
                                                        </div>
                                                    </div>

                                                    <div class="form-actions">
                                                        <button type="submit" class="btn btn-primary">修改密码</button>
                                                    </div>
                                                </form>
                                            </div>

                                            <!-- 账户管理标签页 -->
                                            <div class="tab-content" id="account-tab">
                                                <div class="content-header">
                                                    <h2>账户管理</h2>
                                                    <p>管理您的账户设置</p>
                                                </div>

                                                <div class="form-section">
                                                    <h3>账户信息</h3>

                                                    <div class="account-info">
                                                        <div class="info-item">
                                                            <span class="info-label">用户ID</span>
                                                            <span class="info-value">
                                                                <%= user.getId() %>
                                                            </span>
                                                        </div>
                                                        <div class="info-item">
                                                            <span class="info-label">用户名</span>
                                                            <span class="info-value">
                                                                <%= user.getUsername() %>
                                                            </span>
                                                        </div>
                                                        <div class="info-item">
                                                            <span class="info-label">注册时间</span>
                                                            <span class="info-value">
                                                                <%= user.getCreateTime() !=null ?
                                                                    user.getCreateTime().substring(0, 16) : "未知时间" %>
                                                            </span>
                                                        </div>
                                                    </div>
                                                </div>

                                                <div class="form-section danger-zone">
                                                    <h3>危险区域</h3>
                                                    <p>⚠️ 以下操作不可逆转，请谨慎操作</p>

                                                    <button type="button" class="btn btn-danger"
                                                        onclick="showDeleteAccountModal()">
                                                        注销账户
                                                    </button>
                                                    <small class="form-help">注销账户后将无法恢复，所有数据将被永久删除</small>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                </main>

                <!-- 注销账户确认模态框 -->
                <div class="modal" id="deleteAccountModal">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h3>⚠️ 确认注销账户</h3>
                            <button type="button" class="modal-close"
                                onclick="closeDeleteAccountModal()">&times;</button>
                        </div>

                        <div class="modal-body">
                            <div class="warning-content">
                                <div class="warning-icon">⚠️</div>
                                <div class="warning-text">
                                    <h4>您确定要注销账户吗？</h4>
                                    <p>注销账户后，以下操作将无法恢复：</p>
                                    <ul>
                                        <li>❌ 所有个人信息将被永久删除</li>
                                        <li>❌ 所有收藏的歌曲将被清空</li>
                                        <li>❌ 账户将被彻底注销，无法重新激活</li>
                                        <li>❌ 如需重新使用，需要重新注册新账户</li>
                                    </ul>
                                    <p class="final-warning">这是一个<strong>不可逆转</strong>的操作，请谨慎决定！</p>
                                </div>
                            </div>

                            <div class="confirmation-section">
                                <label class="checkbox-label">
                                    <input type="checkbox" id="confirmDeleteCheckbox">
                                    <span class="checkmark"></span>
                                    我已了解并同意上述风险，确认注销账户
                                </label>
                            </div>

                            <div class="password-confirmation">
                                <label for="deletePasswordConfirm">请输入当前密码以确认操作：</label>
                                <input type="password" id="deletePasswordConfirm" class="form-input"
                                    placeholder="输入当前密码">
                                <span class="error-message" id="passwordError"></span>
                            </div>
                        </div>

                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" onclick="closeDeleteAccountModal()">
                                取消
                            </button>
                            <button type="button" class="btn btn-danger" id="confirmDeleteBtn" disabled
                                onclick="confirmDeleteAccount()">
                                确认注销
                            </button>
                        </div>
                    </div>
                </div>

                <!-- 加载遮罩 -->
                <div class="loading-overlay" id="loadingOverlay">
                    <div class="spinner"></div>
                    <p>正在处理...</p>
                </div>

                <script src="${pageContext.request.contextPath}/js/settings.js"></script>
            </body>

            </html>