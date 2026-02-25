<%@ page contentType="text/html;charset=UTF-8" language="java" %>
    <% /* Disable browser caching */ response.setHeader("Cache-Control", "no-cache, no-store, must-revalidate" );
        response.setHeader("Pragma", "no-cache" ); response.setDateHeader("Expires", 0); %>

        <%@ page import="com.music.javabean.*, com.music.dao.*, java.util.*" %>
            <% /* User Login Check */ User user=(User) session.getAttribute("user"); if (user==null) {
                response.sendRedirect("index.jsp"); return; } /* Initialize DAO */ SongDAO songDAO=new SongDAO();
                PlayHistoryDAO playHistoryDAO=new PlayHistoryDAO(); PlaylistDAO playlistDAO=new PlaylistDAO(); /*
                获取用户歌单列表 */ List<Playlist> playlists = playlistDAO.getUserPlaylists(user.getId());
                if (playlists == null) playlists = new ArrayList<>();

                    /* 获取默认歌单（用于收藏统计和收藏歌曲列表） */
                    Playlist defaultPlaylist = playlistDAO.getDefaultPlaylist(user.getId());
                    List<Song> favoriteSongsList = new ArrayList<>();
                            int favoriteCount = 0;
                            if (defaultPlaylist != null) {
                            favoriteSongsList = playlistDAO.getPlaylistSongs(defaultPlaylist.getId());
                            favoriteCount = defaultPlaylist.getSongCount();
                            }


                            /* Get Charts data */
                            List<Song> hotSongs = songDAO.getHotSongs(10);
                                if (hotSongs == null) hotSongs = new ArrayList<>();

                                    List<Song> newSongs = songDAO.getNewSongs(10);
                                        if (newSongs == null) newSongs = new ArrayList<>();

                                            List<Song> favoriteSongs = songDAO.getFavoriteSongs(10);
                                                if (favoriteSongs == null) favoriteSongs = new ArrayList<>();

                                                    /* Get Recommendations */
                                                    List<Song> recommendedSongs =
                                                        songDAO.getRecommendationsByRandom(user.getId(), 5);
                                                        if (recommendedSongs == null) recommendedSongs = new ArrayList<>
                                                            ();

                                                            /* Get Play History */
                                                            List<PlayHistory> playHistory =
                                                                playHistoryDAO.getRecentPlays(user.getId());
                                                                if (playHistory == null) playHistory = new ArrayList<>
                                                                    ();

                                                                    /* Get Display Name */
                                                                    String displayName = (user.getNickname() != null &&
                                                                    !user.getNickname().trim().isEmpty())
                                                                    ? user.getNickname()
                                                                    : user.getUsername();

                                                                    String firstChar = (displayName != null &&
                                                                    !displayName.isEmpty())
                                                                    ? displayName.substring(0, 1)
                                                                    : "U";
                                                                    %>
                                                                    <!DOCTYPE html>
                                                                    <html lang="zh-CN">

                                                                    <head>
                                                                        <meta charset="UTF-8">
                                                                        <meta name="viewport"
                                                                            content="width=device-width, initial-scale=1.0">
                                                                        <title>用户中心 - MusicWeb</title>
                                                                        <link rel="stylesheet"
                                                                            href="${pageContext.request.contextPath}/css/style.css">
                                                                        <link rel="stylesheet"
                                                                            href="${pageContext.request.contextPath}/css/search.css">
                                                                        <link rel="stylesheet"
                                                                            href="${pageContext.request.contextPath}/css/player.css">
                                                                    </head>

                                                                    <body>
                                                                        <!-- 头部导航 -->
                                                                        <header class="header">
                                                                            <div class="nav-container">
                                                                                <a href="index.jsp"
                                                                                    class="logo">MusicWeb</a>
                                                                                <nav class="nav-links">
                                                                                    <a href="user.jsp"
                                                                                        class="nav-link">首页</a>
                                                                                    <a href="#discover"
                                                                                        class="nav-link">发现</a>
                                                                                    <a href="#charts"
                                                                                        class="nav-link">排行榜</a>
                                                                                    <a href="#favorites"
                                                                                        class="nav-link">我的收藏</a>
                                                                                </nav>
                                                                                <div class="user-info">
                                                                                    <div class="user-avatar">
                                                                                        <%= firstChar %>
                                                                                    </div>
                                                                                    <span>欢迎, <%= displayName %></span>
                                                                                    <a href="logout"
                                                                                        class="btn btn-outline"
                                                                                        style="margin-right: 0.5rem;">退出</a>
                                                                                    <a href="settings.jsp"
                                                                                        class="btn btn-secondary">⚙️
                                                                                        设置</a>
                                                                                </div>
                                                                            </div>
                                                                        </header>

                                                                        <!-- 主要内容 -->
                                                                        <main class="main-container">
                                                                            <!-- 用户信息卡片 -->
                                                                            <section class="user-profile">
                                                                                <div class="user-avatar-large">
                                                                                    <%= firstChar %>
                                                                                </div>
                                                                                <div class="user-info">
                                                                                    <h1
                                                                                        style="margin: 0 0 0.5rem 0; font-size: 2rem;">
                                                                                        <%= displayName %>
                                                                                    </h1>
                                                                                    <p style="margin: 0; opacity: 0.9;">
                                                                                        @<%= user.getUsername() %>
                                                                                    </p>
                                                                                    <% if (user.getEmail() !=null &&
                                                                                        !user.getEmail().isEmpty()) { %>
                                                                                        <p
                                                                                            style="margin: 0.5rem 0 0 0; opacity: 0.8;">
                                                                                            📧 <%= user.getEmail() %>
                                                                                        </p>
                                                                                        <% } %>
                                                                                            <% if (user.getPhone()
                                                                                                !=null &&
                                                                                                !user.getPhone().isEmpty())
                                                                                                { %>
                                                                                                <p
                                                                                                    style="margin: 0.5rem 0 0 0; opacity: 0.8;">
                                                                                                    📱 <%=
                                                                                                        user.getPhone()
                                                                                                        %>
                                                                                                </p>
                                                                                                <% } %>
                                                                                </div>
                                                                            </section>

                                                                            <!-- 用户数据统计 -->
                                                                            <div class="user-stats">
                                                                                <div class="stat-card">
                                                                                    <span class="stat-number"
                                                                                        id="fav-count">
                                                                                        <%= favoriteCount %>
                                                                                    </span>
                                                                                    <span class="stat-label">收藏歌曲</span>
                                                                                </div>
                                                                                <div class="stat-card">
                                                                                    <span class="stat-number">
                                                                                        <%= playlists.size() %>
                                                                                    </span>
                                                                                    <span class="stat-label">创建歌单</span>
                                                                                </div>
                                                                                <div class="stat-card">
                                                                                    <span class="stat-number">
                                                                                        <%= PlayHistoryDAO.formatListenDuration(playHistoryDAO.getTotalListenDuration(user.getId()))
                                                                                            %>
                                                                                    </span>
                                                                                    <span class="stat-label">收听时长</span>
                                                                                </div>
                                                                                <div class="stat-card">
                                                                                    <span class="stat-number">
                                                                                        <% /* 获取用户创建时间 */ String
                                                                                            createTime=user.getCreateTime();
                                                                                            if (createTime !=null &&
                                                                                            createTime.length()>= 10) {
                                                                                            out.print(createTime.substring(0,
                                                                                            10));
                                                                                            } else {
                                                                                            out.print("新用户");
                                                                                            }
                                                                                            %>
                                                                                    </span>
                                                                                    <span class="stat-label">加入日期</span>
                                                                                </div>
                                                                            </div>

                                                                            <!-- 搜索模块 (Google 风格) -->
                                                                            <section class="search-section">
                                                                                <div class="search-wrapper">
                                                                                    <form action="search" method="get"
                                                                                        id="search-form">
                                                                                        <div class="google-search-bar">
                                                                                            <div
                                                                                                class="search-icon-wrapper">
                                                                                                <svg viewBox="0 0 24 24"
                                                                                                    width="20"
                                                                                                    height="20"
                                                                                                    fill="none"
                                                                                                    stroke="currentColor"
                                                                                                    stroke-width="2">
                                                                                                    <circle cx="11"
                                                                                                        cy="11" r="8">
                                                                                                    </circle>
                                                                                                    <path
                                                                                                        d="m21 21-4.35-4.35">
                                                                                                    </path>
                                                                                                </svg>
                                                                                            </div>
                                                                                            <input type="text"
                                                                                                name="keyword"
                                                                                                id="search-input"
                                                                                                class="google-search-input"
                                                                                                placeholder="搜索你喜欢的音乐..."
                                                                                                autocomplete="off">
                                                                                            <button type="submit"
                                                                                                class="google-search-btn"
                                                                                                title="搜索">
                                                                                                <svg viewBox="0 0 24 24"
                                                                                                    width="24"
                                                                                                    height="24"
                                                                                                    fill="none"
                                                                                                    stroke="currentColor"
                                                                                                    stroke-width="2">
                                                                                                    <polyline
                                                                                                        points="9 18 15 12 9 6">
                                                                                                    </polyline>
                                                                                                </svg>
                                                                                            </button>
                                                                                        </div>

                                                                                        <div class="search-dropdown"
                                                                                            id="search-history"
                                                                                            style="display: none;">
                                                                                            <div
                                                                                                class="search-dropdown-header">
                                                                                                <span
                                                                                                    class="dropdown-title">搜索历史</span>
                                                                                                <button type="button"
                                                                                                    class="clear-history-btn"
                                                                                                    id="clear-history">清空</button>
                                                                                            </div>
                                                                                            <div class="search-dropdown-list"
                                                                                                id="search-history-list">
                                                                                            </div>
                                                                                        </div>
                                                                                    </form>
                                                                                </div>
                                                                            </section>

                                                                            <!-- 我的歌单 -->
                                                                            <section id="my-playlists">
                                                                                <h2 class="section-title">我的歌单</h2>
                                                                                <% if (playlists.isEmpty()) { %>
                                                                                    <div class="empty-state">
                                                                                        <div class="empty-state-icon">🎵
                                                                                        </div>
                                                                                        <h3>还没有创建歌单</h3>
                                                                                        <p>创建你的第一个歌单，收藏喜欢的音乐吧！</p>
                                                                                        <div class="action-buttons">
                                                                                            <button
                                                                                                class="btn btn-primary"
                                                                                                onclick="showCreatePlaylistModal()">创建歌单</button>
                                                                                        </div>
                                                                                    </div>
                                                                                    <% } else { %>
                                                                                        <div class="playlist-grid">
                                                                                            <% for (Playlist playlist :
                                                                                                playlists) { %>
                                                                                                <div class="playlist-card fade-in"
                                                                                                    onclick="viewPlaylist(<%= playlist.getId() %>)">
                                                                                                    <div
                                                                                                        class="playlist-cover">
                                                                                                        <img src="<%= playlist.getDisplayCover() %>"
                                                                                                            alt="<%= playlist.getName() %>">
                                                                                                    </div>
                                                                                                    <div
                                                                                                        class="playlist-info">
                                                                                                        <h3
                                                                                                            class="playlist-name">
                                                                                                            <%= playlist.getName()
                                                                                                                %>
                                                                                                        </h3>
                                                                                                    </div>
                                                                                                </div>
                                                                                                <% } %>

                                                                                                    <!-- 创建新歌单卡片 -->
                                                                                                    <div class="playlist-card create-playlist"
                                                                                                        onclick="showCreatePlaylistModal()">
                                                                                                        <div
                                                                                                            class="create-icon">
                                                                                                            ➕</div>
                                                                                                        <p>创建新歌单</p>
                                                                                                    </div>
                                                                                        </div>
                                                                                        <% } %>
                                                                            </section>

                                                                            <!-- 创建歌单弹窗 -->
                                                                            <div id="createPlaylistModal" class="modal"
                                                                                style="display: none;">
                                                                                <div class="modal-content">
                                                                                    <div class="modal-header">
                                                                                        <h2>创建新歌单</h2>
                                                                                        <span class="close"
                                                                                            onclick="hideCreatePlaylistModal()">&times;</span>
                                                                                    </div>
                                                                                    <div class="modal-body">
                                                                                        <form id="createPlaylistForm">
                                                                                            <div class="form-group">
                                                                                                <label
                                                                                                    for="playlistName">歌单名称
                                                                                                    *</label>
                                                                                                <input type="text"
                                                                                                    id="playlistName"
                                                                                                    name="name" required
                                                                                                    placeholder="请输入歌单名称"
                                                                                                    maxlength="100">
                                                                                            </div>
                                                                                            <div class="form-group">
                                                                                                <label
                                                                                                    for="playlistDesc">歌单描述（可选）</label>
                                                                                                <textarea
                                                                                                    id="playlistDesc"
                                                                                                    name="description"
                                                                                                    rows="3"
                                                                                                    placeholder="描述一下这个歌单..."
                                                                                                    maxlength="500"></textarea>
                                                                                            </div>
                                                                                            <div class="form-actions">
                                                                                                <button type="button"
                                                                                                    class="btn btn-secondary"
                                                                                                    onclick="hideCreatePlaylistModal()">取消</button>
                                                                                                <button type="submit"
                                                                                                    class="btn btn-primary">创建</button>
                                                                                            </div>
                                                                                        </form>
                                                                                    </div>
                                                                                </div>
                                                                            </div>

                                                                            <!-- 推荐歌曲 -->
                                                                            <section id="discover"
                                                                                style="margin-top: 3rem;">
                                                                                <div
                                                                                    style="display: flex; align-items: flex-end; gap: 1rem; margin-bottom: 1rem;">
                                                                                    <h2 class="section-title"
                                                                                        style="margin-bottom: 0;">每日推荐
                                                                                    </h2>
                                                                                    <button id="refresh-recommend-btn"
                                                                                        title="换一批"
                                                                                        style="background: rgba(255, 255, 255, 0.15); color: white; border: none; border-radius: 50%; width: 32px; height: 32px; cursor: pointer; display: flex; align-items: center; justify-content: center; transition: all 0.3s ease; backdrop-filter: blur(4px); margin-top: 4px;"
                                                                                        onmouseover="this.style.background='rgba(255, 255, 255, 0.25)'; this.style.transform='rotate(90deg)';"
                                                                                        onmouseout="this.style.background='rgba(255, 255, 255, 0.15)'; this.style.transform='rotate(0deg)';">
                                                                                        <svg viewBox="0 0 24 24"
                                                                                            width="18" height="18"
                                                                                            fill="none"
                                                                                            stroke="currentColor"
                                                                                            stroke-width="2"
                                                                                            stroke-linecap="round"
                                                                                            stroke-linejoin="round">
                                                                                            <path d="M23 4v6h-6"></path>
                                                                                            <path d="M1 20v-6h6"></path>
                                                                                            <path
                                                                                                d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15">
                                                                                            </path>
                                                                                        </svg>
                                                                                    </button>
                                                                                </div>

                                                                                <div class="song-list"
                                                                                    id="recommend-list">
                                                                                    <% for (Song song :
                                                                                        recommendedSongs) { boolean
                                                                                        isRecFavorited=playlistDAO.isFavorite(user.getId(),
                                                                                        song.getId());
                                                                                        request.setAttribute("song",
                                                                                        song);
                                                                                        request.setAttribute("isFavorited",
                                                                                        isRecFavorited); %>
                                                                                        <jsp:include
                                                                                            page="includes/song-item.jsp" />
                                                                                        <% } %>
                                                                                </div>
                                                                            </section>

                                                                            <!-- 热门排行榜 -->
                                                                            <section id="charts"
                                                                                style="margin-top: 3rem;">
                                                                                <h2 class="section-title">热门排行榜</h2>
                                                                                <div class="charts-container">
                                                                                    <!-- 热歌榜 -->
                                                                                    <div class="chart-card">
                                                                                        <div class="chart-header"
                                                                                            style="background: linear-gradient(135deg, #667eea, #764ba2);">
                                                                                            <div class="chart-icon">🔥
                                                                                            </div>
                                                                                            <div class="chart-title">
                                                                                                <h3>热歌榜</h3>
                                                                                                <p>最新热门歌曲TOP10</p>
                                                                                            </div>
                                                                                        </div>
                                                                                        <div class="chart-content">
                                                                                            <% if (hotSongs.isEmpty()) {
                                                                                                %>
                                                                                                <div
                                                                                                    class="empty-chart">
                                                                                                    <p>暂无热歌数据</p>
                                                                                                </div>
                                                                                                <% } else { %>
                                                                                                    <% for (int i=0; i <
                                                                                                        Math.min(hotSongs.size(),
                                                                                                        5); i++) { Song
                                                                                                        song=hotSongs.get(i);
                                                                                                        boolean
                                                                                                        isFavorited=playlistDAO.isFavorite(user.getId(),
                                                                                                        song.getId());
                                                                                                        request.setAttribute("song",
                                                                                                        song);
                                                                                                        request.setAttribute("isFavorited",
                                                                                                        isFavorited);
                                                                                                        request.setAttribute("rank",
                                                                                                        i + 1); %>
                                                                                                        <jsp:include
                                                                                                            page="includes/chart-item.jsp" />
                                                                                                        <% } %>
                                                                                                            <% } %>
                                                                                        </div>
                                                                                    </div>

                                                                                    <!-- 新歌榜 -->
                                                                                    <div class="chart-card">
                                                                                        <div class="chart-header"
                                                                                            style="background: linear-gradient(135deg, #f093fb, #f5576c);">
                                                                                            <div class="chart-icon">🆕
                                                                                            </div>
                                                                                            <div class="chart-title">
                                                                                                <h3>新歌榜</h3>
                                                                                                <p>最新发布歌曲</p>
                                                                                            </div>
                                                                                        </div>
                                                                                        <div class="chart-content">
                                                                                            <% if (newSongs.isEmpty()) {
                                                                                                %>
                                                                                                <div
                                                                                                    class="empty-chart">
                                                                                                    <p>暂无新歌数据</p>
                                                                                                </div>
                                                                                                <% } else { %>
                                                                                                    <% for (int i=0; i <
                                                                                                        Math.min(newSongs.size(),
                                                                                                        5); i++) { Song
                                                                                                        song=newSongs.get(i);
                                                                                                        boolean
                                                                                                        isFavorited=playlistDAO.isFavorite(user.getId(),
                                                                                                        song.getId());
                                                                                                        request.setAttribute("song",
                                                                                                        song);
                                                                                                        request.setAttribute("isFavorited",
                                                                                                        isFavorited);
                                                                                                        request.setAttribute("rank",
                                                                                                        i + 1); %>
                                                                                                        <jsp:include
                                                                                                            page="includes/chart-item.jsp" />
                                                                                                        <% } %>
                                                                                                            <% } %>
                                                                                        </div>
                                                                                    </div>

                                                                                    <!-- 收藏榜 -->
                                                                                    <div class="chart-card">
                                                                                        <div class="chart-header"
                                                                                            style="background: linear-gradient(135deg, #4facfe, #00f2fe);">
                                                                                            <div class="chart-icon">❤️
                                                                                            </div>
                                                                                            <div class="chart-title">
                                                                                                <h3>收藏榜</h3>
                                                                                                <p>用户收藏最多的歌曲</p>
                                                                                            </div>
                                                                                        </div>
                                                                                        <div class="chart-content">
                                                                                            <% if
                                                                                                (favoriteSongs.isEmpty())
                                                                                                { %>
                                                                                                <div
                                                                                                    class="empty-chart">
                                                                                                    <p>暂无收藏数据</p>
                                                                                                </div>
                                                                                                <% } else { %>
                                                                                                    <% for (int i=0; i <
                                                                                                        Math.min(favoriteSongs.size(),
                                                                                                        5); i++) { Song
                                                                                                        song=favoriteSongs.get(i);
                                                                                                        boolean
                                                                                                        isFavorited=playlistDAO.isFavorite(user.getId(),
                                                                                                        song.getId());
                                                                                                        request.setAttribute("song",
                                                                                                        song);
                                                                                                        request.setAttribute("isFavorited",
                                                                                                        isFavorited);
                                                                                                        request.setAttribute("rank",
                                                                                                        i + 1); %>
                                                                                                        <jsp:include
                                                                                                            page="includes/chart-item.jsp" />
                                                                                                        <% } %>
                                                                                                            <% } %>
                                                                                        </div>
                                                                                    </div>
                                                                                </div>
                                                                            </section>

                                                                            <!-- 最近播放 -->
                                                                            <section id="recent-plays"
                                                                                style="margin-top: 3rem;">
                                                                                <div
                                                                                    style="display: flex; align-items: flex-end; gap: 1rem; margin-bottom: 1rem;">
                                                                                    <h2 class="section-title"
                                                                                        style="margin-bottom: 0;">最近播放
                                                                                    </h2>
                                                                                    <a href="playHistory.jsp"
                                                                                        title="查看全部播放历史"
                                                                                        style="background: rgba(255, 255, 255, 0.15); color: white; text-decoration: none; padding: 6px 16px; border-radius: 20px; font-size: 0.85rem; display: flex; align-items: center; gap: 4px; transition: all 0.3s ease; backdrop-filter: blur(4px);"
                                                                                        onmouseover="this.style.background='rgba(255, 255, 255, 0.25)';"
                                                                                        onmouseout="this.style.background='rgba(255, 255, 255, 0.15)';">
                                                                                        More
                                                                                        <svg width="14" height="14"
                                                                                            viewBox="0 0 24 24"
                                                                                            fill="none"
                                                                                            stroke="currentColor"
                                                                                            stroke-width="2">
                                                                                            <path d="M9 18l6-6-6-6" />
                                                                                        </svg>
                                                                                    </a>
                                                                                </div>
                                                                                <% if (playHistory.isEmpty()) { %>
                                                                                    <div class="empty-state">
                                                                                        <div class="empty-state-icon">🔥
                                                                                        </div>
                                                                                        <h3>还没有播放记录</h3>
                                                                                        <p>开始播放音乐，记录你的音乐时光</p>
                                                                                    </div>
                                                                                    <% } else { %>
                                                                                        <div class="song-list">
                                                                                            <% java.util.Set<Integer>
                                                                                                addedSongs = new
                                                                                                java.util.HashSet<>();
                                                                                                    int count = 0;
                                                                                                    for (PlayHistory
                                                                                                    history
                                                                                                    : playHistory) {
                                                                                                    if (count >= 10)
                                                                                                    break;
                                                                                                    if
                                                                                                    (addedSongs.contains(history.getSongId()))
                                                                                                    continue;
                                                                                                    addedSongs.add(history.getSongId());
                                                                                                    count++;

                                                                                                    Song song =
                                                                                                    history.getSong();
                                                                                                    boolean isFavorited
                                                                                                    =
                                                                                                    playlistDAO.isFavorite(user.getId(),
                                                                                                    song.getId());
                                                                                                    String playTime =
                                                                                                    history.getPlayTime()
                                                                                                    !=
                                                                                                    null ?
                                                                                                    history.getPlayTime().substring(0,
                                                                                                    16) : "未知时间";

                                                                                                    request.setAttribute("song",
                                                                                                    song);
                                                                                                    request.setAttribute("isFavorited",
                                                                                                    isFavorited);
                                                                                                    request.setAttribute("playTime",
                                                                                                    playTime);
                                                                                                    %>
                                                                                                    <jsp:include
                                                                                                        page="includes/song-item.jsp" />
                                                                                                    <% } %>
                                                                                        </div>
                                                                                        <% } %>
                                                                            </section>
                                                                        </main>

                                                                        <!-- 音乐播放器 -->
                                                                        <audio id="audio-player"></audio>

                                                                        <!-- 底部固定播放条 -->
                                                                        <div class="music-player"
                                                                            style="display: none;">
                                                                            <div class="player-left">
                                                                                <div class="player-cover">
                                                                                    <img id="player-cover"
                                                                                        src="${pageContext.request.contextPath}/img/cover.jpg"
                                                                                        alt="封面">
                                                                                </div>
                                                                                <div class="player-info">
                                                                                    <div class="player-title"
                                                                                        id="player-title">未播放</div>
                                                                                    <div class="player-artist"
                                                                                        id="player-artist"></div>
                                                                                </div>
                                                                            </div>
                                                                            <div class="player-center">
                                                                                <div class="player-controls">
                                                                                    <button class="player-btn"
                                                                                        id="btn-prev"
                                                                                        title="上一曲">⏮️</button>
                                                                                    <button
                                                                                        class="player-btn player-btn-play"
                                                                                        id="btn-play-pause"
                                                                                        title="播放/暂停">▶️</button>
                                                                                    <button class="player-btn"
                                                                                        id="btn-next"
                                                                                        title="下一曲">⏭️</button>
                                                                                </div>
                                                                                <div class="player-progress-bar">
                                                                                    <span class="player-time"
                                                                                        id="current-time">00:00</span>
                                                                                    <div class="progress-container"
                                                                                        id="progress-container">
                                                                                        <div class="progress-bar"
                                                                                            id="progress-bar">
                                                                                            <div
                                                                                                class="progress-handle">
                                                                                            </div>
                                                                                        </div>
                                                                                    </div>
                                                                                    <span class="player-time"
                                                                                        id="total-time">00:00</span>
                                                                                </div>
                                                                            </div>
                                                                            <div class="player-right">
                                                                                <div class="volume-control">
                                                                                    <button class="volume-btn"
                                                                                        id="volume-btn">🔈</button>
                                                                                    <input type="range"
                                                                                        class="volume-slider"
                                                                                        id="volume-slider" min="0"
                                                                                        max="1" step="0.01" value="0.7">
                                                                                </div>
                                                                                <button class="mode-btn" id="mode-btn"
                                                                                    title="播放模式">🔁</button>
                                                                                <button class="queue-btn" id="queue-btn"
                                                                                    title="播放队列">
                                                                                    📑 <span class="queue-count"
                                                                                        id="queue-count">0</span>
                                                                                </button>
                                                                            </div>
                                                                        </div>

                                                                        <div class="play-queue" id="play-queue">
                                                                            <div class="queue-header">
                                                                                <h3 class="queue-title">播放队列</h3>
                                                                                <button class="queue-clear"
                                                                                    id="queue-clear">清空</button>
                                                                            </div>
                                                                            <div class="queue-list" id="queue-list">
                                                                                <div class="queue-empty">
                                                                                    播放队列为空<br />点击歌曲添加到队列</div>
                                                                            </div>
                                                                        </div>

                                                                        <script
                                                                            src="${pageContext.request.contextPath}/js/qqLoginModal.js"></script>
                                                                        <script
                                                                            src="${pageContext.request.contextPath}/js/player.js"></script>
                                                                        <script
                                                                            src="${pageContext.request.contextPath}/js/search.js"></script>
                                                                        <script
                                                                            src="${pageContext.request.contextPath}/js/addToPlaylist.js"></script>
                                                                        <script
                                                                            src="${pageContext.request.contextPath}/js/user-logic.js"></script>
                                                                    </body>

                                                                    </html>