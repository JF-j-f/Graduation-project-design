/**
 * 添加歌曲到歌单功能模块
 * 提供下拉菜单选择歌单和 Toast 提示反馈
 */
(function () {
    'use strict';

    /* 用户歌单缓存 */
    var cachedPlaylists = null;
    var activeDropdown = null;

    /* Toast 提示组件 */
    function showToast(message, type) {
        type = type || 'success';

        /* 移除旧的 toast */
        var existingToast = document.querySelector('.add-playlist-toast');
        if (existingToast) {
            existingToast.remove();
        }

        var toast = document.createElement('div');
        toast.className = 'add-playlist-toast';
        toast.style.cssText = 'position: fixed; bottom: 100px; right: 20px; padding: 12px 24px; border-radius: 8px; color: white; font-size: 14px; z-index: 10000; animation: slideIn 0.3s ease; box-shadow: 0 4px 12px rgba(0,0,0,0.2);';

        if (type === 'success') {
            toast.style.background = 'linear-gradient(135deg, #667eea, #764ba2)';
        } else if (type === 'error') {
            toast.style.background = '#e74c3c';
        } else {
            toast.style.background = '#333';
        }

        toast.textContent = message;
        document.body.appendChild(toast);

        /* 自动消失 */
        setTimeout(function () {
            toast.style.opacity = '0';
            toast.style.transform = 'translateX(100px)';
            toast.style.transition = 'all 0.3s ease';
            setTimeout(function () {
                if (toast.parentNode) {
                    toast.remove();
                }
            }, 300);
        }, 2500);
    }

    /* 获取用户歌单列表 */
    function fetchPlaylists(callback) {
        if (cachedPlaylists) {
            callback(cachedPlaylists);
            return;
        }

        fetch('api/userPlaylists')
            .then(function (r) { return r.json(); })
            .then(function (result) {
                if (result.code === 0 && result.data) {
                    cachedPlaylists = result.data;
                    callback(cachedPlaylists);
                } else {
                    callback([]);
                    console.error('获取歌单失败:', result.message);
                }
            })
            .catch(function (err) {
                callback([]);
                console.error('获取歌单请求失败:', err);
            });
    }

    /* 渲染下拉菜单 */
    function renderDropdown(dropdown, playlists, songId) {
        if (!playlists || playlists.length === 0) {
            dropdown.innerHTML = '<div style="padding: 1rem; text-align: center; color: #888;">暂无歌单</div>';
            return;
        }

        var html = '';
        playlists.forEach(function (playlist) {
            html += '<div class="playlist-dropdown-item" data-playlist-id="' + playlist.id + '" data-song-id="' + songId + '" ' +
                'style="padding: 10px 16px; cursor: pointer; border-bottom: 1px solid #eee; transition: background 0.2s; display: flex; align-items: center; gap: 10px;">' +
                '<span style="font-size: 1.2rem;">' + (playlist.isDefault ? '❤️' : '📁') + '</span>' +
                '<div style="flex: 1; overflow: hidden;">' +
                '<div style="font-size: 14px; color: #333; white-space: nowrap; text-overflow: ellipsis; overflow: hidden;">' + escapeHtml(playlist.name) + '</div>' +
                '<div style="font-size: 12px; color: #888;">' + (playlist.songCount || 0) + ' 首歌曲</div>' +
                '</div>' +
                '</div>';
        });
        dropdown.innerHTML = html;

        /* 绑定点击事件 */
        dropdown.querySelectorAll('.playlist-dropdown-item').forEach(function (item) {
            item.addEventListener('mouseenter', function () {
                this.style.background = '#f5f5f5';
            });
            item.addEventListener('mouseleave', function () {
                this.style.background = '';
            });
            item.addEventListener('click', function (e) {
                e.stopPropagation();
                var playlistId = this.getAttribute('data-playlist-id');
                var songIdAttr = this.getAttribute('data-song-id');
                var playlistName = this.querySelector('div > div').textContent;
                addSongToPlaylist(playlistId, songIdAttr, playlistName);
                closeAllDropdowns();
            });
        });
    }

    /* 添加歌曲到歌单 */
    function addSongToPlaylist(playlistId, songId, playlistName) {
        fetch('playlist?action=addSong&playlistId=' + playlistId + '&songId=' + songId, {
            method: 'POST'
        })
            .then(function (r) { return r.json(); })
            .catch(function () {
                /* 如果返回不是JSON，尝试当成成功处理 */
                return { success: true };
            })
            .then(function (result) {
                if (result.success || result.code === 0) {
                    showToast('已添加到「' + playlistName + '」', 'success');
                    /* 清除缓存以便下次刷新歌单数量 */
                    cachedPlaylists = null;
                } else {
                    showToast(result.message || '添加失败', 'error');
                }
            })
            .catch(function (err) {
                console.error('添加歌曲失败:', err);
                showToast('添加失败，请重试', 'error');
            });
    }

    /* 关闭所有下拉菜单 */
    function closeAllDropdowns() {
        document.querySelectorAll('.playlist-dropdown').forEach(function (d) {
            d.style.display = 'none';
        });
        activeDropdown = null;
    }

    /* HTML转义 */
    function escapeHtml(text) {
        if (!text) return '';
        var div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /* 初始化按钮事件 */
    function initAddToPlaylistButtons() {
        document.querySelectorAll('.add-to-playlist-btn').forEach(function (btn) {
            if (btn.getAttribute('data-initialized') === 'true') return;
            btn.setAttribute('data-initialized', 'true');

            btn.addEventListener('click', function (e) {
                e.preventDefault();
                e.stopPropagation();

                var wrapper = this.closest('.add-to-playlist-wrapper');
                var dropdown = wrapper.querySelector('.playlist-dropdown');
                var songId = this.getAttribute('data-song-id');

                /* 如果当前下拉已打开，则关闭 */
                if (dropdown.style.display === 'block') {
                    dropdown.style.display = 'none';
                    activeDropdown = null;
                    return;
                }

                /* 关闭其他下拉菜单 */
                closeAllDropdowns();

                /* 显示加载状态 */
                dropdown.innerHTML = '<div style="padding: 1rem; text-align: center; color: #888;">加载中...</div>';
                dropdown.style.display = 'block';
                activeDropdown = dropdown;

                /* 获取歌单并渲染 */
                fetchPlaylists(function (playlists) {
                    if (dropdown.style.display === 'block') {
                        renderDropdown(dropdown, playlists, songId);
                    }
                });
            });

            /* 悬停效果 */
            btn.addEventListener('mouseenter', function () {
                this.style.transform = 'scale(1.2)';
                this.style.color = '#667eea';
            });
            btn.addEventListener('mouseleave', function () {
                this.style.transform = '';
                this.style.color = '#666';
            });
        });
    }

    /* 点击页面其他位置关闭下拉菜单 */
    document.addEventListener('click', function (e) {
        if (!e.target.closest('.add-to-playlist-wrapper')) {
            closeAllDropdowns();
        }
    });

    /* 页面加载后初始化 */
    document.addEventListener('DOMContentLoaded', function () {
        initAddToPlaylistButtons();
    });

    /* 暴露到全局方便动态内容调用 */
    window.initAddToPlaylistButtons = initAddToPlaylistButtons;
    window.showAddPlaylistToast = showToast;

})();
