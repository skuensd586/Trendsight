"""Calendar-day report counts, matching events.json's `/api/events/{event_id}/trend`
response shape: `[{"date": "...", "count": ...}, ...]`.

Separate from `bucket.bucket_report_counts` (fixed-width windows anchored to the first
report, used internally for lifecycle/changepoint detection at finer-than-daily
granularity) — this one aggregates by actual calendar date, filling gaps with zero.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta


def daily_report_counts(publish_times: list[datetime]) -> list[dict]:
    if not publish_times:
        return []

    counts_by_date = Counter(t.date() for t in publish_times)
    start, end = min(counts_by_date), max(counts_by_date)

    result = []
    day = start
    while day <= end:
        result.append({"date": day.isoformat(), "count": counts_by_date.get(day, 0)})
        day += timedelta(days=1)
    return result
