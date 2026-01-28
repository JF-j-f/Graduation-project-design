-- ============================================
-- MusicWeb 数据库初始化脚本
-- 功能：创建数据库、表结构、插入测试数据、配置自动清理任务
-- ============================================

-- 创建数据库（如果不存在）
-- IF NOT EXISTS: 避免重复创建导致错误
-- CHARACTER SET utf8mb4: 使用 UTF-8 编码，支持中文和 emoji
-- COLLATE utf8mb4_unicode_ci: 使用 Unicode 排序规则，不区分大小写
CREATE DATABASE IF NOT EXISTS musicweb CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- 切换到 musicweb 数据库，后续所有操作都在此数据库中执行
USE musicweb;

-- ============================================
-- 创建用户表 (users)
-- 存储用户账号信息、状态管理、冻结和删除记录
-- ============================================
CREATE TABLE IF NOT EXISTS users (
    id INT PRIMARY KEY AUTO_INCREMENT,                                  -- 用户ID，主键，自动递增
    username VARCHAR(50) NOT NULL UNIQUE,                               -- 用户名，不能为空，必须唯一
    password VARCHAR(100) NOT NULL,                                     -- 密码，不能为空（建议加密存储）
    email VARCHAR(100),                                                 -- 邮箱地址，可为空
    nickname VARCHAR(50),                                               -- 昵称，可为空
    phone VARCHAR(20),                                                  -- 手机号，可为空
    status ENUM('active', 'frozen', 'deleted') DEFAULT 'active',        -- 账号状态：active=正常，frozen=冻结，deleted=已删除
    frozen_until TIMESTAMP NULL,                                        -- 冻结截止时间，NULL表示未冻结
    frozen_reason VARCHAR(200),                                         -- 冻结原因说明
    deleted_at TIMESTAMP NULL,                                          -- 删除时间，用于30天后自动清理
    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP                     -- 账号创建时间，默认为当前时间
);

-- ============================================
-- 创建歌曲表 (songs)
-- 存储音乐库中的所有歌曲信息
-- ============================================
CREATE TABLE IF NOT EXISTS songs (
    id INT PRIMARY KEY AUTO_INCREMENT,                                  -- 歌曲ID，主键，自动递增
    title VARCHAR(100) NOT NULL,                                        -- 歌曲标题，不能为空
    artist VARCHAR(100) NOT NULL,                                       -- 艺术家/歌手名称，不能为空
    album VARCHAR(100),                                                 -- 专辑名称，可为空
    duration INT,                                                       -- 歌曲时长（单位：秒）
    genre VARCHAR(50),                                                  -- 音乐类型（如：流行、摇滚、中国风）
    release_year INT,                                                   -- 发行年份
    file_path VARCHAR(200),                                             -- 音频文件路径
    cover_image VARCHAR(200),                                           -- 封面图片路径
    kkbox_id VARCHAR(50),                                               -- KKBOX 歌曲唯一标识
    genre_ids VARCHAR(100),                                             -- KKBOX 流派ID组合 (如 465|458)
    language VARCHAR(50),                                               -- 歌曲语种 (原始值为数字代码，如 31.0，计划标准化为中文)
    popularity INT DEFAULT 0                                            -- 歌曲热度
);

-- ============================================
-- 创建收藏表 (favorites)
-- 存储用户收藏的歌曲关系，多对多关系表
-- ============================================
CREATE TABLE IF NOT EXISTS favorites (
    id INT PRIMARY KEY AUTO_INCREMENT,                                  -- 收藏记录ID，主键，自动递增
    user_id INT NOT NULL,                                               -- 用户ID，外键关联 users 表
    song_id INT NOT NULL,                                               -- 歌曲ID，外键关联 songs 表
    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,                    -- 收藏时间，默认为当前时间
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,       -- 外键约束：用户被删除时，自动删除其收藏记录
    FOREIGN KEY (song_id) REFERENCES songs(id) ON DELETE CASCADE,       -- 外键约束：歌曲被删除时，自动删除相关收藏记录
    UNIQUE KEY unique_favorite (user_id, song_id)                       -- 唯一约束：同一用户不能重复收藏同一首歌
);

-- ============================================
-- 创建播放历史表 (play_history)
-- 存储用户的歌曲播放记录
-- ============================================
CREATE TABLE IF NOT EXISTS play_history (
    id INT PRIMARY KEY AUTO_INCREMENT,                                  -- 播放历史ID，主键，自动递增
    user_id INT NOT NULL,                                               -- 用户ID，外键关联 users 表
    song_id INT NOT NULL,                                               -- 歌曲ID，外键关联 songs 表
    play_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,                      -- 播放时间，默认为当前时间
    play_duration INT DEFAULT 0,                                        -- 实际播放时长（单位：秒），记录用户听了多久
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,       -- 外键约束：用户被删除时，自动删除其播放历史
    FOREIGN KEY (song_id) REFERENCES songs(id) ON DELETE CASCADE,       -- 外键约束：歌曲被删除时，自动删除相关播放历史
    INDEX idx_user_time (user_id, play_time DESC)                       -- 索引：按用户ID和播放时间倒序，提高查询效率
);

-- ============================================
-- 插入示例歌曲数据
-- INSERT IGNORE: 如果主键冲突则忽略，避免重复插入
-- 注意：file_path 对应 music/ 文件夹中的实际音频文件
-- ============================================
INSERT IGNORE INTO songs (id, title, artist, album, duration, genre, release_year, file_path, cover_image) VALUES
(1, '說好的幸福呢', '周杰伦', '魔杰座', 270, '流行', 2008, '說好的幸福呢.mp3', 'img/cover.jpg'),      -- 歌曲1：說好的幸福呢
(2, '聽媽媽的話', '周杰伦', '依然范特西', 258, '流行', 2006, '聽媽媽的話.mp3', 'img/cover.jpg'),    -- 歌曲2：聽媽媽的話
(3, '我是如此相信', '周杰伦', '我很忙', 264, '流行', 2007, '我是如此相信.mp3', 'img/cover.jpg'),    -- 歌曲3：我是如此相信
(4, '星晴', '周杰伦', 'Jay', 270, '流行', 2000, '星晴.mp3', 'img/cover.jpg'),                     -- 歌曲4：星晴
(5, '煙花易冷', '周杰伦', '跨时代', 261, '中国风', 2010, '煙花易冷.mp3', 'img/cover.jpg'),           -- 歌曲5：煙花易冷
(6, '一路向北', '周杰伦', '11月的萧邦', 303, '流行', 2005, '一路向北.mp3', 'img/cover.jpg'),        -- 歌曲6：一路向北
(7, '怎麼了', '周杰伦', '12新作', 247, '流行', 2012, '怎麼了 (feat. Cindy Yen).mp3', 'img/cover.jpg'), -- 歌曲7：怎麼了
(8, '最偉大的作品', '周杰伦', '最伟大的作品', 235, '流行', 2022, '最偉大的作品.mp3', 'img/cover.jpg'); -- 歌曲8：最偉大的作品

-- ============================================
-- 显示数据库中的所有表
-- 用于验证表是否创建成功
-- ============================================
SHOW TABLES;

-- ============================================
-- 显示各表的数据统计
-- 使用 UNION ALL 合并多个查询结果
-- ============================================
SELECT
    'users' as table_name,                                              -- 表名：users
    COUNT(*) as record_count                                            -- 统计用户表的记录数
FROM
    users
UNION ALL                                                               -- 合并查询结果（保留重复行）
SELECT
    'songs' as table_name,                                              -- 表名：songs
    COUNT(*) as record_count                                            -- 统计歌曲表的记录数
FROM
    songs
UNION ALL                                                               -- 合并查询结果
SELECT
    'favorites' as table_name,                                          -- 表名：favorites
    COUNT(*) as record_count                                            -- 统计收藏表的记录数
FROM
    favorites
UNION ALL                                                               -- 合并查询结果
SELECT
    'play_history' as table_name,                                       -- 表名：play_history
    COUNT(*) as record_count                                            -- 统计播放历史表的记录数
FROM
    play_history;

-- ============================================
-- 开启 MySQL 事件调度器
-- 事件调度器用于执行定时任务（类似 Linux 的 cron）
-- ============================================
SET GLOBAL event_scheduler = ON;

-- ============================================
-- 创建定时任务：自动清理超过30天的已删除用户
-- 功能：每天凌晨2点检查并删除 deleted_at 超过30天的用户
-- ============================================
DROP EVENT IF EXISTS delete_expired_users;                              -- 如果事件已存在，先删除
CREATE EVENT delete_expired_users                                       -- 创建名为 delete_expired_users 的事件
ON SCHEDULE EVERY 1 DAY                                                 -- 调度频率：每天执行一次
STARTS TIMESTAMP(CURRENT_DATE, '02:00:00')                              -- 开始时间：每天凌晨2点
DO                                                                      -- 执行以下 SQL 语句
DELETE FROM users                                                       -- 从 users 表中删除记录
WHERE status = 'deleted'                                                -- 条件1：状态为已删除
AND deleted_at IS NOT NULL                                              -- 条件2：删除时间不为空
AND deleted_at < DATE_SUB(NOW(), INTERVAL 30 DAY);                     -- 条件3：删除时间早于30天前（NOW() - 30天）

-- ============================================
-- 创建申诉表 (appeals)
-- 存储用户对账号冻结或删除的申诉记录
-- ============================================
CREATE TABLE IF NOT EXISTS appeals (
    id INT PRIMARY KEY AUTO_INCREMENT,                                  -- 申诉ID，主键，自动递增
    username VARCHAR(50) NOT NULL,                                      -- 申诉用户名
    user_id INT,                                                        -- 用户ID，外键关联 users 表（可为NULL，因为账号可能已删除）
    appeal_type ENUM('frozen', 'deleted') NOT NULL,                     -- 申诉类型：frozen=冻结申诉，deleted=删除申诉
    reason TEXT NOT NULL,                                               -- 申诉原因，用户填写的详细说明
    contact_email VARCHAR(100) NOT NULL,                                -- 联系邮箱，用于接收审批结果通知
    status ENUM('pending', 'approved', 'rejected') DEFAULT 'pending',   -- 申诉状态：pending=待处理，approved=已同意，rejected=已拒绝
    admin_reply TEXT,                                                   -- 管理员回复内容
    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,                    -- 申诉创建时间
    update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP, -- 最后更新时间
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL       -- 外键约束：用户被删除时，user_id 设为 NULL
);

-- 1. 创建歌单表 (playlist_info)
CREATE TABLE IF NOT EXISTS playlist_info (
                                             id INT AUTO_INCREMENT PRIMARY KEY,
                                             playlist_id VARCHAR(50) UNIQUE COMMENT '网易云歌单ID',
                                             title VARCHAR(255) COMMENT '歌单标题',
                                             category VARCHAR(50) COMMENT '所属分类',
                                             tags VARCHAR(255) COMMENT '歌单标签',
                                             play_count BIGINT COMMENT '播放量',
                                             fav_count INT COMMENT '收藏量',
                                             share_count INT COMMENT '分享量',
                                             comment_count INT COMMENT '评论数',
                                             url VARCHAR(255) COMMENT '歌单链接',
                                             create_time DATETIME DEFAULT CURRENT_TIMESTAMP
) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- 2. 创建歌曲表 (song_info)
CREATE TABLE IF NOT EXISTS song_info (
                                         id INT AUTO_INCREMENT PRIMARY KEY,
                                         playlist_id VARCHAR(50) COMMENT '关联的歌单ID',
                                         song_name VARCHAR(255) COMMENT '歌曲名',
                                         duration VARCHAR(20) COMMENT '时长',
                                         artist VARCHAR(255) COMMENT '歌手',
                                         album VARCHAR(255) COMMENT '专辑',
                                         FOREIGN KEY (playlist_id) REFERENCES playlist_info(playlist_id) ON DELETE CASCADE
) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- 3.创建推荐表（recommendations）
DROP TABLE IF EXISTS `recommendations`;

CREATE TABLE `recommendations` (
                                   `id` INT NOT NULL AUTO_INCREMENT,
                                   `user_id` INT NOT NULL COMMENT '目标用户ID',
                                   `song_id` INT NOT NULL COMMENT '推荐的歌曲ID',
                                   `score` DOUBLE DEFAULT '0' COMMENT '推荐得分(相似度累加)',
                                   `create_time` DATETIME DEFAULT CURRENT_TIMESTAMP,
                                   PRIMARY KEY (`id`),
                                   KEY `idx_user` (`user_id`),
                                   KEY `idx_user_score` (`user_id`, `score`) -- 联合索引优化排序
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 创建用户歌单表 (user_playlists)
-- 存储用户创建的自定义歌单信息
-- ============================================
CREATE TABLE IF NOT EXISTS user_playlists (
    id INT PRIMARY KEY AUTO_INCREMENT,                                  -- 歌单ID，主键，自动递增
    user_id INT NOT NULL,                                               -- 用户ID，外键关联 users 表
    name VARCHAR(100) NOT NULL,                                         -- 歌单名称
    description TEXT,                                                   -- 歌单描述
    cover_image VARCHAR(200),                                           -- 歌单封面图片路径
    is_default BOOLEAN DEFAULT FALSE,                                   -- 是否为默认歌单（TRUE=默认歌单，不可删除）
    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,                    -- 歌单创建时间
    update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP, -- 最后更新时间
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,      -- 外键约束：用户被删除时，自动删除其歌单
    INDEX idx_user_default (user_id, is_default)                        -- 索引：优化查询用户的默认歌单
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户歌单表';

-- ============================================
-- 创建歌单歌曲关联表 (playlist_songs)
-- 存储歌单与歌曲的多对多关系
-- ============================================
CREATE TABLE IF NOT EXISTS playlist_songs (
    id INT PRIMARY KEY AUTO_INCREMENT,                                  -- 关联记录ID，主键，自动递增
    playlist_id INT NOT NULL,                                           -- 歌单ID，外键关联 user_playlists 表
    song_id INT NOT NULL,                                               -- 歌曲ID，外键关联 songs 表
    add_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,                       -- 添加时间
    FOREIGN KEY (playlist_id) REFERENCES user_playlists(id) ON DELETE CASCADE, -- 外键约束：歌单被删除时，自动删除关联歌曲
    FOREIGN KEY (song_id) REFERENCES songs(id) ON DELETE CASCADE,      -- 外键约束：歌曲被删除时，自动删除关联记录
    UNIQUE KEY unique_song_in_playlist (playlist_id, song_id),         -- 唯一约束：同一首歌不能重复添加到同一歌单
    INDEX idx_playlist_time (playlist_id, add_time DESC)               -- 索引：优化歌单歌曲查询，按添加时间倒序
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='歌单歌曲关联表';

