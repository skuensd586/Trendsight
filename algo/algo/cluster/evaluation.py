"""Clustering-quality metrics for offline evaluation against labeled data (dev/test only)."""
from __future__ import annotations

from collections import Counter, defaultdict


def purity(predicted_labels: list, true_labels: list) -> float:
    """Fraction of documents whose cluster's majority true label matches their own.

    Standard clustering purity metric (docs/algorithm-plan.md's evaluation section);
    needs ground-truth labels, so it's for evaluating against a labeled sample, not
    something the production pipeline computes on live, unlabeled data.
    """
    if not true_labels:
        return 0.0
    clusters: dict = defaultdict(list)
    for pred, true in zip(predicted_labels, true_labels):
        clusters[pred].append(true)
    correct = sum(Counter(members).most_common(1)[0][1] for members in clusters.values())
    return correct / len(true_labels)
