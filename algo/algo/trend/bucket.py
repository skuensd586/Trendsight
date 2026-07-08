"""Bucket report timestamps into a fixed-width time series for trend/lifecycle analysis."""
from __future__ import annotations

from datetime import datetime, timedelta


def bucket_report_counts(
    publish_times: list[datetime],
    bucket_hours: float = 6.0,
    now: datetime | None = None,
) -> list[int]:
    """Count reports per `bucket_hours`-wide time bucket, from the earliest report to `now`
    (or the latest report if `now` isn't given). Index 0 is the earliest bucket."""
    if not publish_times:
        return []

    start = min(publish_times)
    end = now or max(publish_times)
    bucket_size = timedelta(hours=bucket_hours)
    n_buckets = max(int((end - start) / bucket_size) + 1, 1)

    counts = [0] * n_buckets
    for t in publish_times:
        index = min(int((t - start) / bucket_size), n_buckets - 1)
        counts[index] += 1
    return counts
