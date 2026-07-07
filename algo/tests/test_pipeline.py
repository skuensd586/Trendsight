import re
from datetime import datetime

from algo.pipeline import discover_events, run_pipeline
from algo.sample_data import RAW_RECORDS

_HAS_WORD_CHAR_RE = re.compile(r"[一-鿿\w]")

NOW = datetime(2026, 7, 6, 18, 0, 0)
# Sample posts are single short paragraphs, so their near-duplicate pairs land farther
# apart in SimHash distance than the module's article-length default of 3 (see
# preprocess.dedup); this was picked by inspecting this sample set's pairwise distances.
DEDUP_THRESHOLD = 20


def _report_for(reports: list[dict], event_id: str) -> dict:
    return next(r for r in reports if r["event_id"] == event_id)


def test_pipeline_runs_end_to_end_over_sample_data():
    reports = run_pipeline(RAW_RECORDS, now=NOW, dedup_threshold=DEDUP_THRESHOLD)
    assert {r["event_id"] for r in reports} == {"evt-flood", "evt-phone", "evt-canteen"}


def test_dedup_collapses_the_planted_near_duplicate_wire_reprints():
    reports = run_pipeline(RAW_RECORDS, now=NOW, dedup_threshold=DEDUP_THRESHOLD)
    assert _report_for(reports, "evt-flood")["duplicate_count"] == 1
    assert _report_for(reports, "evt-phone")["duplicate_count"] == 1
    assert _report_for(reports, "evt-canteen")["duplicate_count"] == 0


def test_older_event_scores_lower_heat_despite_similar_report_count():
    reports = run_pipeline(RAW_RECORDS, now=NOW, dedup_threshold=DEDUP_THRESHOLD)
    flood = _report_for(reports, "evt-flood")
    canteen = _report_for(reports, "evt-canteen")
    assert flood["heat"] > canteen["heat"]


def test_sentiment_matches_the_planted_tone_per_event():
    reports = run_pipeline(RAW_RECORDS, now=NOW, dedup_threshold=DEDUP_THRESHOLD)
    phone = _report_for(reports, "evt-phone")["sentiment"]
    canteen = _report_for(reports, "evt-canteen")["sentiment"]
    assert phone["positive"] > phone["negative"]
    assert canteen["negative"] > canteen["positive"]


def test_keywords_are_word_weight_pairs_with_no_punctuation():
    reports = run_pipeline(RAW_RECORDS, now=NOW, dedup_threshold=DEDUP_THRESHOLD)
    for report in reports:
        for keyword in report["keywords"]:
            assert _HAS_WORD_CHAR_RE.search(keyword["word"])
            assert 0 < keyword["weight"] <= 1.0


def test_platform_distribution_ratios_sum_to_one():
    reports = run_pipeline(RAW_RECORDS, now=NOW, dedup_threshold=DEDUP_THRESHOLD)
    for report in reports:
        assert abs(sum(p["ratio"] for p in report["platform_distribution"]) - 1.0) < 1e-9


def test_pipeline_includes_trend_and_lifecycle_fields():
    reports = run_pipeline(RAW_RECORDS, now=NOW, dedup_threshold=DEDUP_THRESHOLD)
    flood = _report_for(reports, "evt-flood")
    assert flood["stage"] == "decline"
    assert flood["key_timepoints"]
    assert flood["future_trend"]
    assert sum(p["count"] for p in flood["trend"]) == flood["report_count"]


def test_pipeline_runs_over_events_discovered_without_ground_truth_labels():
    unlabeled_records = [{k: v for k, v in raw.items() if k != "event_id"} for raw in RAW_RECORDS]

    discovered_records = discover_events(unlabeled_records)
    reports = run_pipeline(discovered_records, now=NOW, dedup_threshold=DEDUP_THRESHOLD)

    # Discovered event_ids are synthetic cluster labels, not the original evt-* names,
    # but every original report must land in exactly one discovered event.
    assert sum(r["report_count"] + r["duplicate_count"] for r in reports) == len(RAW_RECORDS)
