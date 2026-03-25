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
├── Document/                        # 项目文档目录
│   ├── README.md                    # 项目核心文档
│   ├── OPERATION_MANUAL.md          # 运维操作手册
│   ├── CHANGELOG.md                 # 项目更新日志
│   └── playlist_square_plan.md      # 歌单广场开发计划
├── sql/                             # 数据库脚本目录
│   └── database.sql                 # 数据库初始化脚本
├── scripts/                         # 自动化运维脚本目录
│   ├── run_services.bat             # 一键启动所有服务
│   ├── stop_services.bat            # 一键停止所有服务
│   ├── start_qq_api.bat             # Python QQ 音乐服务启动脚本
│   ├── start_redis.bat              # Redis 服务启动脚本
│   ├── start.bat                    # Node.js 网易云服务启动脚本
│   ├── start_unblock.bat            # UnblockNeteaseMusic 启动脚本
│   ├── mvnw.cmd                     # Maven Wrapper 脚本 (Windows)
│   └── mvnw                         # Maven Wrapper 脚本 (Unix)
├── src/
│   └── main/
│       ├── java/com/music/
│       │   ├── javabean/            # 实体类目录
│       │   │   ├── Appeal.java              # 申诉实体
│       │   │   ├── DBUtil.java              # 数据库连接工具
│       │   │   ├── Favorite.java            # 收藏实体
│       │   │   ├── PlayHistory.java         # 播放历史实体
│       │   │   ├── Playlist.java            # 歌单实体
│       │   │   ├── Song.java                # 歌曲实体
│       │   │   └── User.java                # 用户实体
│       │   ├── dao/                 # 数据访问层目录
│       │   │   ├── AdminDAO.java             # 管理员数据操作
│       │   │   ├── AppealDAO.java            # 申诉数据操作
│       │   │   ├── FavoriteDAO.java          # 收藏数据操作
│       │   │   ├── PlayHistoryDAO.java       # 播放历史数据操作
│       │   │   ├── PlaylistDAO.java          # 歌单数据操作
│       │   │   ├── RedisUtil.java            # Redis 缓存工具
│       │   │   ├── SongDAO.java              # 歌曲与元数据管理
│       │   │   └── UserDAO.java              # 用户数据操作
│       │   ├── service/             # 业务逻辑层目录
│       │   │   └── RecommendationService.java    # 推荐服务
│       │   ├── servlet/             # 业务控制层目录
│       │   │   ├── AdminServlet.java             # 管理员业务处理接口
│       │   │   ├── AppealServlet.java            # 申诉业务处理接口
│       │   │   ├── AudioServlet.java             # 音频流代理接口
│       │   │   ├── ChangePasswordServlet.java    # 密码修改接口
│       │   │   ├── DeleteAccountServlet.java     # 账号注销接口
│       │   │   ├── FavoriteServlet.java          # 收藏业务处理接口
│       │   │   ├── GetPlayUrlServlet.java        # 多源播放链接接口
│       │   │   ├── ImageProxyServlet.java        # 封面图片代理接口
│       │   │   ├── LogoutServlet.java            # 用户登出接口
│       │   │   ├── PlayHistoryPageServlet.java   # 播放历史分页查询接口
│       │   │   ├── PlayHistoryServlet.java       # 播放历史记录接口
│       │   │   ├── PlaylistServlet.java          # 歌单管理接口
│       │   │   ├── PlaylistSongsPageServlet.java # 歌单歌曲分页接口
│       │   │   ├── RefreshRecommendServlet.java  # 推荐刷新接口
│       │   │   ├── SearchServlet.java            # 混合搜索接口
│       │   │   ├── TestDBServlet.java            # 数据库连接测试接口
│       │   │   ├── UniversalPlayHistoryServlet.java # 通用播放历史接口
│       │   │   ├── UpdatePlayDurationServlet.java # 播放时长上报接口
│       │   │   ├── UpdateProfileServlet.java     # 用户资料更新接口
│       │   │   ├── UserPreferenceServlet.java    # 用户口味偏好接口
│       │   │   ├── UserLoginServlet.java         # 用户登录接口
│       │   │   ├── UserPlaylistsServlet.java     # 用户歌单列表接口
│       │   │   └── UserRegisterServlet.java      # 用户注册接口
│       │   ├── util/                # 工具类目录
│       │   │   ├── CoverDownloadUtil.java    # 封面下载工具
│       │   │   └── EmailUtil.java            # 邮件发送工具
│       │   └── utils/               # 扩展工具类目录
│       │       └── MetadataCleaner.java      # 元数据清洗工具
│       ├── resources/               # 配置文件目录
│       │   ├── c3p0-config.xml      # 数据库连接池配置
│       │   ├── music-api.properties # 第三方 API 配置
│       │   ├── email.properties     # 邮件服务配置
│       │   └── logging.properties   # 日志配置
│       └── webapp/                  # 前端资源根目录
│           ├── WEB-INF/web.xml      # Web 应用部署配置
│           ├── MusicServer/         # 独立音乐 API 服务目录
│           │   ├── Cookie/          # 缓存 Cookie 目录
│           │   ├── node_modules/    # Node 依赖库目录
│           │   ├── qq_api/          # Python QQ 音乐 API 服务目录
│           │   │   ├── app.py               # QQ 音乐 FastAPI 服务
│           │   │   ├── metadata_provider.py # 五级元数据聚合引擎
│           │   │   ├── qq_credential.json   # QQ 音乐登录凭证
│           │   │   ├── qq_music_mapping.json # 流派语种映射表
│           │   │   └── requirements.txt     # Python 依赖配置
│           │   ├── unblock/         # UnblockNeteaseMusic 服务目录
│           │   ├── package.json     # Node 项目依赖配置
│           │   └── server.log       # Node 服务日志
│           ├── js/                  # 前端脚本目录
│           │   ├── app.js            # 主业务入口逻辑
│           │   ├── addToPlaylist.js  # 添加到歌单逻辑
│           │   ├── player.js         # 播放器核心逻辑
│           │   ├── qqLoginModal.js   # QQ登录弹窗逻辑
│           │   ├── search.js         # 搜索功能逻辑
│           │   ├── server.js         # Node服务交互逻辑
│           │   ├── settings.js       # 设置页交互逻辑
│           │   ├── user-logic.js     # 用户状态管理逻辑
│           │   ├── verify_qq.js      # QQ验证逻辑
│           │   └── verify_qq_multi.js # 多用户验证逻辑
│           ├── css/                 # 样式表目录
│           │   ├── admin/            # 后台专属样式目录
│           │   │   ├── admin.css           # 后台公共样式
│           │   │   ├── appeals.css         # 申诉页面样式
│           │   │   ├── songs.css           # 歌曲管理页面样式
│           │   │   └── userDetails.css     # 用户详情专属样式
│           │   ├── style.css         # 主样式表
│           │   ├── player.css        # 播放器样式
│           │   ├── search.css        # 搜索页样式
│           │   ├── settings.css      # 设置页样式
│           │   ├── login.css         # 登录页样式
│           │   ├── register.css      # 注册页样式
│           │   └── appeal.css        # 申诉页样式
│           ├── img/                 # 图片资源目录
│           ├── log/                 # 运行日志目录
│           ├── admin/               # 后台管理页面目录
│           │   ├── appeals.jsp       # 申诉管理页面
│           │   ├── dashboard.jsp     # 管理后台仪表盘
│           │   ├── favorites.jsp     # 收藏管理页面
│           │   ├── songs.jsp         # 歌曲管理页面
│           │   ├── userDetails.jsp   # 用户详情页面
│           │   └── users.jsp         # 用户列表页面
│           ├── includes/            # 通用 JSP 组件目录
│           │   ├── song-item.jsp     # 歌曲列表项组件
│           │   └── chart-item.jsp    # 排行榜列表项组件
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

存储用户账号基本信息及状态，含推荐模型所需的用户画像字段。

- `id` (INT): 主键，自增
- `username` (VARCHAR): 用户名，唯一
- `password` (VARCHAR): 密码
- `email` (VARCHAR): 邮箱
- `nickname` (VARCHAR): 昵称
- `phone` (VARCHAR): 手机号
- `status` (ENUM): 状态 (`active`/`frozen`/`deleted`)
- `frozen_until` (TIMESTAMP): 冻结截止时间
- `frozen_reason` (VARCHAR): 冻结原因
- `deleted_at` (TIMESTAMP): 逻辑删除时间
- `create_time` (TIMESTAMP): 注册时间
- `preferred_genres` (VARCHAR): 偏好流派标签（分号分隔）
- `preferred_artists` (VARCHAR): 偏好歌手标签（分号分隔）
- `city` (VARCHAR): 所在城市（推荐特征）
- `gender` (VARCHAR): 性别（推荐特征）
- `bd` (TINYINT): 年龄（推荐特征）

#### 2. 歌曲表 (`songs`)

本地音乐库核心信息，含 KKBOX 元数据及多轮数据清洗后的语种/国家字段。

- `id` (INT): 主键，自增
- `title` (VARCHAR): 歌名
- `artist` (VARCHAR): 歌手
- `album` (VARCHAR): 专辑
- `duration` (INT): 时长（秒）
- `genre` (VARCHAR): 流派
- `release_year` (INT): 发行年份
- `file_path` (VARCHAR): 音频文件路径
- `cover_image` (VARCHAR): 封面图片路径
- `kkbox_id` (VARCHAR): KKBOX 原曲 ID（与推荐模型对齐）
- `genre_ids` (VARCHAR): KKBOX 曲风 ID 列表
- `language` (VARCHAR): 语言标签（经 ISRC 交叉验证修正，未知比例 3.09%）
- `popularity` (INT): 歌曲热度（KKBOX 已归一化至 0~100，网易云 0~100）
- `origin_country` (CHAR(2)): 原产国家码（ISRC 推断，用于推荐特征）

#### 3. 播放历史表 (`play_history`)

记录用户全量播放行为，是推荐模型的核心训练数据来源。

- `id` (INT): 主键，自增
- `user_id` (INT): 用户 ID
- `song_id` (INT): 歌曲 ID
- `play_time` (TIMESTAMP): 播放时间
- `play_duration` (INT): 播放时长（秒）
- `source_type` (VARCHAR): 来源类型（如 `kkbox`/`netease`/`local`）
- `target` (TINYINT): 推荐模型标签（1=完整收听，0=跳过）
- `source_channel` (VARCHAR): 播放触发渠道（如 `PERSONAL_PLAYLIST`/`RADIO`）

#### 4. 申诉表 (`appeals`)

账号申诉记录，支持管理员审批及邮件回复。

- `id` (INT): 主键，自增
- `username` (VARCHAR): 申诉账号
- `user_id` (INT): 关联用户 ID
- `appeal_type` (ENUM): 申诉类型（`frozen`/`deleted`）
- `reason` (TEXT): 申诉理由
- `contact_email` (VARCHAR): 联系邮箱
- `status` (ENUM): 审批状态（`pending`/`approved`/`rejected`）
- `admin_reply` (TEXT): 管理员回复内容
- `create_time` (TIMESTAMP): 申诉创建时间
- `update_time` (TIMESTAMP): 最后更新时间（自动更新）

#### 5. 自建歌单表 (`user_playlists`)

用户创建的个人歌单。`is_default=1` 的歌单为系统自动生成的"我喜欢的音乐"默认收藏夹，承接旧版收藏表的功能。

- `id` (INT): 主键，自增
- `user_id` (INT): 创建者 ID
- `name` (VARCHAR): 歌单名称
- `description` (TEXT): 歌单描述
- `cover_image` (VARCHAR): 歌单封面路径
- `is_default` (TINYINT): 是否为默认收藏歌单（0/1）
- `create_time` (TIMESTAMP): 创建时间
- `update_time` (TIMESTAMP): 最后更新时间（自动更新）

#### 6. 歌单歌曲关联表 (`playlist_songs`)

用户歌单与歌曲的多对多关系表，唯一约束防止重复添加。

- `id` (INT): 主键，自增
- `playlist_id` (INT): 关联歌单 ID
- `song_id` (INT): 关联歌曲 ID
- `add_time` (TIMESTAMP): 添加时间

#### 7. 用户内容屏蔽表 (`user_content_blocks`)

记录用户主动屏蔽的流派或艺术家，推荐时过滤对应内容，支持有效期与屏蔽次数管理。

- `id` (INT): 主键，自增
- `user_id` (INT): 用户 ID
- `block_type` (ENUM): 屏蔽类型（`genre`/`artist`）
- `block_value` (VARCHAR): 屏蔽的具体值（如"电子"/"周杰伦"）
- `block_count` (INT): 屏蔽触发次数（默认 1）
- `blocked_at` (TIMESTAMP): 屏蔽创建时间
- `blocked_until` (DATE): 屏蔽有效期截止日期
- `is_active` (TINYINT): 屏蔽是否当前生效（0/1）

#### 8. 推荐反馈表 (`recommendation_feedback`)

记录用户对每条推荐记录的交互行为，驱动推荐冷却与反馈评分机制。

- `id` (INT): 主键，自增
- `user_id` (INT): 目标用户 ID
- `song_id` (INT): 推荐歌曲 ID
- `recommend_date` (DATE): 推荐日期
- `was_played` (TINYINT): 是否已播放（0/1）
- `play_completion` (FLOAT): 播放完成比例
- `was_favorited` (TINYINT): 是否收藏（0/1）
- `consecutive_ignore_days` (INT): 连续被忽略天数
- `feedback_score` (FLOAT): 综合反馈得分
- `cooldown_until` (DATE): 推荐冷却期截止日期
- `created_at` (TIMESTAMP): 记录创建时间
- `updated_at` (TIMESTAMP): 最后更新时间（自动更新）

#### 9. 用户口味反馈表 (`user_preference_feedback`)

归档用户每日对推荐结果的显式满意度评价，作为推荐算法调权的训练信号。同一用户同一天多次提交则覆盖。

- `id` (INT): 主键，自增
- `user_id` (INT): 用户 ID
- `feedback_date` (DATE): 反馈日期（与 user_id 构成唯一约束）
- `satisfaction` (ENUM): 满意度（`very_satisfied`/`satisfied`/`neutral`/`dissatisfied`）
- `genres_added` (VARCHAR): 本次新增流派偏好（分号分隔）
- `artists_added` (VARCHAR): 本次新增艺术家偏好（分号分隔）
- `created_at` (TIMESTAMP): 记录时间

#### 10. 推荐结果表 (`recommendations`)

存储算法生成的个性化推荐列表，供前端实时读取展示。

- `id` (INT): 主键，自增
- `user_id` (INT): 目标用户 ID
- `song_id` (INT): 推荐歌曲 ID
- `score` (DOUBLE): 推荐得分
- `create_time` (DATETIME): 推荐生成时间
- `source_type` (VARCHAR): 推荐来源标识（默认 `deepfm`）


## 核心功能

### 1. 用户管理

- **用户注册**: 注册账号，填写用户名、密码、邮箱等基础信息
- **用户登录**: 账号密码验证，支持管理员自动识别跳转后台
- **个人信息管理**: 修改昵称、邮箱、手机号、性别、城市（`settings.jsp`）
- **密码修改**: 当前密码验证 + 新密码强度实时指示器
- **账户注销**: 需勾选确认并输入密码，操作不可逆

### 2. 音乐播放与搜索

- **多源搜索**: 支持网易云音乐、QQ 音乐、全部三种来源切换（`SearchServlet` 调用 Node.js API）
- **VIP 检测**: 搜索结果自动标注 VIP 歌曲（网易云 fee=1/4，QQ pay.pay_play=1）
- **搜索历史**: 自动保存最近 5 条搜索词，支持一键清空
- **在线播放器**: 底部固定悬浮播放器，支持上/下一曲、进度拖拽、音量控制、播放模式切换（循环/随机）
- **播放队列**: 队列侧边栏展示当前播放列表，支持清空队列
- **排行榜**: 热歌榜（全局播放量）、新歌榜（发行时间）、收藏榜（被收藏次数），各展示 10 首
- **外部歌曲自动入库**: 播放网易云/QQ 歌曲时自动写入 `songs` 表并下载封面（`UniversalPlayHistoryServlet`）
- **元数据自动补全**: 缺失 `release_year`/`genre`/`language` 时，自动从 Node.js 或 Python 多源服务拉取补全

### 3. 收藏与歌单管理

- **收藏歌曲**: 点击 ❤️ 收藏至默认"我喜欢的音乐"歌单，再次点击取消（基于 Redis 缓存加速状态判断）
- **创建歌单**: 用户可创建任意数量的自定义歌单（名称必填，描述可选）
- **歌单列表**: 网格卡片式展示所有歌单（封面 + 名称）
- **歌单详情**: 查看歌单内全部歌曲，支持播放全部、单曲播放、收藏、从歌单移除
- **歌单排序**: 支持按添加时间、歌手、专辑、年份、播放次数共 5 种排序方式及升/降序切换
- **歌单编辑/删除**: 修改自定义歌单名称和描述，或删除整个歌单（默认歌单不可删除）
- **分页加载**: 歌单内歌曲每页 25 首，支持分页翻页

### 4. 播放历史

- **历史记录**: 自动记录每次播放（含外部歌曲），写入 `play_history` 表
- **时间范围过滤**: 支持查看最近一周、一个月、三个月的播放记录
- **分页浏览**: 每页 25 条，显示歌曲封面、名称、艺术家和精确播放时间
- **播放统计**: 展示所选时间范围内的总播放曲目数

### 5. 个性化推荐系统

- **ML 模型驱动推荐**: 推荐列表来源于 Python 端 LightGBM + DeepFM + DIEN 集成模型离线计算结果，存储于 `recommendations` 表
- **每日推荐展示**: 用户主页展示前 5 首高分推荐歌曲，支持播放全部推荐
- **推荐分页刷新**: `RefreshRecommendServlet` 支持 offset 参数分页加载更多推荐（每次 5 首）
- **冷启动推荐**: 新用户注册时根据所选流派和歌手偏好生成初始 20 首推荐（`RecommendationService.initForNewUser`）
- **推荐反馈冷却**: `recommendation_feedback` 表记录每首推荐的播放/收藏/忽略行为，驱动推荐冷却期机制

### 6. 用户偏好与内容屏蔽

- **口味偏好反馈**: 用户可提交每日满意度评价（非常满意/满意/中立/不满意），同步更新 `preferred_genres`/`preferred_artists` 偏好标签（`UserPreferenceServlet`）
  - 不满意：清空旧偏好，替换为新选内容
  - 满意/中立：与现有偏好合并去重追加
- **屏蔽流派/艺术家**: 用户可主动屏蔽不喜欢的流派或歌手（`BlockContentServlet`），推荐结果自动过滤
  - 首次屏蔽 14 天，重复屏蔽每次递增 7 天
  - 支持手动解除屏蔽
  - 屏蔽状态通过 Redis 缓存（TTL=1小时）加速查询

### 7. 管理员后台

- **数据仪表盘**: 展示总用户数、总歌曲数、总收藏数、近 7 日新增用户四项 KPI
- **用户管理**: 查看全量用户信息，支持搜索、排序；账号冻结/解冻操作
- **歌曲管理**: 增删改查歌曲，支持按名称/艺术家/专辑搜索，分页浏览
- **歌单管理**: 查看所有用户歌单
- **申诉管理**: 审批用户申诉，同意后自动恢复账号状态并发送 163 邮件通知

### 8. 账号申诉

- **账号状态提示**: 登录时检测冻结/删除状态，跳转至申诉引导页
- **申诉提交**: 填写申诉类型（冻结/注销）、申诉理由、联系邮箱提交
- **管理员审批**: 支持同意/拒绝，填写回复内容
- **邮件通知**: 审批后自动向申诉邮箱发送 163 邮件通知审批结果
- **自动恢复**: 同意申诉后自动将账号状态恢复为 `active`

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

- **UserLoginServlet**: 用户登录，支持管理员自动识别跳转后台
- **UserRegisterServlet**: 用户注册，触发冷启动推荐初始化
- **LogoutServlet**: 用户登出，清除 Session
- **FavoriteServlet**: 收藏操作（添加/取消），实际写入默认歌单
- **PlaylistServlet**: 歌单完整 CRUD（创建/编辑/删除，添加/移除歌曲，分页排序）
- **AdminServlet**: 管理员后台主控制器（用户/歌曲/歌单/申诉管理）
- **ChangePasswordServlet**: 密码修改（需验证当前密码）
- **UpdateProfileServlet**: 个人信息更新（昵称/邮箱/手机/性别/城市）
- **DeleteAccountServlet**: 账户注销（需密码二次确认）
- **SearchServlet**: 多源音乐搜索（网易云/QQ，含 VIP 检测）
- **RefreshRecommendServlet**: 分页获取个性化推荐（每次 5 首，支持 offset）
- **UniversalPlayHistoryServlet**: 通用播放记录（外部歌曲自动入库 + 元数据补全）
- **PlayHistoryServlet**: 播放历史 CRUD（添加/查询/清空）
- **UserPreferenceServlet**: 用户口味偏好反馈（更新 preferred_genres/preferred_artists）
- **BlockContentServlet**: 内容屏蔽管理（屏蔽/解除流派或艺术家）
- **AppealServlet**: 账号申诉提交与管理员审批

### DAO 数据访问层

- **UserDAO**: 用户数据操作（登录验证、注册、信息管理、账号状态变更）
- **SongDAO**: 歌曲数据操作（排行榜、推荐查询、外部歌曲查找/创建）
- **PlaylistDAO**: 歌单及收藏操作（创建歌单、歌曲增删、收藏状态判断，含 Redis 缓存）
- **PlayHistoryDAO**: 播放历史增删查（含时间范围过滤和分页）
- **AdminDAO**: 管理员数据操作（严格 PreparedStatement 防注入）
- **AppealDAO**: 申诉数据操作（提交、审批状态更新）
- **RedisUtil**: Redis 缓存工具（收藏状态缓存、屏蔽内容缓存）

## 前端界面

### 首页 (index.jsp)

- 未登录用户：显示平台宣传 + 登录表单 + 新歌推荐预览（8首）
- 已登录用户：自动重定向至 `user.jsp`

### 用户主页 (user.jsp)

- 用户信息卡片（昵称、邮箱、收藏数、歌单数、收听时长、加入日期）
- 搜索框（含历史下拉）
- 每日推荐（前 5 首高分推荐，支持刷新加载更多）
- 我的歌单（网格卡片布局，支持创建歌单弹窗）
- 我的收藏（默认歌单内歌曲列表）
- 热门排行榜（热歌榜/新歌榜/收藏榜，各 10 首）
- 最近播放快速预览
- 底部固定播放器（队列、播放模式、音量）

### 搜索结果页 (search.jsp)

- 顶部搜索框 + 搜索历史
- 音乐源切换按钮（网易云 / QQ / 全部）
- 搜索结果列表（含来源标签、VIP 标签）
- 每首歌支持：播放、添加到歌单、收藏

### 播放历史页 (playHistory.jsp)

- 时间范围切换（最近一周 / 一个月 / 三个月）
- 历史记录列表（封面、歌名、艺术家、精确播放时间）
- 分页浏览（每页 25 条）

### 歌单详情页 (playlist.jsp)

- 歌单封面、名称、描述、歌曲数展示
- 播放全部、编辑、删除操作（默认歌单仅可编辑）
- 歌曲列表支持：播放、收藏、从歌单移除
- 排序方式（添加时间/歌手/专辑/年份/播放次数）+ 升降序切换
- 分页浏览（每页 25 首）

### 账户设置页 (settings.jsp)

- 个人信息标签页：修改昵称、邮箱、手机、性别、城市
- 账户安全标签页：修改密码（含强度指示器）
- 账户管理标签页：查看账户信息 + 注销账户（二次确认）

### 注册页 (register.jsp)

- 注册表单（用户名、密码、邮箱）
- 实时表单验证 + 用户名重复检查

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

- Cargo 插件部署的工件名是 musicweb
- 应用程序上下文：/musicweb
- 默认浏览器是：Chrome

### 环境要求

- Java 23+
- Maven 3.x
- MySQL 8.4
- Apache Tomcat 10.x

### 一键启动（推荐）

运行 `scripts/run_services.bat` 可按顺序启动全部5项服务，每项服务均通过端口就绪检测后才启动下一项，任一服务超时则自动终止并提示：

1. **Redis**（端口 6379，超时 15s）
2. **Python QQ Music API**（端口 8000，超时 30s）
3. **Unblock 解灰服务**（端口 8081，超时 15s）
4. **Node.js 音乐 API**（端口 3000，超时 20s）
5. **Java Web 应用 / Tomcat**（端口 8082，由 Maven 自身控制）

停止所有服务：运行 `scripts/stop_services.bat`

### 手动部署步骤

1. 创建数据库 `musicweb`
2. 执行 SQL 脚本创建表结构
3. 修改 `c3p0-config.xml` 中的数据库连接信息
4. 使用 Maven 构建项目：`mvn clean package`
5. 将生成的 WAR 文件部署到 Tomcat
6. 启动 Tomcat 服务器

### 访问地址

- 首页：`http://localhost:8082/musicweb/index.jsp`
- 登录：首页集成登录功能
- 注册：`http://localhost:8082/musicweb/register.jsp`

## 特色功能

### 1. 三模型集成推荐系统

- Python 端 LightGBM + DeepFM + DIEN 三模型加权集成，离线计算推荐评分
- 推荐结果存储于 `recommendations` 表，前端实时读取展示
- 支持冷启动（新用户选择偏好流派/歌手后生成初始推荐）
- 推荐反馈冷却机制：多次忽略同一首歌自动延长冷却期

### 2. 多源音乐搜索与自动入库

- 同时接入网易云音乐和 QQ 音乐，三种来源模式可切换
- 播放外部歌曲时自动写入本地数据库并下载封面图
- 元数据（语言/流派/发行年份）通过 Node.js 和 Python 服务自动补全

### 3. 用户偏好智能管理

- 口味满意度反馈：每日可提交满意度评价，动态更新偏好流派和歌手标签
- 内容屏蔽：主动屏蔽不喜欢的流派或艺术家，推荐自动过滤，支持有效期管理

### 4. 丰富的排行榜

- 热歌榜：全局播放量排序
- 新歌榜：按发行时间排序
- 收藏榜：被收藏次数最多的歌曲

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

- [X] ~~管理员后台系统~~ ✅ 已完成
- [X] ~~用户详情与账号管理~~ ✅ 已完成
- [X] ~~账号申诉与邮件通知系统~~ ✅ 已完成
- [X] ~~歌曲播放功能~~ ✅ 已完成
- [X] ~~音乐搜索功能~~ ✅ 已完成
- [X] ~~歌单创建和管理~~ ✅ 已完成（v1.7.3）
- [X] ~~第三方音乐平台集成~~ ✅ 已完成（v1.8.0）
- [X] ~~启动脚本与目录重构~~ ✅ 已完成（v1.8.1/v2.1.2）
- [X] ~~通用播放历史系统~~ ✅ 已完成（v3.1.0）
- [X] ~~元数据架构升级 (语种/流派)~~ ✅ 已完成（v3.2.0）
- [ ] **🎯 歌单广场** (P0): 接入网易云歌单API，替代"我的收藏"导航
- [ ] **收藏系统迁移**: 统一收藏与歌单系统，❤️ 操作写入默认歌单
- [ ] **排行榜重构**: 飙升榜（增长率）+ 个性化新歌榜 + 口碑榜
- [X] **Redis 缓存进阶**: 缓存用户收藏状态 (v4.0.2)
- [ ] 高级搜索筛选: 基于流派、年份、语种的组合筛选
- [ ] 存量数据清洗: 批量更新旧版网易云数据的元信息

### 长期规划

- [ ] **序列推荐增强**: 引入 Transformer (SASRec) 提升推荐精准度
- [ ] **知识图谱增强**: 构建音乐知识图谱，解决冷启动问题
- [ ] **音乐社区化**: 评论、弹幕、动态分享、关注系统
- [ ] **多端适配**: 开发移动端 App
- [ ] **沉浸式体验**: 歌词滚动、频谱可视化
- [ ] **签到/任务系统**: 提升用户留存率

## 联系信息

**项目名称**: MusicWeb 在线音乐平台

**开发语言**: Java 23 + JSP + Servlet

**技术框架**: Jakarta EE 10+ (Servlet 6.1, JSP 3.1)

**数据库**: MySQL 8.4.0

**连接池**: C3P0 0.9.5.5

**项目类型**: 数据库应用开发课程设计

**初创时间**: 2025年11月

**最新版本**: v4.2.0

---

*本文档最后更新时间：2026年3月25日*
