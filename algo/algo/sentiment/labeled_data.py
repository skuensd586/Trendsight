"""Shared CSV/TSV loading + label normalization for the sentiment training/validation scripts."""
from __future__ import annotations

import csv
from pathlib import Path

_LABEL_ALIASES = {
    "0": "negative",
    "1": "positive",
    "neg": "negative",
    "pos": "positive",
    "negative": "negative",
    "positive": "positive",
    "neutral": "neutral",
}


def load_labeled_csv(path: Path) -> tuple[list[str], list[str]]:
    """Load a (label, text) CSV/TSV file. Delimiter is inferred from the file extension
    (.tsv -> tab, else comma). Labels are normalized via _LABEL_ALIASES ("0"/"1", "neg"/
    "pos", "negative"/"positive"/"neutral"); anything else raises rather than silently
    mis-training or mis-scoring on a typo'd label.
    """
    delimiter = "\t" if path.suffix.lower() == ".tsv" else ","
    texts: list[str] = []
    labels: list[str] = []
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter=delimiter)
        if reader.fieldnames is None or {"label", "text"} - set(reader.fieldnames):
            raise ValueError(f"{path} must have 'label' and 'text' columns, got {reader.fieldnames}")
        for row in reader:
            raw_label = row["label"].strip().lower()
            if raw_label not in _LABEL_ALIASES:
                raise ValueError(
                    f"unrecognized label {row['label']!r} in {path}; expected one of "
                    f"{sorted(set(_LABEL_ALIASES.values()))}"
                )
            labels.append(_LABEL_ALIASES[raw_label])
            texts.append(row["text"])
    return texts, labels
