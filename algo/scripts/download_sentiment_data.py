"""Download ChnSentiCorp and export to the CSV format expected by train_sentiment_model.py.

ChnSentiCorp is a public Chinese hotel-review dataset (~12k samples, binary pos/neg),
a standard benchmark for Chinese sentiment classification.  It maps directly to our
comment text_type: short, colloquial, user-generated text — the same domain as Weibo.

The output CSV has two columns: label (positive/negative) and text.  Pass the result
straight to the training script:

    python -m scripts.download_sentiment_data
    python -m scripts.train_sentiment_model --text-type comment --data data/sentiment_comment.csv

No extra dependencies — uses only the stdlib urllib.
"""
from __future__ import annotations

import argparse
import csv
import urllib.request
from pathlib import Path

# ChnSentiCorp hotel reviews hosted on GitHub (SophonPlus/ChineseNlpCorpus).
# Columns: label (0=negative / 1=positive), review (text).
_SOURCE_URL = (
    "https://raw.githubusercontent.com/SophonPlus/ChineseNlpCorpus"
    "/master/datasets/ChnSentiCorp_htl_all/ChnSentiCorp_htl_all.csv"
)


def download_chn_senticorp(output_path: Path) -> None:
    print(f"Downloading ChnSentiCorp from GitHub...")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    tmp = output_path.with_suffix(".tmp")
    try:
        urllib.request.urlretrieve(_SOURCE_URL, tmp)

        total = pos = neg = 0
        with tmp.open(encoding="utf-8", newline="") as src, \
             output_path.open("w", encoding="utf-8", newline="") as dst:
            reader = csv.DictReader(src)
            writer = csv.DictWriter(dst, fieldnames=["label", "text"])
            writer.writeheader()
            for row in reader:
                raw_label = row.get("label", "").strip()
                text = row.get("review", "").strip()
                if not text or raw_label not in ("0", "1"):
                    continue
                label = "positive" if raw_label == "1" else "negative"
                writer.writerow({"label": label, "text": text})
                total += 1
                if label == "positive":
                    pos += 1
                else:
                    neg += 1
    finally:
        tmp.unlink(missing_ok=True)

    print(f"Saved {total} samples ({pos} positive, {neg} negative) -> {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/sentiment_comment.csv"),
        help="output CSV path (default: data/sentiment_comment.csv)",
    )
    args = parser.parse_args()
    download_chn_senticorp(args.output)


if __name__ == "__main__":
    main()
