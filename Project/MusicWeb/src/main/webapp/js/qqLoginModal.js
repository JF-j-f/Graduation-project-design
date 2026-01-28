/**
 * QQ 音乐登录模态框组件
 * 
 * 功能：
 * 1. 显示/隐藏登录窗口
 * 2. 切换扫码/手机验证码登录
 * 3. 轮询二维码状态
 * 4. 发送/验证手机验证码
 */
const QQLoginModal = {
    checkInterval: null,
    onSuccessCallback: null,
    API_BASE: 'http://localhost:3000', // 指向 Node.js 代理服务

    // 初始化模态框 HTML
    init() {
        if (document.getElementById('qq-login-modal')) return;

        const modalHtml = `
            <div id="qq-login-modal" class="modal-overlay" style="display: none;">
                <div class="modal-content">
                    <button class="modal-close" onclick="QQLoginModal.hide()">×</button>
                    <div class="modal-header">
                        <h3>QQ 音乐登录</h3>
                        <p>该歌曲需要 VIP 权限，请登录后播放</p>
                    </div>
                    <div class="modal-tabs">
                        <button class="tab-btn active" onclick="QQLoginModal.switchTab('qr')">扫码登录</button>
                        <button class="tab-btn" onclick="QQLoginModal.switchTab('phone')">手机号登录</button>
                    </div>
                    
                    <!-- 扫码登录面板 -->
                    <div id="panel-qr" class="tab-panel active">
                        <div class="qr-container">
                            <img id="qr-img" src="" alt="加载中..." />
                            <div id="qr-status">正在获取二维码...</div>
                            <div class="qr-tip">请使用 QQ 或 微信 扫码</div>
                        </div>
                    </div>

                    <!-- 手机登录面板 -->
                    <div id="panel-phone" class="tab-panel">
                        <div class="input-group">
                            <input type="text" id="phone-number" placeholder="请输入手机号" />
                        </div>
                        <div class="input-group">
                            <input type="text" id="auth-code" placeholder="验证码" />
                            <button id="btn-send-code" onclick="QQLoginModal.sendCode()">获取验证码</button>
                        </div>
                        <button class="btn-primary" onclick="QQLoginModal.verifyCode()">登录</button>
                    </div>
                    <!-- Captcha iframe container -->
                    <div id="captcha-container" style="display: none; position: absolute; top: 0; left: 0; width: 100%; height: 100%; background: rgba(45, 45, 45, 0.98); border-radius: 12px; z-index: 10; flex-direction: column; align-items: center; justify-content: center;">
                        <div style="width: 100%; display: flex; justify-content: space-between; padding: 10px 15px; border-bottom: 1px solid #444;">
                            <span style="font-size: 14px;">请完成安全验证</span>
                            <button onclick="QQLoginModal.closeCaptcha()" style="background:none; border:none; color:#ddd; cursor:pointer;">×</button>
                        </div>
                        <div style="flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; padding: 20px;">
                            <div style="font-size: 3rem; margin-bottom: 20px;">🛡️</div>
                            <h3 style="margin: 0 0 10px 0; font-size: 1.2rem;">安全验证</h3>
                            <p style="color: #aaa; font-size: 0.9rem; margin: 0 0 20px 0;">验证页面已在新窗口打开<br>请在完成验证后点击下方按钮</p>
                            <a href="#" onclick="QQLoginModal.reopenCaptcha(); return false;" style="color: #31c27c; font-size: 0.9rem; text-decoration: none;">没有弹出？点击这里</a>
                        </div>
                        <div style="padding: 10px; width: 100%;">
                            <button class="btn-primary" onclick="QQLoginModal.captchaCompleted()">我已完成验证，继续登录</button>
                        </div>
                    </div>

                </div>
            </div>
            <style>
                .modal-overlay {
                    position: fixed; top: 0; left: 0; width: 100%; height: 100%;
                    background: rgba(0,0,0,0.6); z-index: 10000;
                    display: flex; justify-content: center; align-items: center;
                }
                .modal-content {
                    background: #2d2d2d; color: #fff; padding: 20px; border-radius: 12px;
                    width: 320px; height: 450px; position: relative; text-align: center; /* Height fixed for consistency */
                    box-shadow: 0 4px 20px rgba(0,0,0,0.5);
                    display: flex; flex-direction: column;
                }
                .modal-close {
                    position: absolute; top: 10px; right: 15px; background: none; border: none;
                    color: #999; font-size: 24px; cursor: pointer; z-index: 5;
                }
                /* Ensure captcha container covers content */
                #captcha-container { animation: fadeIn 0.2s; }
                
                .modal-header h3 { margin: 0 0 10px 0; }
                .modal-header p { color: #aaa; font-size: 12px; margin-bottom: 20px; }
                .modal-tabs { display: flex; justify-content: space-around; margin-bottom: 20px; border-bottom: 1px solid #444; }
                .tab-btn { background: none; border: none; color: #888; padding: 10px; cursor: pointer; }
                .tab-btn.active { color: #31c27c; border-bottom: 2px solid #31c27c; }
                .tab-panel { display: none; flex: 1; }
                .tab-panel.active { display: block; }
                .qr-container { margin-top: 20px; }
                .qr-container img { width: 150px; height: 150px; border-radius: 8px; }
                .qr-tip { font-size: 12px; color: #888; margin-top: 10px; }
                .input-group { display: flex; margin-bottom: 15px; }
                .input-group input { 
                    flex: 1; padding: 8px; border: 1px solid #444; border-radius: 4px; 
                    background: #333; color: #fff; outline: none;
                }
                .input-group button { 
                    margin-left: 10px; padding: 0 12px; background: #444; color: #fff; 
                    border: none; border-radius: 4px; cursor: pointer; white-space: nowrap;
                }
                .btn-primary { 
                    width: 100%; padding: 10px; background: #31c27c; color: #fff; 
                    border: none; border-radius: 4px; cursor: pointer; font-weight: bold;
                }
                .btn-primary:hover { background: #2caf6f; }
                
                @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
            </style>
        `;
        document.body.insertAdjacentHTML('beforeend', modalHtml);
    },

    // 显示模态框
    show({ onSuccess }) {
        this.init();
        this.onSuccessCallback = onSuccess;
        document.getElementById('qq-login-modal').style.display = 'flex';
        this.switchTab('qr'); // 默认显示二维码
    },

    // 隐藏模态框
    hide() {
        const modal = document.getElementById('qq-login-modal');
        if (modal) modal.style.display = 'none';
        this.stopCheck();
    },

    // 切换标签页
    switchTab(tab) {
        document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
        document.querySelectorAll('.tab-panel').forEach(panel => panel.classList.remove('active'));

        if (tab === 'qr') {
            document.querySelector('.tab-btn:nth-child(1)').classList.add('active');
            document.getElementById('panel-qr').classList.add('active');
            this.loadQrCode();
        } else {
            document.querySelector('.tab-btn:nth-child(2)').classList.add('active');
            document.getElementById('panel-phone').classList.add('active');
            this.stopCheck();
        }
    },

    // 加载二维码
    async loadQrCode() {
        try {
            this.stopCheck();
            const userId = window.CURRENT_USER_ID || 'guest';
            const res = await fetch(`${this.API_BASE}/qq/login/qr?type=qq&userid=${encodeURIComponent(userId)}`); // 默认使用 QQ 扫码
            const data = await res.json();

            if (data.code === 0 && data.data.qrcode) {
                document.getElementById('qr-img').src = data.data.qrcode;
                document.getElementById('qr-status').textContent = '请扫码...';
                this.startCheck();
            } else {
                document.getElementById('qr-status').textContent = '获取失败，点击重试';
                document.getElementById('qr-img').onclick = () => this.loadQrCode();
            }
        } catch (e) {
            console.error('加载二维码失败', e);
            document.getElementById('qr-status').textContent = '加载失败';
        }
    },

    // 开始轮询二维码状态
    startCheck() {
        this.checkInterval = setInterval(async () => {
            try {
                const userId = window.CURRENT_USER_ID || 'guest';
                const res = await fetch(`${this.API_BASE}/qq/login/qr/check?userid=${encodeURIComponent(userId)}`, { method: 'POST' });
                const data = await res.json();

                if (data.code === 0) {
                    const status = data.data.status;
                    const msg = data.data.message;

                    document.getElementById('qr-status').textContent = msg;

                    if (status === 'DONE') {
                        this.handleLoginSuccess();
                    } else if (status === 'TIMEOUT') {
                        this.stopCheck();
                        document.getElementById('qr-img').onclick = () => this.loadQrCode();
                    }
                }
            } catch (e) {
                console.error('轮询失败', e);
            }
        }, 2000);
    },

    // 停止轮询
    stopCheck() {
        if (this.checkInterval) {
            clearInterval(this.checkInterval);
            this.checkInterval = null;
        }
    },

    // 发送验证码
    async sendCode() {
        const phone = document.getElementById('phone-number').value;
        if (!phone) return alert('请输入手机号');

        try {
            const userId = window.CURRENT_USER_ID || 'guest';
            const res = await fetch(`${this.API_BASE}/qq/login/phone/send`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ phone: parseInt(phone), country_code: 86, userid: userId })
            });
            const data = await res.json();

            if (data.code === 0) {
                if (data.data.status === 'CAPTCHA') {
                    // 显示图形验证码
                    this.showCaptcha(data.data.captcha_url);
                } else if (data.data.status === 'SEND') {
                    alert(data.data.message);
                } else {
                    alert(data.data.message || '未知状态');
                }
            } else {
                alert('发送失败: ' + (data.message || '未知错误'));
            }
        } catch (e) {
            alert('网络错误');
        }
    },

    // 显示验证码
    showCaptcha(url) {
        this.currentCaptchaUrl = url;
        const container = document.getElementById('captcha-container');
        container.style.display = 'flex';

        // 打开新窗口
        this.openCaptchaWindow(url);
    },

    openCaptchaWindow(url) {
        const width = 375;
        const height = 600;
        const left = (window.screen.width - width) / 2;
        const top = (window.screen.height - height) / 2;
        window.open(url, 'QQMusicCaptcha', `width=${width},height=${height},left=${left},top=${top},menubar=no,toolbar=no,location=no,status=no,resizable=yes,scrollbars=yes`);
    },

    // 重新打开验证码
    reopenCaptcha() {
        if (this.currentCaptchaUrl) {
            this.openCaptchaWindow(this.currentCaptchaUrl);
        }
    },

    // 关闭验证码
    closeCaptcha() {
        document.getElementById('captcha-container').style.display = 'none';
        this.currentCaptchaUrl = null;
    },

    // 备用：在新窗口打开验证码 (已废弃，保留兼容性)
    openCaptchaFallback() {
        this.reopenCaptcha();
    },

    // 验证码完成
    captchaCompleted() {
        this.closeCaptcha();
        // 重新发送验证码
        this.sendCode();
    },

    // 验证验证码登录
    async verifyCode() {
        const phone = document.getElementById('phone-number').value;
        const code = document.getElementById('auth-code').value;
        if (!phone || !code) return alert('请填写完整信息');

        try {
            const res = await fetch(`${this.API_BASE}/qq/login/phone/verify`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    phone: parseInt(phone),
                    code: parseInt(code),
                    country_code: 86,
                    userid: window.CURRENT_USER_ID || 'guest'
                })
            });
            const data = await res.json();

            if (data.code === 0 && data.data.status === 'DONE') {
                this.handleLoginSuccess();
            } else {
                alert('登录失败: ' + (data.message || '验证码错误'));
            }
        } catch (e) {
            alert('网络错误');
        }
    },

    // 登录成功处理
    handleLoginSuccess() {
        this.hide();
        // showNotification is global in player.js usually, or distinct
        if (window.player && window.player.showNotification) {
            window.player.showNotification('✅ 登录成功！');
        } else {
            alert('登录成功！');
        }

        if (this.onSuccessCallback) {
            this.onSuccessCallback();
        }
    }
};
