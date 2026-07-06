"""Shared TF-IDF vocabulary statistics, used by both keyword extraction and event clustering."""
from __future__ import annotations

import math
from collections import Counter


def compute_idf(corpus_tokens: list[list[str]]) -> dict[str, float]:
    n_docs = len(corpus_tokens)
    doc_freq: Counter = Counter()
    for tokens in corpus_tokens:
        doc_freq.update(set(tokens))
    return {term: math.log((n_docs + 1) / (df + 1)) + 1 for term, df in doc_freq.items()}


def tfidf_vector(tokens: list[str], idf: dict[str, float]) -> dict[str, float]:
    """L2-normalized TF-IDF vector so cosine similarity reduces to a plain dot product."""
    tf = Counter(tokens)
    vec = {term: count * idf.get(term, 0.0) for term, count in tf.items()}
    norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
    return {term: v / norm for term, v in vec.items()}
