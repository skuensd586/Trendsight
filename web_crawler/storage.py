# -*- coding: utf-8 -*-
"""
数据库操作仓库。
封装引擎创建、文档去重（URL + SimHash）、文档入库。

去重策略（两阶段）：
  1. check_url()  — URL 精确匹配，在正文提取前调用，
                    快速跳过已知文章，避免不必要的 HTTP 请求。
  2. check_content() — SimHash 近似去重，在正文提取后调用，
                    检测不同 URL 但内容高度相似的重复文章。
  所有爬虫平台统一经过这两道检查。
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
    "database": os.getenv("DB_DATABASE", "public_opinion_system"),
}


def create_db_engine():
    """创建 SQLAlchemy 数据库引擎"""
    conn_str = (
        f"mysql+pymysql://{DB_CONFIG['user']}:{DB_CONFIG['password']}"
        f"@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
    )
    return create_engine(conn_str)


def check_url(engine, source_url: str) -> str | None:
    """URL 精确去重。
    返回: 重复原因字符串（如 "URL已存在"），或 None 表示通过。
    应在正文提取前调用，以节省 HTTP 开销。
    """
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT 1 FROM raw_documents WHERE source_url = :url LIMIT 1"),
            {"url": source_url},
        )
        return "URL已存在" if result.first() is not None else None


def save_document(engine, doc: dict):
    """文档入库"""
    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO raw_documents
                (doc_id, source_platform, source_url, title, content,
                 author, publish_time, crawl_time, content_hash, event_id)
                VALUES
                (:doc_id, :source_platform, :source_url, :title, :content,
                 :author, :publish_time, :crawl_time, :content_hash, :event_id)
            """),
            doc,
        )


def check_content(engine, content: str, threshold: int = 3) -> str | None:
    """
    SimHash 近似去重。
    将新内容的 SimHash 与表中所有已有指纹逐一比对，
    如果海明距离 <= threshold，视为近似重复。
    返回: 重复原因字符串（如 "内容近似重复，海明距离=X"），或 None。
    注：数据量大时可改用分块索引策略提升性能。
    """
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT content_hash FROM raw_documents "
                 "WHERE content_hash IS NOT NULL AND content_hash != ''")
        ).all()
    new_fp = Simhash(content).value
    for row in rows:
        try:
            old_fp = int(row[0])
        except (ValueError, TypeError):
            continue
        distance = (new_fp ^ old_fp).bit_count()
        if distance <= threshold:
            return f"内容近似重复，海明距离={distance}"
    return None


# ─── 评论（raw_comments）操作 ─────────────────────────────────


def check_comment_url(engine, source_url: str) -> str | None:
    """评论 URL 精确去重。
    返回: 重复原因字符串，或 None 表示通过。
    """
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT 1 FROM raw_comments WHERE source_url = :url LIMIT 1"),
            {"url": source_url},
        )
        return "评论URL已存在" if result.first() is not None else None


def save_comment(engine, comment: dict):
    """评论入库"""
    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO raw_comments
                (comment_id, source_platform, parent_post_id, source_url,
                 content, author, user_id, commenter_ip, likes_count,
                 publish_time, crawl_time, content_hash, clean_status)
                VALUES
                (:comment_id, :source_platform, :parent_post_id, :source_url,
                 :content, :author, :user_id, :commenter_ip, :likes_count,
                 :publish_time, :crawl_time, :content_hash, :clean_status)
            """),
            comment,
        )


def check_comment_content(engine, content: str, threshold: int = 3) -> str | None:
    """SimHash 近似去重，逻辑同 check_content，在 raw_comments 表上操作。"""
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT content_hash FROM raw_comments "
                 "WHERE content_hash IS NOT NULL AND content_hash != ''")
        ).all()
    new_fp = Simhash(content).value
    for row in rows:
        try:
            old_fp = int(row[0])
        except (ValueError, TypeError):
            continue
        distance = (new_fp ^ old_fp).bit_count()
        if distance <= threshold:
            return f"评论内容近似重复，海明距离={distance}"
    return None
