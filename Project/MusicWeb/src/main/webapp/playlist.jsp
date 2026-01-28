<%@ page contentType="text/html;charset=UTF-8" language="java" %>
<%@ page import="com.music.javabean.*, com.music.dao.*, java.util.*" %>
<%
    // 检查用户是否登录
    User user = (User) session.getAttribute("user");
    if (user == null) {
        response.sendRedirect("index.jsp");
        return;
    }

    // 获取歌单信息（由 PlaylistServlet 传递）
    Playlist playlist = (Playlist) request.getAttribute("playlist");
    if (playlist == null) {
        response.sendRedirect("user.jsp");
        return;
    }

    // 获取歌单中的歌曲列表
    List<Song> songs = playlist.getSongs();
    if (songs == null) {
        songs = new ArrayList<>();
    }

    // 初始化 DAO
    FavoriteDAO favoriteDAO = new FavoriteDAO();
%>
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title><%= playlist.getName() %> - MusicWeb</title>
    <link rel="stylesheet" href="css/style.css">
    <link rel="stylesheet" href="css/player.css">
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
                <h1 class="playlist-title"><%= playlist.getName() %></h1>
                <% if (playlist.getDescription() != null && !playlist.getDescription().isEmpty()) { %>
                <p class="playlist-description"><%= playlist.getDescription() %></p>
                <% } %>
                <div class="playlist-stats">
                    <span>📊 <%= songs.size() %> 首歌曲</span>
                    <span>📅 创建于 <%= playlist.getCreateTime() %></span>
                </div>
                <div class="playlist-actions">
                    <button class="btn btn-primary" onclick="playAll()" style="padding: 0.75rem 2rem; font-size: 1rem;">
                        ▶️ 播放全部
                    </button>
                    <% if (!playlist.isDefault()) { %>
                    <button class="btn btn-secondary" onclick="editPlaylist()" style="padding: 0.75rem 1.5rem;">
                        ✏️ 编辑
                    </button>
                    <button class="btn btn-danger" onclick="deletePlaylist()" style="padding: 0.75rem 1.5rem;">
                        🗑️ 删除
                    </button>
                    <% } %>
                </div>
            </div>
        </div>
    </section>

    <!-- 歌曲列表 -->
    <section class="playlist-songs" style="margin-top: 3rem;">
        <h2 class="section-title">歌曲列表</h2>
        <% if (songs.isEmpty()) { %>
        <div class="empty-state">
            <div class="empty-state-icon">🎵</div>
            <h3>歌单还是空的</h3>
            <p>快去添加你喜欢的歌曲吧！</p>
            <div class="action-buttons">
                <a href="user.jsp#discover" class="btn btn-primary">发现音乐</a>
            </div>
        </div>
        <% } else { %>
        <div class="song-list">
            <% for (int i = 0; i < songs.size(); i++) {
                Song song = songs.get(i);
                boolean isFavorited = favoriteDAO.isFavorite(user.getId(), song.getId());
            %>
            <div class="song-item fade-in" id="song-item-<%= song.getId() %>">
                <div class="song-number"><%= i + 1 %></div>
                <div class="song-cover">
                    <% if (song.getCoverImage() != null && !song.getCoverImage().isEmpty()) { %>
                    <img src="<%= song.getCoverImage() %>" alt="封面">
                    <% } else { %>
                    🎵
                    <% } %>
                </div>
                <div class="song-info">
                    <div class="song-title"><%= song.getTitle() %></div>
                    <div class="song-artist"><%= song.getArtist() %> • <%= song.getAlbum() %></div>
                </div>
                <div class="song-duration"><%= song.getFormattedDuration() %></div>
                <div class="song-actions">
                    <button class="play-btn" data-song-id="<%= song.getId() %>"
                            data-song-title="<%= song.getTitle() %>"
                            data-song-artist="<%= song.getArtist() %>"
                            data-song-album="<%= song.getAlbum() %>"
                            data-song-duration="<%= song.getDuration() %>"
                            style="background: none; border: none; font-size: 1.25rem; cursor: pointer; padding: 0.5rem;">▶️</button>

                    <button class="favorite-btn-ajax <%= isFavorited ? "favorited" : "" %>"
                            data-action="<%= isFavorited ? "remove" : "add" %>"
                            data-song-id="<%= song.getId() %>"
                            style="background: none; border: none; font-size: 1.25rem; cursor: pointer; padding: 0.5rem; color: <%= isFavorited ? "red" : "#666" %>;">
                        <%= isFavorited ? "❤️" : "🤍" %>
                    </button>

                    <button class="remove-from-playlist-btn" data-song-id="<%= song.getId() %>"
                            style="background: none; border: none; font-size: 1.25rem; cursor: pointer; padding: 0.5rem; color: #666;"
                            title="从歌单移除">
                        ➖
                    </button>
                </div>
            </div>
            <% } %>
        </div>
        <% } %>
    </section>
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
                    <button type="button" class="btn btn-secondary" onclick="hideEditModal()">取消</button>
                    <button type="submit" class="btn btn-primary">保存</button>
                </div>
            </form>
        </div>
    </div>
</div>

<!-- 播放器 -->
<div id="player-container"></div>

<script src="js/player.js"></script>
<script>
    const playlistId = <%= playlist.getId() %>;
    const isDefaultPlaylist = <%= playlist.isDefault() %>;

    document.addEventListener('DOMContentLoaded', function() {

        // --- 播放功能 ---
        document.body.addEventListener('click', function(e) {
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
        window.playAll = function() {
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
        document.body.addEventListener('click', function(e) {
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
        document.body.addEventListener('click', function(e) {
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
        window.editPlaylist = function() {
            document.getElementById('editPlaylistModal').style.display = 'flex';
            document.getElementById('editPlaylistName').focus();
        };

        window.hideEditModal = function() {
            document.getElementById('editPlaylistModal').style.display = 'none';
        };

        const editForm = document.getElementById('editPlaylistForm');
        if (editForm) {
            editForm.addEventListener('submit', function(e) {
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
        window.deletePlaylist = function() {
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
        window.addEventListener('click', function(e) {
            const modal = document.getElementById('editPlaylistModal');
            if (e.target === modal) {
                hideEditModal();
            }
        });
    });
</script>
</body>
</html>
