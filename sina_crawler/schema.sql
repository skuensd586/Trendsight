-- ============================================
-- 舆情分析系统 - raw_documents 表建表脚本
-- 负责人：A（爬虫 + 数据清洗）
-- ============================================

CREATE DATABASE IF NOT EXISTS public_opinion_system
    DEFAULT CHARACTER SET utf8mb4
    DEFAULT COLLATE utf8mb4_unicode_ci;

USE public_opinion_system;

-- 注意：如果C的events表还没建好，event_id先不加外键约束
-- 等C把events表建好之后，再执行下面这条ALTER语句加外键：
-- ALTER TABLE raw_documents ADD CONSTRAINT fk_event
--     FOREIGN KEY (event_id) REFERENCES events(event_id);

CREATE TABLE IF NOT EXISTS raw_documents (
    doc_id           VARCHAR(64)   NOT NULL PRIMARY KEY,
    source_platform  VARCHAR(20)   NOT NULL,
    source_url       VARCHAR(500)  NOT NULL,
    title            VARCHAR(500)  NOT NULL,
    content          TEXT          NOT NULL,
    author           VARCHAR(100)  DEFAULT NULL,
    publish_time     DATETIME      NOT NULL,
    crawl_time       DATETIME      NOT NULL,
    content_hash     VARCHAR(64)   DEFAULT NULL,
    event_id         INT           DEFAULT NULL,
    UNIQUE KEY uk_source_url (source_url(255)),
    KEY idx_platform (source_platform),
    KEY idx_publish_time (publish_time),
    KEY idx_event_id (event_id),
    -- 以下字段由 C 模块回填（情感分析、关键词等）
    sentiment_label  VARCHAR(10)  DEFAULT NULL COMMENT '正面/负面/中性（C 回填）',
    sentiment_score  FLOAT        DEFAULT NULL COMMENT '情感置信度分（C 回填）',
    keywords         TEXT         DEFAULT NULL COMMENT '逗号分隔的关键词列表（C 回填）',
    clean_status     VARCHAR(20)  DEFAULT 'raw' COMMENT '数据状态：raw/cleaned/enriched',
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
