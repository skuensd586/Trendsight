"""TF-IDF keyword extraction over a corpus of already-tokenized documents."""
from __future__ import annotations

import math
from collections import Counter


def _tf(tokens: list[str]) -> Counter:
    return Counter(tokens)


def _idf(corpus_tokens: list[list[str]]) -> dict[str, float]:
    n_docs = len(corpus_tokens)
    doc_freq: Counter = Counter()
    for tokens in corpus_tokens:
        doc_freq.update(set(tokens))
    return {term: math.log((n_docs + 1) / (df + 1)) + 1 for term, df in doc_freq.items()}


def extract_keywords(corpus_tokens: list[list[str]], top_k: int = 10) -> list[list[tuple[str, float]]]:
    """For each document (as a token list) in `corpus_tokens`, return its top-k (term, tf-idf) pairs."""
    idf = _idf(corpus_tokens)
    results = []
    for tokens in corpus_tokens:
        tf = _tf(tokens)
        scores = {term: count * idf.get(term, 0.0) for term, count in tf.items()}
        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:top_k]
        results.append(ranked)
    return results
