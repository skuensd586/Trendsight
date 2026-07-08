"""Cosine similarity over (already L2-normalized) TF-IDF vectors, for event clustering."""
from __future__ import annotations


def cosine_similarity(a: dict[str, float], b: dict[str, float]) -> float:
    if len(b) < len(a):
        a, b = b, a
    return sum(weight * b.get(term, 0.0) for term, weight in a.items())
