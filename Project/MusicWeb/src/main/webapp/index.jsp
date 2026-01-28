<%@ page contentType="text/html;charset=UTF-8" language="java" %>
<%@ page import="com.music.javabean.*, com.music.dao.*, java.util.*" %>
<%
    // 1. 获取用户Session
    User user = (User) session.getAttribute("user");

    // 2. 如果用户已登录，直接在这里跳转并结束
    if (user != null) {
        response.sendRedirect("user.jsp");
        return; // 结束当前页面的执行
    }

    // 3. 后续逻辑只会在"未登录"状态下执行
    FavoriteDAO favoriteDAO = new FavoriteDAO();
    List<Favorite> favorites = new ArrayList<>();

    // 推荐歌曲数据 (为了防止数据库空指针，加了容错)
    SongDAO songDAO = new SongDAO();
    List<Song> recommendedSongs = new ArrayList<>();
    try {
        recommendedSongs = songDAO.getNewSongs(8);
    } catch(Exception e) {
        // 数据库连接失败时的容错处理，防止页面崩溃
        System.out.println("加载推荐歌曲失败: " + e.getMessage());
    }

    // 获取消息参数
    String message = request.getParameter("message");
    String messageType = request.getParameter("messageType");
    String successMsg = null;
    String errorMsg = null;

    if (message != null && !message.isEmpty()) {
        if ("success".equals(messageType)) successMsg = message;
        else errorMsg = message;
    }
%>
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MusicWeb - 听见好音乐</title>
    <link rel="stylesheet" href="css/style.css">
</head>
<body>

<!-- 头部导航 -->
<header class="header">
    <div class="nav-container">
        <a href="index.jsp" class="logo">MusicWeb</a>
        <nav class="nav-links">
            <a href="index.jsp" class="nav-link" style="color:var(--primary-color)">首页</a>
            <!-- 未登录用户点击这些通常会跳回登录页或不做反应，这里指向user.jsp会让拦截器处理 -->
            <a href="user.jsp#discover" class="nav-link">发现</a>
            <a href="user.jsp#charts" class="nav-link">排行榜</a>
        </nav>
        <div class="user-info">
            <!-- 因为顶部已经拦截了已登录用户，所以这里肯定是未登录状态 -->
            <span style="font-size: 0.9rem; color: #666;">登录畅享高音质</span>
        </div>
    </div>
</header>

<!-- 全局提示框 -->
<% if (successMsg != null) { %>
<div class="alert alert-success alert-temporary" onclick="this.remove()">
    <span class="alert-icon">✅</span>
    <span><%= successMsg %></span>
</div>
<% } %>
<% if (errorMsg != null) { %>
<div class="alert alert-error alert-temporary" onclick="this.remove()">
    <span class="alert-icon">❌</span>
    <span><%= errorMsg %></span>
</div>
<% } %>

<!-- ================= 未登录：网易云风格首页 ================= -->

<!-- 1. Hero Banner 区域 -->
<section class="hero-banner">
    <div class="hero-content">
        <!-- 左侧：宣传文案 -->
        <div class="hero-text fade-in">
            <h1>发现属于你的<br>音乐世界</h1>
            <p>海量曲库，无损音质，个性化推荐。<br>让每一次聆听都成为享受。</p>
            <a href="register.jsp" class="hero-btn">免费注册账号</a>
        </div>

        <!-- 右侧：悬浮登录框 -->
        <div class="login-card-wrapper">
            <div class="login-header">
                <h2>欢迎回来</h2>
            </div>
            <form action="userLogin" method="post">
                <div class="input-group">
                    <input type="text" name="username" class="modern-input" placeholder="请输入用户名/手机号" required>
                </div>
                <div class="input-group">
                    <input type="password" name="password" class="modern-input" placeholder="请输入密码" required>
                </div>

                <div class="form-options">
                    <label style="cursor: pointer; display: flex; align-items: center; gap: 0.3rem;">
                        <input type="checkbox" name="remember"> 记住我
                    </label>
                    <a href="#">忘记密码?</a>
                </div>

                <button type="submit" class="submit-btn">立即登录</button>

                <div style="text-align: center; margin-top: 1.5rem; font-size: 0.9rem;">
                    还没有账号？ <a href="register.jsp" style="color: var(--primary-color); font-weight: bold;">去注册</a>
                </div>
            </form>
        </div>
    </div>
</section>

<!-- 2. 特性展示区域 (白色背景) -->
<section class="features-section">
    <div class="features-container">
        <h2 style="text-align: center; margin-bottom: 3rem; font-size: 2rem;">为什么选择 MusicWeb</h2>
        <div class="grid grid-3">
            <div class="feature-box">
                <div class="feature-icon">🎧</div>
                <h3>千万曲库</h3>
                <p style="color: #666;">收录华语/欧美/日韩等热门歌曲，你想听的这里都有。</p>
            </div>
            <div class="feature-box">
                <div class="feature-icon">💿</div>
                <h3>无损音质</h3>
                <p style="color: #666;">Hi-Res 级别的音质体验，还原录音室级别的听感。</p>
            </div>
            <div class="feature-box">
                <div class="feature-icon">📱</div>
                <h3>多端同步</h3>
                <p style="color: #666;">手机、电脑、平板，随时随地同步你的收藏列表。</p>
            </div>
        </div>
    </div>
</section>

<!-- 3. 热门推荐预览 -->
<section style="padding: 4rem 0; background: #f8fafc;">
    <div class="features-container">
        <h2 style="text-align: center; margin-bottom: 2rem;">热门推荐</h2>
        <div class="song-list" style="grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));">
            <%-- 循环显示几首推荐歌曲，如果数据库没数据则不显示 --%>
            <% for(Song song : recommendedSongs) { %>
            <div class="song-item" style="background: white;">
                <div class="song-cover">
                    <% if(song.getCoverImage() != null && !song.getCoverImage().isEmpty()) { %>
                    <img src="<%=song.getCoverImage()%>" alt="cover" style="width:100%;height:100%;object-fit:cover;border-radius:4px;">
                    <% } else { %>
                    🎵
                    <% } %>
                </div>
                <div class="song-info">
                    <div class="song-title"><%=song.getTitle()%></div>
                    <div class="song-artist"><%=song.getArtist()%></div>
                </div>
            </div>
            <% } %>

            <% if(recommendedSongs.isEmpty()) { %>
            <!-- 静态假数据占位 (当数据库为空时显示) -->
            <div class="song-item" style="background: white;">
                <div class="song-cover">🎵</div>
                <div class="song-info">
                    <div class="song-title">演示歌曲 1</div>
                    <div class="song-artist">歌手 A</div>
                </div>
            </div>
            <div class="song-item" style="background: white;">
                <div class="song-cover">🎵</div>
                <div class="song-info">
                    <div class="song-title">演示歌曲 2</div>
                    <div class="song-artist">歌手 B</div>
                </div>
            </div>
            <% } %>

            <div class="song-item" style="background: white;">
                <div style="display: flex; align-items: center; justify-content: center; width: 100%; height: 100%; color: var(--primary-color); cursor: pointer;" onclick="location.href='register.jsp'">
                    登录查看更多...
                </div>
            </div>
        </div>
    </div>
</section>

<!-- 页脚 -->
<footer style="background: #333; color: #999; padding: 3rem 0; margin-top: 0;">
    <div style="max-width: 1200px; margin: 0 auto; text-align: center;">
        <p>&copy; 2023 MusicWeb 在线音乐平台. All rights reserved.</p>
        <p style="font-size: 0.8rem; margin-top: 0.5rem;">设计灵感致敬网易云音乐</p>
    </div>
</footer>

<script>
    document.addEventListener('DOMContentLoaded', function() {
        // 自动隐藏提示框
        setTimeout(function() {
            const alerts = document.querySelectorAll('.alert-temporary');
            alerts.forEach(alert => {
                alert.style.opacity = '0';
                setTimeout(() => alert.remove(), 500);
            });
        }, 3000);
    });
</script>
</body>
</html>