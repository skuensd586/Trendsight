"""Lexicon-based sentiment classification: the M1 fallback ahead of the BERT classifier in M2."""
from __future__ import annotations

from .lexicon import NEGATIVE_WORDS, POSITIVE_WORDS


def classify_sentiment(tokens: list[str]) -> tuple[str, float]:
    """Classify tokenized text as positive/negative/neutral.

    Score is (pos_count - neg_count) / (pos_count + neg_count), in [-1, 1];
    used as the confidence value. Ties (including no sentiment words) are neutral.
    """
    pos_count = sum(1 for t in tokens if t in POSITIVE_WORDS)
    neg_count = sum(1 for t in tokens if t in NEGATIVE_WORDS)
    total = pos_count + neg_count

    if total == 0:
        return "neutral", 0.0

    score = (pos_count - neg_count) / total
    if score > 0:
        return "positive", score
    if score < 0:
        return "negative", score
    return "neutral", 0.0
