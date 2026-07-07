"""ML-based sentiment classification: a parallel implementation to dict_sentiment's lexicon
approach, backed by a trained TF-IDF + classifier model.

Models are trained separately per text_type (see scripts/train_sentiment_model.py) because
the labeled data available today is Weibo-style comments (short, colloquial) while the
system also has to score full news articles (long, written register) — a domain shift
that a single comment-trained model won't handle well. Only a "comment" model exists so
far; requesting "article" transparently falls back to the comment model (logging a
one-time warning) until an article-labeled dataset justifies training one. Callers don't
need to change when that happens — see get_model_status() to check what's actually in use.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib

logger = logging.getLogger(__name__)

MODEL_DIR = Path(__file__).resolve().parents[2] / "models"
REPORT_PATH = Path(__file__).resolve().parents[2] / "reports" / "sentiment_training_report.md"

SUPPORTED_TEXT_TYPES = ("comment", "article")
_FALLBACK_TEXT_TYPE = "comment"

# NOTE: text_type should come from doc.text_type, set once during preprocessing from the
# platform -> text_type table in preprocess.text_type. This length threshold is *only* a
# degraded fallback for "auto" (i.e. the platform wasn't in that table) -- it is not the
# primary way text_type gets decided, and callers shouldn't treat it as such.
AUTO_LENGTH_THRESHOLD = 200  # chars; longer than this guesses "article", else "comment"

DEFAULT_CONFIDENCE_THRESHOLD = 0.6


@dataclass
class _ModelEntry:
    text_type: str  # the type actually served (== requested type, unless is_fallback)
    model_path: Path
    vectorizer: Any
    classifier: Any
    is_fallback: bool


_model_cache: dict[str, _ModelEntry] = {}
_warned_fallback_types: set[str] = set()


def _latest_model_file(text_type: str, model_dir: Path) -> Path | None:
    candidates = sorted(model_dir.glob(f"sentiment_model_{text_type}_*.joblib"))
    return candidates[-1] if candidates else None


def _resolve_model_path(text_type: str, model_dir: Path) -> tuple[Path, bool]:
    """Return (path, is_fallback) for `text_type`, falling back to the comment model."""
    path = _latest_model_file(text_type, model_dir)
    if path is not None:
        return path, False

    if text_type != _FALLBACK_TEXT_TYPE:
        fallback_path = _latest_model_file(_FALLBACK_TEXT_TYPE, model_dir)
        if fallback_path is not None:
            return fallback_path, True

    raise FileNotFoundError(
        f"no sentiment model found for text_type={text_type!r} (or fallback "
        f"{_FALLBACK_TEXT_TYPE!r}) in {model_dir} -- run scripts/train_sentiment_model.py first"
    )


def _load_model(text_type: str) -> _ModelEntry:
    if text_type in _model_cache:
        return _model_cache[text_type]

    # Read MODEL_DIR fresh (not as a default arg) so tests/callers can point it at a
    # different directory via `ml_sentiment.MODEL_DIR = ...` and have it actually apply --
    # a default bound at def-time would freeze in the value from module import.
    path, is_fallback = _resolve_model_path(text_type, MODEL_DIR)
    bundle = joblib.load(path)
    entry = _ModelEntry(
        text_type=text_type,
        model_path=path,
        vectorizer=bundle["vectorizer"],
        classifier=bundle["classifier"],
        is_fallback=is_fallback,
    )
    _model_cache[text_type] = entry

    if is_fallback and text_type not in _warned_fallback_types:
        logger.warning(
            "no %r sentiment model yet; using the %r model (%s) instead -- accuracy may be "
            "lower on %r text until an %r model is trained",
            text_type, _FALLBACK_TEXT_TYPE, path.name, text_type, text_type,
        )
        _warned_fallback_types.add(text_type)

    return entry


def label_from_proba(proba: dict[str, float], confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD) -> str:
    """Turn a binary {"positive": p, "negative": p} distribution into positive/negative/
    neutral: neutral when neither class clears `confidence_threshold`. Shared by
    predict_sentiment and the training script's own evaluation, so "what counts as
    neutral" can't drift between training-time metrics and runtime behavior."""
    positive = proba.get("positive", 0.0)
    negative = proba.get("negative", 0.0)
    if max(positive, negative) < confidence_threshold:
        return "neutral"
    return "positive" if positive > negative else "negative"


def _auto_text_type(text: str) -> str:
    return "article" if len(text) > AUTO_LENGTH_THRESHOLD else "comment"


def predict_sentiment(
    text: str,
    text_type: str = "auto",
    confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
) -> str:
    """Classify `text` as "positive"/"negative"/"neutral" using the trained model for
    `text_type` (falling back to the comment model if that type isn't trained yet).

    `text_type` should normally be `doc.text_type` from preprocessing, not guessed here.
    "auto" (the default) is a degraded fallback for when preprocessing couldn't map the
    document's platform to a text_type -- see preprocess.text_type -- and just guesses
    from `text`'s length; pass the real text_type whenever you have one.
    """
    resolved_type = _auto_text_type(text) if text_type == "auto" else text_type
    if resolved_type not in SUPPORTED_TEXT_TYPES:
        raise ValueError(f"text_type must be one of {SUPPORTED_TEXT_TYPES} or 'auto', got {text_type!r}")

    entry = _load_model(resolved_type)
    features = entry.vectorizer.transform([text])
    proba = dict(zip(entry.classifier.classes_, entry.classifier.predict_proba(features)[0]))
    return label_from_proba(proba, confidence_threshold)


def get_model_status() -> dict[str, dict[str, Any]]:
    """Report, for every supported text_type, which model file actually serves it and
    whether that's a fallback -- for debugging and for citing in reports. Reflects models
    already loaded (from real predict_sentiment calls) plus a cheap path lookup for types
    that haven't been requested yet, so calling this doesn't itself trigger a full load."""
    status: dict[str, dict[str, Any]] = {}
    for text_type in SUPPORTED_TEXT_TYPES:
        if text_type in _model_cache:
            entry = _model_cache[text_type]
            status[text_type] = {
                "model_path": str(entry.model_path),
                "is_fallback": entry.is_fallback,
                "loaded": True,
            }
            continue
        try:
            path, is_fallback = _resolve_model_path(text_type, MODEL_DIR)
            status[text_type] = {"model_path": str(path), "is_fallback": is_fallback, "loaded": False}
        except FileNotFoundError:
            status[text_type] = {"model_path": None, "is_fallback": False, "loaded": False}
    return status
