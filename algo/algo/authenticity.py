"""Source-credibility-based authenticity scoring for event clusters.

Scores are derived from the crawler's `verification_type` field, which encodes
the account tier of the document's author (官方平台 / 认证机构 / 头部认证个人 /
认证个人 / 普通用户).  Sina News articles receive 官方平台 automatically since
the platform itself is the authoritative source (set in preprocess/clean.py).

Output shape (added to each event report under "authenticity"):
  credibility_score    float [0, 1]  — weighted-average author credibility,
                                       penalised by duplicate_rate
  official_ratio       float [0, 1]  — fraction of 官方平台 documents
  verified_ratio       float [0, 1]  — fraction of any verified-tier documents
  plain_user_ratio     float [0, 1]  — fraction of 普通用户 / unknown documents
  verification_dist    dict          — full breakdown by tier
  factors              list[str]     — machine-readable signal codes for LLM /
                                       frontend to turn into natural language
"""
from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .schema import Document

# Credibility weight per tier: reflects how much a document from this tier
# should contribute to the event's overall credibility score.
_WEIGHTS: dict[str, float] = {
    "官方平台":    1.00,   # 央媒/平台官方账号 (新华社、人民日报、央视新闻等)
    "官方机构":    1.00,   # 知乎官方机构 (等同于官方平台)
    "认证机构":    0.75,   # 政府/媒体/企业/校园机构蓝V
    "头部认证个人": 0.50,  # 橙V / 金V 知名个人
    "认证个人":    0.30,   # 普通蓝V 个人
    "普通用户":    0.10,   # 未认证用户
}
_DEFAULT_WEIGHT = 0.10   # None / 未知 → 等同于普通用户

# Tiers counted as "verified" (any recognised certification)
_VERIFIED_TIERS = frozenset(_WEIGHTS) - {"普通用户"}

# Signal thresholds — tune as real data accumulates
_OFFICIAL_ABSENT_THRESHOLD  = 0.10   # official_ratio below this → flag
_MOSTLY_UNVERIFIED_THRESHOLD = 0.70  # plain_user_ratio above this → flag
_HIGH_DUPLICATE_THRESHOLD   = 0.30   # duplicate_rate above this → flag
_DUPLICATE_PENALTY_FACTOR   = 0.30   # how much duplicate_rate dampens score


def compute_authenticity(
    docs: list[Document],
    duplicate_rate: float = 0.0,
) -> dict[str, Any]:
    """Compute source-credibility authenticity metrics for one event cluster.

    Args:
        docs:           Document objects after dedup (as produced by pipeline.py).
        duplicate_rate: duplicate_count / (report_count + duplicate_count), used
                        to penalise coordinated-spreading patterns.

    Returns a dict with keys: credibility_score, official_ratio, verified_ratio,
    plain_user_ratio, verification_dist, factors.
    """
    if not docs:
        return _empty_result()

    # ── per-document weights ──────────────────────────────────────────────────
    tier_counts: Counter[str] = Counter()
    weight_sum = 0.0

    for doc in docs:
        tier = doc.verification_type or "普通用户"
        tier_counts[tier] += 1
        weight_sum += _WEIGHTS.get(tier, _DEFAULT_WEIGHT)

    total = len(docs)
    raw_score = weight_sum / total  # ∈ [0.1, 1.0]

    # Penalise high duplicate rate: coordinated spreading of identical content
    # inflates raw document count without adding independent corroboration.
    score = raw_score * (1.0 - duplicate_rate * _DUPLICATE_PENALTY_FACTOR)
    score = round(max(0.0, min(1.0, score)), 3)

    # ── ratio breakdowns ──────────────────────────────────────────────────────
    official_tiers  = {"官方平台", "官方机构"}
    plain_tiers     = {"普通用户"}

    official_count  = sum(tier_counts[t] for t in official_tiers)
    verified_count  = sum(
        cnt for tier, cnt in tier_counts.items() if tier in _VERIFIED_TIERS
    )
    plain_count     = sum(
        cnt for tier, cnt in tier_counts.items()
        if tier in plain_tiers or tier not in _WEIGHTS
    )

    official_ratio  = round(official_count / total, 3)
    verified_ratio  = round(verified_count / total, 3)
    plain_ratio     = round(plain_count    / total, 3)

    verification_dist = {
        tier: round(cnt / total, 3)
        for tier, cnt in sorted(tier_counts.items(), key=lambda x: -x[1])
    }

    # ── signal factors ────────────────────────────────────────────────────────
    factors: list[str] = []
    if official_ratio < _OFFICIAL_ABSENT_THRESHOLD:
        factors.append("official_absent")       # 缺乏官方媒体报道
    if plain_ratio > _MOSTLY_UNVERIFIED_THRESHOLD:
        factors.append("mostly_unverified")     # 以普通用户为主
    if duplicate_rate > _HIGH_DUPLICATE_THRESHOLD:
        factors.append("high_duplicate_rate")   # 大量重复/转发内容
    if verified_ratio > 0.5 and official_ratio > 0.2:
        factors.append("well_sourced")          # 来源多元且可信

    return {
        "credibility_score":   score,
        "official_ratio":      official_ratio,
        "verified_ratio":      verified_ratio,
        "plain_user_ratio":    plain_ratio,
        "verification_dist":   verification_dist,
        "factors":             factors,
    }


def _empty_result() -> dict[str, Any]:
    return {
        "credibility_score":   None,
        "official_ratio":      None,
        "verified_ratio":      None,
        "plain_user_ratio":    None,
        "verification_dist":   {},
        "factors":             [],
    }
