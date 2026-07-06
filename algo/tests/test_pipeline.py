import re
from datetime import datetime

from algo.pipeline import run_pipeline
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


def test_older_event_scores_lower_hotness_despite_similar_report_count():
    reports = run_pipeline(RAW_RECORDS, now=NOW, dedup_threshold=DEDUP_THRESHOLD)
    flood = _report_for(reports, "evt-flood")
    canteen = _report_for(reports, "evt-canteen")
    assert flood["hotness"] > canteen["hotness"]


def test_sentiment_distribution_matches_the_planted_tone_per_event():
    reports = run_pipeline(RAW_RECORDS, now=NOW, dedup_threshold=DEDUP_THRESHOLD)
    phone = _report_for(reports, "evt-phone")["sentiment_distribution"]
    canteen = _report_for(reports, "evt-canteen")["sentiment_distribution"]
    assert phone["positive"] > phone["negative"]
    assert canteen["negative"] > canteen["positive"]


def test_top_keywords_have_no_punctuation_tokens():
    reports = run_pipeline(RAW_RECORDS, now=NOW, dedup_threshold=DEDUP_THRESHOLD)
    for report in reports:
        for keyword in report["top_keywords"]:
            assert _HAS_WORD_CHAR_RE.search(keyword)
