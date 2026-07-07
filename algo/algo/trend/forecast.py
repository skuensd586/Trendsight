"""Naive future-trend forecast, matching prediction.json's `future_trend` field.

Linear extrapolation of the recent bucket-count slope — a placeholder baseline, not the
ARIMA/Prophet/LSTM model docs/algorithm-plan.md lists for real forecasting; swap this out
once there's enough historical data to justify fitting a real time-series model.
"""
from __future__ import annotations

from datetime import datetime, timedelta


def forecast_future_trend(
    counts: list[int],
    last_bucket_start: datetime,
    bucket_hours: float,
    horizon: int = 3,
) -> list[dict]:
    """Project `horizon` future buckets forward from the recent trend slope.

    `predict_heat` treats each future bucket's own predicted volume as its heat
    contribution (i.e. zero-decay, since decay only applies to *past* reports aging
    relative to "now" — see cluster.hotness); it isn't compounded with the event's
    current accumulated heat.
    """
    if not counts:
        return []

    recent = counts[-3:] if len(counts) >= 3 else counts
    slope = (recent[-1] - recent[0]) / max(len(recent) - 1, 1)
    last_value = counts[-1]

    forecast = []
    for step in range(1, horizon + 1):
        predicted_count = max(0.0, last_value + slope * step)
        bucket_time = last_bucket_start + timedelta(hours=bucket_hours * step)
        forecast.append({
            "date": bucket_time.date().isoformat(),
            "predict_count": round(predicted_count, 1),
            "predict_heat": round(predicted_count, 1),
        })
    return forecast
