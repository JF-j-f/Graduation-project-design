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

/* ============================================================
   v4.0: 调整口味 Modal 逻辑
   ============================================================ */
var tasteModal = (function () {
    var overlay         = null;
    var selectedSati    = null;   // 当前选中满意度
    var selectedGenres  = new Set();
    var artistList      = [];     // 当前艺术家列表
    var blockedGenres   = new Set();  // 屏蔽的流派
    var blockedArtists  = [];         // 屏蔽的歌手

    // ── 初始化 ──────────────────────────────────────────────
    function init() {
        overlay = document.getElementById('taste-modal-overlay');
        if (!overlay) return;

        // 绑定打开按钮
        var btn = document.getElementById('taste-feedback-btn');
        if (btn) btn.addEventListener('click', open);

        // 满意度按钮
        document.querySelectorAll('.sati-btn').forEach(function (b) {
            b.addEventListener('click', function () {
                selectedSati = this.dataset.val;
                document.querySelectorAll('.sati-btn').forEach(function (x) {
                    x.style.background = 'transparent';
                    x.style.color = 'rgba(255,255,255,0.8)';
                    x.style.borderColor = 'rgba(255,255,255,0.2)';
                });
                this.style.background = 'rgba(102,126,234,0.5)';
                this.style.color = '#fff';
                this.style.borderColor = 'rgba(102,126,234,0.8)';
            });
        });

        // 流派 Tag 按钮
        document.querySelectorAll('.genre-tag').forEach(function (t) {
            t.addEventListener('click', function () {
                var genre = this.dataset.genre;
                if (selectedGenres.has(genre)) {
                    selectedGenres.delete(genre);
                    this.style.background = 'transparent';
                    this.style.color = 'rgba(255,255,255,0.75)';
                    this.style.borderColor = 'rgba(255,255,255,0.18)';
                } else {
                    selectedGenres.add(genre);
                    this.style.background = 'rgba(102,126,234,0.45)';
                    this.style.color = '#fff';
                    this.style.borderColor = 'rgba(102,126,234,0.7)';
                }
            });
        });

        // 屏蔽流派 Tag 按钮
        document.querySelectorAll('.block-genre-tag').forEach(function (t) {
            t.addEventListener('click', function () {
                var genre = this.dataset.genre;
                if (blockedGenres.has(genre)) {
                    // 取消屏蔽
                    unblock('genre', genre, this);
                } else {
                    // 添加屏蔽
                    blockGenre(genre, this);
                }
            });
        });

        // 提交按钮
        var submitBtn = document.getElementById('taste-submit-btn');
        if (submitBtn) submitBtn.addEventListener('click', submit);

        // 点击遮罩关闭
        overlay.addEventListener('click', function (e) {
            if (e.target === overlay) close();
        });
    }

    // ── 打开 Modal，并从后端加载已有偏好 ─────────────────────
    function open() {
        if (!overlay) return;
        overlay.style.display = 'flex';
        // 重置状态
        selectedSati = null;
        selectedGenres.clear();
        artistList = [];
        document.querySelectorAll('.sati-btn').forEach(function (b) {
            b.style.background = 'transparent'; b.style.color = 'rgba(255,255,255,0.8)';
            b.style.borderColor = 'rgba(255,255,255,0.2)';
        });
        document.querySelectorAll('.genre-tag').forEach(function (t) {
            t.style.background = 'transparent'; t.style.color = 'rgba(255,255,255,0.75)';
            t.style.borderColor = 'rgba(255,255,255,0.18)';
        });
        renderArtistChips();

        // 加载屏蔽列表
        loadBlocks();

        // 加载已有偏好并预填
        fetch('api/userPreference').then(function (r) { return r.json(); }).then(function (data) {
            if (!data.success) return;
            // 预选流派
            if (data.preferredGenres) {
                data.preferredGenres.split(';').forEach(function (g) {
                    var g2 = g.trim();
                    var tag = document.querySelector('.genre-tag[data-genre="' + g2 + '"]');
                    if (tag) {
                        selectedGenres.add(g2);
                        tag.style.background = 'rgba(102,126,234,0.45)';
                        tag.style.color = '#fff';
                        tag.style.borderColor = 'rgba(102,126,234,0.7)';
                    }
                });
            }
            // 预填艺术家
            if (data.preferredArtists) {
                data.preferredArtists.split(';').forEach(function (a) {
                    var a2 = a.trim(); if (a2 && !artistList.includes(a2)) artistList.push(a2);
                });
                renderArtistChips();
            }
        }).catch(function () {});
    }

    function close() {
        if (overlay) overlay.style.display = 'none';
    }

    // ── 艺术家 Chip ───────────────────────────────────────────
    function addArtist() {
        var input = document.getElementById('artist-input');
        var val = input.value.trim();
        if (val && !artistList.includes(val)) { artistList.push(val); renderArtistChips(); }
        input.value = '';
    }

    function renderArtistChips() {
        var container = document.getElementById('artist-chips');
        if (!container) return;
        container.innerHTML = artistList.map(function (a, i) {
            return '<span style="display:inline-flex;align-items:center;gap:5px;background:rgba(118,75,162,0.4);'
                + 'border:1px solid rgba(118,75,162,0.6);border-radius:14px;padding:4px 10px;font-size:12px;color:#fff;">'
                + escHtml(a)
                + '<span onclick="tasteModal.removeArtist(' + i + ')" style="cursor:pointer;opacity:0.7;font-size:14px;line-height:1;">&times;</span>'
                + '</span>';
        }).join('');
    }

    function removeArtist(index) {
        artistList.splice(index, 1);
        renderArtistChips();
    }

    // ── 屏蔽管理 ─────────────────────────────────────────────
    function loadBlocks() {
        blockedGenres.clear();
        blockedArtists = [];
        renderBlockedArtistChips();
        // 重置 block genre tag 样式
        document.querySelectorAll('.block-genre-tag').forEach(function (t) {
            t.style.background = 'transparent';
            t.style.color = 'rgba(255,255,255,0.55)';
            t.style.borderColor = 'rgba(255,255,255,0.18)';
        });

        fetch('api/blockContent').then(function (r) { return r.json(); }).then(function (data) {
            if (!data.success || !data.blocks) return;
            data.blocks.forEach(function (b) {
                if (!b.isActive) return;
                if (b.type === 'genre') {
                    blockedGenres.add(b.value);
                    var tag = document.querySelector('.block-genre-tag[data-genre="' + b.value + '"]');
                    if (tag) {
                        tag.style.background = 'rgba(255,80,80,0.35)';
                        tag.style.color = '#ff6b6b';
                        tag.style.borderColor = 'rgba(255,80,80,0.5)';
                    }
                } else if (b.type === 'artist') {
                    blockedArtists.push(b.value);
                }
            });
            renderBlockedArtistChips();
        }).catch(function () {});
    }

    function blockGenre(genre, tagEl) {
        fetch('api/blockContent', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ type: 'genre', value: genre })
        }).then(function (r) { return r.json(); }).then(function (data) {
            if (data.success) {
                blockedGenres.add(genre);
                tagEl.style.background = 'rgba(255,80,80,0.35)';
                tagEl.style.color = '#ff6b6b';
                tagEl.style.borderColor = 'rgba(255,80,80,0.5)';
                showToast('已屏蔽流派：' + genre);
            } else {
                showToast(data.message || '操作失败', '#e74c3c');
            }
        }).catch(function () { showToast('网络错误', '#e74c3c'); });
    }

    function blockArtistAction() {
        var input = document.getElementById('block-artist-input');
        var val = input.value.trim();
        if (!val) return;
        input.value = '';

        fetch('api/blockContent', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ type: 'artist', value: val })
        }).then(function (r) { return r.json(); }).then(function (data) {
            if (data.success && !blockedArtists.includes(val)) {
                blockedArtists.push(val);
                renderBlockedArtistChips();
                showToast('已屏蔽歌手：' + val);
            } else {
                showToast(data.message || '操作失败', '#e74c3c');
            }
        }).catch(function () { showToast('网络错误', '#e74c3c'); });
    }

    function unblock(type, value, tagEl) {
        fetch('api/blockContent?type=' + encodeURIComponent(type) + '&value=' + encodeURIComponent(value), {
            method: 'DELETE'
        }).then(function (r) { return r.json(); }).then(function (data) {
            if (data.success) {
                if (type === 'genre') {
                    blockedGenres.delete(value);
                    if (tagEl) {
                        tagEl.style.background = 'transparent';
                        tagEl.style.color = 'rgba(255,255,255,0.55)';
                        tagEl.style.borderColor = 'rgba(255,255,255,0.18)';
                    }
                } else {
                    blockedArtists = blockedArtists.filter(function (a) { return a !== value; });
                    renderBlockedArtistChips();
                }
                showToast('已取消屏蔽：' + value);
            }
        }).catch(function () { showToast('网络错误', '#e74c3c'); });
    }

    function renderBlockedArtistChips() {
        var container = document.getElementById('block-artist-chips');
        if (!container) return;
        container.innerHTML = blockedArtists.map(function (a, i) {
            return '<span style="display:inline-flex;align-items:center;gap:5px;background:rgba(255,80,80,0.3);'
                + 'border:1px solid rgba(255,80,80,0.5);border-radius:14px;padding:4px 10px;font-size:12px;color:#ff6b6b;">'
                + escHtml(a)
                + '<span onclick="tasteModal.unblockArtist(\'' + escHtml(a).replace(/'/g, "\\'") + '\')" '
                + 'style="cursor:pointer;opacity:0.7;font-size:14px;line-height:1;">&times;</span>'
                + '</span>';
        }).join('');
    }

    function unblockArtist(name) {
        unblock('artist', name, null);
    }

    // ── 提交 ─────────────────────────────────────────────────
    function submit() {
        if (!selectedSati) {
            showToast('请先选择满意度 😊', '#e74c3c');
            return;
        }
        var payload = {
            satisfaction: selectedSati,
            genres:  Array.from(selectedGenres),
            artists: artistList.slice()
        };
        document.getElementById('taste-submit-btn').disabled = true;
        fetch('api/userPreference', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        }).then(function (r) { return r.json(); })
          .then(function (data) {
              document.getElementById('taste-submit-btn').disabled = false;
              if (data.success) {
                  close();
                  showToast('✅ 偏好已更新，明日推荐将更贴合您的口味');
              } else {
                  showToast('❌ 保存失败：' + (data.message || '未知错误'), '#e74c3c');
              }
          }).catch(function () {
              document.getElementById('taste-submit-btn').disabled = false;
              showToast('❌ 网络错误，请稍后重试', '#e74c3c');
          });
    }

    // ── Toast 通知 ────────────────────────────────────────────
    function showToast(msg, color) {
        color = color || 'rgba(40,40,60,0.95)';
        var el = document.createElement('div');
        el.textContent = msg;
        el.style.cssText = 'position:fixed;top:24px;right:24px;background:' + color
            + ';color:#fff;padding:12px 20px;border-radius:10px;z-index:99999;font-size:14px;'
            + 'box-shadow:0 4px 20px rgba(0,0,0,0.4);transition:opacity 0.3s;';
        document.body.appendChild(el);
        setTimeout(function () { el.style.opacity = '0'; setTimeout(function () { el.remove(); }, 300); }, 3000);
    }

    function escHtml(s) { return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

    // 页面加载完成后初始化
    document.addEventListener('DOMContentLoaded', init);

    // 暴露公共接口
    return {
        open: open, close: close,
        addArtist: addArtist, removeArtist: removeArtist,
        blockArtist: blockArtistAction, unblockArtist: unblockArtist
    };
})();

/* ============================================================
   v4.0: 一键播放每日推荐
   将推荐列表全部歌曲加入队列并从第一首开始播放
   ============================================================ */
document.addEventListener('DOMContentLoaded', function () {
    var playAllBtn = document.getElementById('play-all-recommend-btn');
    if (!playAllBtn) return;

    playAllBtn.addEventListener('click', function () {
        if (typeof player === 'undefined') {
            console.error('[一键播放] 播放器未初始化');
            return;
        }
        var playBtns = document.querySelectorAll('#recommend-list .play-btn');
        if (!playBtns.length) {
            console.warn('[一键播放] 推荐列表为空');
            return;
        }

        // 直接重置队列（不弹 confirm）
        player.playQueue = [];
        player.currentIndex = -1;

        // 收集全部推荐歌曲并加入队列
        playBtns.forEach(function (btn) {
            var song = {
                id:       parseInt(btn.dataset.songId),
                title:    btn.dataset.songTitle   || '未知歌曲',
                artist:   btn.dataset.songArtist  || '未知歌手',
                album:    btn.dataset.songAlbum   || '',
                duration: parseInt(btn.dataset.songDuration) || 0
            };
            player.playQueue.push(song);
        });

        // 从第一首开始播放
        player.playQueueItem(0);
        player.updateQueueUI && player.updateQueueUI();
    });
});
