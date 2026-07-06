"""Run the M2 clustering step end-to-end: strip the ground-truth event_id off the sample
data (simulating unlabeled crawler output), discover events via Single-Pass clustering,
then run the same M1 report pipeline over the discovered events.

Also prints purity against the sample data's known ground truth, since that's only
available for this fixture — a real deployment has no ground truth to check against.

Usage (from the algo/ directory, with requirements.txt installed):
    python run_demo_cluster.py
"""
from __future__ import annotations

import json
from datetime import datetime

from algo.cluster import purity
from algo.pipeline import discover_events, run_pipeline
from algo.sample_data import RAW_RECORDS

NOW = datetime(2026, 7, 6, 18, 0, 0)


def main() -> None:
    true_event_ids = [raw["event_id"] for raw in RAW_RECORDS]
    unlabeled_records = [{k: v for k, v in raw.items() if k != "event_id"} for raw in RAW_RECORDS]

    discovered_records = discover_events(unlabeled_records)
    discovered_event_ids = [rec["event_id"] for rec in discovered_records]
    print(f"discovered {len(set(discovered_event_ids))} clusters from {len(discovered_records)} unlabeled records")
    print(f"purity vs. ground truth: {purity(discovered_event_ids, true_event_ids):.3f}")

    reports = run_pipeline(discovered_records, now=NOW, dedup_threshold=20)
    print(json.dumps(reports, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
