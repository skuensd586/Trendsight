from datetime import datetime, timedelta

from algo.cluster import compute_hotness


def test_hotness_decays_with_report_age():
    now = datetime(2026, 1, 2, 12, 0, 0)
    recent_reports = [now - timedelta(hours=1)] * 5
    older_reports = [now - timedelta(hours=100)] * 5

    recent_score = compute_hotness(recent_reports, now=now)
    older_score = compute_hotness(older_reports, now=now)

    assert recent_score > 4
    assert recent_score > older_score
    assert compute_hotness([], now=now) == 0.0
