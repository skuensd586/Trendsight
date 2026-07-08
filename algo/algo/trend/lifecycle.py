"""Rule-based lifecycle stage classification over a bucketed report-count time series.

Stage codes match api-design/prediction.json's `stage` field: latent (潜伏期, low & flat),
growth (成长期, accelerating), peak (高潮期, near-max and flattening), decline (衰退期,
well past peak).
"""
from __future__ import annotations

LATENT = "latent"
GROWING = "growth"
PEAK = "peak"
DECLINING = "decline"

_STAGE_ORDER = [LATENT, GROWING, PEAK, DECLINING]

_ANALYSIS_TEMPLATES = {
    LATENT: "当前事件报道数量较低且平稳，尚处于潜伏期。",
    GROWING: "当前事件报道数量持续增加，公众关注度快速提升，处于成长期。",
    PEAK: "当前事件报道量已接近峰值，关注度趋于稳定，处于高潮期。",
    DECLINING: "当前事件报道数量持续下降，公众关注度减弱，处于衰退期。",
}


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


def predict_lifecycle(counts: list[int], quiet_threshold: int = 1, decline_ratio: float = 0.5) -> dict:
    """Shape the stage classification to match prediction.json: stage, confidence, and a
    stage_probability distribution, plus a template `analysis` sentence for the report.

    This is a rule-based classifier, not a trained model, so "confidence" and
    "stage_probability" aren't learned probabilities — they're a heuristic: more buckets
    of evidence raises confidence (capped at 0.9), and the remaining probability mass is
    split across the stages adjacent to the classified one in the natural latent -> growth
    -> peak -> decline order, since that's where a rule-based call is most likely to be
    off by one stage. Replace with real posteriors if this becomes a trained classifier.
    """
    stage = classify_lifecycle_stage(counts, quiet_threshold, decline_ratio)
    stage_index = _STAGE_ORDER.index(stage)

    confidence = min(0.5 + 0.1 * len(counts), 0.9)
    stage_probability = {s: 0.0 for s in _STAGE_ORDER}
    stage_probability[stage] = confidence

    neighbor_indices = [i for i in (stage_index - 1, stage_index + 1) if 0 <= i < len(_STAGE_ORDER)]
    remainder = 1.0 - confidence
    if neighbor_indices:
        share = remainder / len(neighbor_indices)
        for i in neighbor_indices:
            stage_probability[_STAGE_ORDER[i]] = share
    else:
        stage_probability[stage] += remainder

    return {
        "stage": stage,
        "confidence": round(confidence, 3),
        "stage_probability": {s: round(p, 3) for s, p in stage_probability.items()},
        "analysis": _ANALYSIS_TEMPLATES[stage],
    }
