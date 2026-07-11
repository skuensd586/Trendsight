"""C 模块后台分析工作者。

从爬虫数据库 (public_opinion_system) 读取 clean_status='raw' 的原始数据，
调用 B 模块 Algo 服务进行分析，将结果写入 events 表，并回写原始数据状态。

环境变量（指向爬虫的 public_opinion_system 数据库）:
  CRAWLER_DB_HOST     (default: localhost)
  CRAWLER_DB_PORT     (default: 3306)
  CRAWLER_DB_USER     (default: root)
  CRAWLER_DB_PASSWORD (default: "")
  CRAWLER_DB_NAME     (default: public_opinion_system)
  ALGO_SENTIMENT_METHOD (default: bert)

用法:
    from services.analysis_worker import process_pending_documents
    stats = process_pending_documents(limit=100)
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any

from sqlalchemy import create_engine, text

from dependencies import SessionLocal
from services.event_service import save_event
from utils.algo_client import call_algo


# ── 爬虫数据库连接 ──────────────────────────────────────────────

def _crawler_db_url() -> str:
    """从环境变量组装爬虫数据库连接 URL。"""
    host = os.getenv("CRAWLER_DB_HOST", "localhost")
    port = os.getenv("CRAWLER_DB_PORT", "3306")
    user = os.getenv("CRAWLER_DB_USER", "root")
    password = os.getenv("CRAWLER_DB_PASSWORD", "")
    name = os.getenv("CRAWLER_DB_NAME", "public_opinion_system")
    return (
        f"mysql+pymysql://{user}:{password}@{host}:{port}/"
        f"{name}?charset=utf8mb4"
    )


def _make_crawler_engine():
    """创建爬虫数据库引擎。"""
    return create_engine(_crawler_db_url(), pool_pre_ping=True)


# ── 格式转换 ────────────────────────────────────────────────────

def _to_algo_records(rows: list[dict]) -> list[dict]:
    """将数据库行转为 Algo /analyze 认可的输入格式。

    Algo 的 normalize_document() 直接读取以下字段名，与爬虫表列名一致:
      doc_id / comment_id → doc_id
      title, content, author, publish_time
      source_platform, source_url

    其中 publish_time 为 None 时兜底为当前时间，避免 Algo 解析抛 ValueError。
    """
    records: list[dict[str, Any]] = []
    for row in rows:
        publish_time = row.get("publish_time")
        if publish_time is None:
            publish_time = datetime.now()
        if isinstance(publish_time, datetime):
            publish_time = publish_time.isoformat()

        records.append({
            "doc_id": row.get("doc_id") or row.get("comment_id", ""),
            "title": row.get("title", ""),
            "content": row.get("content", ""),
            "author": row.get("author", ""),
            "source_platform": row.get("source_platform", ""),
            "source_url": row.get("source_url", ""),
            'verification_type': row.get('verification_type'),
            "publish_time": publish_time,
        })
    return records


# ── 状态回写 ────────────────────────────────────────────────────

def _mark_enriched(engine, doc_ids: list[str]):
    """将 raw_documents 的 clean_status 更新为 'enriched'。

    当前 Algo /analyze 接口仅返回事件级聚合结果（热度、情感分布、关键词等），
    不返回逐条文档的聚类分配或情感标签，因此无法回填以下字段:
      - event_id:       缺少逐文档 → 事件映射关系
      - sentiment_label / sentiment_score: 仅返回事件级分布，无逐条标签
      - keywords:       仅返回事件级关键词，无逐条结果
    这些字段留待后续 Algo API 增强后补全。
    """
    if not doc_ids:
        return
    with engine.begin() as conn:
        conn.execute(
            text("""
                UPDATE raw_documents
                SET clean_status = 'enriched'
                WHERE doc_id IN :doc_ids
            """),
            {"doc_ids": tuple(doc_ids)},
        )


# ── 主流程 ──────────────────────────────────────────────────────

def process_pending_documents(limit: int = 100) -> dict:
    """执行一轮爬虫原始数据 → Algo 分析 → 事件入库 → 状态回写。

    Args:
        limit: 本轮最多处理的文档数。

    Returns:
        {
            "processed": int,     已处理的文档数
            "events_found": int,  Algo 分析产出的事件数
            "errors": int,        处理中出错的文档数
        }
    """
    stats: dict[str, int] = {"processed": 0, "events_found": 0, "errors": 0}
    engine = _make_crawler_engine()

    try:
        # 1. 读取 clean_status='raw' 的文档
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT * FROM raw_documents "
                    "WHERE clean_status = 'raw' "
                    "LIMIT :lim"
                ),
                {"lim": limit},
            ).all()

            if not rows:
                return stats

            raw_docs = [dict(r._mapping) for r in rows]
            doc_ids = [d["doc_id"] for d in raw_docs]

            # 2. 读取关联评论
            comment_rows = conn.execute(
                text(
                    "SELECT * FROM raw_comments "
                    "WHERE parent_post_id IN :ids"
                ),
                {"ids": tuple(doc_ids)},
            ).all()
            raw_comments = [dict(r._mapping) for r in comment_rows]

        stats["processed"] = len(raw_docs)

        # 3. 转为 Algo 输入格式
        algo_docs = _to_algo_records(raw_docs)
        algo_comments = _to_algo_records(raw_comments)

        # 4. 调用 Algo 分析
        try:
            method = os.getenv("ALGO_SENTIMENT_METHOD", "bert")
            events_result = call_algo(
                documents=algo_docs,
                comments=algo_comments,
                sentiment_method=method,
            )
        except RuntimeError:
            stats["errors"] = stats["processed"]
            stats["processed"] = 0
            return stats

        # 5. 保存事件到后端 events 表
        db = SessionLocal()
        try:
            for report in events_result:
                save_event(db, report)
                stats["events_found"] += 1
        finally:
            db.close()

        # 6. 回写 clean_status = 'enriched'
        _mark_enriched(engine, doc_ids)

    finally:
        engine.dispose()

    return stats


if __name__ == "__main__":
    import sys
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    result = process_pending_documents(limit=limit)
    print(result)
