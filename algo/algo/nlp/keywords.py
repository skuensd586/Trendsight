"""TF-IDF keyword extraction over a corpus of already-tokenized documents."""
from __future__ import annotations

from collections import Counter

from .tfidf import compute_idf


def extract_keywords(corpus_tokens: list[list[str]], top_k: int = 10) -> list[list[tuple[str, float]]]:
    """For each document (as a token list) in `corpus_tokens`, return its top-k (term, tf-idf) pairs."""
    idf = compute_idf(corpus_tokens)
    results = []
    for tokens in corpus_tokens:
        tf = Counter(tokens)
        scores = {term: count * idf.get(term, 0.0) for term, count in tf.items()}
        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:top_k]
        results.append(ranked)
    return results
