document.addEventListener('DOMContentLoaded', function () {

    // --- 1. 播放功能 (使用事件委托，更稳定) ---
    document.body.addEventListener('click', function (e) {
        // 查找是否点击了 play-btn 或其子元素
        const btn = e.target.closest('.play-btn');
        if (btn) {
            e.preventDefault();

            // 确保播放器对象存在
            if (typeof player === 'undefined') {
                console.error('播放器未初始化');
                return;
            }

            // 获取数据
            const song = {
                id: parseInt(btn.dataset.songId),
                title: btn.dataset.songTitle || '未知歌曲',
                artist: btn.dataset.songArtist || '未知歌手',
                album: btn.dataset.songAlbum || '',
                duration: parseInt(btn.dataset.songDuration) || 0
            };

            // 播放
            player.playSong(song);
        }
    });

    // --- 2. AJAX 收藏功能 (关键修复：不刷新页面) ---
    document.body.addEventListener('click', function (e) {
        const btn = e.target.closest('.favorite-btn-ajax');
        if (btn) {
            e.preventDefault();

            const songId = btn.dataset.songId;
            const currentAction = btn.dataset.action; // 'add' or 'remove'

            // 发送 AJAX 请求
            fetch('favorite', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
                body: 'action=' + currentAction + '&songId=' + songId
            })
                .then(response => {
                    if (response.ok || response.redirected) {
                        // UI 更新
                        if (currentAction === 'add') {
                            // 变成已收藏状态
                            updateButtonState(songId, true);
                        } else {
                            // 变成未收藏状态
                            updateButtonState(songId, false);
                        }
                    } else {
                        console.error('操作失败');
                    }
                })
                .catch(err => console.error('网络错误:', err));
        }
    });

    // 辅助函数：更新页面上所有该歌曲的按钮状态
    function updateButtonState(songId, isFavorited) {
        const allBtns = document.querySelectorAll('.favorite-btn-ajax[data-song-id="' + songId + '"]');
        allBtns.forEach(btn => {
            if (isFavorited) {
                btn.innerHTML = '❤️';
                btn.classList.add('favorited');
                btn.style.color = 'red';
                btn.dataset.action = 'remove';
            } else {
                btn.innerHTML = '🤍';
                btn.classList.remove('favorited');
                btn.style.color = 'inherit';
                btn.dataset.action = 'add';
            }
        });

        // 如果是在"我的收藏"列表中取消收藏，隐藏该项 (可选)
        if (!isFavorited) {
            const favItem = document.getElementById('fav-item-' + songId);
            if (favItem) {
                favItem.style.opacity = '0.5'; // 变灰提示已移除
            }
        }
    }

    // --- 3. 刷新推荐功能 ---
    var refreshBtn = document.getElementById('refresh-recommend-btn');
    var recommendOffset = 5; // 初始页面已经加载了 0~4

    if (refreshBtn) {
        refreshBtn.addEventListener('click', function () {
            var btn = this;
            var list = document.getElementById('recommend-list');

            // 1. 添加旋转动画类
            btn.style.transform = 'rotate(360deg)';
            list.style.opacity = '0.5';

            // 2. 发起请求带上 offset
            fetch('api/refreshRecommend?offset=' + recommendOffset)
                .then(function (response) { return response.json(); })
                .then(function (songs) {

                    // 如果拉到底了（后端不足5首说明这20发子弹打光了），重置游标从头开始
                    if (songs.length < 5) {
                        recommendOffset = 0;
                    } else {
                        recommendOffset += 5;
                    }
                    // 3. 清空列表
                    list.innerHTML = '';

                    // 4. 重新渲染 (使用字符串拼接代替模板字符串，解决 JSP 冲突)
                    songs.forEach(function (song) {
                        // 构建封面 HTML
                        var coverHtml = song.coverImage ?
                            '<img src="' + song.coverImage + '" alt="封面" style="width: 100%; height: 100%; border-radius: 8px; object-fit: cover;">' :
                            '🎵';

                        // 构建收藏按钮状态
                        var favClass = song.isFavorited ? 'favorited' : '';
                        var favAction = song.isFavorited ? 'remove' : 'add';
                        var favIcon = song.isFavorited ? '❤️' : '🤍';
                        var favColor = song.isFavorited ? 'red' : 'inherit';

                        // 构建完整的 HTML 字符串
                        var html =
                            '<div class="song-item fade-in">' +
                            '<div class="song-cover">' +
                            coverHtml +
                            '</div>' +
                            '<div class="song-info">' +
                            '<div class="song-title">' + song.title + '</div>' +
                            '<div class="song-artist">' + song.artist + ' - ' + song.album + '</div>' +
                            '</div>' +
                            '<div class="song-actions">' +
                            '<button class="play-btn" ' +
                            'data-song-id="' + song.id + '" ' +
                            'data-song-title="' + song.title + '" ' +
                            'data-song-artist="' + song.artist + '" ' +
                            'data-song-album="' + song.album + '" ' +
                            'data-song-duration="' + song.duration + '" ' +
                            'style="background: none; border: none; font-size: 1.25rem; cursor: pointer; padding: 0.5rem;">▶️</button>' +
                            '<button class="favorite-btn-ajax ' + favClass + '" ' +
                            'data-action="' + favAction + '" ' +
                            'data-song-id="' + song.id + '" ' +
                            'style="background: none; border: none; font-size: 1.25rem; cursor: pointer; padding: 0.5rem; color: ' + favColor + ';">' +
                            favIcon +
                            '</button>' +
                            '</div>' +
                            '</div>';

                        list.innerHTML += html;
                    });

                    // 5. 恢复样式
                    list.style.opacity = '1';
                    setTimeout(function () {
                        btn.style.transform = 'rotate(0deg)';
                    }, 500);
                })
                .catch(function (error) {
                    console.error('刷新推荐失败:', error);
                    list.style.opacity = '1';
                    btn.style.transform = 'rotate(0deg)';
                });
        });
    }

    // --- 4. 歌单管理功能 ---

    /**
     * 处理创建歌单表单提交
     */
    const createPlaylistForm = document.getElementById('createPlaylistForm');
    if (createPlaylistForm) {
        createPlaylistForm.addEventListener('submit', function (e) {
            e.preventDefault();

            const formData = new FormData(this);
            const name = formData.get('name').trim();
            const description = formData.get('description').trim();

            if (!name) {
                alert('请输入歌单名称');
                return;
            }

            // 发送创建请求
            fetch('playlist?action=create', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded'
                },
                body: 'action=create&name=' + encodeURIComponent(name) +
                    '&description=' + encodeURIComponent(description)
            })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        alert('歌单创建成功！');
                        window.location.reload();
                    } else {
                        alert('创建失败：' + data.message);
                    }
                })
                .catch(error => {
                    console.error('创建歌单失败:', error);
                    alert('创建失败，请重试');
                });
        });
    }

    // 点击弹窗外部关闭
    window.addEventListener('click', function (e) {
        const modal = document.getElementById('createPlaylistModal');
        if (e.target === modal) {
            hideCreatePlaylistModal();
        }
    });
});

// --- 全局函数 (用于 onclick 调用) ---

/**
 * 查看歌单详情
 */
window.viewPlaylist = function (playlistId) {
    window.location.href = 'playlist?action=view&id=' + playlistId;
};

/**
 * 显示创建歌单弹窗
 */
window.showCreatePlaylistModal = function () {
    document.getElementById('createPlaylistModal').style.display = 'flex';
    document.getElementById('playlistName').focus();
};

/**
 * 隐藏创建歌单弹窗
 */
window.hideCreatePlaylistModal = function () {
    document.getElementById('createPlaylistModal').style.display = 'none';
    document.getElementById('createPlaylistForm').reset();
};
