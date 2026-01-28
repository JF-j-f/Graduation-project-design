/**
 * 搜索功能 JavaScript
 * 功能：搜索历史管理、筛选面板交互
 */

// 搜索历史管理类
class SearchHistory {
    constructor() {
        this.maxHistory = 5; // 最多保存5条历史
        this.storageKey = 'musicweb_search_history';
    }

    // 获取搜索历史
    getHistory() {
        try {
            const history = localStorage.getItem(this.storageKey);
            return history ? JSON.parse(history) : [];
        } catch (e) {
            console.error('读取搜索历史失败:', e);
            return [];
        }
    }

    // 添加搜索记录
    addHistory(keyword) {
        if (!keyword || keyword.trim() === '') return;

        keyword = keyword.trim();
        let history = this.getHistory();

        // 移除重复项
        history = history.filter(item => item !== keyword);

        // 添加到开头
        history.unshift(keyword);

        // 限制数量
        if (history.length > this.maxHistory) {
            history = history.slice(0, this.maxHistory);
        }

        try {
            localStorage.setItem(this.storageKey, JSON.stringify(history));
        } catch (e) {
            console.error('保存搜索历史失败:', e);
        }
    }

    // 清除搜索历史
    clearHistory() {
        try {
            localStorage.removeItem(this.storageKey);
        } catch (e) {
            console.error('清除搜索历史失败:', e);
        }
    }
}

// 搜索UI管理
class SearchUI {
    constructor() {
        this.searchHistory = new SearchHistory();
        this.searchInput = document.getElementById('search-input');
        this.searchForm = document.getElementById('search-form');
        this.historyContainer = document.getElementById('search-history');
        this.historyList = document.getElementById('search-history-list');
        this.clearHistoryBtn = document.getElementById('clear-history');

        this.init();
    }

    init() {
        // 输入框焦点事件
        if (this.searchInput) {
            this.searchInput.addEventListener('focus', () => this.showHistory());
            this.searchInput.addEventListener('blur', () => {
                // 延迟隐藏，以便点击历史项
                setTimeout(() => this.hideHistory(), 200);
            });
        }

        // 表单提交事件
        if (this.searchForm) {
            this.searchForm.addEventListener('submit', (e) => {
                const keyword = this.searchInput.value.trim();
                if (keyword) {
                    this.searchHistory.addHistory(keyword);
                }
            });
        }

        // 清除历史按钮
        if (this.clearHistoryBtn) {
            this.clearHistoryBtn.addEventListener('click', (e) => {
                e.preventDefault();
                this.searchHistory.clearHistory();
                this.renderHistory();
            });
        }

        // 渲染历史记录
        this.renderHistory();
    }

    // 显示搜索历史
    showHistory() {
        const history = this.searchHistory.getHistory();
        if (history.length > 0 && this.historyContainer) {
            this.renderHistory(); // 重新渲染以确保最新
            this.historyContainer.style.display = 'block';
        }
    }

    // 隐藏搜索历史
    hideHistory() {
        if (this.historyContainer) {
            this.historyContainer.style.display = 'none';
        }
    }

    // 渲染搜索历史
    renderHistory() {
        if (!this.historyList) return;

        const history = this.searchHistory.getHistory();

        if (history.length === 0) {
            this.historyList.innerHTML = '<div class="history-empty">暂无搜索历史</div>';
            return;
        }

        this.historyList.innerHTML = history.map(keyword => `
            <div class="history-item" data-keyword="${this.escapeHtml(keyword)}">
                <span class="history-icon">🔍</span>
                <span class="history-text">${this.escapeHtml(keyword)}</span>
            </div>
        `).join('');

        // 为每个历史项添加点击事件
        this.historyList.querySelectorAll('.history-item').forEach(item => {
            item.addEventListener('click', () => {
                const keyword = item.getAttribute('data-keyword');
                if (this.searchInput) {
                    this.searchInput.value = keyword;
                    this.searchForm.submit();
                }
            });
        });
    }

    // HTML转义
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', function() {
    // 初始化搜索UI
    const searchUI = new SearchUI();

    console.log('✅ 搜索功能已初始化');
});
