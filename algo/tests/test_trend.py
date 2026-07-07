from datetime import datetime, timedelta

from algo.trend import (
    bucket_report_counts,
    classify_lifecycle_stage,
    daily_report_counts,
    detect_changepoints,
    forecast_future_trend,
    predict_lifecycle,
)


def test_bucket_report_counts_groups_by_fixed_width_window():
    start = datetime(2026, 1, 1, 0, 0, 0)
    times = [start, start + timedelta(hours=1), start + timedelta(hours=7)]
    counts = bucket_report_counts(times, bucket_hours=6.0)
    assert counts == [2, 1]


def test_bucket_report_counts_extends_to_now_even_with_no_recent_reports():
    start = datetime(2026, 1, 1, 0, 0, 0)
    now = start + timedelta(hours=18)
    counts = bucket_report_counts([start], bucket_hours=6.0, now=now)
    assert counts == [1, 0, 0, 0]


def test_daily_report_counts_fills_gap_days_with_zero():
    times = [datetime(2026, 1, 1, 9), datetime(2026, 1, 1, 14), datetime(2026, 1, 3, 10)]
    assert daily_report_counts(times) == [
        {"date": "2026-01-01", "count": 2},
        {"date": "2026-01-02", "count": 0},
        {"date": "2026-01-03", "count": 1},
    ]


def test_lifecycle_stage_latent_when_volume_never_rises():
    assert classify_lifecycle_stage([0, 1, 0, 0]) == "latent"


def test_lifecycle_stage_growing_when_still_accelerating_at_the_latest_bucket():
    assert classify_lifecycle_stage([1, 2, 4, 8]) == "growth"


def test_lifecycle_stage_peak_when_plateaued_near_the_max():
    assert classify_lifecycle_stage([1, 3, 5, 5]) == "peak"


def test_lifecycle_stage_declining_once_well_past_the_peak():
    assert classify_lifecycle_stage([5, 3, 1]) == "decline"


def test_predict_lifecycle_shapes_stage_confidence_and_probability_like_the_api():
    result = predict_lifecycle([5, 3, 1])
    assert result["stage"] == "decline"
    assert 0 < result["confidence"] <= 0.9
    probs = result["stage_probability"]
    assert set(probs) == {"latent", "growth", "peak", "decline"}
    assert abs(sum(probs.values()) - 1.0) < 1e-9
    assert probs["decline"] == max(probs.values())
    assert result["analysis"]


def test_forecast_future_trend_extrapolates_recent_slope():
    start = datetime(2026, 1, 1, 0, 0, 0)
    forecast = forecast_future_trend([1, 2, 4], last_bucket_start=start, bucket_hours=24.0, horizon=2)
    assert len(forecast) == 2
    assert forecast[0]["predict_count"] > 4  # still rising
    assert forecast[1]["predict_count"] > forecast[0]["predict_count"]


def test_forecast_future_trend_never_predicts_negative_counts():
    start = datetime(2026, 1, 1, 0, 0, 0)
    forecast = forecast_future_trend([5, 1, 0], last_bucket_start=start, bucket_hours=24.0, horizon=3)
    assert all(point["predict_count"] >= 0 for point in forecast)


def test_detect_changepoints_flags_the_sharp_drop_after_a_burst():
    # burst of 4, then a sharp drop, then a small steady trickle
    assert detect_changepoints([4, 1, 0, 1, 1, 0]) == [1]


def test_detect_changepoints_empty_for_short_or_flat_series():
    assert detect_changepoints([1, 1]) == []
    assert detect_changepoints([3, 3, 3, 3]) == []
