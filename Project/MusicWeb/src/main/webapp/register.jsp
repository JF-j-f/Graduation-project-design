<%@ page contentType="text/html;charset=UTF-8" language="java" %>
    <!DOCTYPE html>
    <html lang="zh-CN">

    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>用户注册 - MusicWeb</title>
        <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@400;500;700&display=swap"
            rel="stylesheet">
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }

            body {
                font-family: 'Noto Sans SC', sans-serif;
                background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
                min-height: 100vh;
                color: #fff;
            }

            .container {
                max-width: 900px;
                margin: 0 auto;
                padding: 40px 20px;
            }

            .progress-bar {
                display: flex;
                justify-content: center;
                margin-bottom: 40px;
            }

            .step {
                display: flex;
                align-items: center;
            }

            .step-circle {
                width: 40px;
                height: 40px;
                border-radius: 50%;
                background: rgba(255, 255, 255, 0.1);
                border: 2px solid rgba(255, 255, 255, 0.3);
                display: flex;
                align-items: center;
                justify-content: center;
                font-weight: bold;
                transition: all 0.3s;
            }

            .step-circle.active {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                border-color: transparent;
                box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
            }

            .step-circle.completed {
                background: #28a745;
                border-color: transparent;
            }

            .step-line {
                width: 80px;
                height: 2px;
                background: rgba(255, 255, 255, 0.2);
                margin: 0 10px;
            }

            .step-line.completed {
                background: linear-gradient(90deg, #28a745, #667eea);
            }

            /* Step 1: 基本信息表单 */
            .form-section {
                background: rgba(255, 255, 255, 0.05);
                backdrop-filter: blur(10px);
                border-radius: 20px;
                padding: 40px;
                margin-bottom: 30px;
                border: 1px solid rgba(255, 255, 255, 0.1);
            }

            .section-title {
                font-size: 24px;
                font-weight: 700;
                margin-bottom: 30px;
                text-align: center;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
            }

            .form-grid {
                display: grid;
                grid-template-columns: repeat(2, 1fr);
                gap: 20px;
            }

            .form-group {
                margin-bottom: 0;
            }

            .form-group.full-width {
                grid-column: span 2;
            }

            .form-group label {
                display: block;
                margin-bottom: 8px;
                font-size: 14px;
                color: rgba(255, 255, 255, 0.8);
            }

            .form-group input {
                width: 100%;
                padding: 14px 18px;
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 12px;
                background: rgba(255, 255, 255, 0.05);
                color: #fff;
                font-size: 16px;
                transition: all 0.3s;
            }

            .form-group input:focus {
                outline: none;
                border-color: #667eea;
                background: rgba(102, 126, 234, 0.1);
                box-shadow: 0 0 20px rgba(102, 126, 234, 0.2);
            }

            .form-group input::placeholder {
                color: rgba(255, 255, 255, 0.4);
            }

            /* Step 2: 兴趣标签选择 */
            .tags-section {
                display: none;
            }

            .tags-section.active {
                display: block;
            }

            .tags-header {
                text-align: center;
                margin-bottom: 30px;
            }

            .tags-header h2 {
                font-size: 28px;
                margin-bottom: 10px;
            }

            .tags-header p {
                color: rgba(255, 255, 255, 0.6);
            }

            .selected-count {
                display: inline-block;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                padding: 8px 20px;
                border-radius: 20px;
                font-size: 14px;
                margin-top: 15px;
            }

            .tags-category {
                margin-bottom: 40px;
            }

            .category-title {
                font-size: 18px;
                font-weight: 600;
                margin-bottom: 20px;
                padding-left: 15px;
                border-left: 4px solid #667eea;
            }

            .tags-grid {
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
                gap: 15px;
            }

            .tag-card {
                background: rgba(255, 255, 255, 0.05);
                border: 2px solid rgba(255, 255, 255, 0.1);
                border-radius: 16px;
                padding: 20px 15px;
                text-align: center;
                cursor: pointer;
                transition: all 0.3s ease;
            }

            .tag-card:hover {
                transform: translateY(-5px);
                border-color: rgba(102, 126, 234, 0.5);
                box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
            }

            .tag-card.selected {
                background: linear-gradient(135deg, rgba(102, 126, 234, 0.3) 0%, rgba(118, 75, 162, 0.3) 100%);
                border-color: #667eea;
                box-shadow: 0 5px 20px rgba(102, 126, 234, 0.3);
            }

            .tag-card.selected::after {
                content: '✓';
                position: absolute;
                top: 8px;
                right: 8px;
                width: 24px;
                height: 24px;
                background: #667eea;
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 12px;
            }

            .tag-card {
                position: relative;
            }

            .tag-icon {
                font-size: 32px;
                margin-bottom: 10px;
            }

            .tag-name {
                font-size: 14px;
                font-weight: 500;
            }

            /* 歌手头像卡片 */
            .artist-grid {
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(100px, 1fr));
                gap: 15px;
            }

            .artist-card {
                background: rgba(255, 255, 255, 0.05);
                border: 2px solid rgba(255, 255, 255, 0.1);
                border-radius: 16px;
                padding: 15px 10px;
                text-align: center;
                cursor: pointer;
                transition: all 0.3s ease;
                position: relative;
            }

            .artist-card:hover {
                transform: scale(1.05);
                border-color: rgba(102, 126, 234, 0.5);
            }

            .artist-card.selected {
                border-color: #667eea;
                background: linear-gradient(135deg, rgba(102, 126, 234, 0.2) 0%, rgba(118, 75, 162, 0.2) 100%);
            }

            .artist-avatar {
                width: 60px;
                height: 60px;
                border-radius: 50%;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                margin: 0 auto 10px;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 24px;
                font-weight: bold;
            }

            .artist-name {
                font-size: 12px;
                color: rgba(255, 255, 255, 0.9);
            }

            /* 按钮样式 */
            .btn-group {
                display: flex;
                gap: 15px;
                margin-top: 30px;
            }

            .btn {
                flex: 1;
                padding: 16px 30px;
                border: none;
                border-radius: 12px;
                font-size: 16px;
                font-weight: 600;
                cursor: pointer;
                transition: all 0.3s;
            }

            .btn-primary {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
            }

            .btn-primary:hover {
                transform: translateY(-2px);
                box-shadow: 0 6px 25px rgba(102, 126, 234, 0.5);
            }

            .btn-secondary {
                background: rgba(255, 255, 255, 0.1);
                color: white;
                border: 1px solid rgba(255, 255, 255, 0.2);
            }

            .btn-secondary:hover {
                background: rgba(255, 255, 255, 0.15);
            }

            .back-link {
                text-align: center;
                margin-top: 20px;
            }

            .back-link a {
                color: rgba(255, 255, 255, 0.6);
                text-decoration: none;
                transition: color 0.3s;
            }

            .back-link a:hover {
                color: #fff;
            }

            /* 隐藏的表单字段 */
            #hiddenTags {
                display: none;
            }

            /* 自定义输入框样式 */
            .custom-input-container {
                display: none;
                margin-top: 15px;
                padding: 20px;
                background: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(102, 126, 234, 0.3);
                border-radius: 12px;
            }

            .custom-input-container.active {
                display: block;
                animation: fadeIn 0.3s ease;
            }

            @keyframes fadeIn {
                from {
                    opacity: 0;
                    transform: translateY(-10px);
                }

                to {
                    opacity: 1;
                    transform: translateY(0);
                }
            }

            .custom-input-container label {
                display: block;
                margin-bottom: 10px;
                font-size: 14px;
                color: rgba(255, 255, 255, 0.8);
            }

            .custom-input-container input {
                width: 100%;
                padding: 12px 16px;
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 10px;
                background: rgba(255, 255, 255, 0.05);
                color: #fff;
                font-size: 14px;
            }

            .custom-input-container input:focus {
                outline: none;
                border-color: #667eea;
                background: rgba(102, 126, 234, 0.1);
            }

            .custom-input-container input::placeholder {
                color: rgba(255, 255, 255, 0.4);
            }

            .custom-input-hint {
                font-size: 12px;
                color: rgba(255, 255, 255, 0.5);
                margin-top: 8px;
            }

            /* "其他"卡片特殊样式 */
            .tag-card.other-card,
            .artist-card.other-card {
                border-style: dashed;
            }

            .tag-card.other-card.active,
            .artist-card.other-card.active {
                border-color: #667eea;
                border-style: solid;
                background: linear-gradient(135deg, rgba(102, 126, 234, 0.2) 0%, rgba(118, 75, 162, 0.2) 100%);
            }

            /* 响应式 */
            @media (max-width: 768px) {
                .form-grid {
                    grid-template-columns: 1fr;
                }

                .form-group.full-width {
                    grid-column: span 1;
                }

                .tags-grid {
                    grid-template-columns: repeat(2, 1fr);
                }

                .artist-grid {
                    grid-template-columns: repeat(3, 1fr);
                }
            }
        </style>
    </head>

    <body>
        <div class="container">
            <!-- 进度条 -->
            <div class="progress-bar">
                <div class="step">
                    <div class="step-circle active" id="step1-circle">1</div>
                </div>
                <div class="step-line" id="step-line"></div>
                <div class="step">
                    <div class="step-circle" id="step2-circle">2</div>
                </div>
            </div>

            <form action="userRegister" method="post" id="registerForm">
                <!-- Step 1: 基本信息 -->
                <div class="form-section" id="step1">
                    <h2 class="section-title">🎵 创建你的音乐账号</h2>
                    <div class="form-grid">
                        <div class="form-group">
                            <label>用户名 *</label>
                            <input type="text" name="username" placeholder="请输入用户名" required>
                        </div>
                        <div class="form-group">
                            <label>密码 *</label>
                            <input type="password" name="password" placeholder="请输入密码" required>
                        </div>
                        <div class="form-group">
                            <label>邮箱</label>
                            <input type="email" name="email" placeholder="example@email.com">
                        </div>
                        <div class="form-group">
                            <label>昵称</label>
                            <input type="text" name="nickname" placeholder="你的个性昵称">
                        </div>
                        <div class="form-group">
                            <label>性别</label>
                            <select name="gender" style="width:100%; padding:12px 16px; background:rgba(255,255,255,0.08); border:1px solid rgba(255,255,255,0.15); border-radius:12px; color:#fff; font-size:14px; outline:none; appearance:none; -webkit-appearance:none;">
                                <option value="" style="background:#1a1a2e;">不透露</option>
                                <option value="male" style="background:#1a1a2e;">男</option>
                                <option value="female" style="background:#1a1a2e;">女</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label>城市</label>
                            <input type="text" name="city" placeholder="你所在的城市">
                        </div>
                        <div class="form-group full-width">
                            <label>手机号</label>
                            <input type="text" name="phone" placeholder="请输入手机号">
                        </div>
                    </div>
                    <div class="btn-group">
                        <button type="button" class="btn btn-primary" onclick="nextStep()">下一步：选择音乐偏好 →</button>
                    </div>
                </div>

                <!-- Step 2: 兴趣标签选择 -->
                <div class="form-section tags-section" id="step2">
                    <div class="tags-header">
                        <h2>🎧 告诉我们你喜欢什么</h2>
                        <p>选择你最喜欢的音乐风格和歌手，我们将为你推荐专属歌单</p>
                        <div class="selected-count">已选择 <span id="selectedCount">0</span> 个标签</div>
                    </div>

                    <!-- 流派选择 -->
                    <div class="tags-category">
                        <h3 class="category-title">🎼 音乐风格</h3>
                        <div class="tags-grid">
                            <div class="tag-card" data-genre="465" data-type="genre">
                                <div class="tag-icon">🎤</div>
                                <div class="tag-name">流行</div>
                            </div>
                            <div class="tag-card" data-genre="1259" data-type="genre">
                                <div class="tag-icon">🎧</div>
                                <div class="tag-name">嘻哈</div>
                            </div>
                            <div class="tag-card" data-genre="921" data-type="genre">
                                <div class="tag-icon">🎸</div>
                                <div class="tag-name">摇滚</div>
                            </div>
                            <div class="tag-card" data-genre="444" data-type="genre">
                                <div class="tag-icon">🎹</div>
                                <div class="tag-name">电子</div>
                            </div>
                            <div class="tag-card" data-genre="726" data-type="genre">
                                <div class="tag-icon">🎷</div>
                                <div class="tag-name">R&B</div>
                            </div>
                            <div class="tag-card" data-genre="1011" data-type="genre">
                                <div class="tag-icon">🪕</div>
                                <div class="tag-name">民谣</div>
                            </div>
                            <div class="tag-card" data-genre="1152" data-type="genre">
                                <div class="tag-icon">🎻</div>
                                <div class="tag-name">古典</div>
                            </div>
                            <div class="tag-card" data-genre="2122" data-type="genre">
                                <div class="tag-icon">🎺</div>
                                <div class="tag-name">爵士</div>
                            </div>
                            <div class="tag-card" data-genre="468" data-type="genre">
                                <div class="tag-icon">🗾</div>
                                <div class="tag-name">日语</div>
                            </div>
                            <div class="tag-card" data-genre="359" data-type="genre">
                                <div class="tag-icon">🎬</div>
                                <div class="tag-name">影视原声</div>
                            </div>
                            <div class="tag-card other-card" data-type="other-genre" id="otherGenreCard">
                                <div class="tag-icon">✨</div>
                                <div class="tag-name">其他</div>
                            </div>
                        </div>
                        <!-- 自定义风格输入框 -->
                        <div class="custom-input-container" id="customGenreContainer">
                            <label>🎵 输入你喜欢的其他音乐风格</label>
                            <input type="text" id="customGenreInput" name="customGenres" placeholder="例如：蓝调；乡村；雷鬼">
                            <div class="custom-input-hint">💡 提示：如有多个风格，请用中文分号"；"分隔</div>
                        </div>
                    </div>

                    <!-- 歌手选择 -->
                    <div class="tags-category">
                        <h3 class="category-title">🌟 热门歌手</h3>
                        <div class="artist-grid">
                            <div class="artist-card" data-artist="周杰伦" data-type="artist">
                                <div class="artist-avatar">杰</div>
                                <div class="artist-name">周杰伦</div>
                            </div>
                            <div class="artist-card" data-artist="陈奕迅" data-type="artist">
                                <div class="artist-avatar">迅</div>
                                <div class="artist-name">陈奕迅</div>
                            </div>
                            <div class="artist-card" data-artist="林俊杰" data-type="artist">
                                <div class="artist-avatar">杰</div>
                                <div class="artist-name">林俊杰</div>
                            </div>
                            <div class="artist-card" data-artist="薛之谦" data-type="artist">
                                <div class="artist-avatar">谦</div>
                                <div class="artist-name">薛之谦</div>
                            </div>
                            <div class="artist-card" data-artist="邓紫棋" data-type="artist">
                                <div class="artist-avatar">棋</div>
                                <div class="artist-name">邓紫棋</div>
                            </div>
                            <div class="artist-card" data-artist="Taylor Swift" data-type="artist">
                                <div class="artist-avatar">T</div>
                                <div class="artist-name">Taylor Swift</div>
                            </div>
                            <div class="artist-card" data-artist="Ed Sheeran" data-type="artist">
                                <div class="artist-avatar">E</div>
                                <div class="artist-name">Ed Sheeran</div>
                            </div>
                            <div class="artist-card" data-artist="Bruno Mars" data-type="artist">
                                <div class="artist-avatar">B</div>
                                <div class="artist-name">Bruno Mars</div>
                            </div>
                            <div class="artist-card" data-artist="The Weeknd" data-type="artist">
                                <div class="artist-avatar">W</div>
                                <div class="artist-name">The Weeknd</div>
                            </div>
                            <div class="artist-card" data-artist="五月天" data-type="artist">
                                <div class="artist-avatar">五</div>
                                <div class="artist-name">五月天</div>
                            </div>
                            <div class="artist-card other-card" data-type="other-artist" id="otherArtistCard">
                                <div class="artist-avatar">+</div>
                                <div class="artist-name">其他</div>
                            </div>
                        </div>
                        <!-- 自定义歌手输入框 -->
                        <div class="custom-input-container" id="customArtistContainer">
                            <label>🌟 输入你喜欢的其他歌手</label>
                            <input type="text" id="customArtistInput" name="customArtists" placeholder="例如：华晨宇；毛不易；李荣浩">
                            <div class="custom-input-hint">💡 提示：如有多个歌手，请用中文分号"；"分隔</div>
                        </div>
                    </div>

                    <!-- 隐藏字段存储选中的标签 -->
                    <input type="hidden" name="selectedGenres" id="selectedGenres">
                    <input type="hidden" name="selectedArtists" id="selectedArtists">

                    <div class="btn-group">
                        <button type="button" class="btn btn-secondary" onclick="prevStep()">← 返回上一步</button>
                        <button type="submit" class="btn btn-primary">完成注册 🎉</button>
                    </div>
                </div>
            </form>

            <div class="back-link">
                <a href="index.jsp">返回首页</a>
            </div>
        </div>

        <script>
            let selectedGenres = [];
            let selectedArtists = [];

            // 标签点击事件（排除"其他"卡片）
            document.querySelectorAll('.tag-card:not(.other-card), .artist-card:not(.other-card)').forEach(card => {
                card.addEventListener('click', function () {
                    this.classList.toggle('selected');

                    const type = this.dataset.type;
                    if (type === 'genre') {
                        const genre = this.dataset.genre;
                        if (this.classList.contains('selected')) {
                            selectedGenres.push(genre);
                        } else {
                            selectedGenres = selectedGenres.filter(g => g !== genre);
                        }
                    } else if (type === 'artist') {
                        const artist = this.dataset.artist;
                        if (this.classList.contains('selected')) {
                            selectedArtists.push(artist);
                        } else {
                            selectedArtists = selectedArtists.filter(a => a !== artist);
                        }
                    }

                    updateCount();
                });
            });

            // "其他"卡片点击事件 - 显示/隐藏输入框
            document.getElementById('otherGenreCard').addEventListener('click', function () {
                this.classList.toggle('active');
                const container = document.getElementById('customGenreContainer');
                container.classList.toggle('active');
                if (container.classList.contains('active')) {
                    document.getElementById('customGenreInput').focus();
                }
            });

            document.getElementById('otherArtistCard').addEventListener('click', function () {
                this.classList.toggle('active');
                const container = document.getElementById('customArtistContainer');
                container.classList.toggle('active');
                if (container.classList.contains('active')) {
                    document.getElementById('customArtistInput').focus();
                }
            });

            // 监听自定义输入框变化，实时更新计数
            document.getElementById('customGenreInput').addEventListener('input', updateCount);
            document.getElementById('customArtistInput').addEventListener('input', updateCount);

            function updateCount() {
                // 计算自定义输入的数量
                let customGenreCount = 0;
                let customArtistCount = 0;

                const customGenres = document.getElementById('customGenreInput').value.trim();
                if (customGenres) {
                    customGenreCount = customGenres.split(/[;；]/).filter(s => s.trim()).length;
                }

                const customArtists = document.getElementById('customArtistInput').value.trim();
                if (customArtists) {
                    customArtistCount = customArtists.split(/[;；]/).filter(s => s.trim()).length;
                }

                const total = selectedGenres.length + selectedArtists.length + customGenreCount + customArtistCount;
                document.getElementById('selectedCount').textContent = total;

                // 更新隐藏字段
                document.getElementById('selectedGenres').value = selectedGenres.join(',');
                document.getElementById('selectedArtists').value = selectedArtists.join(',');
            }

            function nextStep() {
                // 验证基本信息
                const username = document.querySelector('input[name="username"]').value;
                const password = document.querySelector('input[name="password"]').value;

                if (!username.trim() || !password.trim()) {
                    alert('请填写用户名和密码！');
                    return;
                }

                // 切换到 Step 2
                document.getElementById('step1').style.display = 'none';
                document.getElementById('step2').classList.add('active');

                // 更新进度条
                document.getElementById('step1-circle').classList.remove('active');
                document.getElementById('step1-circle').classList.add('completed');
                document.getElementById('step1-circle').textContent = '✓';
                document.getElementById('step-line').classList.add('completed');
                document.getElementById('step2-circle').classList.add('active');
            }

            function prevStep() {
                // 返回 Step 1
                document.getElementById('step1').style.display = 'block';
                document.getElementById('step2').classList.remove('active');

                // 更新进度条
                document.getElementById('step1-circle').classList.add('active');
                document.getElementById('step1-circle').classList.remove('completed');
                document.getElementById('step1-circle').textContent = '1';
                document.getElementById('step-line').classList.remove('completed');
                document.getElementById('step2-circle').classList.remove('active');
            }
        </script>
    </body>

    </html>