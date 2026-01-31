<%@ page contentType="text/html;charset=UTF-8" language="java" %>
    <%@ page import="com.music.javabean.*, com.music.dao.*, java.util.*" %>
        <% /* 检查用户是否登录 */ User user=(User) session.getAttribute("user"); if (user==null) {
            response.sendRedirect("index.jsp"); return; } /* 获取歌单信息（由 PlaylistServlet 传递） */ Playlist
            playlist=(Playlist) request.getAttribute("playlist"); if (playlist==null) {
            response.sendRedirect("user.jsp"); return; } %>
            <!DOCTYPE html>
            <html lang="zh-CN">

            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>
                    <%= playlist.getName() %> - MusicWeb
                </title>
                <link rel="stylesheet" href="${pageContext.request.contextPath}/css/style.css">
                <link rel="stylesheet" href="${pageContext.request.contextPath}/css/player.css">
            </head>

            <body>
                <!-- 头部导航 -->
                <header class="header">
                    <div class="nav-container">
                        <div class="logo">
                            <a href="user.jsp">🎵 MusicWeb</a>
                        </div>
                        <nav class="nav-menu">
                            <a href="user.jsp">首页</a>
                            <a href="user.jsp#my-playlists" class="active">我的歌单</a>
                            <a href="settings.jsp">设置</a>
                            <a href="logout">退出</a>
                        </nav>
                    </div>
                </header>

                <div class="container" style="padding-top: 100px; max-width: 1200px; margin: 0 auto;">
                    <!-- 歌单头部信息 -->
                    <section class="playlist-header">
                        <div class="playlist-header-content">
                            <div class="playlist-cover-large">
                                <img src="<%= playlist.getDisplayCover() %>" alt="歌单封面">
                            </div>
                            <div class="playlist-header-info">
                                <div class="playlist-type-badge">
                                    <%= playlist.isDefault() ? "默认歌单" : "自定义歌单" %>
                                </div>
                                <h1 class="playlist-title">
                                    <%= playlist.getName() %>
                                </h1>
                                <% if (playlist.getDescription() !=null && !playlist.getDescription().isEmpty()) { %>
                                    <p class="playlist-description">
                                        <%= playlist.getDescription() %>
                                    </p>
                                    <% } %>
                                        <div class="playlist-stats">
                                            <span id="song-count">📊 加载中...</span>
                                            <span>📅 创建于 <%= playlist.getCreateTime() %></span>
                                        </div>
                                        <div class="playlist-actions">
                                            <button class="btn btn-primary" onclick="playAll()"
                                                style="padding: 0.75rem 2rem; font-size: 1rem;">
                                                ▶️ 播放全部
                                            </button>
                                            <% if (!playlist.isDefault()) { %>
                                                <button class="btn btn-secondary" onclick="editPlaylist()"
                                                    style="padding: 0.75rem 1.5rem;">
                                                    ✏️ 编辑
                                                </button>
                                                <button class="btn btn-danger" onclick="deletePlaylist()"
                                                    style="padding: 0.75rem 1.5rem;">
                                                    🗑️ 删除
                                                </button>
                                                <% } %>
                                        </div>
                            </div>
                        </div>
                    </section>

                    <!-- 歌曲列表 -->
                    <section class="playlist-songs" style="margin-top: 3rem;">
                        <div
                            style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem;">
                            <h2 class="section-title" style="margin: 0;">歌曲列表</h2>

                            <!-- 筛选排序控件 -->
                            <div class="sort-controls" style="display: flex; gap: 1rem; align-items: center;">
                                <label style="color: rgba(255, 255, 255, 0.7); font-size: 0.9rem;">排序方式：</label>
                                <select id="sortBySelect"
                                    style="padding: 0.5rem 1rem; border-radius: 8px; background: rgba(255, 255, 255, 0.15); color: white; border: none; cursor: pointer;">
                                    <option value="time" style="background: white; color: black;">添加时间</option>
                                    <option value="artist" style="background: white; color: black;">歌手</option>
                                    <option value="album" style="background: white; color: black;">专辑</option>
                                    <option value="year" style="background: white; color: black;">年份</option>
                                    <option value="playcount" style="background: white; color: black;">播放次数</option>
                                </select>
                                <button id="toggleOrderBtn" class="btn btn-secondary"
                                    style="padding: 0.5rem 1rem; min-width: 80px;" title="切换排序方向">
                                    ⬇️ 降序
                                </button>
                            </div>
                        </div>

                        <!-- 动态内容容器 -->
                        <div id="songs-content">
                            <div class="loading"
                                style="text-align: center; padding: 3rem; color: rgba(255, 255, 255, 0.6);">
                                <div class="loading-spinner"
                                    style="width: 40px; height: 40px; border: 3px solid rgba(255, 255, 255, 0.2); border-top-color: white; border-radius: 50%; animation: spin 1s linear infinite; margin: 0 auto 1rem;">
                                </div>
                                <p>正在加载歌曲...</p>
                            </div>
                        </div>

                        <!-- 分页控件 -->
                        <div id="pagination" class="pagination"
                            style="display: none; justify-content: center; align-items: center; gap: 1rem; margin-top: 2rem; padding: 1rem;">
                            <button class="page-btn" id="prev-btn" onclick="loadPage(currentPage - 1)"
                                style="background: rgba(255, 255, 255, 0.15); color: white; border: none; padding: 0.75rem 1.5rem; border-radius: 8px; cursor: pointer; transition: all 0.3s ease;">上一页</button>
                            <span class="page-info" id="page-info"
                                style="color: rgba(255, 255, 255, 0.7); font-size: 0.9rem;">第 1 页</span>
                            <button class="page-btn" id="next-btn" onclick="loadPage(currentPage + 1)"
                                style="background: rgba(255, 255, 255, 0.15); color: white; border: none; padding: 0.75rem 1.5rem; border-radius: 8px; cursor: pointer; transition: all 0.3s ease;">下一页</button>
                        </div>
                    </section>

                    <style>
                        @keyframes spin {
                            to {
                                transform: rotate(360deg);
                            }
                        }

                        .page-btn:hover:not(:disabled) {
                            background: rgba(255, 255, 255, 0.25);
                        }

                        .page-btn:disabled {
                            opacity: 0.4;
                            cursor: not-allowed;
                        }
                    </style>
                </div>

                <!-- 编辑歌单弹窗 -->
                <div id="editPlaylistModal" class="modal" style="display: none;">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h2>编辑歌单</h2>
                            <span class="close" onclick="hideEditModal()">&times;</span>
                        </div>
                        <div class="modal-body">
                            <form id="editPlaylistForm">
                                <div class="form-group">
                                    <label for="editPlaylistName">歌单名称 *</label>
                                    <input type="text" id="editPlaylistName" name="name" required
                                        value="<%= playlist.getName() %>" maxlength="100">
                                </div>
                                <div class="form-group">
                                    <label for="editPlaylistDesc">歌单描述（可选）</label>
                                    <textarea id="editPlaylistDesc" name="description" rows="3"
                                        maxlength="500"><%= playlist.getDescription() != null ? playlist.getDescription() : "" %></textarea>
                                </div>
                                <div class="form-actions">
                                    <button type="button" class="btn btn-secondary"
                                        onclick="hideEditModal()">取消</button>
                                    <button type="submit" class="btn btn-primary">保存</button>
                                </div>
                            </form>
                        </div>
                    </div>
                </div>

                <!-- 音乐播放器 -->
                <audio id="audio-player"></audio>

                <!-- 底部固定播放条 -->
                <div class="music-player" style="display: none;">
                    <div class="player-left">
                        <div class="player-cover">
                            <img id="player-cover" src="${pageContext.request.contextPath}/img/cover.jpg" alt="封面">
                        </div>
                        <div class="player-info">
                            <div class="player-title" id="player-title">未播放</div>
                            <div class="player-artist" id="player-artist"></div>
                        </div>
                    </div>
                    <div class="player-center">
                        <div class="player-controls">
                            <button class="player-btn" id="btn-prev" title="上一曲">⏮️</button>
                            <button class="player-btn player-btn-play" id="btn-play-pause" title="播放/暂停">▶️</button>
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
                    <div class="player-right">
                        <div class="volume-control">
                            <button class="volume-btn" id="volume-btn">🔈</button>
                            <input type="range" class="volume-slider" id="volume-slider" min="0" max="1" step="0.01"
                                value="0.7">
                        </div>
                        <button class="mode-btn" id="mode-btn" title="播放模式">🔁</button>
                        <button class="queue-btn" id="queue-btn" title="播放队列">
                            📑 <span class="queue-count" id="queue-count">0</span>
                        </button>
                    </div>
                </div>

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
                <script>
                    const playlistId = <%= playlist.getId() %>;
                    const isDefaultPlaylist = <%= playlist.isDefault() %>;

                    document.addEventListener('DOMContentLoaded', function () {
                        /* 分页和筛选变量 - 暴露到全局以便 onclick 访问 */
                        window.currentPage = 1;
                        window.totalPages = 1;
                        window.currentSortBy = 'time';
                        window.currentOrder = 'desc';
                        var pageSize = 25;

                        /* Ajax 加载歌曲 */
                        function loadSongs() {
                            var content = document.getElementById('songs-content');
                            content.innerHTML = '<div class="loading" style="text-align: center; padding: 3rem; color: rgba(255, 255, 255, 0.6);"><div class="loading-spinner" style="width: 40px; height: 40px; border: 3px solid rgba(255, 255, 255, 0.2); border-top-color: white; border-radius: 50%; animation: spin 1s linear infinite; margin: 0 auto 1rem;"></div><p>正在加载...</p></div>';

                            var url = 'api/playlistSongsPage?playlistId=' + playlistId + '&page=' + currentPage + '&pageSize=' + pageSize + '&sortBy=' + currentSortBy + '&order=' + currentOrder;

                            fetch(url)
                                .then(r => r.json())
                                .then(result => {
                                    if (result.code === 0) {
                                        renderSongs(result.data);
                                    } else {
                                        content.innerHTML = '<div class="empty-state"><p>加载失败: ' + result.message + '</p></div>';
                                    }
                                })
                                .catch(err => {
                                    console.error('加载歌曲失败:', err);
                                    content.innerHTML = '<div class="empty-state"><p>加载失败，请刷新重试</p></div>';
                                });
                        }

                        /* 渲染歌曲列表 */
                        function renderSongs(data) {
                            var content = document.getElementById('songs-content');
                            var pagination = document.getElementById('pagination');
                            var songCountSpan = document.getElementById('song-count');

                            totalPages = data.totalPages;
                            songCountSpan.textContent = '📊 ' + data.totalItems + ' 首歌曲';

                            if (!data.items || data.items.length === 0) {
                                content.innerHTML = '<div class="empty-state"><div class="empty-state-icon">🎵</div><h3>歌单还是空的</h3><p>快去添加你喜欢的歌曲吧！</p><div class="action-buttons"><a href="user.jsp#discover" class="btn btn-primary">发现音乐</a></div></div>';
                                pagination.style.display = 'none';
                                return;
                            }

                            var html = '<div class="song-list">';
                            data.items.forEach(function (song, index) {
                                var coverImg = song.coverImage || 'img/cover.jpg';
                                var num = (currentPage - 1) * pageSize + index + 1;
                                var isFav = song.isFavorited;
                                var favAction = isFav ? 'remove' : 'add';
                                var favIcon = isFav ? '❤️' : '🤍';
                                var favColor = isFav ? 'red' : '#666';
                                var favClass = 'favorite-btn-ajax' + (isFav ? ' favorited' : '');

                                html += '<div class="song-item fade-in" id="song-item-' + song.id + '">' +
                                    '<div class="song-number">' + num + '</div>' +
                                    '<div class="song-cover"><img src="' + escapeHtml(coverImg) + '" alt="封面" style="width:100%;height:100%;border-radius:8px;object-fit:cover;" onerror="this.src=\'img/cover.jpg\'"></div>' +
                                    '<div class="song-info">' +
                                    '<div class="song-title">' + escapeHtml(song.title || '未知') + '</div>' +
                                    '<div class="song-artist">' + escapeHtml(song.artist || '') + ' • ' + escapeHtml(song.album || '') + '</div>' +
                                    '</div>' +
                                    '<div class="song-duration">' + formatDuration(song.duration || 0) + '</div>' +
                                    '<div class="song-actions">' +
                                    '<button class="play-btn" data-song-id="' + song.id + '" data-song-title="' + escapeAttr(song.title) + '" data-song-artist="' + escapeAttr(song.artist) + '" data-song-album="' + escapeAttr(song.album) + '" data-song-duration="' + song.duration + '" style="background:none;border:none;font-size:1.25rem;cursor:pointer;padding:0.5rem;">▶️</button>' +
                                    '<button class="' + favClass + '" data-action="' + favAction + '" data-song-id="' + song.id + '" style="background:none;border:none;font-size:1.25rem;cursor:pointer;padding:0.5rem;color:' + favColor + ';">' + favIcon + '</button>' +
                                    '<button class="remove-from-playlist-btn" data-song-id="' + song.id + '" style="background:none;border:none;font-size:1.25rem;cursor:pointer;padding:0.5rem;color:#666;" title="从歌单移除">➖</button>' +
                                    '</div>' +
                                    '</div>';
                            });
                            html += '</div>';
                            content.innerHTML = html;

                            /* 更新分页控件 */
                            if (totalPages > 1) {
                                pagination.style.display = 'flex';
                                document.getElementById('page-info').textContent = '第 ' + currentPage + ' 页 / 共 ' + totalPages + ' 页';
                                document.getElementById('prev-btn').disabled = currentPage <= 1;
                                document.getElementById('next-btn').disabled = currentPage >= totalPages;
                            } else {
                                pagination.style.display = 'none';
                            }
                        }

                        /* 工具函数 */
                        function escapeHtml(text) {
                            if (!text) return '';
                            var div = document.createElement('div');
                            div.textContent = text;
                            return div.innerHTML;
                        }

                        function escapeAttr(text) {
                            if (!text) return '';
                            return text.replace(/"/g, '&quot;').replace(/'/g, '&#39;');
                        }

                        function formatDuration(seconds) {
                            var m = Math.floor(seconds / 60);
                            var s = seconds % 60;
                            return m + ':' + (s < 10 ? '0' : '') + s;
                        }

                        /* 分页功能 */
                        window.loadPage = function (page) {
                            if (page < 1 || page > totalPages) return;
                            currentPage = page;
                            loadSongs();
                            window.scrollTo({ top: 0, behavior: 'smooth' });
                        };

                        // === 筛选排序功能 ===
                        document.getElementById('sortBySelect').addEventListener('change', function (e) {
                            currentSortBy = e.target.value;
                            currentPage = 1;
                            loadSongs();
                        });

                        document.getElementById('toggleOrderBtn').addEventListener('click', function () {
                            currentOrder = currentOrder === 'desc' ? 'asc' : 'desc';
                            this.textContent = currentOrder === 'desc' ? '⬇️ 降序' : '⬆️ 升序';
                            currentPage = 1;
                            loadSongs();
                        });

                        // 初始加载
                        loadSongs();

                        // --- 播放功能 ---
                        document.body.addEventListener('click', function (e) {
                            const btn = e.target.closest('.play-btn');
                            if (btn) {
                                e.preventDefault();

                                if (typeof player === 'undefined') {
                                    console.error('播放器未初始化');
                                    return;
                                }

                                const song = {
                                    id: parseInt(btn.dataset.songId),
                                    title: btn.dataset.songTitle || '未知歌曲',
                                    artist: btn.dataset.songArtist || '未知艺术家',
                                    album: btn.dataset.songAlbum || '未知专辑',
                                    duration: parseInt(btn.dataset.songDuration) || 0
                                };

                                player.addToQueue(song);
                                player.play(song);
                            }
                        });

                        // --- 播放全部 ---
                        window.playAll = function () {
                            if (typeof player === 'undefined') {
                                alert('播放器未初始化');
                                return;
                            }

                            const playBtns = document.querySelectorAll('.play-btn');
                            if (playBtns.length === 0) {
                                alert('歌单中没有歌曲');
                                return;
                            }

                            // 清空播放队列
                            player.clearQueue();

                            // 添加所有歌曲到队列
                            playBtns.forEach(btn => {
                                const song = {
                                    id: parseInt(btn.dataset.songId),
                                    title: btn.dataset.songTitle || '未知歌曲',
                                    artist: btn.dataset.songArtist || '未知艺术家',
                                    album: btn.dataset.songAlbum || '未知专辑',
                                    duration: parseInt(btn.dataset.songDuration) || 0
                                };
                                player.addToQueue(song);
                            });

                            // 播放第一首
                            const firstBtn = playBtns[0];
                            const firstSong = {
                                id: parseInt(firstBtn.dataset.songId),
                                title: firstBtn.dataset.songTitle,
                                artist: firstBtn.dataset.songArtist,
                                album: firstBtn.dataset.songAlbum,
                                duration: parseInt(firstBtn.dataset.songDuration)
                            };
                            player.play(firstSong);
                        };

                        // --- 收藏功能 ---
                        document.body.addEventListener('click', function (e) {
                            const btn = e.target.closest('.favorite-btn-ajax');
                            if (btn) {
                                e.preventDefault();

                                const songId = btn.dataset.songId;
                                const currentAction = btn.dataset.action;

                                fetch('favorite', {
                                    method: 'POST',
                                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                                    body: 'action=' + currentAction + '&songId=' + songId
                                })
                                    .then(response => {
                                        if (response.ok || response.redirected) {
                                            const isFavorited = currentAction === 'add';
                                            btn.textContent = isFavorited ? '❤️' : '🤍';
                                            btn.style.color = isFavorited ? 'red' : '#666';
                                            btn.dataset.action = isFavorited ? 'remove' : 'add';
                                            if (isFavorited) {
                                                btn.classList.add('favorited');
                                            } else {
                                                btn.classList.remove('favorited');
                                            }
                                        }
                                    })
                                    .catch(error => {
                                        console.error('收藏操作失败:', error);
                                    });
                            }
                        });

                        // --- 从歌单移除歌曲 ---
                        document.body.addEventListener('click', function (e) {
                            const btn = e.target.closest('.remove-from-playlist-btn');
                            if (btn) {
                                e.preventDefault();

                                if (!confirm('确定要从歌单中移除这首歌曲吗？')) {
                                    return;
                                }

                                const songId = btn.dataset.songId;

                                fetch('playlist', {
                                    method: 'POST',
                                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                                    body: 'action=removeSong&playlistId=' + playlistId + '&songId=' + songId
                                })
                                    .then(response => response.json())
                                    .then(data => {
                                        if (data.success) {
                                            // 移除DOM元素
                                            const songItem = document.getElementById('song-item-' + songId);
                                            if (songItem) {
                                                songItem.style.opacity = '0';
                                                setTimeout(() => songItem.remove(), 300);
                                            }

                                            // 更新歌曲数量
                                            const statsSpan = document.querySelector('.playlist-stats span:first-child');
                                            if (statsSpan) {
                                                const currentCount = parseInt(statsSpan.textContent.match(/\d+/)[0]);
                                                statsSpan.textContent = '📊 ' + (currentCount - 1) + ' 首歌曲';
                                            }

                                            // 如果歌单为空，刷新页面显示空状态
                                            if (document.querySelectorAll('.song-item').length === 1) {
                                                setTimeout(() => window.location.reload(), 500);
                                            }
                                        } else {
                                            alert('移除失败：' + data.message);
                                        }
                                    })
                                    .catch(error => {
                                        console.error('移除歌曲失败:', error);
                                        alert('移除失败，请重试');
                                    });
                            }
                        });

                        // --- 编辑歌单 ---
                        window.editPlaylist = function () {
                            document.getElementById('editPlaylistModal').style.display = 'flex';
                            document.getElementById('editPlaylistName').focus();
                        };

                        window.hideEditModal = function () {
                            document.getElementById('editPlaylistModal').style.display = 'none';
                        };

                        const editForm = document.getElementById('editPlaylistForm');
                        if (editForm) {
                            editForm.addEventListener('submit', function (e) {
                                e.preventDefault();

                                const formData = new FormData(this);
                                const name = formData.get('name').trim();
                                const description = formData.get('description').trim();

                                if (!name) {
                                    alert('请输入歌单名称');
                                    return;
                                }

                                fetch('playlist', {
                                    method: 'POST',
                                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                                    body: 'action=update&playlistId=' + playlistId +
                                        '&name=' + encodeURIComponent(name) +
                                        '&description=' + encodeURIComponent(description)
                                })
                                    .then(response => response.json())
                                    .then(data => {
                                        if (data.success) {
                                            alert('更新成功！');
                                            window.location.reload();
                                        } else {
                                            alert('更新失败：' + data.message);
                                        }
                                    })
                                    .catch(error => {
                                        console.error('更新歌单失败:', error);
                                        alert('更新失败，请重试');
                                    });
                            });
                        }

                        // --- 删除歌单 ---
                        window.deletePlaylist = function () {
                            if (isDefaultPlaylist) {
                                alert('默认歌单不可删除');
                                return;
                            }

                            if (!confirm('确定要删除这个歌单吗？歌单中的歌曲将全部移除。')) {
                                return;
                            }

                            fetch('playlist', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                                body: 'action=delete&playlistId=' + playlistId
                            })
                                .then(response => response.json())
                                .then(data => {
                                    if (data.success) {
                                        alert('歌单已删除');
                                        window.location.href = 'user.jsp#my-playlists';
                                    } else {
                                        alert('删除失败：' + data.message);
                                    }
                                })
                                .catch(error => {
                                    console.error('删除歌单失败:', error);
                                    alert('删除失败，请重试');
                                });
                        };

                        // 点击弹窗外部关闭
                        window.addEventListener('click', function (e) {
                            const modal = document.getElementById('editPlaylistModal');
                            if (e.target === modal) {
                                hideEditModal();
                            }
                        });
                    });
                </script>
            </body>

            </html>