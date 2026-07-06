"""End-to-end pipeline: (discover events) -> preprocess -> dedup -> nlp -> hotness -> sentiment.

`run_pipeline` takes `event_id` as given on each raw record (e.g. from `discover_events`,
or pre-tagged crawler output) and produces a per-event report ready for the dashboard.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any

from .cluster import compute_hotness, single_pass_cluster
from .nlp import extract_keywords, tokenize
from .preprocess import is_near_duplicate, normalize_document, simhash
from .schema import Document
from .sentiment import classify_sentiment


def discover_events(raw_records: list[dict[str, Any]], threshold: float = 0.04) -> list[dict[str, Any]]:
    """Cluster unlabeled raw records into events (Single-Pass, see cluster.single_pass) and tag
    each with a discovered `event_id`, overwriting any existing one — the M2 replacement for
    relying on a crawler (or test fixture) to pre-assign event_id."""
    docs = [normalize_document(raw) for raw in raw_records]
    cluster_ids = single_pass_cluster(docs, threshold=threshold)
    return [{**raw, "event_id": f"cluster-{cluster_id}"} for raw, cluster_id in zip(raw_records, cluster_ids)]


def _drop_near_duplicates(docs: list[Document], dedup_threshold: int) -> tuple[list[Document], int]:
    kept: list[Document] = []
    kept_fingerprints: list[int] = []
    duplicate_count = 0
    for doc in docs:
        fingerprint = simhash(doc.title + doc.content)
        if any(is_near_duplicate(fingerprint, existing, dedup_threshold) for existing in kept_fingerprints):
            duplicate_count += 1
            continue
        kept.append(doc)
        kept_fingerprints.append(fingerprint)
    return kept, duplicate_count


def _event_keywords(corpus_tokens: list[list[str]], top_k: int) -> list[str]:
    merged_scores: dict[str, float] = defaultdict(float)
    for doc_keywords in extract_keywords(corpus_tokens, top_k=top_k):
        for term, score in doc_keywords:
            merged_scores[term] += score
    ranked = sorted(merged_scores.items(), key=lambda kv: kv[1], reverse=True)
    return [term for term, _ in ranked[:top_k]]


def _sentiment_distribution(corpus_tokens: list[list[str]]) -> dict[str, float]:
    counts = {"positive": 0, "negative": 0, "neutral": 0}
    for tokens in corpus_tokens:
        label, _ = classify_sentiment(tokens)
        counts[label] += 1
    total = sum(counts.values()) or 1
    return {label: round(count / total, 3) for label, count in counts.items()}


def analyze_event(
    raws: list[dict[str, Any]],
    now: datetime | None = None,
    top_k_keywords: int = 8,
    dedup_threshold: int = 3,
) -> dict[str, Any]:
    """Run one event's raw records through preprocess -> dedup -> nlp -> hotness -> sentiment.

    `dedup_threshold` (max Hamming distance treated as a duplicate) should scale with report
    length: 3 suits full articles; short social posts need a looser threshold since a few
    edited words are a much bigger fraction of a short text's shingles (see preprocess.dedup).
    """
    docs = [normalize_document(raw) for raw in raws]
    docs, duplicate_count = _drop_near_duplicates(docs, dedup_threshold)
    corpus_tokens = [tokenize(doc.title + " " + doc.content) for doc in docs]

    return {
        "event_id": raws[0]["event_id"] if raws else None,
        "title": docs[0].title if docs else "",
        "report_count": len(docs),
        "duplicate_count": duplicate_count,
        "hotness": round(compute_hotness([doc.publish_time for doc in docs], now=now), 3),
        "sentiment_distribution": _sentiment_distribution(corpus_tokens),
        "top_keywords": _event_keywords(corpus_tokens, top_k_keywords),
        "sources": sorted({doc.source for doc in docs}),
        "platforms": sorted({doc.platform for doc in docs}),
        "time_range": [
            min(doc.publish_time for doc in docs).isoformat(),
            max(doc.publish_time for doc in docs).isoformat(),
        ] if docs else None,
    }


def run_pipeline(
    raw_records: list[dict[str, Any]],
    now: datetime | None = None,
    dedup_threshold: int = 3,
) -> list[dict[str, Any]]:
    """Group raw records by their (pre-assigned) event_id and produce a per-event report,
    ranked by hotness — the shape the event dashboard/detail report will consume."""
    by_event: dict[str, list[dict]] = defaultdict(list)
    for raw in raw_records:
        by_event[raw["event_id"]].append(raw)

    reports = [analyze_event(raws, now=now, dedup_threshold=dedup_threshold) for raws in by_event.values()]
    reports.sort(key=lambda r: r["hotness"], reverse=True)
    return reports
