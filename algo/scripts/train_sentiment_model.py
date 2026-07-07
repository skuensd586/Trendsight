"""Train a sentiment model for a given text_type from labeled (label, text) CSV/TSV data.

Generic over text_type on purpose: today there's only a Weibo-style comment dataset, so
`--text-type comment` is the only run that makes sense, but the script itself doesn't know
or care what "comment" means -- point it at a news-article labeled dataset later and
`--text-type article` trains that model with no code changes here.

Usage:
    python scripts/train_sentiment_model.py --text-type comment --data path/to/labeled.csv
"""
from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from sklearn.model_selection import train_test_split
from sklearn.naive_bayes import MultinomialNB

from algo.nlp.tokenize import tokenize
from algo.sentiment.labeled_data import load_labeled_csv
from algo.sentiment.ml_sentiment import DEFAULT_CONFIDENCE_THRESHOLD, MODEL_DIR, REPORT_PATH, label_from_proba

_CANDIDATE_MODELS = {
    "MultinomialNB": lambda: MultinomialNB(),
    "LogisticRegression": lambda: LogisticRegression(max_iter=1000),
}


def _build_vectorizer() -> TfidfVectorizer:
    # tokenizer=tokenize reuses the exact same segmentation as the rest of the pipeline
    # (nlp.tokenize), so training and runtime never disagree on how text gets split.
    return TfidfVectorizer(tokenizer=tokenize, token_pattern=None, lowercase=False)


def train_and_evaluate(
    texts: list[str],
    labels: list[str],
    confidence_threshold: float,
    test_size: float,
    random_seed: int,
) -> tuple[TfidfVectorizer, dict[str, dict]]:
    """Fit each candidate classifier on a train/test split and score it on the held-out set.

    Returns (vectorizer, {model_name: {"classifier", "accuracy", "report", "confusion_matrix"}}).
    """
    x_train, x_test, y_train, y_test = train_test_split(
        texts, labels, test_size=test_size, random_state=random_seed, stratify=labels
    )

    vectorizer = _build_vectorizer()
    x_train_vec = vectorizer.fit_transform(x_train)
    x_test_vec = vectorizer.transform(x_test)

    results: dict[str, dict] = {}
    for name, make_classifier in _CANDIDATE_MODELS.items():
        classifier = make_classifier()
        classifier.fit(x_train_vec, y_train)

        proba_matrix = classifier.predict_proba(x_test_vec)
        y_pred = [
            label_from_proba(dict(zip(classifier.classes_, proba)), confidence_threshold)
            for proba in proba_matrix
        ]

        results[name] = {
            "classifier": classifier,
            "accuracy": accuracy_score(y_test, y_pred),
            "report": classification_report(y_test, y_pred, zero_division=0),
            "confusion_matrix": confusion_matrix(y_test, y_pred, labels=sorted(set(y_test) | set(y_pred))),
            "confusion_matrix_labels": sorted(set(y_test) | set(y_pred)),
        }

    return vectorizer, results


def save_model(vectorizer: TfidfVectorizer, classifier, text_type: str, model_dir: Path) -> Path:
    model_dir.mkdir(parents=True, exist_ok=True)
    path = model_dir / f"sentiment_model_{text_type}_{date.today().strftime('%Y%m%d')}.joblib"
    joblib.dump(
        {"vectorizer": vectorizer, "classifier": classifier, "text_type": text_type, "trained_at": date.today().isoformat()},
        path,
    )
    return path


def append_report(
    report_path: Path,
    text_type: str,
    data_path: Path,
    best_name: str,
    results: dict[str, dict],
    confidence_threshold: float,
    model_path: Path,
) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"## {date.today().isoformat()} 训练结果 -- text_type={text_type}",
        "",
        f"- 训练数据: `{data_path}`",
        f"- 置信度阈值 (confidence_threshold): {confidence_threshold}",
        f"- 选中模型: **{best_name}**（held-out 测试集 accuracy 最高）",
        f"- 保存路径: `{model_path}`",
        "",
    ]
    for name, result in results.items():
        lines += [
            f"### {name}",
            "",
            f"accuracy: {result['accuracy']:.4f}",
            "",
            "```",
            result["report"].rstrip(),
            "```",
            "",
            f"混淆矩阵（标签顺序 {result['confusion_matrix_labels']}）:",
            "",
            "```",
            str(result["confusion_matrix"]),
            "```",
            "",
        ]
    with report_path.open("a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n---\n\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--text-type", required=True, help="label for the model being trained, e.g. comment/article")
    parser.add_argument("--data", required=True, type=Path, help="labeled CSV/TSV path (columns: label, text)")
    parser.add_argument("--confidence-threshold", type=float, default=DEFAULT_CONFIDENCE_THRESHOLD)
    parser.add_argument("--test-size", type=float, default=0.2)
    parser.add_argument("--random-seed", type=int, default=42)
    parser.add_argument("--model-dir", type=Path, default=MODEL_DIR)
    parser.add_argument("--report", type=Path, default=REPORT_PATH)
    args = parser.parse_args()

    texts, labels = load_labeled_csv(args.data)
    if "neutral" in labels:
        raise ValueError(
            "training data must be binary positive/negative only (neutral is a runtime "
            "confidence-threshold decision, not a trained class) -- found 'neutral' rows in "
            f"{args.data}"
        )

    vectorizer, results = train_and_evaluate(texts, labels, args.confidence_threshold, args.test_size, args.random_seed)
    best_name = max(results, key=lambda name: results[name]["accuracy"])

    model_path = save_model(vectorizer, results[best_name]["classifier"], args.text_type, args.model_dir)
    append_report(args.report, args.text_type, args.data, best_name, results, args.confidence_threshold, model_path)

    for name, result in results.items():
        marker = " (selected)" if name == best_name else ""
        print(f"{name}{marker}: accuracy={result['accuracy']:.4f}")
    print(f"saved model: {model_path}")
    print(f"report appended: {args.report}")


if __name__ == "__main__":
    main()
