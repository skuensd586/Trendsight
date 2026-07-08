"""Lexicon-based sentiment classification: the M1 fallback ahead of the BERT classifier in M2."""
from __future__ import annotations

from .lexicon import NEGATIVE_WORDS, POSITIVE_WORDS


def _contains_any(token: str, lexicon: set[str]) -> bool:
    # jieba's dictionary segmentation often folds a sentiment root into a longer
    # compound (e.g. "不满" -> "强烈不满", "满意" -> "表示满意"), so an exact-match
    # lookup against the token would miss it; substring containment catches both.
    return any(word in token for word in lexicon)


def classify_sentiment(tokens: list[str]) -> tuple[str, float]:
    """Classify tokenized text as positive/negative/neutral.

    Score is (pos_count - neg_count) / (pos_count + neg_count), in [-1, 1];
    used as the confidence value. Ties (including no sentiment words) are neutral.
    """
    pos_count = sum(1 for t in tokens if _contains_any(t, POSITIVE_WORDS))
    neg_count = sum(1 for t in tokens if _contains_any(t, NEGATIVE_WORDS))
    total = pos_count + neg_count

    if total == 0:
        return "neutral", 0.0

    score = (pos_count - neg_count) / total
    if score > 0:
        return "positive", score
    if score < 0:
        return "negative", score
    return "neutral", 0.0
