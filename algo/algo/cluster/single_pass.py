"""Single-Pass incremental clustering: groups documents into events by TF-IDF cosine similarity.

Processes documents in chronological order, comparing each to existing cluster centroids and
either joining the closest one above `threshold` or starting a new cluster — the streaming-
friendly alternative to a full batch clustering pass (see docs/algorithm-plan.md, section 3).

Simplification: IDF is computed once over the whole input batch rather than updated
incrementally as documents "arrive", since a true streaming IDF needs a running vocabulary
service. Fine for this offline demo; swap in an incrementally-updated IDF for production.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..nlp.tfidf import compute_idf, tfidf_vector
from ..nlp.tokenize import tokenize
from ..schema import Document
from .vectorize import cosine_similarity


@dataclass
class _Cluster:
    size: int = 0
    centroid: dict[str, float] = field(default_factory=dict)

    def add(self, vector: dict[str, float]) -> None:
        self.size += 1
        terms = set(self.centroid) | set(vector)
        self.centroid = {
            term: (self.centroid.get(term, 0.0) * (self.size - 1) + vector.get(term, 0.0)) / self.size
            for term in terms
        }


def cluster_with_centroids(
    docs: list[Document], threshold: float = 0.04
) -> tuple[list[int], list[dict[str, float]], dict[str, float]]:
    """Single-Pass clustering that also returns the cluster centroids and the IDF table.

    The extra return values let callers assign *new* documents (e.g. comments) to the
    nearest existing cluster without re-running a full clustering pass — useful when
    comments are too short to cluster reliably on their own but should be grouped with
    the post they relate to (see scripts/run_xls_pipeline.py two-stage analysis).

    Returns:
        assignments  — cluster id per doc, aligned to the input order of `docs`
        centroids    — averaged TF-IDF centroid vector per cluster
        idf          — IDF table built from this corpus (reuse for new doc vectors)
    """
    if not docs:
        return [], [], {}

    corpus_tokens = [tokenize(doc.title + " " + doc.content) for doc in docs]
    idf = compute_idf(corpus_tokens)
    vectors = [tfidf_vector(tokens, idf) for tokens in corpus_tokens]

    order = sorted(range(len(docs)), key=lambda i: docs[i].publish_time)
    clusters: list[_Cluster] = []
    assignment = [-1] * len(docs)

    for i in order:
        best_cluster, best_score = -1, 0.0
        for cluster_id, cluster in enumerate(clusters):
            score = cosine_similarity(vectors[i], cluster.centroid)
            if score > best_score:
                best_cluster, best_score = cluster_id, score

        if best_cluster != -1 and best_score >= threshold:
            clusters[best_cluster].add(vectors[i])
            assignment[i] = best_cluster
        else:
            new_cluster = _Cluster()
            new_cluster.add(vectors[i])
            clusters.append(new_cluster)
            assignment[i] = len(clusters) - 1

    return assignment, [c.centroid for c in clusters], idf


def single_pass_cluster(docs: list[Document], threshold: float = 0.04) -> list[int]:
    """Assign each document a cluster id, aligned to the *input* order of `docs`.

    Documents are visited in chronological order (as a real event-discovery pass over an
    incoming stream would), each joining the most similar existing cluster if its cosine
    similarity to that cluster's centroid is at least `threshold`, else starting a new one.

    TF-IDF cosine similarity over short news posts tends to need a much lower threshold
    than you'd expect from full-document search — 0.04 was picked by sweeping thresholds
    against `algo.sample_data`'s labeled events (see tests/test_single_pass.py): it gives
    perfect purity there, though one event still splits into two clusters because its
    early ("launch") and later ("hands-on review") reports share little vocabulary. TF-IDF
    only sees exact term overlap; semantic embeddings (M3+, docs/algorithm-plan.md) would
    catch that a same-event vocabulary drift like this is still one story. Retune per corpus.
    """
    assignment, _, _ = cluster_with_centroids(docs, threshold)
    return assignment
