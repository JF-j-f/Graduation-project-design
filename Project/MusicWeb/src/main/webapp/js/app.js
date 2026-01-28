// 音乐网站主JavaScript文件
class MusicApp {
    constructor() {
        this.init();
    }

    init() {
        this.bindEvents();
        this.loadUserPreferences();
        console.log('Music App Initialized');
    }

    bindEvents() {
        // 绑定全局事件
        this.bindNavigation();
        this.bindMusicControls();
        this.bindSearch();
        this.bindFavoriteActions();
    }

    bindNavigation() {
        // 移动端菜单切换
        const menuToggle = document.querySelector('.menu-toggle');
        const navLinks = document.querySelector('.nav-links');

        if (menuToggle && navLinks) {
            menuToggle.addEventListener('click', () => {
                navLinks.classList.toggle('active');
                menuToggle.classList.toggle('active');
            });
        }

        // 平滑滚动
        document.querySelectorAll('a[href^="#"]').forEach(anchor => {
            anchor.addEventListener('click', function (e) {
                e.preventDefault();
                const target = document.querySelector(this.getAttribute('href'));
                if (target) {
                    target.scrollIntoView({
                        behavior: 'smooth',
                        block: 'start'
                    });
                }
            });
        });
    }

    bindMusicControls() {
        // 播放/暂停控制
        document.querySelectorAll('.play-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                this.togglePlayback(e.target);
            });
        });

        // 进度条控制
        document.querySelectorAll('.progress-bar').forEach(bar => {
            bar.addEventListener('click', (e) => {
                const rect = bar.getBoundingClientRect();
                const percent = (e.clientX - rect.left) / rect.width;
                this.seekAudio(percent);
            });
        });
    }

    bindSearch() {
        const searchInput = document.querySelector('.search-input');
        if (searchInput) {
            searchInput.addEventListener('input', this.debounce((e) => {
                this.performSearch(e.target.value);
            }, 300));
        }
    }

    bindFavoriteActions() {
        // 收藏按钮事件
        document.querySelectorAll('.favorite-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                this.toggleFavorite(e.target);
            });
        });
    }

    togglePlayback(button) {
        const songItem = button.closest('.song-item');
        const isPlaying = songItem.classList.contains('playing');

        if (isPlaying) {
            this.pauseAudio(songItem);
        } else {
            this.playAudio(songItem);
        }
    }

    playAudio(songItem) {
        // 停止所有其他播放
        document.querySelectorAll('.song-item.playing').forEach(item => {
            this.pauseAudio(item);
        });

        // 开始播放当前歌曲
        songItem.classList.add('playing');
        const playBtn = songItem.querySelector('.play-btn');
        playBtn.textContent = '⏸️';

        // 模拟播放逻辑
        console.log('开始播放:', songItem.querySelector('.song-title').textContent);
    }

    pauseAudio(songItem) {
        songItem.classList.remove('playing');
        const playBtn = songItem.querySelector('.play-btn');
        playBtn.textContent = '▶️';

        console.log('暂停播放');
    }

    seekAudio(percent) {
        // 模拟跳转播放进度
        console.log('跳转到:', Math.round(percent * 100) + '%');
    }

    async toggleFavorite(button) {
        const songId = button.dataset.songId;
        const isFavorite = button.classList.contains('favorited');

        try {
            // 发送收藏/取消收藏请求
            const response = await fetch('/favorite', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
                body: `action=${isFavorite ? 'remove' : 'add'}&songId=${songId}`
            });

            if (response.ok) {
                button.classList.toggle('favorited');
                button.textContent = button.classList.contains('favorited') ? '❤️' : '🤍';

                this.showNotification(
                    isFavorite ? '已取消收藏' : '收藏成功',
                    'success'
                );
            }
        } catch (error) {
            console.error('收藏操作失败:', error);
            this.showNotification('操作失败，请重试', 'error');
        }
    }

    performSearch(query) {
        if (query.length < 2) return;

        console.log('搜索:', query);
        // 这里可以添加实际的搜索逻辑
    }

    showNotification(message, type = 'info') {
        // 创建通知元素
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.innerHTML = `
            <span>${message}</span>
            <button class="notification-close">&times;</button>
        `;

        // 添加样式
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: ${type === 'success' ? '#38a169' : type === 'error' ? '#e53e3e' : '#3182ce'};
            color: white;
            padding: 1rem 1.5rem;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            z-index: 10000;
            animation: slideInRight 0.3s ease-out;
        `;

        document.body.appendChild(notification);

        // 自动消失
        setTimeout(() => {
            notification.remove();
        }, 3000);

        // 点击关闭
        notification.querySelector('.notification-close').addEventListener('click', () => {
            notification.remove();
        });
    }

    loadUserPreferences() {
        // 加载用户偏好设置
        const theme = localStorage.getItem('theme') || 'light';
        this.setTheme(theme);
    }

    setTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem('theme', theme);
    }

    // 防抖函数
    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }
}

// 工具函数
const Utils = {
    formatTime(seconds) {
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    },

    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    },

    truncateText(text, maxLength) {
        if (text.length <= maxLength) return text;
        return text.substr(0, maxLength) + '...';
    }
};

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', function() {
    window.musicApp = new MusicApp();

    // 添加CSS动画
    const style = document.createElement('style');
    style.textContent = `
        @keyframes slideInRight {
            from {
                opacity: 0;
                transform: translateX(100%);
            }
            to {
                opacity: 1;
                transform: translateX(0);
            }
        }
        
        .notification {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 1rem;
        }
        
        .notification-close {
            background: none;
            border: none;
            color: white;
            font-size: 1.25rem;
            cursor: pointer;
            padding: 0;
            width: 20px;
            height: 20px;
            display: flex;
            align-items: center;
            justify-content: center;
        }
    `;
    document.head.appendChild(style);
});