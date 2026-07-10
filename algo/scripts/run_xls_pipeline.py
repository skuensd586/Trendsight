"""Two-stage pipeline for crawler XLS files: cluster posts, assign comments by proximity.

Stage 1 — cluster posts only (longer texts, reliable TF-IDF signal):
  discover_events on post records → N event clusters with centroids

Stage 2 — assign comments to nearest cluster:
  Each comment's TF-IDF vector (built with the post-corpus IDF) is compared to all
  cluster centroids; the comment joins whichever cluster scores highest regardless of
  threshold (nearest-neighbour, no cutoff).

Stage 3 (optional) — topic relevance filtering:
  Build a TF-IDF seed vector from --topic keywords and compute each cluster centroid's
  cosine similarity to it.  Clusters below --relevance-threshold are dropped.  This
  removes off-topic noise (unrelated news that happened to share a word) without any
  hardcoded keyword lists.

Per-cluster output:
  structural metrics (heat / keywords / lifecycle / platform_distribution / trend)
    ← posts only
  sentiment distribution
    ← comments assigned to this cluster (stronger signal than neutral news text)

Usage:
    python -m scripts.run_xls_pipeline \\
        ../7.8广西洪灾新闻帖子数据.xls \\
        ../7.8广西洪灾评论数据.xls \\
        --topic "广西 洪灾 洪水 暴雨 救援" \\
        --output ../reports/guangxi_flood_report.json
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import xlrd

from algo.cluster import cluster_with_centroids
from algo.cluster.vectorize import cosine_similarity
from algo.nlp.tfidf import tfidf_vector
from algo.nlp.tokenize import tokenize
from algo.pipeline import analyze_event
from algo.preprocess import normalize_document
from algo.sentiment import classify_sentiment, predict_bert_sentiment, predict_sentiment

SENTIMENT_METHODS = ("auto", "ml", "dict", "bert")


# ── data loading ──────────────────────────────────────────────────────────────

def _read_xls(path: Path) -> list[dict]:
    wb = xlrd.open_workbook(str(path))
    ws = wb.sheet_by_index(0)
    headers = ws.row_values(0)
    records = []
    for r in range(1, ws.nrows):
        record = dict(zip(headers, ws.row_values(r)))
        if "comment_id" in record and "doc_id" not in record:
            record["doc_id"] = record["comment_id"]
        if not record.get("title"):
            record["title"] = str(record.get("content", ""))[:30]
        records.append(record)
    return records


# ── comment sentiment ─────────────────────────────────────────────────────────

def _sentiment_from_comments(comment_docs, method: str = "auto") -> dict[str, float]:
    """Sentiment distribution computed from comment documents.

    method: "auto" — comment→bert, article→dict（按 text_type 自动路由）
            "bert" — pretrained RoBERTa (uer/roberta-base-finetuned-jd-binary-chinese)
            "dict" — lexicon-based (no model needed)
            "ml"   — TF-IDF + LogisticRegression (trained on hotel reviews)
    """
    counts = {"positive": 0, "negative": 0, "neutral": 0}
    _ml_available = True
    for doc in comment_docs:
        text = doc.title + " " + doc.content
        effective = method
        if method == "auto":
            effective = "bert" if doc.text_type == "comment" else "dict"

        if effective == "bert":
            label = predict_bert_sentiment(text)
        elif effective == "dict":
            label, _ = classify_sentiment(tokenize(text))
        else:  # ml with fallback
            if _ml_available:
                try:
                    label = predict_sentiment(text, doc.text_type)
                except FileNotFoundError:
                    _ml_available = False
                    label, _ = classify_sentiment(tokenize(text))
            else:
                label, _ = classify_sentiment(tokenize(text))
        counts[label] += 1
    total = sum(counts.values()) or 1
    return {k: round(v / total, 3) for k, v in counts.items()}


# ── topic relevance filtering ────────────────────────────────────────────────

def _topic_relevance_scores(
    centroids: list[dict[str, float]],
    idf: dict[str, float],
    topic_keywords: list[str],
) -> list[float]:
    """Cosine similarity of each cluster centroid to a TF-IDF seed vector built from
    topic_keywords.  Uses the same IDF table as the clustering step so the vector space
    is consistent.  Score 0.0 means the cluster shares no vocabulary with the topic."""
    topic_tokens = [t for kw in topic_keywords for t in tokenize(kw)]
    topic_vec = tfidf_vector(topic_tokens, idf)
    return [cosine_similarity(centroid, topic_vec) for centroid in centroids]


# ── comment assignment ────────────────────────────────────────────────────────

def _assign_comments(comment_docs, centroids, idf) -> list[int]:
    """Nearest-centroid assignment for comment documents using the post-corpus IDF."""
    assignments = []
    for doc in comment_docs:
        tokens = tokenize(doc.title + " " + doc.content)
        vec = tfidf_vector(tokens, idf)
        best_id, best_score = 0, -1.0
        for cluster_id, centroid in enumerate(centroids):
            score = cosine_similarity(vec, centroid)
            if score > best_score:
                best_id, best_score = cluster_id, score
        assignments.append(best_id)
    return assignments


# ── main ──────────────────────────────────────────────────────────────────────

def two_stage_pipeline(
    post_records: list[dict],
    comment_records: list[dict],
    post_threshold: float = 0.04,
    dedup_threshold: int = 3,
    topic_keywords: list[str] | None = None,
    relevance_threshold: float = 0.02,
    sentiment_method: str = "ml",
) -> tuple[list[dict], list[dict]]:
    # Stage 1: cluster posts
    post_docs = [normalize_document(r) for r in post_records]
    assignments, centroids, idf = cluster_with_centroids(post_docs, threshold=post_threshold)

    posts_by_cluster: dict[int, list[dict]] = defaultdict(list)
    for raw, cluster_id in zip(post_records, assignments):
        posts_by_cluster[cluster_id].append({**raw, "event_id": f"cluster-{cluster_id}"})

    # Stage 2: assign comments to nearest post cluster
    comment_docs = [normalize_document(r) for r in comment_records]
    comment_assignments = _assign_comments(comment_docs, centroids, idf)

    comments_by_cluster: dict[int, list] = defaultdict(list)
    for doc, cluster_id in zip(comment_docs, comment_assignments):
        comments_by_cluster[cluster_id].append(doc)

    # Stage 3: analyse each cluster
    reports = []
    for cluster_id, raws in posts_by_cluster.items():
        report = analyze_event(raws, dedup_threshold=dedup_threshold)

        assigned_comments = comments_by_cluster.get(cluster_id, [])
        if assigned_comments:
            report["sentiment"] = _sentiment_from_comments(assigned_comments, method=sentiment_method)
            report["comment_count"] = len(assigned_comments)
        else:
            report["comment_count"] = 0

        reports.append(report)

    # Stage 3: topic relevance filtering
    if topic_keywords:
        relevance = _topic_relevance_scores(centroids, idf, topic_keywords)
        kept, dropped = [], []
        for report in reports:
            cluster_id = int(report["event_id"].replace("cluster-", ""))
            score = relevance[cluster_id]
            report["relevance_score"] = round(score, 4)
            (kept if score >= relevance_threshold else dropped).append(report)
        reports = kept
    else:
        dropped = []

    reports.sort(key=lambda r: r["heat"], reverse=True)
    return reports, dropped


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("files", nargs="+", type=Path, help=".xls files; posts first, then comments")
    parser.add_argument("--output", type=Path, default=Path("reports/pipeline_report.json"))
    parser.add_argument("--post-threshold", type=float, default=0.04)
    parser.add_argument("--dedup-threshold", type=int, default=3)
    parser.add_argument("--top", type=int, default=20, help="print only the top N clusters")
    parser.add_argument("--topic", type=str, default=None, help="space-separated topic keywords for relevance filtering")
    parser.add_argument("--relevance-threshold", type=float, default=0.035, help="min centroid-topic similarity to keep a cluster (default 0.035)")
    parser.add_argument("--sentiment-method", choices=SENTIMENT_METHODS, default="auto",
                        help="sentiment backend: auto (comment→bert, article→dict), bert, ml, dict")
    parser.add_argument("--compare", action="store_true",
                        help="run dict AND bert and print a side-by-side comparison (ignores --sentiment-method)")
    args = parser.parse_args()

    post_records: list[dict] = []
    comment_records: list[dict] = []

    for path in args.files:
        records = _read_xls(path)
        headers = set(xlrd.open_workbook(str(path)).sheet_by_index(0).row_values(0))
        if "comment_id" in headers:
            comment_records.extend(records)
            print(f"  评论: {len(records)} 条  ← {path.name}")
        else:
            post_records.extend(records)
            print(f"  帖子: {len(records)} 条  ← {path.name}")

    topic_keywords = args.topic.split() if args.topic else None

    print(f"\nStage 1: 对 {len(post_records)} 条帖子做事件聚类...")
    if topic_keywords:
        print(f"话题关键词: {topic_keywords}  相关度阈值: {args.relevance_threshold}")

    # shared kwargs for both runs
    pipeline_kwargs = dict(
        post_threshold=args.post_threshold,
        dedup_threshold=args.dedup_threshold,
        topic_keywords=topic_keywords,
        relevance_threshold=args.relevance_threshold,
    )

    if args.compare:
        # run dict and bert, print side-by-side comparison
        print("\n[1/2] 词典法 (dict)…")
        reports_dict, dropped = two_stage_pipeline(post_records, comment_records, sentiment_method="dict", **pipeline_kwargs)
        print("[2/2] BERT (uer/roberta-base-finetuned-jd-binary-chinese)…")
        reports_bert, _ = two_stage_pipeline(post_records, comment_records, sentiment_method="bert", **pipeline_kwargs)

        if dropped:
            print(f"\n过滤掉 {len(dropped)} 个不相关簇 (两次相同):")
            for r in sorted(dropped, key=lambda x: x.get("relevance_score", 0)):
                print(f"  [{r['event_id']}] 相似度={r.get('relevance_score',0):.4f}  {r['title'][:35]}")

        bert_by_id = {r["event_id"]: r for r in reports_bert}
        print(f"\n{'簇':10} {'帖子':>4} {'评论':>4}  {'--- 词典法 ---':^32}  {'--- BERT ---':^32}  标题")
        print("-" * 120)
        for r in reports_dict[:args.top]:
            eid = r["event_id"]
            s_dict = r["sentiment"]
            s_bert = bert_by_id.get(eid, {}).get("sentiment", {})
            print(
                f"{eid:10} {r['report_count']:>4} {r['comment_count']:>4}  "
                f"pos={s_dict.get('positive',0):.2f} neg={s_dict.get('negative',0):.2f} neu={s_dict.get('neutral',0):.2f}  "
                f"pos={s_bert.get('positive',0):.2f} neg={s_bert.get('negative',0):.2f} neu={s_bert.get('neutral',0):.2f}  "
                f"{r['title'][:30]}"
            )

        # save bert version as the main report
        reports = reports_bert
    else:
        reports, dropped = two_stage_pipeline(
            post_records, comment_records,
            sentiment_method=args.sentiment_method,
            **pipeline_kwargs,
        )
        if dropped:
            print(f"\n过滤掉 {len(dropped)} 个不相关簇:")
            for r in sorted(dropped, key=lambda x: x.get("relevance_score", 0)):
                print(f"  [{r['event_id']}] 相似度={r.get('relevance_score',0):.4f}  {r['title'][:35]}")
        print(f"\n发现 {len(reports)} 个事件簇，Top {args.top}  [方法: {args.sentiment_method}]\n")
        for r in reports[:args.top]:
            print(
                f"  [{r['event_id']}] {r['title'][:28]}…\n"
                f"    帖子{r['report_count']}条  评论{r['comment_count']}条  热度{r['heat']}  阶段{r.get('stage','?')}\n"
                f"    情感{r['sentiment']}  关键词: {[kw['word'] for kw in r['keywords'][:5]]}\n"
            )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as f:
        json.dump(reports, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n完整报告 → {args.output}")


if __name__ == "__main__":
    main()
