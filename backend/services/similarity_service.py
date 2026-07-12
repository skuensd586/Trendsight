"""Similarity service: find historical events similar to a given event.

Uses simple TF-IDF (character bigrams) + cosine similarity.
No external dependencies beyond Python stdlib.
"""

from __future__ import annotations

import math
from collections import Counter
from typing import Any

from sqlalchemy.orm import Session, subqueryload


def _tokenize(text: str | None) -> list[str]:
    """Character bigram tokenizer for Chinese and mixed text."""
    if not text:
        return []
    text = text.strip()
    if not text:
        return []
    return [text[i:i+2] for i in range(len(text) - 1)]


def _extract_keywords_text(event) -> str:
    """Join all keywords into a single space-separated string."""
    if not event.keywords:
        return ""
    return " ".join(kw.word for kw in event.keywords)


def _combined_text(event) -> str:
    """Combine title, summary, cause and keywords for similarity comparison."""
    parts = [
        event.title or "",
        event.summary or "",
        event.cause or "",
        _extract_keywords_text(event),
    ]
    return " ".join(parts)


def _tf(tokens: list[str]) -> dict[str, float]:
    """Compute term frequency (TF) from a token list."""
    tf = Counter(tokens)
    total = len(tokens) or 1
    return {term: count / total for term, count in tf.items()}


def _idf(all_token_lists: list[list[str]]) -> dict[str, float]:
    """Compute inverse document frequency (IDF) from a corpus."""
    n = len(all_token_lists)
    df: Counter = Counter()
    for tokens in all_token_lists:
        df.update(set(tokens))
    return {
        term: math.log((n + 1) / (count + 1)) + 1
        for term, count in df.items()
    }


def _cosine_similarity(
    vec1: dict[str, float],
    vec2: dict[str, float],
) -> float:
    """Cosine similarity between two sparse term vectors."""
    common = set(vec1) & set(vec2)
    if not common:
        return 0.0
    dot = sum(vec1[t] * vec2[t] for t in common)
    norm1 = math.sqrt(sum(v * v for v in vec1.values()))
    norm2 = math.sqrt(sum(v * v for v in vec2.values()))
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot / (norm1 * norm2)


def _build_reason(
    current_title: str,
    other_title: str,
    current_keywords: set[str],
    other_keywords: set[str],
    current_content: str,
    other_content: str,
) -> str:
    """Generate a human-readable reason string for similarity."""
    reasons: list[str] = []
    if set(_tokenize(current_title)) & set(_tokenize(other_title)):
        reasons.append("\u6807\u9898")
    if current_keywords & other_keywords:
        reasons.append("\u5173\u952e\u8bcd")
    if set(_tokenize(current_content)) & set(_tokenize(other_content)):
        reasons.append("\u5185\u5bb9")
    if not reasons:
        return "\u5185\u5bb9\u7279\u5f81\u76f8\u4f3c"
    return "\u3001".join(reasons) + "\u76f8\u4f3c"


def find_similar_events(
    db: Session,
    event_id: int,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Find events similar to the given event using TF-IDF + cosine similarity.

    Args:
        db: SQLAlchemy session.
        event_id: ID of the source event.
        limit: Maximum number of similar events to return.

    Returns:
        List of dicts with keys: event_id, title, similarity, reason.
    """
    from models.event import Event

    current = (
        db.query(Event)
        .options(subqueryload(Event.keywords))
        .filter(Event.event_id == event_id)
        .first()
    )
    if not current:
        return []

    current_text = _combined_text(current)
    if not current_text.strip():
        return []

    current_tokens = _tokenize(current_text)
    current_keyword_set = {kw.word for kw in (current.keywords or [])}

    others = (
        db.query(Event)
        .options(subqueryload(Event.keywords))
        .filter(Event.event_id != event_id)
        .all()
    )
    if not others:
        return []

    # Build IDF from all documents
    all_texts = [current_text] + [_combined_text(o) for o in others]
    all_token_lists = [_tokenize(t) for t in all_texts]
    idf = _idf(all_token_lists)

    # Compute TF-IDF for current event
    current_tf = _tf(current_tokens)
    current_vec = {t: v * idf.get(t, 1.0) for t, v in current_tf.items()}

    results: list[dict[str, Any]] = []
    for other in others:
        other_text = _combined_text(other)
        if not other_text.strip():
            continue

        other_tokens = _tokenize(other_text)
        other_tf = _tf(other_tokens)
        other_vec = {t: v * idf.get(t, 1.0) for t, v in other_tf.items()}

        sim = _cosine_similarity(current_vec, other_vec)
        if sim <= 0:
            continue

        other_keyword_set = {kw.word for kw in (other.keywords or [])}
        reason = _build_reason(
            current.title or "",
            other.title or "",
            current_keyword_set,
            other_keyword_set,
            (current.summary or "") + (current.cause or ""),
            (other.summary or "") + (other.cause or ""),
        )

        results.append({
            "event_id": other.event_id,
            "title": other.title or "",
            "similarity": round(sim, 4),
            "reason": reason,
        })

    results.sort(key=lambda r: r["similarity"], reverse=True)
    return results[:limit]
