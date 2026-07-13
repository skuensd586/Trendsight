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

from .authenticity import compute_authenticity
from .cluster import compute_hotness, single_pass_cluster
from .extract import extract_event_details
from .propagation import detect_propagation
from .nlp import extract_keywords, tokenize
from .preprocess import is_near_duplicate, normalize_document, simhash
from .schema import Document
from .sentiment import classify_sentiment, predict_sentiment
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


def _sentiment_distribution(docs: list[Document], corpus_tokens: list[list[str]]) -> dict[str, float]:
    """Classify each document's sentiment and return the positive/neutral/negative ratio.

    Routing strategy by text_type:
      article — lexicon (dict): news articles are formal/neutral; the comment-trained
                ML model is systematically biased toward "positive" on formal prose.
      comment — ML model with fallback to dict: colloquial text matches the training
                domain better; if no model file exists, dict is the safe default.
    """
    counts = {"positive": 0, "negative": 0, "neutral": 0}
    use_ml = True
    for doc, tokens in zip(docs, corpus_tokens):
        if doc.text_type == "article":
            label, _ = classify_sentiment(tokens)
        elif use_ml:
            try:
                label = predict_sentiment(doc.title + " " + doc.content, doc.text_type)
            except FileNotFoundError:
                use_ml = False
                label, _ = classify_sentiment(tokens)
        else:
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


_RISK_THRESHOLDS = [("high", 40), ("mid_high", 15), ("mid", 5), ("low", 0)]


def _risk_level(heat: float, sentiment: dict[str, float]) -> str:
    """Rule-based risk level: heat amplified by negative-sentiment ratio.

    Tiers (high/mid_high/mid/low) map to the risk_level filter in
    api-design/events.json's /api/events/hot endpoint.  Thresholds are heuristic
    and should be re-calibrated once real labelled data is available.
    """
    score = heat * (1.0 + sentiment.get("negative", 0.0) * 2.0)
    for level, threshold in _RISK_THRESHOLDS:
        if score >= threshold:
            return level
    return "low"


def _recent_window(publish_times: list[datetime], window_days: float) -> list[datetime]:
    """Trim archive-dated outliers: keep only reports within `window_days` of the most
    recent one.  Crawler search results sometimes include years-old articles that merely
    match the keyword; without this, `daily_report_counts` fills the whole span day-by-day
    and the trend chart stretches across years of empty days (and time_start is wrong)."""
    if not publish_times:
        return publish_times
    cutoff = max(publish_times) - timedelta(days=window_days)
    return [t for t in publish_times if t >= cutoff]


def _event_time(daily_trend: list[dict[str, Any]], time_start: str) -> str:
    """Representative timestamp for the event: noon on the peak-activity day."""
    if not daily_trend:
        return time_start
    peak_day = max(daily_trend, key=lambda d: d["count"])
    return peak_day["date"] + "T12:00:00"


def _lifecycle(daily_trend: list[dict[str, Any]], publish_times: list[datetime], now: datetime | None, bucket_hours: float) -> dict[str, Any]:
    """Return a `lifecycle` object (api-design/prediction.json shape) plus `key_timepoints`.

    `lifecycle` contains: stage / confidence / stage_probability / future_trend / analysis.
    `key_timepoints` is an extra field not yet in the API contract, kept for the frontend
    trend chart's "关键时间节点" markers.
    """
    fine_counts = bucket_report_counts(publish_times, bucket_hours=bucket_hours, now=now)
    fine_bucket_starts = [min(publish_times) + timedelta(hours=bucket_hours * i) for i in range(len(fine_counts))]

    daily_counts = [day["count"] for day in daily_trend]
    last_day = datetime.fromisoformat(daily_trend[-1]["date"])

    prediction = predict_lifecycle(fine_counts)
    prediction["future_trend"] = forecast_future_trend(daily_counts, last_day, bucket_hours=24.0)
    key_timepoints = [fine_bucket_starts[i].isoformat() for i in detect_changepoints(fine_counts)]
    return prediction, key_timepoints


def analyze_event(
    raws: list[dict[str, Any]],
    now: datetime | None = None,
    top_k_keywords: int = 8,
    dedup_threshold: int = 3,
    lifecycle_bucket_hours: float = 6.0,
    timeline_window_days: float = 45.0,
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

    # Timeline fields (trend / lifecycle / time span / propagation) use only the recent
    # activity window; heat/keywords/sentiment/authenticity stay on the full doc set (old
    # posts already contribute ~0 to the time-decayed heat).
    timeline_times = _recent_window(publish_times, timeline_window_days)
    cutoff = max(publish_times) - timedelta(days=timeline_window_days) if publish_times else None
    timeline_docs = [d for d in docs if cutoff is None or d.publish_time >= cutoff]

    sentiment = _sentiment_distribution(docs, corpus_tokens)
    time_start = min(timeline_times).isoformat() if timeline_times else None
    time_end = max(timeline_times).isoformat() if timeline_times else None
    heat = round(compute_hotness(publish_times, now=now), 3)
    dup_rate = duplicate_count / max(len(docs) + duplicate_count, 1)

    keywords = _keywords(corpus_tokens, top_k_keywords)
    details = extract_event_details(docs, keywords)

    report: dict[str, Any] = {
        "event_id": raws[0]["event_id"] if raws else None,
        "title": docs[0].title if docs else "",
        "report_count": len(docs),
        "duplicate_count": duplicate_count,
        "heat": heat,
        "risk_level": _risk_level(heat, sentiment),
        "sentiment": sentiment,
        "keywords": keywords,
        "platform_distribution": _platform_distribution(docs),
        "sources": sorted({doc.source for doc in docs}),
        "time_start": time_start,
        "time_end": time_end,
        "authenticity": compute_authenticity(docs, duplicate_rate=dup_rate),
        # Event-detail fields for the frontend detail page (see algo/extract.py).
        "summary": details["summary"],
        "cause": details["cause"],
        "location": details["location"],
        "people": details["people"],
        # Key-node propagation analysis (see algo/propagation.py).
        "propagation": detect_propagation(timeline_docs),
    }
    if timeline_times:
        daily_trend = daily_report_counts(timeline_times)
        report["event_time"] = _event_time(daily_trend, time_start)
        report["trend"] = daily_trend
        lifecycle, key_timepoints = _lifecycle(daily_trend, timeline_times, now, lifecycle_bucket_hours)
        report["stage"] = lifecycle["stage"]       # top-level for /hot list view
        report["lifecycle"] = lifecycle            # nested for /events/{id} detail view
        report["key_timepoints"] = key_timepoints  # extra, not in API contract yet
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
