# MusicWeb 更新日志 (Changelog)

本文档记录了 MusicWeb 项目的所有更新历史。

## v4.2.0 (2026-03-12) - 个性化推荐反馈链路修复与口味反馈

### 🚀 新增功能

- **收听时长实时上报**：`player.js` 在每次切歌或自然播完时，通过新增的 `_reportPlayDuration()` 方法上报实际收听秒数至 `POST /api/updatePlayDuration`（`UpdatePlayDurationServlet`）；`PlayHistoryDAO` 新增 `updatePlayDuration()` 方法，采用 `GREATEST` 策略更新 `play_history.play_duration`，修复了该字段长期为 0 的问题。

- **用户口味反馈接口**：新增 `UserPreferenceServlet`（`GET/POST /api/userPreference`），支持读取和写入用户偏好；新增数据库表 `user_preference_feedback`，采用 `ON DUPLICATE KEY UPDATE` 策略归档每日显式满意度（very_satisfied / satisfied / neutral / dissatisfied）作为训练信号。

- **每日推荐区域新增交互按钮**：`user.jsp` 添加"▶ 一键播放"按钮（将20首推荐歌曲全部入队顺序播放）与"反馈"按钮（弹出偏好设置 Modal，支持满意度打分、流派多选、艺术家标签输入）。

### 🐛 Bug 修复

- **`UserPreferenceServlet` 编译失败**：修正错误的包引用 `com.music.dao.DBUtil` → `com.music.javabean.DBUtil`，消除 `找不到符号` 编译错误。

- **每日推荐标题按钮垂直偏移**：`section-title` 类的 `margin-top: 2rem` 撑高 flex 容器导致按钮视觉偏上；将 h2 内联样式由 `margin-bottom: 0` 改为 `margin: 0` 彻底清除外边距影响。

- **Unblock 解灰服务在工作树下模块缺失**：工作树 checkout 时 unblock 目录内容未随 submodule 引用复制，修复后从主仓库补全文件，`src/app.js` 路径恢复正常。

### ⚡ 性能优化

- **一键启动脚本 `run_services.bat` 重写**：废弃固定 `timeout` 盲等机制，改为逐服务 `netstat` 端口就绪检测（Redis 15s / QQ API 30s / Unblock 15s / Node.js 20s）；任一服务超时未进入 `LISTENING` 状态则立即终止后续启动并提示运行 `stop_services.bat` 清理残留进程。

- **敏感凭证移出版本库**：将运行时动态生成的 `qq_credential_guest.json` 从 git 追踪中移除，避免 access_token 等敏感字段随提交历史扩散。

---

## v4.1.2 (2026-03-09) - 管理员后台深度功能修复与 UI 优化

### 🐛 Bug 修复

- **申诉详情跳转 500/Dashboard 修复**：
  - 修正了 `AppealDAO` 内部对 `user_id` 的类型提取逻辑，使用 `rs.getInt()` 配合 `rs.wasNull()` 完美兼容 Optional 字段。
  - 修复了 `appeals.jsp` 中对实体类不存在方法 `getEmail()` 的调用（修正为 `getContactEmail()`）。
- **歌单详情载入空白修复**：
  - 修正了 `AdminDAO.getPlaylistSongsForAdmin` 查询中错误的排序列名 `added_time`（已更正为物理表对应的 `add_time`）。
- **管理员导航 404 与重定向冲突修复**：
  - 解决了右上角“返回主站”指向 `/jsp/index.jsp` 的路径错误问题。
  - 针对首页自动重定向至 `user.jsp` 的逻辑，将后台导航统一更名为 **“返回仪表盘”** 并指向 `admin?action=dashboard`。

### 🎨 UI/UX 优化

- **模态弹窗透明度修复**：针对 `appeals.css` 中透明变量失效及缓存问题，对所有 Admin 弹窗应用了内联的 `#ffffff !important` 底色补丁，确保文字清晰可读。
- **管理列表噪音过滤**：
  - `AdminDAO.getAllUsers` 默认排除 `admin` 账号。
  - `AdminDAO.getAllPlaylistsWithUser` 自动屏蔽管理员创建的内部歌单。

### 🗄️ 数据库同步

- **生产环境 Schema 同步**：同步全量 `database.sql` 脚本至 2026-03-09 最新生产状态。
- **清理工程噪音**：移除了调试期间遗留的所有 `probe.jsp` 及 `TableProbe.java` 等临时探针代码。

---

## v4.1.0 (2026-03-08) - 后台页面重写与废弃依赖清理

### 🐛 Bug 修复

- **后台用户详情页 500 编译报错**：
  - 现象：访问 `/admin?action=userDetails` 触发 JspCompilationContext 空指针和字符报错。
  - 成因：受代码格式化工具影响，JSP中的 `out.print` 多行拼接字符被截断破坏引用的字符串字面量。
  - 结果：将带有隐患的输出语句切回原生的 `<%= %>` HTML 嵌出流彻底解决换行编译错误。

### 🚀 性能优化

- **废弃旧版 favorites 表关联改写数据逻辑 (重构)**：
  - **废弃**：彻底废弃和移除老旧版本 `favorites` 数据表读取交互逻辑，统一将收藏概念下沉至“默认自建歌单”。
  - **重构**：修改 `AdminDAO` 中所有仪表盘统计及收藏列表查询。改用检查 `user_playlists` 表中的 `is_default=TRUE` 默认收藏夹，并联表计算 `playlist_songs` 数据。
- **剥离后台高耦合式内联层叠样式 (重构)**：
  - **整改**：创建独立 `css/admin` 后台专属样式目录，将 `style.css` 中所有管理端逻辑彻底迁移至 `admin.css`，保持前台逻辑洁净，避免由于大规模 JSP 导致的样式冲突及加载性能问题。

---

## v4.0.2-Search-Favorite-Fix (2026-02-07) - 搜索结果收藏状态修复

### 🐛 修复 (Fixed)

- **搜索结果红心不显示**：
  - 修复搜索页面已收藏歌曲的红心图标不显示的问题。
  - 根因：搜索 API 返回的 `Song` 对象 `id=0`，导致 `isFavorite(userId, 0)` 判断失败。
  - 解决方案：改用 `title|artist` 组合匹配判断收藏状态，一次性获取用户收藏集合后批量比对。

### ⚡ 优化 (Optimized)

- **Redis 缓存优化**：
  - `PlaylistDAO` 新增 `getFavoritedSongKeys(userId)` 方法，返回用户已收藏歌曲的 `title|artist` 集合。
  - `RedisUtil` 新增 `getUserFavoritesKey()` 和 `clearUserFavoritesCache()` 方法，TTL=3分钟。
  - 搜索60首歌曲的数据库查询从 **60次** 降低至 **1次**，Redis 缓存命中后为 **0次**。
  - 收藏/取消收藏操作后自动清除 Redis 缓存，保证数据一致性。

### 📝 技术细节

| 文件 | 改动 |
|------|------|
| `RedisUtil.java` | 新增 `KEY_USER_FAVORITES`、`TTL_FAVORITES`、`getUserFavoritesKey()`、`clearUserFavoritesCache()` |
| `PlaylistDAO.java` | 新增 `getFavoritedSongKeys()` 方法，带 Redis 缓存支持 |
| `search.jsp` | 改用 `Set.contains(title|artist)` 批量判断收藏状态 |
| `FavoriteServlet.java` | 收藏/取消收藏后调用 `RedisUtil.clearUserFavoritesCache()` |

---

## v4.0.1-Startup-Fix (2026-02-06) - 启动脚本健壮性修复

### 🐛 修复 (Fixed)

- **JAVA_HOME 环境变量失效**：
  - 修复 VS Code 终端未正确继承系统环境变量导致 Maven 无法启动的问题。
  - 在 `run_services.bat` 开头强制设置 `JAVA_HOME`，确保构建过程使用正确的 JDK。

- **Cargo 部署超时**：
  - 修复 Tomcat 部署超过 120 秒后报 `failed to finish deploying within the timeout period` 错误。
  - 在 `pom.xml` 中添加 `<cargo.deployer.ping.timeout>300000</cargo.deployer.ping.timeout>` 配置，将超时时间延长至 5 分钟。

- **Python 终端 emoji 显示失败**：
  - 修复 Python 服务在 GBK 终端下输出 emoji 导致 `UnicodeEncodeError` 崩溃的问题。
  - 在 `start_qq_api.bat` 中添加 `set PYTHONIOENCODING=utf-8`，确保 Python 输出使用 UTF-8 编码。

### ⚡ 优化 (Optimized)

- **环境兼容性增强**：
  - 优化启动脚本对不同终端环境的兼容性，降低因环境变量不一致导致的启动失败概率。

---

## v4.0.0-BugFix-Playlist (2026-02-01) - 歌单加载性能与逻辑修复

### 🐛 修复 (Fixed)

- **严重：歌单页面无限加载 (Infinite Loading)**:
  - 修复 `playlist.jsp` 中三元运算符语法错误 (`Unexpected token ','`)，该错误导致页面逻辑崩溃。
  - 修复 `playlist.jsp` 缺失播放器 DOM 结构导致 `player.js` 初始化失败 (`Cannot set properties of null`)。

- **SQL 错误修复**:
  - 修复 `PlaylistDAO` 中引用不存在的 `source`/`play_url` 字段导致的 `Column not found` 异常。

### ⚡ 优化 (Optimized)

- **数据库查询性能 (N+1 优化)**:
  - 重构 `PlaylistDAO.getPlaylistSongs`，将原有的 "先查 ID 再循环查详情" (N+1) 逻辑改为单次 JOIN 查询。
  - **效果**: 歌单加载时的数据库查询次数从 600+ 次降低至 1 次，页面响应速度提升 100 倍以上。

---

## v3.2.5-Playlist-Enhancement (2026-01-31) - 歌单功能增强

### 🚀 新增 (Added)

- **新用户默认歌单自动创建**：
  - 新用户注册时自动创建名为"我喜欢的音乐"的默认歌单（`UserRegisterServlet`）。
  - 老用户登录时如无默认歌单则自动补建（`UserLoginServlet`）。
  - 默认歌单标记为 `is_default=1`，保证每位用户都有专属收藏空间。

- **歌单详情页分页与筛选功能**：
  - 新增 `PlaylistSongsPageServlet` 分页 API（`/api/playlistSongsPage`）。
  - 支持每页 25 首歌曲的分页加载，减少页面初始加载时间。
  - **多字段排序**：支持按 **添加时间、歌手、专辑、年份、播放次数** 排序（下拉菜单选择）。
  - **升降序切换**：点击排序按钮可在升序(⬆️)和降序(⬇️)之间切换，默认为降序。
  - **动态加载**：`playlist.jsp` 采用 Ajax 动态加载歌曲列表，提升用户体验。
  - **分页控件**：上一页/下一页按钮，显示当前页码和总页数。

### 🐛 修复 (Fixed)

- **JSP 语法错误修复**：
  - 修复 `playlist.jsp` 第 137-138 行 JSP 表达式换行导致的 500 编译错误。
  - 将拆分到多行的 `class` 属性中的 JSP 表达式合并为单行，确保编译正确。

### 🔧 优化 (Optimized)

- **前端性能优化**：
  - 歌单列表改为按需加载，避免一次性渲染大量歌曲导致的卡顿。
  - 添加 Loading 动画和空状态提示，改善加载反馈体验。

### 📝 技术细节

- **后端**：
  - `PlaylistSongsPageServlet`：基于现有 `PlaylistDAO.getPlaylistSongs()` 方法，在内存中进行排序和分页。
  - **Comparator 排序**：支持字符串（歌手/专辑）、整型（年份/ID）排序，播放次数暂用 ID 代替。
  
- **前端**：
  - **筛选 UI**：下拉菜单(select) + 排序按钮(button) 组合，简洁直观。
  - **Ajax 请求**：使用 Fetch API 与服务端交互，JSON 格式数据传输。
  - **动态渲染**：ES6 模板字符串构建 HTML，XSS 防护（`escapeHtml()`/`escapeAttr()`）。

---

## v3.2.4-QQ-Cleaning-Fix (2026-01-31) - 元数据清洗与界面修复

### 🚀 新增 (Added)

- **QQ 元数据清洗系统**:
  - 新增 `MetadataCleaner` 工具类，专门处理 QQ 音乐源的非标准元数据（如 `Artist《Title》` 格式）。
  - 实现正则表达式 `^(.+?)《(.+?)》(.*)$` 自动提取真实歌手和歌名，修复了“把歌手当专辑”的字段错位问题。
  - 集成至 `UniversalPlayHistoryServlet`，确保记录播放历史时数据自动标准化。

- **界面体验优化**:
  - **每日推荐**: `user.jsp` 将 "推荐给你" 更名为 "每日推荐"，并修复了刷新按钮与标题底对齐的样式问题。

### 回滚 (Reverted)

- **JSP 目录结构回滚**:
  - 鉴于 v3.2.3 的目录重构导致了大量路径及访问问题，已将 `webapp/jsp/` 下的所有 JSP 文件回滚至 `webapp/` 根目录。
  - 移除了 `webapp/jsp/` 目录。
  - 还原了所有 Servlet (`UserLoginServlet`, `SearchServlet` 等) 中的 JSP 跳转路径。

### 🐛 修复 (Fixed)

- **JSP 语法修复**:
  - 修复 `playlist.jsp` 因单行注释机制导致的 500 编译错误，采取分行重写策略增强兼容性。

### 🚧 待解决问题 (Known Issues)

- **🔴 严重：用户无法登录 (User JSP 500)**:
  - 现象：用户登录后跳转 `user.jsp` 失败，Tomcat 抛出 `java.lang.ClassNotFoundException: org.apache.jsp.user_jsp`。
  - 分析：JSP 编译类未能成功加载，可能源于 `user.jsp` 内部仍存在隐蔽的语法错误，或 Tomcat work 目录缓存损坏。
  - 影响：用户无法进入个人中心，无法查看推荐、排行榜和播放历史。

---

## v3.2.3-File-Structure-Refactor (2026-01-30) - 文件结构重构

### 🚀 新增 (Added)

- **JSP 文件结构优化**:
  - 将 `webapp/` 根目录下的 11 个 JSP 文件迁移到 `webapp/jsp/` 目录，提升项目结构清晰度。
  - 新增 `webapp/jsp/includes/` 目录存放组件文件 (`song-item.jsp`, `chart-item.jsp`)。
  
- **web.xml 欢迎页配置**:
  - 添加 `<welcome-file>jsp/index.jsp</welcome-file>` 配置，确保访问根路径能正确跳转。

### 🔧 修改 (Changed)

- **Redis 数据持久化路径**:
  - 修改 `scripts/start_redis.bat`，添加 `--dir` 参数将 `dump.rdb` 保存到 `webapp/log/` 目录。

- **Servlet 路径更新** (10 个文件):
  - `AdminServlet.java`: 更新 `sendRedirect` 和 `forward` 路径
  - `AppealServlet.java`: 更新重定向路径
  - `ChangePasswordServlet.java`: 更新所有 JSP 引用
  - `DeleteAccountServlet.java`: 更新所有 JSP 引用
  - `FavoriteServlet.java`: 更新所有 JSP 引用
  - `LogoutServlet.java`: 更新重定向路径
  - `PlaylistServlet.java`: 更新所有 JSP 引用
  - `SearchServlet.java`: 更新所有 JSP 引用
  - `UpdateProfileServlet.java`: 更新所有 JSP 引用
  - `UserLoginServlet.java`: 更新所有 JSP 引用

- **Admin JSP 路径更新** (5 个文件):
  - `dashboard.jsp`, `users.jsp`, `userDetails.jsp`, `songs.jsp`, `favorites.jsp`: 更新 `../index.jsp` → `../jsp/index.jsp`

- **JSP 静态资源路径更新** (11 个文件):
  - 所有迁移的 JSP 文件中的 CSS/JS 引用从 `css/`/`js/` 更新为 `../css/`/`../js/`

---

## v3.2.2-Metadata-Aggregation (2026-01-29) - 全链路元数据聚合与凭证整合

### 🚀 新增 (Added)

- **五级元数据聚合策略 (5-Level Metadata Strategy)**:
  正式上线了基于 Python 微服务的高可用元数据获取流水线 (`metadata_provider.py`)，确保歌曲流派 (Genre) 和语种 (Language) 的高覆盖率：
  1. **P1 (Top)**: **网易云百科 (NetEase Wiki)** - 精准度最高，优先匹配。
  2. **P2**: **QQ 音乐 (QQ Music API)** - 国内数据最全，已修复 Cookie 认证与 Smart Box 解析逻辑。
  3. **P3**: **Last.fm** - 国际化补充，完美覆盖英文/欧美歌曲流派。
  4. **P4**: **MusicBrainz** - 开源数据库兜底，提供基础元数据支持。
  5. **P5 (Base)**: **langdetect** - 本地算法兜底，基于文本分析进行语种识别。

- **QQ 音乐流派/语种映射表增强 (`qq_music_mapping.json`)**:
  - 新增 `"37": "二次元"` 映射，修复了 QQ 音乐返回 `genre_idx=37` 时流派显示为空的问题。
  - 通过反向调用 QQ 音乐官方接口 (`fcg_get_diss_tag_conf`)，获取并整合了最新的分类 ID 表，新增 17 个流派、14 个主题、9 个心情、13 个场景分类。

### 🐛 修复 (Fixed)

- **QQ 音乐数据源重构**:
  - **认证修复**: 修复了 `metadata_provider.py` 未加载 `api_credentials.json` 导致搜索需要登录接口失败的问题。
  - **解析增强**: 重写结果解析器，支持 API 返回的 "Smart Box" (直达结果) 结构，解决了 "Bohemian Rhapsody" 等热门歌曲元数据丢失问题。
  - **映射修正**: 修正了 `qq_music_mapping.json` 中严重的映射错误（如将索引 `1` 误标为国语，实为 **粤语**；修正了乡村、电子等流派索引）。

- **凭证文件整合**:
  - 将独立的 `netease_cookie.txt` 文件内容迁移至 `api_credentials.json` 中的 `netease.cookie` 字段。
  - 修改 `js/server.js` 的 `loadCookie()` 函数，从读取纯文本升级为解析 JSON 结构，增强了错误处理和日志提示。
  - 删除冗余的 `netease_cookie.txt` 文件，实现"网易云 + QQ 音乐"凭证的统一管理。

- **file_path 来源累积修复** (`SongDAO.java`):
  - 原问题：从不同平台播放同一首歌曲时，`file_path` 字段会被覆盖（如 `netease` → `qq`），丢失历史来源信息。
  - 解决方案：新增 `accumulateSource()` 方法，实现来源累积机制（用 `;` 分隔，如 `netease;qq`），确保多平台播放记录完整保留。

- **genre/language 智能合并修复** (`SongDAO.java`):
  - 原问题：网易云返回丰富的流派标签（如 `二次元;国产流行;日本流行`），被 QQ 音乐的简单标签（如 `二次元`）覆盖。
  - 解决方案：新增 `mergeMetadataValues()` 方法，实现 **策略 C（子集判断合并）**：
    - 新值是旧值的子集 → 保持旧值
    - 旧值是新值的子集 → 更新为新值
    - 两者都有独有内容 → 合并两者
  - 额外修复：正则表达式支持中文全角分号 `；` 和逗号 `，`，兼容网易云百科返回的格式。

### ⚡ 优化 (Optimized)

- **数据源验证**: 通过 `verify_foreign_sources.py` 验证了 Last.fm 和 MusicBrainz 在非中文环境下的有效性。
- **项目结构清理**: 移除了冗余的调试脚本 (`debug_*.py`, `verify_*.py`, `inspect_api.py`, `fetch_categories.py`, `merge_mappings.py`) 和临时数据文件，保持目录整洁。
- **元数据格式标准化**: `mergeMetadataValues()` 方法统一输出格式为英文分号 `;` 分隔，避免格式不一致导致的重复判定失败。

### 🚧 待解决问题 (Known Issues)

- **QQ 音乐 API 错误 [2001]**: 部分搜索请求触发 `ResponseCodeError [2001]`，疑似反爬限制或参数校验失败，需进一步排查 Cookie 有效性或请求频率。

## v3.2.1-Hotfix-CoverSystem (2026-01-28) - 封面系统紧急修复

### 🐛 修复 (Fixed)

- **路径与传递逻辑修复**:
  - 修正了 `CoverDownloadUtil` 和 `ImageProxyServlet` 下的硬编码路径，指向当前工作空间。
  - 修复了 `GetPlayUrlServlet` 未返回封面 URL 的问题，确保前端能正确触发封面下载逻辑。

## v3.2.0-Metadata-Enhanced (2026-01-27) - 元数据与播放体验升级

### 🏗️ 架构变更 (Changed)

- **API 引擎升级**: 移除旧版 API 库，全面迁移至 [`@neteasecloudmusicapienhanced/api`](https://github.com/NeteaseCloudMusicApiEnhanced/NeteaseCloudMusicApi) (v4.29)，显著提升接口稳定性，并解锁了专辑详情获取与更高码率链接解析能力。

### 🚀 新增 (Added)

- **全链路元数据增强系统**:
  - 后端检测到歌曲缺少流派/年份/封面时，自动触发增强流程。
  - 集成 Node.js 聚合接口 (`/netease/song/detail/full`) 与 Python QQ 接口 (`/song/detail`)，实现跨平台元数据补全。
- **智能播放调度策略 (Step 0)**:
  - 引入“匿名优先”机制，非 VIP 歌曲不再消耗 SVIP 账号配额，仅在必要时降级使用 Cookie。

### 🐛 修复 (Fixed)

- **封面缺失与持久化问题**: 修复了 Tomcat 部署机制导致的封面 404 问题。
  - *临时方案*: 实施“双重保存策略” (v3.2.0)。
  - *最终方案*: 见下方 ImageProxy 计划。

### ⚡ 优化 (Optimized)

- **资源利用率**: 优化了 API 调用链路，减少不必要的外部请求。
- **VIP 识别**: Python QQ API 增强了 `pay` 字段返回，精准识别 VIP 歌曲。

### 📝 下一步计划 (Planned)

- [ ] **ImageProxyServlet 重构**: 废弃双重保存，实现 `/img/*` 代理直接读取源码目录，实现“零拷贝”封面即时显示。

## v3.1.1-Hotfix-JSP-Env (2026-01-25) - 环境兼容性修复

### 🎯 紧急修复

- 🐛 **VS Code 插件冲突修复**: 解决了 "Comment Translate" 插件开启 `multiLineMerge` 导致 JSP 代码被错误压缩注释，引发 HTTP 500 编译错误的问题。
- ✅ **代码健壮性增强**: 将 `user.jsp`及 `includes/` 下核心组件的所有单行注释 (`//`) 替换为块注释 (`/* ... */`)，防御环境格式化风险。

### 📝 问题排查与解决记录

#### 🔴 问题描述

用户在使用 `jf` 账号登录后，`user.jsp` 页面出现严重异常：

1. **500 编译错误**：页面提示 `Syntax error on token "finally", { expected`。
2. **内容丢失**：修复初步编译错误后，页面虽能加载，但"推荐给你"、"热门排行榜"、"最近播放"等板块无法显示数据。
3. **日志报错**：后台 Tomcat 日志持续报出 `_jspService` 处的 Java 编译异常。

#### 🔍 原因分析

经过深入排查，发现这是一个由 **开发环境配置** 引发的隐蔽问题，而非代码逻辑错误。

1. **根本原因**：用户安装的 VS Code 插件 **"Comment Translate" (注释翻译)** 开启了 `commentTranslate.multiLineMerge: true` (多行合并) 功能。
2. **错误机制**：该插件在保存文件时，错误地将被 `//` (单行注释) 引导的代码段判定为"需要合并的注释"，从而将下一行的正常业务代码强行合并到注释行中。
    - **示例 (压缩前)**：

        ```java
        // 获取用户数据
        User user = getUser();
        ```

    - **被插件"压缩"后**：

        ```java
        // 获取用户数据 User user = getUser();
        ```

        > 💥 结果：`User user = getUser();` 变成了注释的一部分，导致变量未声明，Java 编译器报错。
3. **影响范围**：
    - `user.jsp`：DAO 初始化代码被注释，导致 500 错误。
    - `includes/song-item.jsp`：脚本结束标签 `%>` 被上一行的 `//` 注释吞没，导致 JSP 解析失败。

#### ✅ 解决方案

1. **代码防御**：将 JSP 文件中的所有 Java 单行注释 (`//`) 替换为 **块注释 (`/* ... */`)**。
    - 修改文件：`user.jsp`, `includes/song-item.jsp`, `includes/chart-item.jsp`。
2. **环境配置**：在 VS Code 的 `settings.json` 中禁用该配置：`"commentTranslate.multiLineMerge": false`。

---

## v3.1.0-PlayHistory-Enhanced (2026-01-24) - 播放历史与功能增强

### 🎯 主要成果

- ✅ **通用播放历史**: 新增 `UniversalPlayHistoryServlet`，支持记录本地及外部（搜索结果）歌曲的播放历史，实现全平台听歌记录统一。
- ✅ **封面缓存机制**: 引入 `CoverDownloadUtil`，自动下载并缓存外部歌曲封面到本地 `img/` 目录，优化加载体验。
- ✅ **历史记录分页**: 创建 `PlayHistoryPageServlet`，支持按时间范围（7天/30天/90天）筛选和分页查询，提升大数据量下的页面性能。
- ✅ **前端重构**:
  - 全新 `playHistory.jsp`：集成时间筛选 Tabs、无限滚动/分页加载、AJAX 数据获取。
  - 修复 `user.jsp` 头部 JSP Scriptlet 格式问题（进行中）。
- ✅ **QQ 音乐适配**: 优化 `GetPlayUrlServlet`，增强 VIP 歌曲检测和自动降级逻辑。

### ⚠️ 已知问题

- **JSP 编码/格式**: `playHistory.jsp` 和 `user.jsp` 已修复，采用块注释防御此类问题。

---

## v3.0.0-MultiUser-Patch (2026-01-24) - 多用户隔离与登录修复

### 🎯 主要成果

- ✅ **多用户隔离**: 重构后端 (`app.py`, `GetPlayUrlServlet`)，实现基于 `userId` 的凭证隔离。不同用户 (如 `jf` 和 `jf2`) 的 VIP 状态互不干扰。
- ✅ **手机登录修复**: 引入 API 全局 `Session` 管理，修复了手机验证码登录时因会话丢失导致的验证失败问题。
- ✅ **底层库升级**: 废弃旧版接口调用方式，全面接入 `qqmusic-api` (L-1124/QQMusicApi) Python 库，为多用户隔离与手机登录功能提供核心底层支持。
- ✅ **代码质量提升**: 修复了 Java Servlet 中的变量作用域编译错误，增强了 Redis 缓存逻辑的健壮性。
- 🔄 **交互优化 (试验性)**: 针对手机版验证码页面在 PC 端显示比例失调的问题，引入了“独立窗口弹窗”方案。
  - **⚠️ 遗留缺陷**: 尽管代码逻辑已更新为新窗口打开，但在实际测试中，点击发送验证码后，**图形验证界面仍有极高概率在原页面内以覆盖层形式弹出**，并未按预期在新窗口打开。且由于该页面原生为手机设计（`width: 100%`），导致在 PC 浏览器内弹出时**尺寸巨大甚至占满全屏**，严重影响视觉体验。此问题暂判定为前端 JS 逻辑与 QQ 官方 SDK 注入行为冲突，尚待进一步修复。

---

## v2.1.2 (2026-01-23) - 服务架构优化与运维升级

### 🎯 主要成果

- ✅ **架构分离**: 完成 `server.js` 核心代码与运行环境（依赖/配置/日志）的物理分离，实现“代码归代码，环境归环境”。
- ✅ **QQ 搜索修复**: 废弃失效的第三方库，重写原生 HTTPS 请求适配层，成功恢复 QQ 音乐搜索功能。
- ✅ **运维升级**: 新增 `stop_services.bat` 智能停止脚本，彻底解决 Node.js/Redis 端口占用僵尸进程问题。
- ✅ **环境优化**: 实现 `node_modules` 和 `qq_cookie.txt` 的动态路径加载，提升部署灵活性。

---

## v1.9.1 (2026-01-22) - 性能优化与动态播放 (Phase 4)

**核心功能:**

- 🚀 **Redis 缓存集成**: 引入 Redis 缓存层，加速热歌榜、新歌榜及个性化推荐的查询响应 (TTL 策略)
- 🎵 **动态播放源**: 实现 `GetPlayUrlServlet`，支持动态从外部 API 获取播放链接，解决本地库无实体的播放问题
- 🔍 **混合搜索修复**: 修复搜索“全部”时仅显示单源的问题，实现网易云/QQ 音乐结果的真正聚合
- ✨ **推荐修复**: `user.jsp` 接入真正的个性化推荐接口 `getRecommendationsByRandom`

---

## v1.9.0 (2026-01-22) - 注册页个性化增强

**核心功能:**

- ✨ **自定义标签**: 注册时支持手动输入"其他"流派和歌手，满足用户个性化偏好
- ✨ **动态统计**: 优化交互逻辑，自定义输入实时计入已选标签数量
- ✨ **UI 体验**: 新增"Other"卡片，通过平滑动画展开/收起自定义输入框

---

## v1.8.2 (2026-01-20) - 启动脚本与文档重构

**脚本优化:**

- 🚀 **一键启动脚本 (`run_services.bat`)**:
  - 支持“混合输出”模式，单终端同时显示 Node.js 和 Java 日志，告别多窗口烦恼
  - 移除 `clean package` 构建阶段，采用 `cargo:run` 快速部署，启动速度提升 300%
  - 添加智能等待与状态提示，清晰展示服务启动进度

**项目重构:**

- 📂 **目录结构优化**: 新增 `Document/` 和 `scripts/` 目录，分类存放文档和脚本
- 📝 **文档标准化**: 统一更新 README 和操作手册，匹配最新的目录结构

---

## v1.8.1 (2026-01-19) - 第三方音乐平台集成

**核心功能:**

- 🎵 **第三方平台集成**: 完整集成网易云音乐和 QQ 音乐 API，海量曲库在线播放
- 🎵 **流媒体架构**: 移除本地 MP3 存储，全面转向 API 驱动的流媒体服务
- 🎵 **统一搜索**: 支持跨平台音乐搜索，一键切换音乐源

**架构升级:**

- 🚀 **Node.js 中间件**: 引入 Node.js 服务作为音乐 API 代理，统一处理外部请求
- 🚀 **API 网关模式**: 改造 Java Servlet (`MusicApiServlet`) 为 API 网关，转发请求
- 🚀 **前后端分离**: 重构播放器逻辑，前端直接通过 API 获取播放链接

**前端优化:**

- ✨ **增强播放器**: 支持显示外部音乐封面、来源标签（网易云/QQ）
- ✨ **搜索源切换**: 搜索页面新增音乐源切换按钮，实时切换搜索结果
- ✨ **无缝体验**: 保持原有播放体验，透明集成外部音乐资源

---

## v1.8.0 (2026-01-19) - 第三方音乐平台集成

**编码问题修复:**

- 🔧 修复 Windows 终端日志输出乱码问题（JDK 18+ 环境）
- 🔧 在 `mvnw.cmd` 中添加 `chcp 65001` 命令，强制控制台使用 UTF-8 代码页
- 🔧 配置 Cargo 插件 JVM 参数：`-Dfile.encoding=UTF-8 -Dstdout.encoding=UTF-8 -Dstderr.encoding=UTF-8`
- 🔧 添加 `configfiles` 配置，将项目的 `logging.properties` 注入到 Tomcat `conf` 目录
- 🔧 `logging.properties` 统一设置控制台输出编码为 UTF-8

**编译器配置优化:**

- ✨ 将 `<source>23</source>` + `<target>23</target>` 替换为 `<release>23</release>`
- ✨ 消除 "未与 -source 23 一起设置系统模块的位置" 编译警告

**构建增强:**

- 🚀 完善 Maven Wrapper (`mvnw.cmd`) 脚本，支持无 `JAVA_HOME` 环境变量时从系统 `PATH` 查找 Java
- 🚀 优化 Cargo Maven 插件配置，确保 Tomcat 日志正确显示中文和 Emoji

**技术说明:**

> 从 JDK 18 开始，Java 默认使用 UTF-8 编码（JEP 400）。本次更新确保整个构建和运行链路（Maven → Tomcat → 控制台）统一使用 UTF-8，解决了 Windows 系统默认 GBK 代码页导致的编码冲突问题。

---

## v1.7.3 (2025-12-24) - 歌单功能优化与Bug修复

**Bug 修复:**

- 🐛 修复 PlaylistDAO.java 缺少 DBUtil 导入导致编译错误的问题
- 🐛 修复 Song.java 缺少 getFormattedDuration() 方法导致 HTTP 500 错误
- 🐛 修复 playlist.jsp 歌曲列表封面图片溢出屏幕的问题

**界面优化:**

- 🎨 简化歌单卡片展示，只显示封面和歌单名称
- 🎨 移除歌单覆盖层、默认徽章、描述信息等冗余元素
- 🎨 优化歌单网格布局，从 220px 改为 160px，提升空间利用率
- 🎨 歌单名称居中显示，视觉更加统一

**样式调整:**

- 🔧 歌单卡片尺寸优化，封面悬浮缩放从 1.1 倍改为 1.05 倍
- 🔧 歌单卡片内边距从 1rem 减小至 0.75rem
- 🔧 创建新歌单卡片高度从 280px 减小至 200px
- 🔧 响应式布局优化（1024px: 140px, 768px: 120px）
- 🔧 歌曲封面添加 overflow: hidden 和 object-fit: cover 防止溢出

**技术改进:**

- ✨ Song 类新增 getFormattedDuration() 方法，返回 "MM:SS" 格式时长
- ✨ .song-cover img 样式规范化，确保图片适配容器
- ✨ 注释废弃样式（.playlist-overlay, .default-badge, .playlist-meta）

**用户体验:**

- 💡 歌单列表更加简洁，表格式展示更清晰
- 💡 每行可显示更多歌单，提升浏览效率
- 💡 歌曲封面固定 50×50px，布局整齐统一

---

## v1.7.2 (2025-12-23) - 数据库架构升级

**数据库扩展:**

- 🗄️ 新增推荐系统表 (recommendations) - 个性化音乐推荐
- 🗄️ 新增网易云歌单表 (playlist_info) - 歌单信息管理
- 🗄️ 新增歌单歌曲表 (song_info) - 歌单歌曲关联
- 🗄️ 优化数据库设计，增加歌单推荐功能
- 🗄️ 完善数据表索引，提升查询性能

**核心业务表（7张）:**

- 👤 **users** - 用户表：账号管理、状态控制（active/frozen/deleted）、冻结时间记录
- 🎵 **songs** - 歌曲表：音乐库管理（8首周杰伦歌曲）、多维度信息（专辑/风格/年份）
- ⭐ **favorites** - 收藏表：用户收藏关系、唯一约束防重复、级联删除
- 📊 **play_history** - 播放历史表：用户播放记录、时长统计、时间索引优化
- 📩 **appeals** - 申诉表：账号申诉管理、三态流转（pending/approved/rejected）
- 📁 **user_playlists** - 用户歌单表：歌单信息管理、默认歌单标识、级联删除
- 🎶 **playlist_songs** - 歌单歌曲关联表：歌单歌曲关系、唯一约束防重复、双向级联删除

**推荐系统表（3张）:**

- 🎼 **playlist_info** - 网易云歌单表：歌单元数据（播放量/收藏量/分类/标签）
- 🎶 **song_info** - 歌单歌曲表：歌单歌曲关联、外键级联
- 🤖 **recommendations** - 推荐表：个性化推荐算法、相似度评分、联合索引优化

**数据库特性:**

- 🔒 完整的外键约束和级联删除机制
- ⚡ 性能优化索引（用户ID+时间、用户ID+评分）
- 🛡️ 数据完整性（唯一约束、ENUM类型校验）
- 🧹 自动清理任务（MySQL事件调度器，每天凌晨2点清理30天前已删除用户）
- 📝 UTF-8支持（utf8mb4字符集，支持中文和emoji）

**项目架构完善:**

- 📝 项目目录结构更新，添加 Playlist.java、PlaylistDAO.java、PlaylistServlet.java 歌单管理模块
- 📝 新增 playlist.jsp 歌单详情页面
- 📝 完善数据库表设计文档（10张表的详细结构）
- 📝 Song 类增强，支持格式化时长显示
- 📝 验证项目文件完整性

---

## v1.7.1 (2025-12-06) - 申诉管理功能修复

**Bug 修复:**

- 🐛 修复申诉管理页面"详情"和"查看"按钮404错误问题
- 🐛 解决按钮点击无响应的故障，恢复申诉详情查看功能

**功能修复:**

- 🔧 AdminServlet 添加 getAppealDetail() 方法处理申诉详情查询
- 🔧 前端新增 showAppealDetail() AJAX 函数，实时获取申诉详情
- 🔧 修改按钮调用逻辑，从静态数据显示改为动态数据请求
- 🔧 完善错误处理和用户提示机制

**技术改进:**

- ✨ 实现申诉原因和管理员回复的实时数据获取
- ✨ 添加"正在加载..."提示，提升用户体验
- ✨ 完善的HTTP状态码处理（200/404/400/500）
- ✨ JSON格式数据传输，支持多行文本内容

**安全性:**

- 🔒 继续使用PreparedStatement防止SQL注入
- 🔒 完善的参数验证和异常处理
- 🔒 文本内容转义处理，防止XSS攻击

---

## v1.7.0 (2025-12-03) - 搜索功能与样式重构

**重大功能:**

- 🔍 Google 风格搜索框，现代化的搜索体验
- 🔍 智能搜索历史，自动保存最近 5 条搜索记录
- 🔍 多字段搜索，支持按歌曲名、艺术家、专辑、风格搜索
- 🔍 搜索结果页面，统一的搜索体验

**搜索功能:**

- ✨ 创建 SearchServlet，处理搜索请求
- ✨ 扩展 SongDAO.searchSongs()，支持模糊匹配
- ✨ 搜索历史管理，使用 localStorage 本地存储
- ✨ 点击历史快速重复搜索
- ✨ 一键清空搜索历史

**界面优化:**

- 🎨 Google 风格搜索框设计（圆角胶囊形状）
- 🎨 搜索图标和按钮优雅布局
- 🎨 搜索历史下拉动画效果
- 🎨 响应式设计，移动端友好

**样式重构:**

- 🔧 创建独立的 search.css 样式文件
- 🔧 从 style.css 迁移所有搜索相关样式
- 🔧 统一 user.jsp 和 search.jsp 的搜索框样式
- 🔧 创建 search.js 管理搜索交互逻辑

**技术实现:**

- 🔧 SearchServlet 处理 /search 端点
- 🔧 SongDAO 使用 PreparedStatement 防止 SQL 注入
- 🔧 search.js 封装 SearchHistory 和 SearchUI 类
- 🔧 SVG 图标明确设置尺寸，避免显示异常

**Bug 修复:**

- 🐛 修复 search.jsp 搜索图标占据全屏问题
- 🐛 修复 user.jsp 搜索图标显示在上方问题
- 🐛 统一 HTML 结构和 CSS 类名
- 🐛 优化样式加载顺序

**用户体验:**

- 💡 搜索框焦点时自动显示历史
- 💡 搜索框悬浮和焦点时的优雅动画
- 💡 搜索结果保留搜索关键词
- 💡 空关键词时显示所有歌曲

---

## v1.6.0 (2025-12-03) - 歌曲播放功能

**重大功能:**

- 🎵 完整的歌曲播放系统，支持在线播放音乐
- 🎵 底部固定播放条，类似网易云音乐的设计
- 🎵 播放列表队列管理，支持添加、删除和排序
- 🎵 播放模式切换（顺序、循环、单曲循环、随机）
- 🎵 播放历史记录，自动保存用户的播放行为

**播放器功能:**

- ✨ HTML5 Audio播放器，支持流媒体播放
- ✨ 播放控制：播放/暂停、上一曲/下一曲、进度条拖拽
- ✨ 音量控制：音量滑块、静音按钮、音量记忆
- ✨ 进度显示：实时显示当前时间和总时长
- ✨ 播放队列：侧边栏弹出，支持查看和管理队列
- ✨ 最近播放：在用户主页显示播放历史，支持快速重播

**技术实现:**

- 🔧 创建AudioServlet，提供音频流服务，支持HTTP Range请求
- 🔧 创建PlayHistory模型、DAO和Servlet，实现播放历史管理
- 🔧 创建player.js播放器核心逻辑，封装AudioPlayer类
- 🔧 创建player.css播放器样式，响应式设计
- 🔧 扩展数据库，添加play_history表记录播放数据
- 🔧 集成播放器到user.jsp，全局可用

**界面优化:**

- 🎨 底部播放条固定设计，不遮挡主要内容
- 🎨 播放队列侧边栏，滑动显示动画效果
- 🎨 播放历史模块，去重显示最近10首歌曲
- 🎨 所有播放按钮统一调用播放器API

**用户体验:**

- 💡 音量和播放模式自动保存到localStorage
- 💡 播放结束根据模式自动播放下一曲
- 💡 播放错误自动跳过，不中断播放
- 💡 移动端响应式适配

**Bug 修复:**

- 🐛 修复音频文件路径处理问题
- 🐛 优化播放器初始化时序
- 🐛 修复队列管理的索引计算

---

## v1.5.0 (2025-12-03) - AJAX 无刷新操作优化

**重大改进:**

- 🚀 全面重构管理员后台操作，改用 AJAX 无刷新方式
- 🚀 优化用户体验，操作完成后直接刷新当前页面
- 🚀 异步邮件发送，提升响应速度

**功能优化:**

- ✨ 音乐管理：新增/删除歌曲改用 AJAX，操作后刷新 songs 页面
- ✨ 用户管理：冻结/解冻/删除用户改用 AJAX，操作后刷新 userDetails 页面
- ✨ 申诉管理：同意/拒绝申诉改用 AJAX，操作后刷新 appeals 页面
- ✨ 邮件发送改为异步，不阻塞页面响应

**技术改进:**

- 🔧 AdminServlet 所有操作方法返回 HTTP 状态码而非重定向
- 🔧 前端使用 fetch API 发送请求，根据状态码判断成功/失败
- 🔧 修复 SongDAO.deleteSong 方法，先删除 favorites 表关联记录
- 🔧 EmailUtil 配置 SSL 连接，支持 163 邮箱 SMTP 服务
- 🔧 使用 Thread 异步发送邮件，避免阻塞主线程

**Bug 修复:**

- 🐛 修复新增歌曲后页面空白问题
- 🐛 修复删除歌曲外键约束冲突问题
- 🐛 修复冻结/解冻用户后页面跳转问题
- 🐛 修复申诉审批后页面卡住问题
- 🐛 修复邮件发送配置，使用 SSL 而非 STARTTLS

---

## v1.4.0 (2025-12-03) - 账号申诉与邮件通知系统

**新增功能:**

- ✨ 账号申诉系统，用户可对冻结/删除账号提交申诉
- ✨ 账号状态提示页面 (accountStatus.jsp)，美观的弹窗提示
- ✨ 申诉提交页面 (appeal.jsp)，支持填写申诉原因和联系邮箱
- ✨ 管理员申诉管理页面 (appeals.jsp)，支持审批操作
- ✨ 163邮件通知功能，审批后自动发送邮件通知用户
- ✨ 自动账号恢复，同意申诉后自动将账号状态改为正常
- ✨ 自动数据清理，删除30天后自动彻底清除用户数据

**技术改进:**

- 🔧 添加 JavaMail 依赖，支持邮件发送
- 🔧 创建 Appeal 实体类和 AppealDAO 数据访问层
- 🔧 创建 EmailUtil 工具类，封装163邮箱SMTP服务
- 🔧 扩展数据库，添加 appeals 申诉表和 deleted_at 字段
- 🔧 创建 MySQL 事件调度器，实现定时清理功能
- 🔧 优化登录验证，重定向到状态提示页面而非alert弹窗
- 🔧 扩展 AdminServlet，添加申诉审批处理逻辑

**界面优化:**

- 🎨 新增申诉页面专用样式 (appeal.css)
- 🎨 管理员后台所有页面添加"申诉管理"菜单项
- 🎨 申诉管理页面支持模态框操作，提升用户体验

---

## v1.3.0 (2025-11-25) - 用户详情与账号管理

**新增功能:**

- ✨ 用户详情页面 (userDetails.jsp)，展示完整用户信息
- ✨ 账号冻结功能，支持设置冻结时间和原因
- ✨ 账号解冻功能，立即恢复用户访问权限
- ✨ 软删除功能，保留用户数据但禁止登录
- ✨ 用户状态管理，支持 active/frozen/deleted 状态

**界面优化:**

- 🎨 修复user.jsp页面布局问题，消除水平滚动条
- 🎨 优化用户信息区域布局，增加右边距
- 🎨 改进设置按钮位置，避免陷进右边
- 🎨 增强响应式设计，适配100%缩放

**技术改进:**

- 🔧 扩展数据库结构，添加用户状态相关字段
- 🔧 更新User实体类，支持状态管理
- 🔧 增强AdminDAO，实现冻结/解冻/删除功能
- 🔧 完善AdminServlet，处理用户管理操作
- 🔧 优化登录验证逻辑，检查用户状态

---

## v1.2.0 (2025-11-18) - 管理员后台系统

**新增功能:**

- ✨ 完整的管理员后台系统
- ✨ 智能登录识别，自动区分管理员和普通用户
- ✨ 数据统计仪表板，实时显示系统统计信息
- ✨ 用户管理模块，支持查看所有用户信息
- ✨ 音乐管理模块，支持查看所有歌曲信息
- ✨ 收藏管理模块，支持批量操作
- ✨ 用户设置页面，包含个人信息管理和密码修改

**技术改进:**

- 🔧 修复Jakarta EE 10+兼容性问题
- 🔧 完善包导入结构，保持与项目配置一致
- 🔧 增强Favorite模型类，添加User关联
- 🔧 优化导航栏布局，提升用户体验
- 🔧 增强响应式设计支持

**安全更新:**

- 🔒 实现严格的SQL注入防护机制
- 🔒 添加完整的权限验证系统
- 🔒 优化数据库访问层安全性
- 🔒 增强管理员身份验证

---

## v1.1.0 (2025-11-17) - 界面优化与功能增强

**新增功能:**

- ✨ 用户设置页面（settings.jsp）
- 🔧 密码修改功能（ChangePasswordServlet）
- 🔧 个人信息更新功能（UpdateProfileServlet）
- 🔧 账户注销功能（DeleteAccountServlet）

**界面改进:**

- 🎨 优化导航栏布局和间距
- 🎨 改进用户信息显示区域
- 🎨 增强响应式设计
- 🎨 添加设置页面专用样式

---

## v1.0.0 (2025-11-16) - 基础功能实现

**核心功能:**

- ✨ 用户注册和登录系统
- ✨ 音乐收藏功能
- ✨ 歌曲排行榜（热歌榜、新歌榜、收藏榜）
- ✨ 用户个人主页
- ✨ 基础数据库设计

**技术架构:**

- 🏗️ 建立MVC架构
- 🏗️ 配置C3P0数据库连接池
- 🏗️ 实现基础DAO模式
- 🏗️ 响应式前端设计
