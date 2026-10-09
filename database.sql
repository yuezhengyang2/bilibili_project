-- 1. 创建数据库
CREATE DATABASE IF NOT EXISTS bilibili_db DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- 2. 切换到该数据库
USE bilibili_db;

-- 3. 创建视频信息表
CREATE TABLE IF NOT EXISTS videos (
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
    bvid VARCHAR(20) UNIQUE NOT NULL COMMENT '视频BV号',
    title VARCHAR(500) NOT NULL COMMENT '视频标题',
    owner VARCHAR(100) COMMENT 'UP主名称',
    tid INT COMMENT '分区ID',
    tags VARCHAR(500) COMMENT '视频标签（毕设核心字段）',
    pub_date DATETIME COMMENT '发布时间',
    pub_timestamp INT COMMENT '发布时间戳',
    view INT DEFAULT 0 COMMENT '播放量',
    danmaku INT DEFAULT 0 COMMENT '弹幕数',
    like_count INT DEFAULT 0 COMMENT '点赞数',
    coin INT DEFAULT 0 COMMENT '投币数',
    favorite INT DEFAULT 0 COMMENT '收藏数',
    share INT DEFAULT 0 COMMENT '转发数',
    interact_rate FLOAT COMMENT '互动率',
    heat_score FLOAT COMMENT '综合热度分（毕设推荐算法用）',
    url VARCHAR(200) COMMENT '视频链接',
    crawl_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '爬取时间'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='B站视频信息表';

-- 4. 新增 video_stats 表（快照表）
CREATE TABLE IF NOT EXISTS video_stats (
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
    bvid VARCHAR(20) NOT NULL COMMENT '视频BV号',
    view INT DEFAULT 0 COMMENT '播放量',
    danmaku INT DEFAULT 0 COMMENT '弹幕数',
    like_count INT DEFAULT 0 COMMENT '点赞数',
    coin INT DEFAULT 0 COMMENT '投币数',
    favorite INT DEFAULT 0 COMMENT '收藏数',
    share INT DEFAULT 0 COMMENT '转发数',
    interact_rate FLOAT COMMENT '互动率',
    heat_score FLOAT COMMENT '综合热度分',
    crawl_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '爬取时间',
    INDEX idx_bvid (bvid),
    INDEX idx_crawl_time (crawl_time),
    CONSTRAINT fk_video_stats_bvid FOREIGN KEY (bvid) REFERENCES videos(bvid) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='B站视频统计快照表';


