# MusicWeb 项目文档

## 项目概述

MusicWeb 是一个基于 Java Web 技术栈开发的在线音乐平台，提供用户注册、登录、音乐收藏、排行榜等功能。项目采用经典的 MVC 架构模式，使用 JSP + Servlet + JavaBean 技术实现，同时包含完整的管理员后台系统，支持数据库安全管理和数据监控。

## 技术栈

### 后端技术

- **Java 23** - 主要编程语言
- **Jakarta Servlet 6.1** - 处理 HTTP 请求
- **JSP 3.1** - 视图层模板引擎
- **JSTL 3.0** - JSP 标签标签库
- **MySQL 8.4.0** - 数据库
- **Redis 5.0+** - 缓存数据库
- **C3P0 0.9.5.5** - 数据库连接池
- **Jedis 5.1.0** - Redis 客户端

### 构建工具

- **Maven 3.x** - 项目构建和依赖管理
- **Maven Compiler Plugin 3.13.0** - Java 编译插件
- **Maven War Plugin 3.4.0** - WAR 包构建插件

### 开发工具

- **JUnit 5.13.2** - 单元测试框架

## 项目核心结构

```text
MusicWeb/
├── pom.xml                          # Maven 项目配置文件
├── database.sql                     # 数据库初始化脚本
├── Document/                        # 项目文档目录
│   ├── README.md                    # 项目核心文档
│   ├── OPERATION_MANUAL.md          # 运维操作手册
│   ├── CHANGELOG.md                 # 项目更新日志
│   └── claude.md                    # 开发过程对话记录
├── scripts/                         # 自动化运维脚本目录
│   ├── run_services.bat             # 一键启动所有服务
│   ├── stop_services.bat            # 一键停止所有服务
│   ├── start_qq_api.bat             # Python QQ 音乐服务启动脚本
│   ├── start_redis.bat              # Redis 服务启动脚本
│   ├── start.bat                    # Node.js 网易云服务启动脚本
│   └── mvnw.cmd                     # Maven Wrapper 脚本
├── src/
│   └── main/
│       ├── java/com/music/
│       │   ├── javabean/            # 实体类目录
│       │   ├── dao/                 # 数据访问层目录
│       │   │   ├── SongDAO.java              # 歌曲与元数据管理
│       │   │   ├── PlayHistoryDAO.java       # 播放历史数据管理
│       │   │   └── ...
│       │   ├── servlet/             # 业务控制层目录
│       │   │   ├── AdminServlet.java             # 管理员业务处理接口
│       │   │   ├── AppealServlet.java            # 申诉业务处理接口
│       │   │   ├── AudioServlet.java             # 音频流代理接口
│       │   │   ├── ChangePasswordServlet.java    # 密码修改接口
│       │   │   ├── DeleteAccountServlet.java     # 账号注销接口
│       │   │   ├── FavoriteServlet.java          # 收藏业务处理接口
│       │   │   ├── GetPlayUrlServlet.java        # 获取多源播放链接接口
│       │   │   ├── ImageProxyServlet.java        # 封面图片代理服务接口
│       │   │   ├── LogoutServlet.java            # 用户登出接口
│       │   │   ├── PlayHistoryPageServlet.java   # 播放历史分页查询接口
│       │   │   ├── PlayHistoryServlet.java       # 播放历史记录接口
│       │   │   ├── PlaylistServlet.java          # 歌单管理接口
│       │   │   ├── RefreshRecommendServlet.java  # 推荐刷新接口
│       │   │   ├── SearchServlet.java            # 混合搜索接口
│       │   │   ├── TestDBServlet.java            # 数据库连接测试接口
│       │   │   ├── UniversalPlayHistoryServlet.java # 通用播放历史记录接口
│       │   │   ├── UpdateProfileServlet.java     # 用户资料更新接口
│       │   │   ├── UserLoginServlet.java         # 用户登录接口
│       │   │   └── UserRegisterServlet.java      # 用户注册接口
│       │   └── util/                # 工具类目录
│       │       ├── CoverDownloadUtil.java    # 封面下载工具
│       │       ├── EmailUtil.java            # 邮件发送工具
│       │       └── MetadataCleaner.java      # 元数据清洗工具
│       ├── resources/               # 配置文件目录
│       │   ├── c3p0-config.xml      # 数据库连接池配置
│       │   ├── music-api.properties # 第三方 API 配置
│       │   └── logging.properties   # 日志配置
│       └── webapp/                  # 前端资源根目录
│           ├── WEB-INF/web.xml      # Web 应用部署配置
│           ├── MusicServer/         # 独立音乐 API 服务目录
│           │   ├── Cookie/          # 缓存 Cookie 目录
│           │   ├── node_modules/    # Node 依赖库目录（不展开）
│           │   ├── qq_api/          # Python 服务目录（不展开）
│           │   ├── unblock/         # UnblockNeteaseMusic 服务目录（不展开）
│           │   ├── package.json     # Node 项目依赖配置
│           │   └── server.log       # Node 服务日志
│           ├── js/                  # 前端脚本目录
│           │   ├── app.js            # 主业务入口逻辑
│           │   ├── player.js         # 播放器核心逻辑
│           │   ├── qqLoginModal.js   # QQ登录弹窗逻辑
│           │   ├── search.js         # 搜索功能逻辑
│           │   ├── server.js         # Node服务交互逻辑
│           │   ├── settings.js       # 设置页交互逻辑
│           │   ├── user-logic.js     # 用户状态管理逻辑
│           │   ├── verify_qq.js      # QQ验证逻辑
│           │   └── verify_qq_multi.js # 多用户验证逻辑
│           ├── css/                 # 样式表目录
│           ├── img/                 # 图片资源目录
│           ├── admin/               # 后台管理页面目录
│           │   ├── appeals.jsp       # 申诉管理页面
│           │   ├── dashboard.jsp     # 管理后台仪表盘
│           │   ├── favorites.jsp     # 收藏管理页面
│           │   ├── songs.jsp         # 歌曲管理页面
│           │   ├── userDetails.jsp   # 用户详情页面
│           │   └── users.jsp         # 用户列表页面
│           ├── includes/            # 通用 JSP 组件目录
│           ├── accountStatus.jsp    # 账号状态页面
│           ├── appeal.jsp           # 申诉提交页面
│           ├── index.jsp            # 网站首页
│           ├── playHistory.jsp      # 播放历史页面
│           ├── playlist.jsp         # 歌单详情页面
│           ├── register.jsp         # 用户注册页面
│           ├── search.jsp           # 搜索结果页面
│           ├── settings.jsp         # 用户设置页面
│           └── user.jsp             # 用户中心页面
└── target/                          # Maven 构建输出目录
```

## 数据库设计

### 数据库配置

- **数据库 (Database)**: `musicweb`
- **用户名 (User)**: `root`
- **密码 (Password)**: `JF123456`
- **连接地址**: `jdbc:mysql://localhost:3306/musicweb?useUnicode=true&characterEncoding=utf-8`

### 核心业务表

#### 1. 用户表 (`users`)

存储用户账号基本信息及状态。

- `id` (INT): 主键，自增
- `username` (VARCHAR): 用户名，唯一
- `password` (VARCHAR): 密码（推荐加密存储）
- `email` (VARCHAR): 邮箱
- `nickname` (VARCHAR): 昵称
- `phone` (VARCHAR): 手机号
- `status` (ENUM): 状态 (`active`/`frozen`/`deleted`)
- `frozen_until` (TIMESTAMP): 冻结截止时间
- `frozen_reason` (VARCHAR): 冻结原因
- `deleted_at` (TIMESTAMP): 逻辑删除时间
- `create_time` (TIMESTAMP): 注册时间

#### 2. 歌曲表 (`songs`)

本地音乐库基础信息。

- `id` (INT): 主键，自增
- `title` (VARCHAR): 歌名
- `artist` (VARCHAR): 歌手
- `album` (VARCHAR): 专辑
- `duration` (INT): 时长(秒)
- `genre` (VARCHAR): 流派
- `release_year` (INT): 发行年份
- `file_path` (VARCHAR): 文件路径 (相对 `music/` 目录)
- `cover_image` (VARCHAR): 封面路径
- `kkbox_id` (VARCHAR): KKBOX 原曲ID
- `genre_ids` (VARCHAR): 曲风ID列表
- `language` (VARCHAR): 语言代码
- `popularity` (INT): 热度值

#### 3. 播放历史表 (`play_history`)

记录用户播放行为，用于统计和推荐。

- `id` (INT): 主键
- `user_id` (INT): 用户ID
- `song_id` (INT): 歌曲ID
- `play_time` (TIMESTAMP): 播放时间
- `play_duration` (INT): 播放时长(秒)

#### 4. 收藏表 (`favorites`)

用户收藏的歌曲。

- `id` (INT): 主键
- `user_id` (INT): 用户ID
- `song_id` (INT): 歌曲ID
- `create_time` (TIMESTAMP): 收藏时间

#### 5. 申诉表 (`appeals`)

账号申诉记录。

- `id` (INT): 主键
- `username` (VARCHAR): 申诉账号
- `user_id` (INT): 关联用户ID
- `appeal_type` (ENUM): 类型 (`frozen`/`deleted`)
- `reason` (TEXT): 申诉理由
- `contact_email` (VARCHAR): 联系邮箱
- `status` (ENUM): 状态 (`pending`/`approved`/`rejected`)
- `admin_reply` (TEXT): 管理员回复

#### 6. 自建歌单表 (`user_playlists`)

用户创建的歌单。

- `id` (INT): 主键
- `user_id` (INT): 创建者ID
- `name` (VARCHAR): 歌单名
- `description` (TEXT): 描述
- `cover_image` (VARCHAR): 封面
- `is_default` (TINYINT): 是否默认 (0/1)
- `create_time` (TIMESTAMP): 创建时间

#### 7. 歌单歌曲关联表 (`playlist_songs`)

自建歌单与歌曲的多对多关系。

- `id` (INT): 主键
- `playlist_id` (INT): 歌单ID
- `song_id` (INT): 歌曲ID
- `add_time` (TIMESTAMP): 添加时间

#### 8. 推荐表 (`recommendations`)

基于算法生成的个性化推荐。

- `id` (INT): 主键
- `user_id` (INT): 目标用户
- `song_id` (INT): 推荐歌曲
- `score` (DOUBLE): 推荐得分
- `create_time` (DATETIME): 生成时间
- `source_type` (VARCHAR): 推荐来源 (默认 `deepfm`)

#### 9. 外部歌单信息表 (`playlist_info`)

**（非核心业务表 - 爬虫/旧版功能数据）**
爬取的网易云歌单元数据，**目前未被核心业务代码引用**。

- `id` (INT): 主键
- `playlist_id` (VARCHAR): 外部歌单ID
- `title` (VARCHAR): 标题
- `play_count` (BIGINT): 播放量
- `url` (VARCHAR): 链接

#### 10. 外部歌单歌曲表 (`song_info`)

**（非核心业务表 - 爬虫/旧版功能数据）**
外部歌单包含的歌曲详情，**目前未被核心业务代码引用**。

- `id` (INT): 主键
- `playlist_id` (VARCHAR): 关联外部歌单ID
- `song_name` (VARCHAR): 歌名
- `artist` (VARCHAR): 歌手
- `album` (VARCHAR): 专辑

#### 11. 歌曲更新临时表 (`songs_update_temp`)

用于批量更新歌曲信息的临时表。

- `id` (INT): 歌曲ID
- `title` (LONGTEXT): 标题
- `genre` (LONGTEXT): 流派
- `username` - 用户名，唯一
- `password` - 密码
- `email` - 邮箱
- `nickname` - 昵称
- `phone` - 手机号
- `status` - 账号状态 (active/frozen/deleted)
- `frozen_until` - 冻结截止时间
- `frozen_reason` - 冻结原因
- `deleted_at` - 删除时间
- `create_time` - 创建时间

#### 歌曲表 (songs)

- `id` - 主键，自增
- `title` - 歌曲标题
- `artist` - 艺术家
- `album` - 专辑
- `duration` - 时长（秒）
- `genre` - 音乐类型
- `release_year` - 发行年份
- `file_path` - 音频文件路径
- `cover_image` - 封面图片路径

#### 收藏表 (favorites)

- `id` - 主键，自增
- `user_id` - 用户ID，外键
- `song_id` - 歌曲ID，外键
- `create_time` - 收藏时间
- **唯一约束**: (user_id, song_id) - 防止重复收藏

#### 申诉表 (appeals)

- `id` - 主键，自增
- `username` - 申诉用户名
- `user_id` - 用户ID，外键（可为NULL）
- `appeal_type` - 申诉类型 (frozen/deleted)
- `reason` - 申诉原因
- `contact_email` - 联系邮箱
- `status` - 申诉状态 (pending/approved/rejected)
- `admin_reply` - 管理员回复
- `create_time` - 创建时间
- `update_time` - 更新时间

#### 播放历史表 (play_history)

- `id` - 主键，自增
- `user_id` - 用户ID，外键
- `song_id` - 歌曲ID，外键
- `play_time` - 播放时间
- `play_duration` - 实际播放时长（秒）
- **索引**: idx_user_time (user_id, play_time DESC) - 优化查询性能

#### 用户歌单表 (user_playlists)

- `id` - 主键，自增
- `user_id` - 用户ID，外键
- `name` - 歌单名称
- `description` - 歌单描述
- `cover_image` - 歌单封面图片路径
- `is_default` - 是否为默认歌单（布尔值）
- `create_time` - 创建时间
- `update_time` - 更新时间
- **外键约束**: FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE

#### 歌单歌曲关联表 (playlist_songs)

- `id` - 主键，自增
- `playlist_id` - 歌单ID，外键
- `song_id` - 歌曲ID，外键
- `add_time` - 添加时间
- **唯一约束**: (playlist_id, song_id) - 防止重复添加
- **外键约束**:
  - FOREIGN KEY (playlist_id) REFERENCES user_playlists(id) ON DELETE CASCADE
  - FOREIGN KEY (song_id) REFERENCES songs(id) ON DELETE CASCADE

### 推荐系统表

#### 网易云歌单表 (playlist_info)

- `id` - 主键，自增
- `playlist_id` - 网易云歌单ID，唯一
- `title` - 歌单标题
- `category` - 所属分类
- `tags` - 歌单标签
- `play_count` - 播放量
- `fav_count` - 收藏量
- `share_count` - 分享量
- `comment_count` - 评论数
- `url` - 歌单链接
- `create_time` - 创建时间

#### 歌单歌曲表 (song_info)

- `id` - 主键，自增
- `playlist_id` - 关联的歌单ID，外键
- `song_name` - 歌曲名
- `duration` - 时长
- `artist` - 歌手
- `album` - 专辑

#### 推荐表 (recommendations)

- `id` - 主键，自增
- `user_id` - 目标用户ID
- `song_id` - 推荐的歌曲ID
- `score` - 推荐得分（相似度累加）
- `create_time` - 创建时间
- **索引**: idx_user (user_id) - 用户查询优化
- **索引**: idx_user_score (user_id, score) - 联合索引优化排序

## 核心功能

### 1. 用户管理

- **用户注册**: 用户可创建账号，包含用户名、密码、邮箱等信息
- **用户登录**: 验证用户身份，支持会话管理
- **用户登出**: 清除会话，安全退出
- **用户信息管理**: 查看和编辑个人信息

### 2. 音乐管理

- **歌曲浏览**: 查看所有歌曲列表
- **歌曲搜索**: Google 风格搜索框，支持按标题、艺术家、专辑、风格搜索
- **搜索历史**: 自动保存最近 5 条搜索记录，支持快速重复搜索
- **排行榜**: 热歌榜、新歌榜、收藏榜
- **在线播放**: HTML5 音频播放器，支持流媒体播放和进度控制

### 3. 收藏功能

- **添加收藏**: 将喜欢的歌曲添加到收藏列表
- **取消收藏**: 从收藏列表中移除歌曲
- **收藏列表**: 查看所有收藏的歌曲
- **收藏状态**: 实时显示歌曲的收藏状态

### 4. 管理员后台系统

- **智能登录识别**: 自动区分管理员和普通用户登录
- **数据统计仪表板**: 实时显示用户数、歌曲数、收藏数等统计信息
- **用户管理**: 查看所有用户信息，支持搜索和排序
- **用户详情管理**: 查看用户详细信息，支持账号冻结和解冻操作
- **音乐管理**: 查看所有歌曲信息，支持播放预览
- **收藏管理**: 管理所有用户收藏记录，支持批量操作
- **安全防护**: 严格的权限控制和SQL注入防护

### 5. 账号申诉功能

- **账号状态提示**: 登录时显示账号冻结/删除状态，提供申诉入口
- **申诉提交**: 用户填写申诉原因和联系邮箱提交申诉
- **申诉管理**: 管理员查看、审批申诉，支持同意/拒绝操作
- **邮件通知**: 审批后自动发送163邮件通知用户
- **自动恢复**: 同意申诉后自动恢复账号状态

### 6. 用户设置功能

- **个人信息管理**: 修改昵称、邮箱、手机号
- **密码修改**: 安全的密码修改功能
- **账户管理**: 注销账户功能

### 7. 推荐系统功能

- **个性化推荐**: 基于用户行为和偏好推荐音乐
- **推荐刷新**: RefreshRecommendServlet 提供推荐算法刷新接口
- **评分机制**: 基于相似度的推荐评分系统
- **歌单集成**: 支持网易云歌单数据的导入和推荐
- **性能优化**: 使用联合索引提升推荐查询效率

### 8. 歌单管理功能

- **创建歌单**: 用户可以创建自定义歌单，自动生成默认"我喜欢的音乐"歌单
- **歌单列表**: 表格式展示所有歌单，仅显示封面和名称，简洁清晰
- **歌单详情**: 查看歌单内的所有歌曲，支持播放、收藏、移除操作
- **歌曲管理**: 添加歌曲到歌单、从歌单移除歌曲
- **歌单编辑**: 修改歌单名称和描述
- **歌单删除**: 删除自定义歌单（默认歌单不可删除）
- **防重复添加**: 唯一约束确保同一首歌不会重复添加到同一歌单
- **级联删除**: 删除歌单时自动删除关联的歌曲记录

## 主要组件

### 数据库连接池 (C3P0)

- 使用 C3P0 连接池管理数据库连接
- 配置参数：
  - 初始连接数：5
  - 最小连接数：5
  - 最大连接数：20
  - 连接超时：30秒
  - 空闲连接测试：30秒

### Servlet 控制器

- **UserLoginServlet**: 处理用户登录请求，支持管理员自动识别
- **UserRegisterServlet**: 处理用户注册请求
- **LogoutServlet**: 处理用户登出请求
- **FavoriteServlet**: 处理收藏相关请求（添加/取消收藏）
- **PlaylistServlet**: 处理歌单相关请求（创建/查看/编辑/删除歌单，添加/移除歌曲）
- **AdminServlet**: 管理员后台主控制器，处理所有后台请求
- **ChangePasswordServlet**: 处理密码修改请求
- **UpdateProfileServlet**: 处理个人信息更新请求
- **DeleteAccountServlet**: 处理账户注销请求

### DAO 数据访问层

- **UserDAO**: 用户数据操作，包括登录验证、注册、信息管理等
- **SongDAO**: 歌曲数据操作，包括获取歌曲列表、排行榜等
- **FavoriteDAO**: 收藏数据操作，包括添加/取消收藏、获取收藏列表等
- **PlaylistDAO**: 歌单数据操作，包括创建歌单、获取歌单列表、歌单歌曲管理、歌单信息更新等
- **AdminDAO**: 管理员数据操作，严格防止SQL注入，提供安全的数据库查询接口

## 前端界面

### 首页 (index.jsp)

- 未登录用户：显示登录表单和网站介绍
- 已登录用户：显示收藏列表和推荐歌曲
- 响应式设计，适配不同屏幕尺寸

### 用户主页 (user.jsp)

- 用户信息展示和个人统计数据
- 我的歌单（表格式展示，仅显示封面和名称）
- 我的收藏歌曲列表
- 推荐歌曲
- 热门排行榜（热歌榜、新歌榜、收藏榜）

### 歌单详情页 (playlist.jsp)

- 歌单信息展示（名称、描述、歌曲数量）
- 歌单内所有歌曲列表
- 歌曲操作（播放、收藏、从歌单移除）
- 歌单编辑和删除功能
- 歌曲封面适配显示（50×50px）

### 注册页面 (register.jsp)

- 用户注册表单
- 实时表单验证
- 用户名重复检查

## 安全特性

### 密码处理

- 密码在传输过程中使用 HTTPS（建议）
- 数据库存储密码（建议加密处理）

### 会话管理

- 使用 HttpSession 管理用户登录状态
- 登录验证：保护需要登录的页面
- 安全登出：清除会话数据

### 输入验证

- 前端 JavaScript 表单验证
- 后端数据验证和空值处理
- SQL 注入防护（使用 PreparedStatement）

## 部署说明

- Tomcat中部署的工件名字是musicweb：war exploded；
- 应用程序上下文：/musicweb_war_exploded
- 默认浏览器是：Chrome

### 环境要求

- Java 25
- Maven 3.0
- MySQL 8.4
- Apache Tomcat 10.1.23

### 部署步骤

1. 创建数据库 `musicweb`
2. 执行 SQL 脚本创建表结构
3. 修改 `c3p0-config.xml` 中的数据库连接信息
4. 使用 Maven 构建项目：`mvn clean package`
5. 将生成的 WAR 文件部署到 Tomcat
6. 启动 Tomcat 服务器

### 访问地址

- 首页：`http://localhost:8082/musicweb_war_exploded/index.jsp`
- 登录：首页集成登录功能
- 注册：`http://localhost:8082/musicweb_war_exploded/index.jspregister.jsp`

## 特色功能

### 1. 智能推荐系统

- 基于新歌榜的推荐算法
- 个性化内容展示

### 2. 丰富的排行榜

- 热歌榜：基于收藏次数排序
- 新歌榜：按发行时间排序
- 收藏榜：用户收藏最多的歌曲

### 3. 用户体验优化

- 响应式设计，支持移动端
- 平滑的动画效果
- 实时状态更新
- 友好的错误提示

### 4. 数据统计

- 用户收藏数量统计
- 歌曲热度统计
- 用户注册时间显示

## 开发规范

### 代码结构

- 严格遵循 MVC 架构模式
- 分层开发：Model-View-Controller
- 统一的异常处理机制

### 命名规范

- 类名：大驼峰命名法
- 方法名和变量名：小驼峰命名法
- 常量：全大写下划线分隔

### 注释规范

- 类和方法使用 Javadoc 注释
- 关键业务逻辑添加行内注释
- 数据库操作日志记录

## 🔧 安全特性

### SQL注入防护

- **严格使用PreparedStatement**: 所有数据库查询都使用参数化查询
- **输入验证**: 对用户输入进行严格的格式和长度验证
- **白名单机制**: 管理员身份验证使用白名单机制
- **错误处理**: 完善的异常处理，避免信息泄露

### 权限控制

- **会话管理**: 基于HttpSession的安全会话管理
- **角色分离**: 自动区分管理员和普通用户权限
- **访问控制**: 每个页面都有登录状态和权限验证
- **安全登出**: 完整清除会话数据

### 数据安全

- **密码存储**: 建议在实际部署时使用密码加密存储
- **HTTPS支持**: 建议在生产环境使用HTTPS协议
- **XSS防护**: 前端输出使用适当转义处理

## 📋 更新日志

详细的更新历史请参阅 **[CHANGELOG.md](CHANGELOG.md)**。

## 扩展计划

### 短期扩展

- [x] ~~管理员后台系统~~ ✅ 已完成
- [x] ~~用户详情与账号管理~~ ✅ 已完成
- [x] ~~账号申诉与邮件通知系统~~ ✅ 已完成
- [x] ~~歌曲播放功能~~ ✅ 已完成
- [x] ~~音乐搜索功能~~ ✅ 已完成
- [x] ~~歌单创建和管理~~ ✅ 已完成（v1.7.3）
- [x] ~~第三方音乐平台集成~~ ✅ 已完成（v1.8.0）
- [x] ~~启动脚本与目录重构~~ ✅ 已完成（v1.8.1/v2.1.2）
- [x] ~~通用播放历史系统~~ ✅ 已完成（v3.1.0）
- [x] ~~元数据架构升级 (语种/流派)~~ ✅ 已完成（v3.2.0）
- [ ] **存量数据清洗**: 批量更新旧版网易云数据的元信息
- [ ] **高级搜索筛选**: 基于流派、年份、语种的组合筛选
- [ ] **封面图本地化**: 实现外部封面图的自动缓存与本地引用
- [ ] 用户头像上传与裁剪
- [ ] 数据导出功能 (Excel/JSON)

### 长期规划

- [ ] **智能推荐引擎**: 引入协同过滤或深度学习模型提升推荐精准度
- [ ] **音乐社区化**: 评论、弹幕、动态分享、关注系统
- [ ] **多端适配**: 开发 Flutter/React Native 移动端 App
- [ ] **沉浸式体验**: Web Audio API 频谱可视化、卡拉OK歌词模式
- [ ] **大数据驾驶舱**: 基于 ECharts 的全站数据可视化大屏
- [ ] **商业化探索**: VIP 会员体系、积分商城

## 联系信息

**项目名称**: MusicWeb 在线音乐平台

**开发语言**: Java 23 + JSP + Servlet

**技术框架**: Jakarta EE 10+ (Servlet 6.1, JSP 3.1)

**数据库**: MySQL 8.4.0

**连接池**: C3P0 0.9.5.5

**项目类型**: 数据库应用开发课程设计

**初创时间**: 2025年11月

**最新版本**: v3.2.4

---

*本文档最后更新时间：2026年1月31日 02:00*
