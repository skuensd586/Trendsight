# -*- coding: utf-8 -*-
"""
数据库操作仓库。

功能：
1. 数据库引擎创建
2. 新闻/帖子去重
    - URL 精确去重
    - SimHash 内容近似去重

3. 评论处理
    - URL 精确去重
    - SimHash 相似评论检测
    - 重复评论次数统计

说明：
    新闻重复：
        由于关键词搜索可能导致同一文章重复出现，
        不用于水军判断。

    评论重复：
        用于发现异常重复传播行为，
        为后续虚假文本/水军分析提供特征。
"""

import os
from dotenv import load_dotenv
from simhash import Simhash
from sqlalchemy import create_engine, text

load_dotenv()
DB_CONFIG = {
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "database": os.getenv(
        "DB_DATABASE",
        "public_opinion_system"
    ),
}


def create_db_engine():
    """创建 SQLAlchemy 数据库引擎"""
    conn_str = (
        f"mysql+pymysql://"
        f"{DB_CONFIG['user']}:{DB_CONFIG['password']}"
        f"@{DB_CONFIG['host']}:{DB_CONFIG['port']}"
        f"/{DB_CONFIG['database']}"
    )
    try:
        return create_engine(conn_str)
    except Exception as e:
        raise RuntimeError(f"数据库引擎创建失败: {e}") from e


def check_url(engine, source_url: str) -> str | None:
    """新闻 URL 精确去重，正文提取前调用"""
    with engine.connect() as conn:
        result = conn.execute(
            text("""
            SELECT 1
            FROM raw_documents
            WHERE source_url=:url
            LIMIT 1
            """),
            {
                "url": source_url
            }
        )
        if result.first():
            return "URL已存在"
    return None

def save_document(engine, doc: dict):
    """新闻入库"""
    with engine.begin() as conn:
        conn.execute(
            text("""
            INSERT INTO raw_documents
            (
                doc_id,
                source_platform,
                source_url,
                title,
                content,
                author,
                publish_time,
                crawl_time,
                content_hash,
                event_id,
                verification_type,
                repost_count,
                like_count,
                comment_count
            )
            VALUES
            (
                :doc_id,
                :source_platform,
                :source_url,
                :title,
                :content,
                :author,
                :publish_time,
                :crawl_time,
                :content_hash,
                :event_id,
                :verification_type,
                :repost_count,
                :like_count,
                :comment_count
            )
            """),
            doc
        )

def check_content(
        engine,
        content: str,
        threshold: int = 3
):
    """新闻正文 SimHash 去重（不参与水军分析）"""
    with engine.connect() as conn:
        rows = conn.execute(
            text("""
            SELECT content_hash
            FROM raw_documents
            WHERE content_hash IS NOT NULL
            """)
        ).all()
    new_fp = Simhash(content).value
    for row in rows:
        try:
            old_fp = int(row[0])
        except Exception:
            continue
        distance = (
            new_fp ^ old_fp
        ).bit_count()
        if distance <= threshold:

            return (
                f"内容近似重复，"
                f"海明距离={distance}"
            )
    return None


def check_comment_url(
        engine,
        source_url: str
):
    """评论 URL 精确去重，防止同一评论重复入库"""
    with engine.connect() as conn:
        result = conn.execute(
            text("""
            SELECT 1
            FROM raw_comments
            WHERE source_url=:url
            LIMIT 1
            """),
            {
                "url": source_url
            }
        )
        if result.first():

            return "评论URL已存在"
    return None

def save_comment(
        engine,
        comment: dict
):
    """评论入库"""
    with engine.begin() as conn:
        conn.execute(
            text("""
            INSERT INTO raw_comments
            (
                comment_id,
                source_platform,
                parent_post_id,
                source_url,
                content,
                author,
                user_id,
                commenter_ip,
                likes_count,
                publish_time,
                crawl_time,
                content_hash,
                duplicate_count,
                clean_status
            )
            VALUES
            (
                :comment_id,
                :source_platform,
                :parent_post_id,
                :source_url,
                :content,
                :author,
                :user_id,
                :commenter_ip,
                :likes_count,
                :publish_time,
                :crawl_time,
                :content_hash,
                :duplicate_count,
                :clean_status
            )
            """),
            comment
        )

def check_comment_content(
        engine,
        content: str,
        threshold: int = 3
):
    """评论 SimHash 相似检测。返回 {content_hash, distance} 或 None"""
    with engine.connect() as conn:
        rows = conn.execute(
            text("""
            SELECT content_hash
            FROM raw_comments
            WHERE content_hash IS NOT NULL
            """)
        ).all()
    new_fp = Simhash(content).value
    for row in rows:
        try:
            old_fp = int(row[0])
        except Exception:
            continue
        distance = (
            new_fp ^ old_fp
        ).bit_count()
        if distance <= threshold:
            return {
                "content_hash": row[0],
                "distance": distance
            }
    return None

def increase_comment_duplicate_count(
        engine,
        content_hash: str
):
    """增加重复评论次数"""
    with engine.begin() as conn:
        conn.execute(
            text("""
            UPDATE raw_comments
            SET duplicate_count =
                duplicate_count + 1
            WHERE content_hash=:hash
            """),
            {
                "hash": content_hash
            }
        )
