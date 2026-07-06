"""SimHash-based near-duplicate detection for deduping crawled reports of the same story."""
from __future__ import annotations

import hashlib
import re

_TOKEN_RE = re.compile(r"[\w一-鿿]+")


def _shingles(text: str, n: int = 4) -> list[str]:
    """Character n-grams, which work better than word-splitting for Chinese text without a tokenizer."""
    chars = [c for c in text if not c.isspace()]
    if len(chars) < n:
        return ["".join(chars)] if chars else []
    return ["".join(chars[i : i + n]) for i in range(len(chars) - n + 1)]


def simhash(text: str, num_bits: int = 64) -> int:
    """Compute a SimHash fingerprint of `text`. Similar texts get fingerprints with a small Hamming distance."""
    weights = [0] * num_bits
    for shingle in _shingles(text):
        digest = hashlib.md5(shingle.encode("utf-8")).hexdigest()
        h = int(digest, 16)
        for bit in range(num_bits):
            weights[bit] += 1 if (h >> bit) & 1 else -1

    fingerprint = 0
    for bit in range(num_bits):
        if weights[bit] > 0:
            fingerprint |= 1 << bit
    return fingerprint


def hamming_distance(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


def is_near_duplicate(fp_a: int, fp_b: int, threshold: int = 3) -> bool:
    """Two fingerprints are treated as the same report if they differ in at most `threshold` bits.

    The right threshold scales with document length (more shingles => more stable votes per
    bit); 3 suits full articles. Tune against a labeled sample before relying on it in prod.
    """
    return hamming_distance(fp_a, fp_b) <= threshold
