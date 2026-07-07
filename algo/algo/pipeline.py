"""End-to-end pipeline: (discover events) -> preprocess -> dedup -> nlp -> heat -> sentiment
-> trend/lifecycle.

Output field names follow api-design/events.json and api-design/prediction.json (module B's
contract with the backend): heat, sentiment (positive/neutral/negative), keywords
(word/weight), platform_distribution (platform_name/ratio), trend (date/count), and the
lifecycle block (stage/confidence/stage_probability/future_trend/analysis).

`run_pipeline` takes `event_id` as given on each raw record (e.g. from `discover_events`,
or pre-tagged crawler output) and produces one such report per event.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Any

from .cluster import compute_hotness, single_pass_cluster
from .nlp import extract_keywords, tokenize
from .preprocess import is_near_duplicate, normalize_document, simhash
from .schema import Document
from .sentiment import classify_sentiment
from .trend import (
    bucket_report_counts,
    daily_report_counts,
    detect_changepoints,
    forecast_future_trend,
    predict_lifecycle,
)


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


def _keywords(corpus_tokens: list[list[str]], top_k: int) -> list[dict[str, Any]]:
    """events.json's /keywords response: [{"word": ..., "weight": ...}], weight in [0, 1]
    (word-cloud sizing) — merged per-document TF-IDF scores, normalized by the top score."""
    merged_scores: dict[str, float] = defaultdict(float)
    for doc_keywords in extract_keywords(corpus_tokens, top_k=top_k):
        for term, score in doc_keywords:
            merged_scores[term] += score
    ranked = sorted(merged_scores.items(), key=lambda kv: kv[1], reverse=True)[:top_k]
    max_score = ranked[0][1] if ranked else 1.0
    return [{"word": term, "weight": round(score / max_score, 3)} for term, score in ranked]


def _sentiment_distribution(corpus_tokens: list[list[str]]) -> dict[str, float]:
    counts = {"positive": 0, "negative": 0, "neutral": 0}
    for tokens in corpus_tokens:
        label, _ = classify_sentiment(tokens)
        counts[label] += 1
    total = sum(counts.values()) or 1
    return {label: round(count / total, 3) for label, count in counts.items()}


def _platform_distribution(docs: list[Document]) -> list[dict[str, Any]]:
    """events.json's /platform response: [{"platform_name": ..., "ratio": ...}]."""
    total = len(docs) or 1
    platform_counts = Counter(doc.platform for doc in docs)
    return [
        {"platform_name": platform, "ratio": round(count / total, 3)}
        for platform, count in sorted(platform_counts.items(), key=lambda kv: kv[1], reverse=True)
    ]


def _lifecycle(daily_trend: list[dict[str, Any]], publish_times: list[datetime], now: datetime | None, bucket_hours: float) -> dict[str, Any]:
    # Stage/changepoint detection use finer buckets (more resolution on *when* things
    # shifted); the forecast extrapolates the same daily series shown in `trend`, so its
    # dates line up with the historical chart instead of drifting on a 6h-aligned clock.
    fine_counts = bucket_report_counts(publish_times, bucket_hours=bucket_hours, now=now)
    fine_bucket_starts = [min(publish_times) + timedelta(hours=bucket_hours * i) for i in range(len(fine_counts))]

    daily_counts = [day["count"] for day in daily_trend]
    last_day = datetime.fromisoformat(daily_trend[-1]["date"])

    prediction = predict_lifecycle(fine_counts)
    prediction["future_trend"] = forecast_future_trend(daily_counts, last_day, bucket_hours=24.0)
    # Not yet part of the api-design contract (events.json/prediction.json have no slot for
    # it), but useful for the "关键时间节点" markers the original spec calls for on the trend
    # chart -- kept as an extra field until the backend adds one.
    prediction["key_timepoints"] = [fine_bucket_starts[i].isoformat() for i in detect_changepoints(fine_counts)]
    return prediction


def analyze_event(
    raws: list[dict[str, Any]],
    now: datetime | None = None,
    top_k_keywords: int = 8,
    dedup_threshold: int = 3,
    lifecycle_bucket_hours: float = 6.0,
) -> dict[str, Any]:
    """Run one event's raw records through preprocess -> dedup -> nlp -> heat -> sentiment
    -> trend/lifecycle, shaped to match module B's API contract (see module docstring).

    `dedup_threshold` (max Hamming distance treated as a duplicate) should scale with report
    length: 3 suits full articles; short social posts need a looser threshold since a few
    edited words are a much bigger fraction of a short text's shingles (see preprocess.dedup).
    """
    docs = [normalize_document(raw) for raw in raws]
    docs, duplicate_count = _drop_near_duplicates(docs, dedup_threshold)
    corpus_tokens = [tokenize(doc.title + " " + doc.content) for doc in docs]
    publish_times = [doc.publish_time for doc in docs]

    report = {
        "event_id": raws[0]["event_id"] if raws else None,
        "title": docs[0].title if docs else "",
        "report_count": len(docs),
        "duplicate_count": duplicate_count,
        "heat": round(compute_hotness(publish_times, now=now), 3),
        "sentiment": _sentiment_distribution(corpus_tokens),
        "keywords": _keywords(corpus_tokens, top_k_keywords),
        "platform_distribution": _platform_distribution(docs),
        "sources": sorted({doc.source for doc in docs}),
        "time_range": [min(publish_times).isoformat(), max(publish_times).isoformat()] if docs else None,
    }
    if docs:
        daily_trend = daily_report_counts(publish_times)
        report["trend"] = daily_trend
        report.update(_lifecycle(daily_trend, publish_times, now, lifecycle_bucket_hours))
    return report


def run_pipeline(
    raw_records: list[dict[str, Any]],
    now: datetime | None = None,
    dedup_threshold: int = 3,
) -> list[dict[str, Any]]:
    """Group raw records by their (pre-assigned) event_id and produce a per-event report,
    ranked by heat — the shape the event dashboard/detail report will consume."""
    by_event: dict[str, list[dict]] = defaultdict(list)
    for raw in raw_records:
        by_event[raw["event_id"]].append(raw)

    reports = [analyze_event(raws, now=now, dedup_threshold=dedup_threshold) for raws in by_event.values()]
    reports.sort(key=lambda r: r["heat"], reverse=True)
    return reports
