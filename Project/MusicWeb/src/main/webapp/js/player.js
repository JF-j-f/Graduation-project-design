/* ============================================
   MusicWeb 音乐播放器核心类
   功能：播放控制、队列管理、播放模式、历史记录
   ============================================ */

class AudioPlayer {
    constructor() {
        // 播放器元素
        this.audio = document.getElementById('audio-player');

        // 播放队列
        this.playQueue = [];
        this.currentIndex = -1;

        // 播放模式：'order'(顺序), 'loop'(列表循环), 'single'(单曲循环), 'random'(随机)
        this.playMode = localStorage.getItem('playMode') || 'order';

        // 音量设置
        this.volume = parseFloat(localStorage.getItem('volume') || '0.7');

        // 播放历史
        this.playHistory = [];

        // v3.1.0: 播放历史计时器（3秒后记录）
        this.playHistoryTimer = null;
        this.playHistoryRecorded = false;

        // 初始化
        this.init();
    }

    /* ============================================
       初始化播放器
       ============================================ */
    init() {
        // 设置初始音量
        this.audio.volume = this.volume;

        // 绑定事件监听器
        this.bindEvents();

        // 更新UI
        this.updateModeUI();
        this.updateVolumeUI();

        console.log('音乐播放器初始化完成');
    }

    /* ============================================
       绑定所有事件监听器
       ============================================ */
    bindEvents() {
        // Audio事件
        this.audio.addEventListener('timeupdate', () => this.onTimeUpdate());
        this.audio.addEventListener('ended', () => this.onSongEnded());
        this.audio.addEventListener('loadedmetadata', () => this.onMetadataLoaded());
        this.audio.addEventListener('error', (e) => this.onError(e));

        // 播放/暂停按钮
        document.getElementById('btn-play-pause').addEventListener('click', () => this.togglePlay());

        // 上一曲/下一曲
        document.getElementById('btn-prev').addEventListener('click', () => this.playPrevious());
        document.getElementById('btn-next').addEventListener('click', () => this.playNext());

        // 进度条
        const progressContainer = document.getElementById('progress-container');
        progressContainer.addEventListener('click', (e) => this.seekTo(e));

        // 音量控制
        document.getElementById('volume-slider').addEventListener('input', (e) => this.setVolume(e.target.value));
        document.getElementById('volume-btn').addEventListener('click', () => this.toggleMute());

        // 播放模式
        document.getElementById('mode-btn').addEventListener('click', () => this.switchMode());

        // 播放列表按钮
        document.getElementById('queue-btn').addEventListener('click', () => this.toggleQueue());
        document.getElementById('queue-clear').addEventListener('click', () => this.clearQueue());
    }

    /* ============================================
       播放控制方法
       ============================================ */

    // 添加歌曲到队列并播放
    playSong(song) {
        // 使用 externalId 检查是否已在队列中（外部歌曲）
        const songKey = song.externalId || song.id;
        const existingIndex = this.playQueue.findIndex(s => (s.externalId || s.id) === songKey);

        if (existingIndex !== -1) {
            // 如果已在队列，直接跳转播放
            this.currentIndex = existingIndex;
        } else {
            // 添加到队列
            this.playQueue.push(song);
            this.currentIndex = this.playQueue.length - 1;
        }

        this.loadAndPlay();
        this.updateQueueUI();
    }

    // 添加到队列末尾（不立即播放）
    addToQueue(song) {
        // 使用 externalId 检查是否已在队列中
        const songKey = song.externalId || song.id;
        if (!this.playQueue.find(s => (s.externalId || s.id) === songKey)) {
            this.playQueue.push(song);
            this.updateQueueUI();
            this.showNotification(`已添加 ${song.title} 到播放队列`);
        } else {
            this.showNotification(`${song.title} 已在队列中`);
        }
    }

    // 加载并播放当前歌曲
    loadAndPlay() {
        if (this.currentIndex < 0 || this.currentIndex >= this.playQueue.length) {
            return;
        }

        const song = this.playQueue[this.currentIndex];

        // 更新UI（显示加载状态）
        this.updatePlayerUI(song);

        // 统一使用 fetchPlayUrl 获取链接 (支持 VIP 检查)
        // 本地歌曲逻辑暂不改动 (此处假设 fetchPlayUrl 处理外部逻辑)
        if (song.source === 'local') {
            // 本地歌曲处理逻辑 (假设直接播放，或需补充)
            this.audio.src = song.url || `audio?id=${song.id}`; // 假设本地歌曲有 url
            this.playAudio(song);
        } else {
            // 网易云/QQ 歌曲 (无论是否有 externalId 都走此流程以检查 VIP)
            this.fetchPlayUrl(song);
        }
    }

    // 动态获取播放链接（支持 VIP 登录重试）
    async fetchPlayUrl(song, isRetry = false) {
        try {
            // 显示加载提示 (重试时不显示)
            if (!isRetry) this.showNotification('🔍 正在获取音源...');

            const params = new URLSearchParams({
                title: song.title || '',
                artist: song.artist || ''
            });

            // 如果已经有 externalId 和 source，直接传递以绕过搜索
            if (song.externalId && song.source) {
                params.append('id', song.externalId);
                params.append('source', song.source);
            }

            const response = await fetch(`api/getPlayUrl?${params}`);
            const data = await response.json();

            // 1. 处理需要登录的情况
            if (data.success && data.needLogin) {
                this.showNotification('⚠️ 该歌曲需要 VIP 权限');
                console.log('唤起登录窗口...');

                if (typeof QQLoginModal !== 'undefined') {
                    QQLoginModal.show({
                        onSuccess: () => {
                            // 登录成功，重试播放
                            console.log('登录成功，重试播放...');
                            this.fetchPlayUrl(song, true);
                        }
                    });
                } else {
                    alert('需要登录 QQ 音乐，但登录组件未加载');
                }
                return;
            }

            // 2. 处理获取成功
            if (data.success && data.url) {
                // 更新歌曲信息
                song.source = data.source;
                song.externalId = data.externalId;
                if (data.releaseYear) song.releaseYear = data.releaseYear;
                if (data.genre) song.genre = data.genre;
                if (data.language) song.language = data.language;

                // 设置播放源并播放
                this.audio.src = data.url;
                this.playAudio(song);

                // 显示来源提示
                const sourceName = data.source === 'netease' ? '网易云' : 'QQ音乐';
                this.showNotification(`✅ 已从${sourceName}获取音源${data.cached ? ' (缓存)' : ''}`);
            } else {
                // 3. 处理失败
                this.showNotification(`❌ ${data.message || '未找到可播放的音源'}`);
                // 尝试播放下一曲 (非重试状态下)
                if (!isRetry) setTimeout(() => this.playNext(), 2000);
            }
        } catch (error) {
            console.error('获取播放链接失败:', error);
            this.showNotification('❌ 获取播放链接失败: ' + error.message);
            if (!isRetry) setTimeout(() => this.playNext(), 2000);
        }
    }

    // 执行播放并记录历史
    playAudio(song) {
        // v3.1.0: 清除之前的计时器
        this.clearPlayHistoryTimer();
        this.playHistoryRecorded = false;

        this.audio.play().then(() => {
            console.log('开始播放:', song.title, '来源:', song.source || 'local');

            // v3.1.0: 3秒后记录播放历史（适用于所有歌曲）
            this.playHistoryTimer = setTimeout(() => {
                if (!this.playHistoryRecorded) {
                    this.recordUniversalPlayHistory(song);
                    this.playHistoryRecorded = true;
                }
            }, 3000);

        }).catch(error => {
            console.error('播放失败:', error);
            this.showNotification('播放失败，可能需要VIP或歌曲已下架');
        });
    }

    // v3.1.0: 清除播放历史计时器
    clearPlayHistoryTimer() {
        if (this.playHistoryTimer) {
            clearTimeout(this.playHistoryTimer);
            this.playHistoryTimer = null;
        }
    }

    // 切换播放/暂停
    togglePlay() {
        if (this.audio.paused) {
            if (this.audio.src) {
                this.audio.play();
            } else if (this.playQueue.length > 0) {
                this.currentIndex = 0;
                this.loadAndPlay();
            }
        } else {
            this.audio.pause();
        }
        this.updatePlayButtonUI();
    }

    // 播放上一曲
    playPrevious() {
        if (this.playQueue.length === 0) return;

        if (this.playMode === 'random') {
            this.currentIndex = Math.floor(Math.random() * this.playQueue.length);
        } else {
            this.currentIndex = (this.currentIndex - 1 + this.playQueue.length) % this.playQueue.length;
        }

        this.loadAndPlay();
    }

    // 播放下一曲
    playNext() {
        if (this.playQueue.length === 0) return;

        if (this.playMode === 'random') {
            this.currentIndex = Math.floor(Math.random() * this.playQueue.length);
        } else {
            this.currentIndex = (this.currentIndex + 1) % this.playQueue.length;
        }

        this.loadAndPlay();
    }

    /* ============================================
       进度和音量控制
       ============================================ */

    // 跳转到指定位置
    seekTo(e) {
        const progressContainer = e.currentTarget;
        const rect = progressContainer.getBoundingClientRect();
        const percent = (e.clientX - rect.left) / rect.width;
        const seekTime = percent * this.audio.duration;

        if (!isNaN(seekTime)) {
            this.audio.currentTime = seekTime;
        }
    }

    // 设置音量
    setVolume(value) {
        this.volume = value;
        this.audio.volume = value;
        localStorage.setItem('volume', value);
        this.updateVolumeUI();
    }

    // 切换静音
    toggleMute() {
        if (this.audio.volume > 0) {
            this.audio.volume = 0;
            document.getElementById('volume-slider').value = 0;
            document.getElementById('volume-btn').textContent = '🔇';
        } else {
            this.audio.volume = this.volume;
            document.getElementById('volume-slider').value = this.volume;
            document.getElementById('volume-btn').textContent = '🔊';
        }
    }

    /* ============================================
       播放模式
       ============================================ */

    // 切换播放模式
    switchMode() {
        const modes = ['order', 'loop', 'single', 'random'];
        const currentModeIndex = modes.indexOf(this.playMode);
        this.playMode = modes[(currentModeIndex + 1) % modes.length];

        localStorage.setItem('playMode', this.playMode);
        this.updateModeUI();
    }

    // 更新播放模式UI
    updateModeUI() {
        const modeBtn = document.getElementById('mode-btn');
        const modeIcons = {
            'order': '➡️',
            'loop': '🔁',
            'single': '🔂',
            'random': '🔀'
        };
        const modeNames = {
            'order': '顺序播放',
            'loop': '列表循环',
            'single': '单曲循环',
            'random': '随机播放'
        };

        modeBtn.textContent = modeIcons[this.playMode];
        modeBtn.title = modeNames[this.playMode];
    }

    /* ============================================
       播放队列管理
       ============================================ */

    // 切换播放队列显示
    toggleQueue() {
        const queue = document.getElementById('play-queue');
        queue.classList.toggle('active');
    }

    // 清空队列
    clearQueue() {
        if (confirm('确定要清空播放队列吗？')) {
            this.playQueue = [];
            this.currentIndex = -1;
            this.audio.pause();
            this.audio.src = '';
            this.updateQueueUI();
            this.updatePlayerUI(null);
        }
    }

    // 从队列移除歌曲
    removeFromQueue(index) {
        this.playQueue.splice(index, 1);

        // 调整当前索引
        if (this.currentIndex > index) {
            this.currentIndex--;
        } else if (this.currentIndex === index) {
            // 如果删除的是当前播放的歌曲
            if (this.playQueue.length > 0) {
                this.currentIndex = Math.min(this.currentIndex, this.playQueue.length - 1);
                this.loadAndPlay();
            } else {
                this.currentIndex = -1;
                this.audio.pause();
                this.audio.src = '';
                this.updatePlayerUI(null);
            }
        }

        this.updateQueueUI();
    }

    /* ============================================
       播放历史
       ============================================ */

    // 记录播放历史（发送到后端）- 仅用于本地歌曲的旧接口
    recordPlayHistory(song) {
        fetch('playHistory', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: `action=add&songId=${song.id}`
        }).then(response => {
            if (!response.ok) {
                console.error('记录播放历史失败');
            }
        }).catch(error => {
            console.error('记录播放历史错误:', error);
        });
    }

    // v3.1.0: 通用播放历史记录（支持本地和外部歌曲）
    recordUniversalPlayHistory(song) {
        const payload = {
            songId: song.id || null,
            title: song.title || '',
            artist: song.artist || '',
            album: song.album || '',
            duration: song.duration || 0,
            source: song.source || 'local',
            externalId: song.externalId || '',
            coverUrl: song.coverUrl || song.coverImage || '',
            releaseYear: song.releaseYear || 0
        };

        console.log('📝 [播放历史] 记录歌曲:', payload.title, '-', payload.artist, '(source:', payload.source + ')');

        fetch('api/universalPlayHistory', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(payload)
        }).then(response => response.json())
            .then(data => {
                if (data.success) {
                    console.log('✅ [播放历史] 记录成功, songId:', data.songId);
                } else {
                    console.error('❌ [播放历史] 记录失败:', data.message);
                }
            }).catch(error => {
                console.error('❌ [播放历史] 请求错误:', error);
            });
    }

    /* ============================================
       UI更新方法
       ============================================ */

    // 更新播放器UI
    updatePlayerUI(song) {
        if (song) {
            document.getElementById('player-title').textContent = song.title;
            document.getElementById('player-artist').textContent = song.artist;

            // 封面图片：优先使用外部封面URL
            const coverPath = song.coverUrl || song.coverImage || 'img/cover.jpg';
            document.getElementById('player-cover').src = coverPath;

            // 显示播放器
            document.querySelector('.music-player').style.display = 'flex';
            document.body.classList.add('player-active');
        } else {
            document.getElementById('player-title').textContent = '未播放';
            document.getElementById('player-artist').textContent = '';
            document.querySelector('.music-player').style.display = 'none';
            document.body.classList.remove('player-active');
        }

        this.updatePlayButtonUI();
    }

    // 更新播放按钮UI
    updatePlayButtonUI() {
        const playBtn = document.getElementById('btn-play-pause');
        playBtn.textContent = this.audio.paused ? '▶️' : '⏸️';
    }

    // 更新进度条
    onTimeUpdate() {
        const current = this.audio.currentTime;
        const duration = this.audio.duration;

        if (!isNaN(duration)) {
            const percent = (current / duration) * 100;
            document.getElementById('progress-bar').style.width = percent + '%';
            document.getElementById('current-time').textContent = this.formatTime(current);
        }
    }

    // 元数据加载完成
    onMetadataLoaded() {
        const duration = this.audio.duration;
        document.getElementById('total-time').textContent = this.formatTime(duration);
    }

    // 歌曲播放结束
    onSongEnded() {
        if (this.playMode === 'single') {
            // 单曲循环
            this.audio.currentTime = 0;
            this.audio.play();
        } else if (this.playMode === 'loop' || this.playMode === 'order') {
            // 列表循环或顺序播放
            this.playNext();
        } else if (this.playMode === 'random') {
            // 随机播放
            this.playNext();
        }
    }

    // 播放错误处理
    onError(e) {
        console.error('播放错误:', e);
        this.showNotification('播放出错，自动跳过');
        setTimeout(() => this.playNext(), 2000);
    }

    // 更新音量UI
    updateVolumeUI() {
        document.getElementById('volume-slider').value = this.volume;
        const volumeBtn = document.getElementById('volume-btn');

        if (this.audio.volume === 0) {
            volumeBtn.textContent = '🔇';
        } else if (this.audio.volume < 0.5) {
            volumeBtn.textContent = '🔉';
        } else {
            volumeBtn.textContent = '🔊';
        }
    }

    // 更新队列UI
    updateQueueUI() {
        const queueList = document.getElementById('queue-list');
        const queueCount = document.getElementById('queue-count');

        queueCount.textContent = this.playQueue.length;

        if (this.playQueue.length === 0) {
            queueList.innerHTML = '<div class="queue-empty">播放队列为空<br/>点击歌曲添加到队列</div>';
            return;
        }

        queueList.innerHTML = this.playQueue.map((song, index) => {
            const coverPath = song.coverUrl || song.coverImage || 'img/cover.jpg';
            const sourceTag = song.source ? `<span class="source-tag source-${song.source}">${song.source === 'netease' ? '网易云' : 'QQ'}</span>` : '';
            return `
            <div class="queue-item ${index === this.currentIndex ? 'playing' : ''}" onclick="player.playQueueItem(${index})">
                <div class="queue-item-cover">
                    <img src="${coverPath}" alt="封面">
                </div>
                <div class="queue-item-info">
                    <div class="queue-item-title">${song.title} ${sourceTag}</div>
                    <div class="queue-item-artist">${song.artist}</div>
                </div>
                <button class="queue-item-remove" onclick="event.stopPropagation(); player.removeFromQueue(${index})">✕</button>
            </div>
        `}).join('');
    }

    // 播放队列中的指定项
    playQueueItem(index) {
        this.currentIndex = index;
        this.loadAndPlay();
        this.updateQueueUI();
    }

    /* ============================================
       工具方法
       ============================================ */

    // 格式化时间（秒 -> mm:ss）
    formatTime(seconds) {
        if (isNaN(seconds)) return '00:00';

        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    }

    // 显示通知
    showNotification(message) {
        // 简单的通知实现
        const notification = document.createElement('div');
        notification.className = 'notification';
        notification.textContent = message;
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: rgba(0, 0, 0, 0.8);
            color: white;
            padding: 12px 20px;
            border-radius: 8px;
            z-index: 10000;
            animation: slideIn 0.3s ease-out;
        `;

        document.body.appendChild(notification);

        setTimeout(() => {
            notification.style.animation = 'slideOut 0.3s ease-out';
            setTimeout(() => notification.remove(), 300);
        }, 3000);
    }
}

/* ============================================
   全局播放器实例
   ============================================ */
let player;

// 页面加载完成后初始化播放器
document.addEventListener('DOMContentLoaded', () => {
    player = new AudioPlayer();
    console.log('AudioPlayer 已准备就绪');
});

/* ============================================
   通知动画CSS（动态添加）
   ============================================ */
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from {
            transform: translateX(400px);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }

    @keyframes slideOut {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(400px);
            opacity: 0;
        }
    }
`;
document.head.appendChild(style);
