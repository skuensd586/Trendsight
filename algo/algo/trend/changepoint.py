"""Changepoint detection over a bucketed report-count series, for flagging the "关键时间节点"
markers on the front-end trend chart.

Simplified stand-in for a full PELT pass (docs/algorithm-plan.md section 5 lists `ruptures`):
flags a bucket-to-bucket jump as a changepoint when it's an outlier relative to the series'
own typical jump size (a z-score on first differences). Swap for `ruptures.Pelt` once that
dependency is available; this needs no extra libraries and is enough to prove the shape works.
"""
from __future__ import annotations

import statistics


def detect_changepoints(counts: list[int], z_threshold: float = 1.5) -> list[int]:
    """Return indices into `counts` where the jump from the previous bucket is an outlier."""
    if len(counts) < 3:
        return []

    diffs = [counts[i] - counts[i - 1] for i in range(1, len(counts))]
    mean = statistics.mean(diffs)
    stdev = statistics.pstdev(diffs)
    if stdev == 0:
        return []

    return [i + 1 for i, diff in enumerate(diffs) if abs((diff - mean) / stdev) >= z_threshold]
