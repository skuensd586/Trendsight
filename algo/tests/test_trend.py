from datetime import datetime, timedelta

from algo.trend import bucket_report_counts, classify_lifecycle_stage, detect_changepoints


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


def test_lifecycle_stage_latent_when_volume_never_rises():
    assert classify_lifecycle_stage([0, 1, 0, 0]) == "潜伏期"


def test_lifecycle_stage_growing_when_still_accelerating_at_the_latest_bucket():
    assert classify_lifecycle_stage([1, 2, 4, 8]) == "成长期"


def test_lifecycle_stage_peak_when_plateaued_near_the_max():
    assert classify_lifecycle_stage([1, 3, 5, 5]) == "高潮期"


def test_lifecycle_stage_declining_once_well_past_the_peak():
    assert classify_lifecycle_stage([5, 3, 1]) == "衰退期"


def test_detect_changepoints_flags_the_sharp_drop_after_a_burst():
    # burst of 4, then a sharp drop, then a small steady trickle
    assert detect_changepoints([4, 1, 0, 1, 1, 0]) == [1]


def test_detect_changepoints_empty_for_short_or_flat_series():
    assert detect_changepoints([1, 1]) == []
    assert detect_changepoints([3, 3, 3, 3]) == []
