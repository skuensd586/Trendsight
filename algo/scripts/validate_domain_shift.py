"""Evaluate a given text_type's model against any labeled validation set, and record the
accuracy in the shared training report -- a reusable tool for checking domain shift both
directions: "comment model on article text" today, or "article model on comment text"
once an article model exists, with the same script either way.

Usage:
    python scripts/validate_domain_shift.py \\
        --text-type comment --data-text-type article --data path/to/small_labeled.csv
"""
from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from algo.sentiment import ml_sentiment
from algo.sentiment.labeled_data import load_labeled_csv
from algo.sentiment.ml_sentiment import REPORT_PATH, predict_sentiment


def evaluate(model_text_type: str, data_path: Path) -> dict:
    texts, labels = load_labeled_csv(data_path)
    predictions = [predict_sentiment(text, text_type=model_text_type) for text in texts]
    correct = sum(1 for predicted, actual in zip(predictions, labels) if predicted == actual)
    return {
        "accuracy": correct / len(labels) if labels else 0.0,
        "n": len(labels),
        "predictions": predictions,
        "labels": labels,
    }


def append_report(report_path: Path, model_text_type: str, data_text_type: str, data_path: Path, result: dict) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"## {date.today().isoformat()} 领域迁移验证 -- 用 {model_text_type} 模型评估 {data_text_type} 类型文本",
        "",
        f"- 验证数据: `{data_path}`（{result['n']} 条）",
        f"- accuracy: {result['accuracy']:.4f}",
        "",
    ]
    with report_path.open("a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n---\n\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--text-type", required=True, help="which model to evaluate, e.g. comment")
    parser.add_argument("--data-text-type", required=True, help="what kind of text the validation set is, e.g. article")
    parser.add_argument("--data", required=True, type=Path, help="labeled CSV/TSV path (columns: label, text)")
    parser.add_argument("--report", type=Path, default=REPORT_PATH)
    parser.add_argument("--model-dir", type=Path, default=None, help="override where predict_sentiment looks for models")
    args = parser.parse_args()

    if args.model_dir is not None:
        ml_sentiment.MODEL_DIR = args.model_dir

    result = evaluate(args.text_type, args.data)
    append_report(args.report, args.text_type, args.data_text_type, args.data, result)

    print(f"accuracy: {result['accuracy']:.4f} ({result['n']} samples)")
    print(f"report appended: {args.report}")


if __name__ == "__main__":
    main()
