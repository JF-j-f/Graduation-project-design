
/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

-- ============================================
-- 用户申诉表
-- ============================================
DROP TABLE IF EXISTS `appeals`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `appeals` (
  `id` int NOT NULL AUTO_INCREMENT,
  `username` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `user_id` int DEFAULT NULL,
  `appeal_type` enum('frozen','deleted') COLLATE utf8mb4_unicode_ci NOT NULL,
  `reason` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `contact_email` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `status` enum('pending','approved','rejected') COLLATE utf8mb4_unicode_ci DEFAULT 'pending',
  `admin_reply` text COLLATE utf8mb4_unicode_ci,
  `create_time` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `update_time` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  CONSTRAINT `appeals_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB AUTO_INCREMENT=18 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户申诉表';
/*!40101 SET character_set_client = @saved_cs_client */;

-- ============================================
-- 播放历史表
-- ============================================
DROP TABLE IF EXISTS `play_history`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `play_history` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `song_id` int NOT NULL,
  `play_time` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `play_duration` int DEFAULT '0',
  PRIMARY KEY (`id`),
  KEY `song_id` (`song_id`),
  KEY `idx_user_time` (`user_id`,`play_time` DESC),
  CONSTRAINT `play_history_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `play_history_ibfk_2` FOREIGN KEY (`song_id`) REFERENCES `songs` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=281 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='播放历史表';
/*!40101 SET character_set_client = @saved_cs_client */;

-- ============================================
-- 歌单歌曲关联表
-- ============================================
DROP TABLE IF EXISTS `playlist_songs`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `playlist_songs` (
  `id` int NOT NULL AUTO_INCREMENT,
  `playlist_id` int NOT NULL,
  `song_id` int NOT NULL,
  `add_time` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_song_in_playlist` (`playlist_id`,`song_id`),
  KEY `song_id` (`song_id`),
  KEY `idx_playlist_time` (`playlist_id`,`add_time` DESC),
  CONSTRAINT `playlist_songs_ibfk_1` FOREIGN KEY (`playlist_id`) REFERENCES `user_playlists` (`id`) ON DELETE CASCADE,
  CONSTRAINT `playlist_songs_ibfk_2` FOREIGN KEY (`song_id`) REFERENCES `songs` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=636 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='歌单歌曲表';
/*!40101 SET character_set_client = @saved_cs_client */;

-- ============================================
-- 推荐反馈表
-- ============================================
DROP TABLE IF EXISTS `recommendation_feedback`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `recommendation_feedback` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `song_id` int NOT NULL,
  `recommend_date` date NOT NULL,
  `was_played` tinyint(1) DEFAULT '0',
  `play_completion` float DEFAULT '0' COMMENT '完播率 0~1',
  `was_favorited` tinyint(1) DEFAULT '0',
  `consecutive_ignore_days` int DEFAULT '0',
  `feedback_score` float DEFAULT '0',
  `cooldown_until` date DEFAULT NULL COMMENT '冷却截止日期',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_user_song_date` (`user_id`,`song_id`,`recommend_date`),
  KEY `idx_user_id` (`user_id`),
  KEY `idx_cooldown` (`user_id`,`cooldown_until`),
  KEY `song_id` (`song_id`),
  CONSTRAINT `recommendation_feedback_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`),
  CONSTRAINT `recommendation_feedback_ibfk_2` FOREIGN KEY (`song_id`) REFERENCES `songs` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=141 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='推荐反馈表';
/*!40101 SET character_set_client = @saved_cs_client */;

-- ============================================
-- 歌曲推荐结果表
-- ============================================
DROP TABLE IF EXISTS `recommendations`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `recommendations` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL COMMENT '目标用户ID',
  `song_id` int NOT NULL COMMENT '推荐的歌曲ID',
  `score` double DEFAULT '0' COMMENT '推荐得分(相似度累加)',
  `create_time` datetime DEFAULT CURRENT_TIMESTAMP,
  `source_type` varchar(20) COLLATE utf8mb4_unicode_ci DEFAULT 'deepfm' COMMENT '推荐来源类型',
  PRIMARY KEY (`id`),
  KEY `idx_user` (`user_id`),
  KEY `idx_user_score` (`user_id`,`score`)
) ENGINE=InnoDB AUTO_INCREMENT=111 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='歌曲推荐表';
/*!40101 SET character_set_client = @saved_cs_client */;

-- ============================================
-- 歌曲主表
-- ============================================
DROP TABLE IF EXISTS `songs`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `songs` (
  `id` int NOT NULL AUTO_INCREMENT,
  `title` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `artist` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `album` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `duration` int DEFAULT NULL,
  `genre` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `release_year` int DEFAULT NULL,
  `file_path` varchar(200) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `cover_image` varchar(200) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `kkbox_id` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'KKBOX原始歌曲ID',
  `genre_ids` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'KKBOX流派ID，以|分隔',
  `language` varchar(10) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '语言代码',
  `popularity` int DEFAULT '0' COMMENT '基于KKBOX交互数据的热度得分',
  `origin_country` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '歌曲原产地（外部元数据补全）',
  PRIMARY KEY (`id`),
  KEY `idx_kkbox_id` (`kkbox_id`),
  KEY `idx_genre_ids` (`genre_ids`),
  KEY `idx_popularity` (`popularity` DESC)
) ENGINE=InnoDB AUTO_INCREMENT=2306846 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='歌曲主表';
/*!40101 SET character_set_client = @saved_cs_client */;

-- ============================================
-- 用户歌单表
-- ============================================
DROP TABLE IF EXISTS `user_playlists`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `user_playlists` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `name` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `description` text COLLATE utf8mb4_unicode_ci,
  `cover_image` varchar(200) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `is_default` tinyint(1) DEFAULT '0',
  `create_time` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `update_time` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_user_default` (`user_id`,`is_default`),
  CONSTRAINT `user_playlists_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户歌单表';
/*!40101 SET character_set_client = @saved_cs_client */;

-- ============================================
-- 用户信息表
-- ============================================
DROP TABLE IF EXISTS `users`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `users` (
  `id` int NOT NULL AUTO_INCREMENT,
  `username` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `password` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `email` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `nickname` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `phone` varchar(20) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `status` enum('active','frozen','deleted') COLLATE utf8mb4_unicode_ci DEFAULT 'active',
  `frozen_until` timestamp NULL DEFAULT NULL,
  `frozen_reason` varchar(200) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `deleted_at` timestamp NULL DEFAULT NULL,
  `create_time` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `preferred_genres` varchar(200) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `preferred_artists` varchar(200) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `city` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '所在城市',
  `gender` varchar(10) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '性别(male/female/other)',
  PRIMARY KEY (`id`),
  UNIQUE KEY `username` (`username`)
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户信息表';
/*!40101 SET character_set_client = @saved_cs_client */;

-- ============================================
-- v4.0：用户对每日推荐的显式满意度反馈表（可作训练数据）
-- ============================================
CREATE TABLE IF NOT EXISTS `user_preference_feedback` (
  `id`           INT AUTO_INCREMENT PRIMARY KEY,
  `user_id`      INT NOT NULL,
  `feedback_date` DATE NOT NULL,
  `satisfaction` ENUM('very_satisfied','satisfied','neutral','dissatisfied') NOT NULL,
  `genres_added`  VARCHAR(200) DEFAULT NULL COMMENT '本次新增流派偏好（分号分隔）',
  `artists_added` VARCHAR(200) DEFAULT NULL COMMENT '本次新增艺术家偏好（分号分隔）',
  `created_at`   TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY `uk_user_date` (`user_id`, `feedback_date`),
  FOREIGN KEY (`user_id`) REFERENCES `users`(`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='用户对每日推荐的显式满意度反馈表（可作训练数据）';

-- ============================================
-- v6.0：用户流派/歌手软屏蔽（递增冷却+衰减回归）
-- ============================================
CREATE TABLE IF NOT EXISTS `user_content_blocks` (
  `id`             INT AUTO_INCREMENT PRIMARY KEY,
  `user_id`        INT NOT NULL,
  `block_type`     ENUM('genre', 'artist') NOT NULL COMMENT '屏蔽类型',
  `block_value`    VARCHAR(100) NOT NULL COMMENT '屏蔽的流派名或歌手名',
  `block_count`    INT DEFAULT 1 COMMENT '屏蔽次数（递增计数器）',
  `blocked_at`     TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '最近一次屏蔽时间',
  `blocked_until`  DATE NOT NULL COMMENT '屏蔽到期日',
  `is_active`      TINYINT(1) DEFAULT 1 COMMENT '1=生效中，0=已到期',
  UNIQUE KEY `uk_user_type_value` (`user_id`, `block_type`, `block_value`),
  KEY `idx_user_active` (`user_id`, `is_active`),
  FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='用户流派/歌手软屏蔽（递增冷却+衰减回归）';

-- ============================================
-- 歌曲滚动统计表（预聚合近7/30天播放量及热度趋势）
-- ============================================
CREATE TABLE IF NOT EXISTS `song_rolling_stats` (
  `song_id`     INT NOT NULL COMMENT '歌曲ID，与songs表一对一对应',
  `cnt_7d`      INT NOT NULL DEFAULT 0 COMMENT '近7天播放次数',
  `cnt_30d`     INT NOT NULL DEFAULT 0 COMMENT '近30天播放次数',
  `trending`    FLOAT NOT NULL DEFAULT 0 COMMENT '热度趋势（7天播放量/30天日均+1）',
  `total_plays` BIGINT NOT NULL DEFAULT 0 COMMENT '累计总播放次数',
  `updated_at`  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                ON UPDATE CURRENT_TIMESTAMP COMMENT '最后更新时间',
  PRIMARY KEY (`song_id`),
  FOREIGN KEY (`song_id`) REFERENCES `songs`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='歌曲滚动统计表（预聚合近7/30天播放量及热度趋势，供推荐引擎实时查询）';

/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;
/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;
