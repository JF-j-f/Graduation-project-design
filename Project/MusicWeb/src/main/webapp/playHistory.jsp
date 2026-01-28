<%@ page contentType="text/html;charset=UTF-8" language="java" %>
<%@ page import="com.music.javabean.User" %>
<%
    /* 检查用户是否登录 */
    User user = (User) session.getAttribute("user");
    if (user == null) {
        response.sendRedirect("index.jsp");
        return;
    }
    /* 获取用户显示名称和首字母 */
    String displayName = (user.getNickname() != null && !user.getNickname().trim().isEmpty()) 
        ? user.getNickname() : user.getUsername();
    String firstChar = (user.getNickname() != null && !user.getNickname().trim().isEmpty()) 
        ? user.getNickname().substring(0, 1) : user.getUsername().substring(0, 1);
%>
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>播放历史 - MusicWeb</title>
    <link rel="stylesheet" href="css/style.css">
    <link rel="stylesheet" href="css/player.css">
    <style>
        .history-container { max-width: 1200px; margin: 0 auto; padding: 2rem; min-height: 100vh; }
        .history-header { display: flex; align-items: center; gap: 1rem; margin-bottom: 2rem; }
        .back-btn { background: rgba(255, 255, 255, 0.15); color: white; border: none; border-radius: 50%; width: 40px; height: 40px; cursor: pointer; display: flex; align-items: center; justify-content: center; transition: all 0.3s ease; }
        .back-btn:hover { background: rgba(255, 255, 255, 0.25); }
        .history-title { font-size: 1.8rem; font-weight: bold; color: white; }
        .tab-container { display: flex; gap: 0.5rem; margin-bottom: 2rem; background: rgba(255, 255, 255, 0.1); padding: 0.5rem; border-radius: 12px; width: fit-content; }
        .tab-btn { background: transparent; color: rgba(255, 255, 255, 0.7); border: none; padding: 0.75rem 1.5rem; border-radius: 8px; cursor: pointer; font-size: 0.95rem; transition: all 0.3s ease; }
        .tab-btn:hover { background: rgba(255, 255, 255, 0.1); color: white; }
        .tab-btn.active { background: rgba(255, 255, 255, 0.2); color: white; font-weight: 600; }
        .loading { text-align: center; padding: 3rem; color: rgba(255, 255, 255, 0.6); }
        .loading-spinner { width: 40px; height: 40px; border: 3px solid rgba(255, 255, 255, 0.2); border-top-color: white; border-radius: 50%; animation: spin 1s linear infinite; margin: 0 auto 1rem; }
        @keyframes spin { to { transform: rotate(360deg); } }
        .empty-state { text-align: center; padding: 4rem 2rem; color: rgba(255, 255, 255, 0.6); }
        .empty-state-icon { font-size: 4rem; margin-bottom: 1rem; }
        .history-list { display: flex; flex-direction: column; gap: 0.75rem; }
        .pagination { display: flex; justify-content: center; align-items: center; gap: 1rem; margin-top: 2rem; padding: 1rem; }
        .page-btn { background: rgba(255, 255, 255, 0.15); color: white; border: none; padding: 0.75rem 1.5rem; border-radius: 8px; cursor: pointer; transition: all 0.3s ease; }
        .page-btn:hover:not(:disabled) { background: rgba(255, 255, 255, 0.25); }
        .page-btn:disabled { opacity: 0.4; cursor: not-allowed; }
        .page-info { color: rgba(255, 255, 255, 0.7); font-size: 0.9rem; }
        .stats { color: rgba(255, 255, 255, 0.6); font-size: 0.85rem; margin-bottom: 1rem; }
    </style>
</head>
<body>
    <header class="header">
        <div class="nav-container">
            <a href="index.jsp" class="logo">MusicWeb</a>
            <nav class="nav-links">
                <a href="user.jsp" class="nav-link">首页</a>
                <a href="user.jsp#discover" class="nav-link">发现</a>
                <a href="user.jsp#charts" class="nav-link">排行榜</a>
                <a href="user.jsp#favorites" class="nav-link">我的收藏</a>
            </nav>
            <div class="user-info">
                <div class="user-avatar"><%= firstChar %></div>
                <span>欢迎, <%= displayName %></span>
                <a href="logout" class="btn btn-outline">退出</a>
            </div>
        </div>
    </header>
    <div class="history-container">
        <div class="history-header">
            <button class="back-btn" onclick="history.back()" title="返回">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 12H5M12 19l-7-7 7-7" /></svg>
            </button>
            <h1 class="history-title">播放历史</h1>
        </div>
        <div class="tab-container">
            <button class="tab-btn active" data-days="7">最近一周</button>
            <button class="tab-btn" data-days="30">最近一个月</button>
            <button class="tab-btn" data-days="90">最近三月</button>
        </div>
        <div class="stats" id="stats">加载中...</div>
        <div id="history-content">
            <div class="loading"><div class="loading-spinner"></div><p>正在加载...</p></div>
        </div>
        <div class="pagination" id="pagination" style="display: none;">
            <button class="page-btn" id="prev-btn" onclick="loadPage(currentPage - 1)">上一页</button>
            <span class="page-info" id="page-info">第 1 页</span>
            <button class="page-btn" id="next-btn" onclick="loadPage(currentPage + 1)">下一页</button>
        </div>
    </div>
    <audio id="audio-player"></audio>
    <div class="music-player" style="display: none;">
        <div class="player-left">
            <div class="player-cover"><img id="player-cover" src="img/cover.jpg" alt="封面"></div>
            <div class="player-info"><div class="player-title" id="player-title">未播放</div><div class="player-artist" id="player-artist"></div></div>
        </div>
        <div class="player-center">
            <div class="player-controls">
                <button class="player-btn" id="btn-prev" title="上一曲"></button>
                <button class="player-btn player-btn-play" id="btn-play-pause" title="播放/暂停"></button>
                <button class="player-btn" id="btn-next" title="下一曲"></button>
            </div>
            <div class="player-progress-bar">
                <span class="player-time" id="current-time">00:00</span>
                <div class="progress-container" id="progress-container"><div class="progress-bar" id="progress-bar"><div class="progress-handle"></div></div></div>
                <span class="player-time" id="total-time">00:00</span>
            </div>
        </div>
        <div class="player-right">
            <div class="volume-control"><button class="volume-btn" id="volume-btn"></button><input type="range" class="volume-slider" id="volume-slider" min="0" max="1" step="0.01" value="0.7"></div>
            <button class="mode-btn" id="mode-btn" title="播放模式"></button>
            <button class="queue-btn" id="queue-btn" title="播放队列"> <span class="queue-count" id="queue-count">0</span></button>
        </div>
    </div>
    <div class="play-queue" id="play-queue">
        <div class="queue-header"><h3 class="queue-title">播放队列</h3><button class="queue-clear" id="queue-clear">清空</button></div>
        <div class="queue-list" id="queue-list"><div class="queue-empty">播放队列为空</div></div>
    </div>
    <script src="js/qqLoginModal.js"></script>
    <script src="js/player.js"></script>
    <script>
        var currentDays = 7;
        var currentPage = 1;
        var totalPages = 1;
        var pageSize = 25;

        document.addEventListener('DOMContentLoaded', function() {
            var tabBtns = document.querySelectorAll('.tab-btn');
            tabBtns.forEach(function(btn) {
                btn.addEventListener('click', function() {
                    tabBtns.forEach(function(b) { b.classList.remove('active'); });
                    btn.classList.add('active');
                    currentDays = parseInt(btn.dataset.days);
                    currentPage = 1;
                    loadHistory();
                });
            });
            loadHistory();
        });

        function loadHistory() {
            var content = document.getElementById('history-content');
            content.innerHTML = '<div class="loading"><div class="loading-spinner"></div><p>正在加载...</p></div>';
            fetch('api/playHistoryPage?days=' + currentDays + '&page=' + currentPage + '&pageSize=' + pageSize)
                .then(function(r) { return r.json(); })
                .then(function(result) {
                    if (result.code === 0) { renderHistory(result.data); }
                    else { content.innerHTML = '<div class="empty-state"><p>加载失败</p></div>'; }
                })
                .catch(function(e) { content.innerHTML = '<div class="empty-state"><p>加载失败</p></div>'; });
        }

        function renderHistory(data) {
            var content = document.getElementById('history-content');
            var pagination = document.getElementById('pagination');
            var stats = document.getElementById('stats');
            totalPages = data.totalPages;
            var daysText = currentDays === 7 ? '一周' : currentDays === 30 ? '一个月' : '三个月';
            stats.textContent = '最近' + daysText + '共播放 ' + data.totalItems + ' 首歌曲';
            if (!data.items || data.items.length === 0) {
                content.innerHTML = '<div class="empty-state"><div class="empty-state-icon"></div><h3>暂无播放记录</h3></div>';
                pagination.style.display = 'none';
                return;
            }
            var html = '<div class="history-list">';
            data.items.forEach(function(item) {
                var song = item.song || {};
                var playTime = item.playTime ? item.playTime.substring(0, 16) : '';
                var coverImg = song.coverImage || 'img/cover.jpg';
                html += '<div class="song-item fade-in">' +
                    '<div class="song-cover"><img src="' + escapeHtml(coverImg) + '" alt="" style="width:100%;height:100%;border-radius:8px;object-fit:cover;" onerror="this.src=\'img/cover.jpg\'"></div>' +
                    '<div class="song-info"><div class="song-title">' + escapeHtml(song.title || '未知') + '</div>' +
                    '<div class="song-artist">' + escapeHtml(song.artist || '') + '</div>' +
                    '<div style="font-size:0.8rem;color:var(--text-light);">播放于: ' + playTime + '</div></div>' +
                    '<div class="song-actions"><button onclick="playSong(' + song.id + ',\'' + escapeJs(song.title) + '\',\'' + escapeJs(song.artist) + '\',\'' + escapeJs(song.album) + '\',' + (song.duration||0) + ')" style="background:none;border:none;font-size:1.25rem;cursor:pointer;"></button></div></div>';
            });
            html += '</div>';
            content.innerHTML = html;
            if (totalPages > 1) {
                pagination.style.display = 'flex';
                document.getElementById('page-info').textContent = '第 ' + currentPage + ' 页 / 共 ' + totalPages + ' 页';
                document.getElementById('prev-btn').disabled = currentPage <= 1;
                document.getElementById('next-btn').disabled = currentPage >= totalPages;
            } else { pagination.style.display = 'none'; }
        }

        function loadPage(page) {
            if (page < 1 || page > totalPages) return;
            currentPage = page;
            loadHistory();
            window.scrollTo({ top: 0, behavior: 'smooth' });
        }

        function playSong(id, title, artist, album, duration) {
            if (typeof player !== 'undefined') {
                player.playSong({ id: id, title: title, artist: artist, album: album, duration: duration });
            }
        }

        function escapeHtml(text) {
            if (!text) return '';
            var div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        function escapeJs(text) {
            if (!text) return '';
            return text.replace(/'/g, "\\'").replace(/"/g, '\\"');
        }
    </script>
</body>
</html>
