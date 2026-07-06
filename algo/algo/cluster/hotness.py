"""M1 hotness scoring: report volume with exponential time decay (full clustering lands in M2)."""
from __future__ import annotations

import math
from datetime import datetime


def compute_hotness(
    publish_times: list[datetime],
    now: datetime | None = None,
    half_life_hours: float = 24.0,
) -> float:
    """Score an event by its reports, weighting older reports less via exponential decay.

    Each report contributes exp(-ln(2) * age_hours / half_life_hours), so a report
    `half_life_hours` old counts for half a fresh report. Score sums to report count
    for a burst of brand-new reports, which keeps it easy to reason about for ranking.
    """
    if not publish_times:
        return 0.0
    reference = now or datetime.utcnow()
    decay_rate = math.log(2) / half_life_hours

    score = 0.0
    for t in publish_times:
        age_hours = max((reference - t).total_seconds() / 3600, 0.0)
        score += math.exp(-decay_rate * age_hours)
    return score
