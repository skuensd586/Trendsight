"""B 模块 FastAPI 服务：对外暴露 /analyze 接口，供 C 后端调用。

B 不直接访问数据库，只负责计算。C 负责从数据库取原始数据传入、拿到结果后写库。

接口：
  GET  /health          健康检查
  POST /analyze         主分析接口（聚类 + 情感 + 关键词 + 趋势）
"""
from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel

from algo.cluster import cluster_with_centroids
from algo.cluster.vectorize import cosine_similarity
from algo.nlp.tfidf import tfidf_vector
from algo.nlp.tokenize import tokenize
from algo.pipeline import analyze_event, discover_events
from algo.preprocess import normalize_document
from algo.sentiment import classify_sentiment, predict_sentiment

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Trendsight Algo Service",
    version="1.0.0",
    description="B 模块：舆情分析算法服务，不直接访问数据库",
)


# ── 请求 / 响应 Schema ────────────────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    documents: list[dict[str, Any]]
    comments: list[dict[str, Any]] = []
    sentiment_method: str = "bert"   # bert / ml / dict


class AnalyzeResponse(BaseModel):
    events: list[dict[str, Any]]


# ── 工具函数 ──────────────────────────────────────────────────────────────────

def _sentiment_labels(docs, method: str) -> list[str]:
    """对一批 Document 对象逐条打情感标签。"""
    labels: list[str] = []
    _ml_ok = True
    for doc in docs:
        text = doc.title + " " + doc.content
        if method == "bert":
            try:
                from algo.sentiment import predict_bert_sentiment
                label = predict_bert_sentiment(text)
            except (ImportError, Exception):
                label, _ = classify_sentiment(tokenize(text))
        elif method == "dict":
            label, _ = classify_sentiment(tokenize(text))
        else:  # ml with fallback to dict
            if _ml_ok:
                try:
                    label = predict_sentiment(text, doc.text_type)
                except FileNotFoundError:
                    _ml_ok = False
                    label, _ = classify_sentiment(tokenize(text))
            else:
                label, _ = classify_sentiment(tokenize(text))
        labels.append(label)
    return labels


def _distribution(labels: list[str]) -> dict[str, float]:
    counts = {"positive": 0, "negative": 0, "neutral": 0}
    for label in labels:
        counts[label] += 1
    total = sum(counts.values()) or 1
    return {k: round(v / total, 3) for k, v in counts.items()}


def _assign_comments(comment_docs, centroids, idf) -> list[int]:
    """最近质心分配：每条评论归入相似度最高的帖子簇。"""
    assignments: list[int] = []
    for doc in comment_docs:
        vec = tfidf_vector(tokenize(doc.title + " " + doc.content), idf)
        best_id, best_score = 0, -1.0
        for cid, centroid in enumerate(centroids):
            score = cosine_similarity(vec, centroid)
            if score > best_score:
                best_id, best_score = cid, score
        assignments.append(best_id)
    return assignments


# ── 接口 ──────────────────────────────────────────────────────────────────────

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(req: AnalyzeRequest) -> dict[str, Any]:
    """
    输入 raw_documents + raw_comments，输出每个事件的完整分析报告。

    有评论时走两阶段流程：
      1. 只对帖子做 Single-Pass 聚类（文本够长，TF-IDF 信号强）
      2. 评论按 TF-IDF 质心最近邻分配到对应事件簇
      3. 情感分布由评论计算（信号比新闻正文更强）
      4. 热度 / 关键词 / 生命周期 / 趋势由帖子计算

    无评论时走标准 pipeline（聚类 + 全文情感）。
    """
    if not req.documents:
        return {"events": []}

    if req.comments:
        post_docs = [normalize_document(r) for r in req.documents]
        assignments, centroids, idf = cluster_with_centroids(post_docs)

        posts_by_cluster: dict[int, list[dict]] = defaultdict(list)
        for raw, cid in zip(req.documents, assignments):
            posts_by_cluster[cid].append({**raw, "event_id": f"cluster-{cid}"})

        comment_docs = [normalize_document(r) for r in req.comments]
        comment_assignments = _assign_comments(comment_docs, centroids, idf)

        comments_by_cluster: dict[int, list] = defaultdict(list)
        for doc, cid in zip(comment_docs, comment_assignments):
            comments_by_cluster[cid].append(doc)

        reports: list[dict] = []
        for cid, raws in posts_by_cluster.items():
            report = analyze_event(raws)
            assigned_comments = comments_by_cluster.get(cid, [])
            if assigned_comments:
                labels = _sentiment_labels(assigned_comments, req.sentiment_method)
                report["sentiment"] = _distribution(labels)
                report["comment_count"] = len(assigned_comments)
            else:
                report["comment_count"] = 0
            reports.append(report)
    else:
        tagged = discover_events(req.documents)
        reports = run_pipeline_simple(tagged)

    reports.sort(key=lambda r: r["heat"], reverse=True)
    return {"events": reports}


def run_pipeline_simple(tagged_records: list[dict]) -> list[dict]:
    by_event: dict[str, list[dict]] = defaultdict(list)
    for raw in tagged_records:
        by_event[raw["event_id"]].append(raw)
    return [analyze_event(raws) for raws in by_event.values()]
