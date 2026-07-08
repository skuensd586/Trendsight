"""Run the M1 pipeline end-to-end over fake sample data and print the per-event report.

Usage (from the algo/ directory, with requirements.txt installed):
    python run_demo.py
"""
from __future__ import annotations

import json
from datetime import datetime

from algo.pipeline import run_pipeline
from algo.sample_data import RAW_RECORDS

NOW = datetime(2026, 7, 6, 18, 0, 0)


def main() -> None:
    # SimHash's default dedup_threshold=3 is tuned for full-length articles; these
    # sample posts are single short paragraphs, where a few edited words are a much
    # bigger share of the text's shingles, so near-duplicates land farther apart in
    # Hamming distance. 20 was picked by inspecting the pairwise distances in this
    # sample set (see docs/algorithm-plan.md dedup notes) — retune per real corpus.
    reports = run_pipeline(RAW_RECORDS, now=NOW, dedup_threshold=20)
    print(json.dumps(reports, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
