<%@ page contentType="text/html;charset=UTF-8" language="java" %>
    <%@ page import="com.music.javabean.*, com.music.dao.*, java.util.*" %>
        <% User user=(User) session.getAttribute("user"); if (user==null) { response.sendRedirect("index.jsp"); return;
            } String keyword=(String) request.getAttribute("keyword"); String source=(String)
            request.getAttribute("source"); @SuppressWarnings("unchecked") List<Song> searchResults = (List<Song>)
                request.getAttribute("searchResults");
                Integer resultCount = (Integer) request.getAttribute("resultCount");

                if (keyword == null) keyword = "";
                if (source == null) source = "netease";
                if (searchResults == null) searchResults = new ArrayList<>();
                    if (resultCount == null) resultCount = 0;

                    String displayName = (user.getNickname() != null && !user.getNickname().trim().isEmpty()) ?
                    user.getNickname() : user.getUsername();
                    String firstChar = (user.getNickname() != null && !user.getNickname().trim().isEmpty()) ?
                    user.getNickname().substring(0, 1) : user.getUsername().substring(0, 1);
                    %>
                    <!DOCTYPE html>
                    <html lang="zh-CN">

                    <head>
                        <meta charset="UTF-8">
                        <meta name="viewport" content="width=device-width, initial-scale=1.0">
                        <title>搜索结果 - MusicWeb</title>
                        <link rel="stylesheet" href="${pageContext.request.contextPath}/css/style.css">
                        <link rel="stylesheet" href="${pageContext.request.contextPath}/css/search.css">
                        <link rel="stylesheet" href="${pageContext.request.contextPath}/css/player.css">
                        <style>
                            body {
                                overflow-x: hidden;
                                max-width: 100vw;
                                width: 100%;
                            }

                            .section-title {
                                font-size: 1.5rem;
                                margin: 2rem 0 1rem 0;
                                color: var(--text-dark);
                                border-left: 4px solid var(--primary-color);
                                padding-left: 1rem;
                            }

                            .empty-state {
                                text-align: center;
                                padding: 3rem;
                                color: var(--text-light);
                            }

                            .empty-state-icon {
                                font-size: 4rem;
                                margin-bottom: 1rem;
                                opacity: 0.5;
                            }

                            /* 修复收藏按钮样式 */
                            .favorite-form {
                                display: inline !important;
                            }

                            .favorite-btn {
                                background: none !important;
                                border: none !important;
                                font-size: 1.25rem !important;
                                cursor: pointer !important;
                                padding: 0.5rem !important;
                            }

                            .favorite-btn.favorited {
                                color: red !important;
                            }

                            /* 搜索框样式优化 */
                            .search-form-inline {
                                display: inline-flex;
                                align-items: center;
                                gap: 0.5rem;
                                margin-left: 1rem;
                            }

                            .search-input {
                                padding: 0.5rem 1rem;
                                border: 1px solid #ddd;
                                border-radius: 20px;
                                outline: none;
                                min-width: 200px;
                                font-size: 0.9rem;
                            }

                            .search-input:focus {
                                border-color: var(--primary-color);
                                box-shadow: 0 0 0 2px rgba(102, 126, 234, 0.1);
                            }

                            .search-btn {
                                background: linear-gradient(135deg, #667eea, #764ba2);
                                color: white;
                                border: none;
                                padding: 0.5rem 1rem;
                                border-radius: 20px;
                                cursor: pointer;
                                font-size: 0.9rem;
                                white-space: nowrap;
                                transition: transform 0.2s;
                            }

                            .search-btn:hover {
                                transform: scale(1.05);
                            }

                            /* 音乐源选择器 */
                            .source-selector {
                                display: flex;
                                gap: 0.5rem;
                                margin-top: 1rem;
                                justify-content: center;
                            }

                            .source-btn {
                                padding: 0.5rem 1rem;
                                border: 2px solid #ddd;
                                border-radius: 20px;
                                background: white;
                                cursor: pointer;
                                transition: all 0.2s;
                                font-size: 0.9rem;
                            }

                            .source-btn:hover {
                                border-color: var(--primary-color);
                            }

                            .source-btn.active {
                                background: linear-gradient(135deg, #667eea, #764ba2);
                                color: white;
                                border-color: transparent;
                            }

                            /* 来源标签 */
                            .source-tag {
                                display: inline-block;
                                padding: 2px 6px;
                                border-radius: 4px;
                                font-size: 0.7rem;
                                margin-left: 0.5rem;
                                font-weight: bold;
                            }

                            .source-netease {
                                background: #e60026;
                                color: white;
                            }

                            .source-qq {
                                background: #12b7f5;
                                color: white;
                            }
                        </style>
                        <script>
                            window.CURRENT_USER_ID = '<%= user.getUsername() %>';
                        </script>
                    </head>

                    <body>
                        <!-- 头部导航 -->
                        <header class="header">
                            <div class="nav-container">
                                <a href="index.jsp" class="logo">MusicWeb</a>
                                <nav class="nav-links">
                                    <a href="user.jsp" class="nav-link">首页</a>
                                    <a href="#discover" class="nav-link">发现</a>
                                    <a href="#charts" class="nav-link">排行榜</a>
                                    <a href="#favorites" class="nav-link">我的收藏</a>
                                </nav>
                                <div class="user-info">
                                    <div class="user-avatar">
                                        <%= firstChar %>
                                    </div>
                                    <span>欢迎, <%= displayName %></span>
                                    <a href="logout" class="btn btn-outline">退出</a>
                                    <a href="settings.jsp" class="btn btn-secondary">⚙️ 设置</a>
                                </div>
                            </div>
                        </header>

                        <!-- 主要内容 -->
                        <main class="main-container">
                            <!-- 搜索模块 (Google 风格) -->
                            <section class="search-section">
                                <div class="search-wrapper">
                                    <form action="search" method="get" id="search-form">
                                        <div class="google-search-bar">
                                            <!-- 左侧图标 -->
                                            <div class="search-icon-wrapper">
                                                <svg viewBox="0 0 24 24" width="20" height="20" fill="none"
                                                    stroke="currentColor" stroke-width="2">
                                                    <circle cx="11" cy="11" r="8"></circle>
                                                    <path d="m21 21-4.35-4.35"></path>
                                                </svg>
                                            </div>
                                            <!-- 中间输入框 -->
                                            <input type="text" name="keyword" id="search-input" value="<%= keyword %>"
                                                class="google-search-input" placeholder="搜索你喜欢的音乐..."
                                                autocomplete="off">
                                            <!-- 右侧按钮 -->
                                            <button type="submit" class="google-search-btn" title="搜索">
                                                <svg viewBox="0 0 24 24" width="24" height="24" fill="none"
                                                    stroke="currentColor" stroke-width="2">
                                                    <polyline points="9 18 15 12 9 6"></polyline>
                                                </svg>
                                            </button>
                                        </div>

                                        <!-- 搜索历史下拉 -->
                                        <div class="search-dropdown" id="search-history" style="display: none;">
                                            <div class="search-dropdown-header">
                                                <span class="dropdown-title">搜索历史</span>
                                                <button type="button" class="clear-history-btn" id="clear-history">
                                                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"
                                                        stroke-width="2">
                                                        <polyline points="3 6 5 6 21 6"></polyline>
                                                        <path
                                                            d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2">
                                                        </path>
                                                    </svg>
                                                    清空
                                                </button>
                                            </div>
                                            <div class="search-dropdown-list" id="search-history-list">
                                                <!-- 动态加载 -->
                                            </div>
                                        </div>
                                    </form>

                                    <!-- 音乐源选择 -->
                                    <div class="source-selector">
                                        <button type="button" class="source-btn <%= " netease".equals(source) ? "active"
                                            : "" %>"
                                            onclick="searchWithSource('netease')">
                                            🏠 网易云音乐
                                        </button>
                                        <button type="button" class="source-btn <%= " qq".equals(source) ? "active" : ""
                                            %>"
                                            onclick="searchWithSource('qq')">
                                            🎵 QQ音乐
                                        </button>
                                        <button type="button" class="source-btn <%= " all".equals(source) ? "active"
                                            : "" %>"
                                            onclick="searchWithSource('all')">
                                            🌍 全部
                                        </button>
                                    </div>
                                </div>
                            </section>

                            <section>
                                <h2 class="section-title">
                                    <% if (keyword !=null && !keyword.isEmpty()) { %>
                                        搜索 "<%= keyword %>" 的结果 (<%= resultCount %> 首歌曲)
                                                <% } else { %>
                                                    所有歌曲 (<%= resultCount %> 首)
                                                        <% } %>
                                </h2>

                                <% if (searchResults.isEmpty()) { %>
                                    <div class="empty-state">
                                        <div class="empty-state-icon">🔍</div>
                                        <h3>未找到相关歌曲</h3>
                                        <p>试试其他关键词吧，或者 <a href="user.jsp" style="color: var(--primary-color);">返回首页</a>
                                        </p>
                                    </div>
                                    <% } else { %>
                                        <div class="song-list">
                                            <% for (Song song : searchResults) { String songSource=song.getSource();
                                                String externalId=song.getExternalId(); String
                                                coverUrl=song.getCoverUrl(); boolean isExternal=songSource !=null &&
                                                !songSource.isEmpty() && !"local".equals(songSource); %>
                                                <div class="song-item fade-in">
                                                    <div class="song-cover">
                                                        <% if (coverUrl !=null && !coverUrl.isEmpty()) { if
                                                            (!coverUrl.startsWith("http") && !coverUrl.startsWith("/"))
                                                            { coverUrl=request.getContextPath() + "/" + coverUrl; } %>
                                                            <img src="<%= coverUrl %>" alt="封面"
                                                                style="width: 100%; height: 100%; border-radius: 8px; object-fit: cover;">
                                                            <% } else if (song.getCoverImage() !=null &&
                                                                !song.getCoverImage().isEmpty()) { String
                                                                localCoverUrl=song.getCoverImage(); if
                                                                (!localCoverUrl.startsWith("http") &&
                                                                !localCoverUrl.startsWith("/")) {
                                                                localCoverUrl=request.getContextPath() + "/" +
                                                                localCoverUrl; } %>
                                                                <img src="<%= localCoverUrl %>" alt="封面"
                                                                    style="width: 100%; height: 100%; border-radius: 8px; object-fit: cover;">
                                                                <% } else { %>
                                                                    🎵
                                                                    <% } %>
                                                    </div>
                                                    <div class="song-info">
                                                        <div class="song-title">
                                                            <%= song.getTitle() %>
                                                                <% if (isExternal) { %>
                                                                    <span class="source-tag source-<%= songSource %>">
                                                                        <%= "netease" .equals(songSource) ? "网易云" : "QQ"
                                                                            %>
                                                                    </span>
                                                                    <% } %>
                                                                        <% if (song.isVip()) { %>
                                                                            <span class="source-tag"
                                                                                style="background: #ffc107; color: #000; padding: 2px 6px; border-radius: 4px; font-size: 0.7rem; font-weight: bold; margin-left: 0.5rem;">VIP</span>
                                                                            <% } %>
                                                        </div>
                                                        <div class="song-artist">
                                                            <%= song.getArtist() %>
                                                                <% if (song.getAlbum() !=null &&
                                                                    !song.getAlbum().isEmpty()) { %> • <%=
                                                                        song.getAlbum() %>
                                                                        <% } %>
                                                        </div>
                                                        <div style="font-size: 0.8rem; color: var(--text-light);">
                                                            <%= song.getFormattedDuration() %>
                                                        </div>
                                                    </div>
                                                    <div class="song-actions">
                                                        <!-- 添加到歌单按钮 -->
                                                        <div class="add-to-playlist-wrapper"
                                                            style="position: relative; display: inline-block;">
                                                            <button class="add-to-playlist-btn"
                                                                data-song-id="<%= song.getId() %>"
                                                                data-song-title="<%= song.getTitle() %>" title="添加到歌单"
                                                                style="background: none; border: none; font-size: 1.1rem; cursor: pointer; padding: 0.3rem 0.5rem; color: #666; transition: all 0.2s ease;">➕</button>
                                                            <div class="playlist-dropdown"
                                                                style="display: none; position: absolute; top: 100%; right: 0; min-width: 180px; background: white; border-radius: 8px; box-shadow: 0 4px 20px rgba(0,0,0,0.15); z-index: 1000; overflow: hidden;">
                                                                <div class="playlist-dropdown-loading"
                                                                    style="padding: 1rem; text-align: center; color: #888;">
                                                                    加载中...</div>
                                                            </div>
                                                        </div>

                                                        <button class="play-btn" data-song-id="<%= song.getId() %>"
                                                            data-song-title="<%= song.getTitle() %>"
                                                            data-song-artist="<%= song.getArtist() %>"
                                                            data-song-album="<%= song.getAlbum() != null ? song.getAlbum() : "" %>"
                                                            data-song-duration="<%= song.getDuration() %>"
                                                            data-song-source="<%= songSource != null ? songSource : "" %>"
                                                            data-song-external-id="<%= externalId != null ? externalId : "" %>"
                                                            data-song-cover-url="<%= coverUrl != null ? coverUrl : "" %>"
                                                            style="background: none; border: none; font-size: 1.25rem; cursor: pointer; padding: 0.5rem;">▶️</button>
                                                    </div>
                                                </div>
                                                <% } %>
                                        </div>
                                        <% } %>
                            </section>
                        </main>

                        <!-- 音乐播放器 -->
                        <audio id="audio-player"></audio>

                        <!-- 底部固定播放条 -->
                        <div class="music-player" style="display: none;">
                            <!-- 左侧：封面和歌曲信息 -->
                            <div class="player-left">
                                <div class="player-cover">
                                    <img id="player-cover" src="${pageContext.request.contextPath}/img/cover.jpg"
                                        alt="封面">
                                </div>
                                <div class="player-info">
                                    <div class="player-title" id="player-title">未播放</div>
                                    <div class="player-artist" id="player-artist"></div>
                                </div>
                            </div>

                            <!-- 中间：播放控制和进度条 -->
                            <div class="player-center">
                                <div class="player-controls">
                                    <button class="player-btn" id="btn-prev" title="上一曲">⏮️</button>
                                    <button class="player-btn player-btn-play" id="btn-play-pause"
                                        title="播放/暂停">▶️</button>
                                    <button class="player-btn" id="btn-next" title="下一曲">⏭️</button>
                                </div>
                                <div class="player-progress-bar">
                                    <span class="player-time" id="current-time">00:00</span>
                                    <div class="progress-container" id="progress-container">
                                        <div class="progress-bar" id="progress-bar">
                                            <div class="progress-handle"></div>
                                        </div>
                                    </div>
                                    <span class="player-time" id="total-time">00:00</span>
                                </div>
                            </div>

                            <!-- 右侧：音量、模式、播放列表 -->
                            <div class="player-right">
                                <div class="volume-control">
                                    <button class="volume-btn" id="volume-btn">🔊</button>
                                    <input type="range" class="volume-slider" id="volume-slider" min="0" max="1"
                                        step="0.01" value="0.7">
                                </div>
                                <button class="mode-btn" id="mode-btn" title="播放模式">➡️</button>
                                <button class="queue-btn" id="queue-btn" title="播放队列">
                                    📋
                                    <span class="queue-count" id="queue-count">0</span>
                                </button>
                            </div>
                        </div>

                        <!-- 播放队列侧边栏 -->
                        <div class="play-queue" id="play-queue">
                            <div class="queue-header">
                                <h3 class="queue-title">播放队列</h3>
                                <button class="queue-clear" id="queue-clear">清空</button>
                            </div>
                            <div class="queue-list" id="queue-list">
                                <div class="queue-empty">播放队列为空<br />点击歌曲添加到队列</div>
                            </div>
                        </div>

                        <script src="${pageContext.request.contextPath}/js/qqLoginModal.js"></script>
                        <script src="${pageContext.request.contextPath}/js/player.js"></script>
                        <script src="${pageContext.request.contextPath}/js/search.js"></script>
                        <script src="${pageContext.request.contextPath}/js/addToPlaylist.js"></script>
                        <script>
                            // 音乐源切换函数
                            function searchWithSource(source) {
                                const keyword = document.getElementById('search-input').value;
                                window.location.href = 'search?keyword=' + encodeURIComponent(keyword) + '&source=' + source;
                            }

                            // 播放器集成代码
                            document.addEventListener('DOMContentLoaded', function () {
                                setTimeout(function () {
                                    if (typeof player === 'undefined') {
                                        console.error('播放器未初始化');
                                        return;
                                    }

                                    // 播放按钮点击事件
                                    document.querySelectorAll('.play-btn').forEach(btn => {
                                        btn.addEventListener('click', function (e) {
                                            e.preventDefault();
                                            e.stopPropagation();

                                            const songId = this.getAttribute('data-song-id');
                                            const songTitle = this.getAttribute('data-song-title');
                                            const songArtist = this.getAttribute('data-song-artist');
                                            const songAlbum = this.getAttribute('data-song-album');
                                            const songDuration = this.getAttribute('data-song-duration');
                                            const songSource = this.getAttribute('data-song-source');
                                            const externalId = this.getAttribute('data-song-external-id');
                                            const coverUrl = this.getAttribute('data-song-cover-url');

                                            const song = {
                                                id: parseInt(songId) || 0,
                                                title: songTitle || '未知歌曲',
                                                artist: songArtist || '未知歌手',
                                                album: songAlbum || '',
                                                duration: parseInt(songDuration) || 0,
                                                source: songSource || '',
                                                externalId: externalId || '',
                                                coverUrl: coverUrl || ''
                                            };

                                            console.log('播放歌曲:', song);
                                            player.playSong(song);
                                        });
                                    });
                                }, 500);
                            });
                        </script>
                    </body>

                    </html>