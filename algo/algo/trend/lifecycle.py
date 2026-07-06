"""Rule-based lifecycle stage classification over a bucketed report-count time series.

Stages per docs/algorithm-plan.md section 5: 潜伏期 (latent, low & flat), 成长期 (growing,
accelerating), 高潮期 (peak, near-max and flattening), 衰退期 (declining, well past peak).
"""
from __future__ import annotations

LATENT = "潜伏期"
GROWING = "成长期"
PEAK = "高潮期"
DECLINING = "衰退期"


def classify_lifecycle_stage(
    counts: list[int],
    quiet_threshold: int = 1,
    decline_ratio: float = 0.5,
) -> str:
    """Classify the current stage from bucketed report counts (oldest bucket first).

    `quiet_threshold`: below this peak volume, treat the event as still latent regardless
    of shape. `decline_ratio`: once past the peak bucket, the most recent bucket falling to
    at or below this fraction of the peak counts as having declined.
    """
    if not counts or max(counts) <= quiet_threshold:
        return LATENT

    peak = max(counts)
    peak_index = max(range(len(counts)), key=lambda i: counts[i])
    latest = counts[-1]
    is_past_peak = peak_index < len(counts) - 1

    if is_past_peak:
        if latest <= peak * decline_ratio:
            return DECLINING
        return PEAK  # past the peak bucket but still near it (plateau)

    if len(counts) >= 2 and counts[-1] > counts[-2]:
        return GROWING
    return PEAK  # the most recent bucket *is* the peak
