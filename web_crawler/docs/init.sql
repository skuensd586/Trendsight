-- ============================================================
-- 舆情分析系统数据库初始化
-- 用法:
--   mysql -u root -p public_opinion_system < docs/init.sql
-- ============================================================

-- 1. 多平台新闻/帖子原始数据表
CREATE TABLE IF NOT EXISTS raw_documents (
    doc_id           VARCHAR(64)   NOT NULL PRIMARY KEY  COMMENT '确定性主键：{platform_code}{timestamp}{md5[:8]}',
    source_platform  VARCHAR(20)   NOT NULL              COMMENT '来源平台（如"新浪新闻"、"微博"）',
    source_url       VARCHAR(500)  DEFAULT NULL          COMMENT '原文 URL（去重依据）',
    title            VARCHAR(500)  DEFAULT NULL          COMMENT '文章标题',
    content          MEDIUMTEXT    NOT NULL              COMMENT '清洗后的正文',
    author           VARCHAR(100)  DEFAULT NULL          COMMENT '作者 / 媒体来源 / 发帖人昵称',
    publish_time     DATETIME      DEFAULT NULL          COMMENT '发布时间',
    crawl_time       DATETIME      NOT NULL              COMMENT '抓取时间',
    content_hash     VARCHAR(64)   DEFAULT NULL          COMMENT 'Simhash 64bit 指纹',
    verification_type VARCHAR(50)  DEFAULT NULL          COMMENT '信源认证类型：官方平台 / 头部认证个人 / 认证个人 / 认证机构 / 普通用户；',
    repost_count     INT           DEFAULT NULL          COMMENT '转发数（仅微博）',
    like_count       INT           DEFAULT NULL          COMMENT '点赞/赞同数（微博/知乎）',
    comment_count    INT           DEFAULT NULL          COMMENT '评论数（微博/知乎）',
    sentiment_label  VARCHAR(10)   DEFAULT NULL          COMMENT '情感标签（B 回填）',
    sentiment_score  FLOAT         DEFAULT NULL          COMMENT '情感置信度（B 回填）',
    keywords         TEXT          DEFAULT NULL          COMMENT '关键词列表（B 回填）',
    event_id         INT           DEFAULT NULL          COMMENT '所属事件 ID（B/C 回填）',
    clean_status     VARCHAR(20)   DEFAULT 'raw' NOT NULL COMMENT '数据状态',

    INDEX idx_platform      (source_platform),
    INDEX idx_publish_time  (publish_time),
    INDEX idx_event         (event_id),
    INDEX idx_clean_status  (clean_status),
    INDEX idx_verification  (verification_type),

    CONSTRAINT chk_verification_type CHECK (
        verification_type IN ('官方平台','头部认证个人','认证个人','认证机构','普通用户')
        OR verification_type IS NULL
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='多平台新闻帖子原始数据';

-- 2. 社交平台评论原始数据表
CREATE TABLE IF NOT EXISTS raw_comments (
    comment_id       VARCHAR(64)   NOT NULL PRIMARY KEY COMMENT '微博接口返回的评论 ID 字符串',
    source_platform  VARCHAR(20)   NOT NULL             COMMENT '来源平台',
    parent_post_id   VARCHAR(64)   NOT NULL             COMMENT '所属帖子的 doc_id（FK→raw_documents.doc_id）',
    source_url       VARCHAR(500)  DEFAULT NULL         COMMENT '评论页面 URL（去重依据）',
    content          TEXT          NOT NULL             COMMENT '评论正文',
    author           VARCHAR(100)  DEFAULT NULL         COMMENT '评论者昵称',
    user_id          VARCHAR(64)   DEFAULT NULL         COMMENT '评论者 UID',
    commenter_ip     VARCHAR(45)   DEFAULT NULL         COMMENT '评论者 IP 地址',
    likes_count      INT           DEFAULT 0            COMMENT '点赞数',
    publish_time     DATETIME      DEFAULT NULL         COMMENT '评论发布时间',
    crawl_time       DATETIME      NOT NULL             COMMENT '抓取时间',
    content_hash     VARCHAR(64)   DEFAULT NULL         COMMENT 'Simhash 值',
    duplicate_count  INT           DEFAULT 1            COMMENT '相同或近似评论累计出现次数',
    sentiment_label  VARCHAR(10)   DEFAULT NULL         COMMENT '情感标签（B 回填）',
    sentiment_score  FLOAT         DEFAULT NULL         COMMENT '情感置信度（B 回填）',
    keywords         TEXT          DEFAULT NULL         COMMENT '关键词列表（B 回填）',
    clean_status     VARCHAR(20)   DEFAULT 'raw' NOT NULL COMMENT '数据状态',

    INDEX idx_post         (parent_post_id),
    INDEX idx_user         (user_id),
    INDEX idx_platform     (source_platform),
    INDEX idx_publish_time (publish_time),
    INDEX idx_content_hash (content_hash)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='社交平台评论原始数据';