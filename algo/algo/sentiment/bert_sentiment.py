"""BERT/RoBERTa-based sentiment classifier using HuggingFace pretrained models.

Replaces the TF-IDF + LR model for cases where domain mismatch is a problem
(e.g. disaster/social-media content vs. hotel-review training data).

Default model: uer/roberta-base-finetuned-jd-binary-chinese
  Chinese RoBERTa fine-tuned on JD product reviews — closer to colloquial comment
  style than hotel reviews, and Chinese-native rather than multilingual.

Neutral detection: the underlying model is binary (positive / negative); texts where
neither class clears `confidence_threshold` (default 0.65) are labelled "neutral",
consistent with how ml_sentiment handles it.

Requires: pip install transformers torch
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "uer/roberta-base-finetuned-jd-binary-chinese"
DEFAULT_CONFIDENCE_THRESHOLD = 0.65

_LABEL_MAP: dict[str, str] = {
    "positive": "positive",
    "negative": "negative",
    "label_1": "positive",
    "label_0": "negative",
    "1": "positive",
    "0": "negative",
    "pos": "positive",
    "neg": "negative",
    # uer/roberta-base-finetuned-jd-binary-chinese uses verbose star-rating labels
    "positive (stars 4 and 5)": "positive",
    "negative (stars 1, 2 and 3)": "negative",
}

_pipeline_cache: dict[str, Any] = {}


def _get_pipeline(model_name: str) -> Any:
    if model_name not in _pipeline_cache:
        try:
            from transformers import pipeline
        except ImportError:
            raise ImportError(
                "transformers is required for BERT sentiment — pip install transformers torch"
            )
        logger.info("Loading BERT sentiment model %r (first call, may take a moment)…", model_name)
        _pipeline_cache[model_name] = pipeline(
            "sentiment-analysis",
            model=model_name,
            truncation=True,
            max_length=512,
        )
        logger.info("Model loaded.")
    return _pipeline_cache[model_name]


def predict_bert_sentiment(
    text: str,
    model_name: str = DEFAULT_MODEL,
    confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
) -> str:
    """Classify `text` as positive / negative / neutral using a pretrained BERT model.

    Model labels are normalised via _LABEL_MAP so the caller doesn't need to know
    each model's internal label scheme.  Texts where neither class clears
    `confidence_threshold` are returned as "neutral".
    """
    pipe = _get_pipeline(model_name)
    result = pipe(text)[0]
    raw_label = result["label"].lower()
    score = float(result["score"])

    label = _LABEL_MAP.get(raw_label)
    if label is None:
        logger.warning("Unknown label %r from model %r — treating as neutral", raw_label, model_name)
        return "neutral"

    return label if score >= confidence_threshold else "neutral"


def clear_cache() -> None:
    """Unload cached pipelines (useful in tests to avoid cross-test state)."""
    _pipeline_cache.clear()
