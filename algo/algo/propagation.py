"""Key-node detection for event propagation (务实版 event tracing).

The course task's advanced feature "事件溯源与关键传播路径" asks to identify the key
nodes in an event's spread — the initial poster, the first big-V amplification, the first
official-media involvement — and to draw a propagation graph.

A *true* retweet tree needs a "reposted-from" edge that the crawler does not yet provide,
so we build the pragmatic version that the available fields DO support:

  key_nodes      — a role timeline built from publish_time + verification_type + engagement:
                     初始爆料 / 首次大V发声 / 首次官方媒体介入 / 传播高峰
  top_influencers — posts ranked by engagement-based influence (转赞评), the amplification hubs
  platform_chain  — platforms ordered by first-appearance time, a platform-level spread path
                     (approximation of the propagation graph, not a strict retweet tree)

Influence of a post is scored from its 转赞评 counts; a repost is the strongest signal of
active spreading, a like the weakest.  News-site articles carry no engagement (score 0) but
still anchor the "官方媒体介入" role by time.
"""
from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .schema import Document

# Engagement weights: a repost actively spreads content, a comment shows engagement, a like
# is the cheapest signal.  Tune as real data accumulates.
_W_REPOST, _W_COMMENT, _W_LIKE = 1.0, 0.5, 0.3

# Account tiers that count as "大V" (influential individual / verified org).
_BIGV_TIERS = frozenset({"头部认证个人", "认证机构"})
# Account tiers / platforms that count as authoritative-official.
_OFFICIAL_TIERS = frozenset({"官方平台", "官方机构"})


def _influence(doc: Document) -> float:
    return doc.repost_count * _W_REPOST + doc.comment_count * _W_COMMENT + doc.like_count * _W_LIKE


def _node(doc: Document, role: str) -> dict[str, Any]:
    return {
        "role": role,
        "author": doc.author or "匿名",
        "platform": doc.platform,
        "verification_type": doc.verification_type or "普通用户",
        "publish_time": doc.publish_time.isoformat(),
        "influence": round(_influence(doc), 1),
        "title": (doc.title or doc.content)[:40],
    }


def _first_where(docs_by_time: list[Document], predicate) -> Document | None:
    for doc in docs_by_time:
        if predicate(doc):
            return doc
    return None


def detect_propagation(docs: list[Document], top_k: int = 5) -> dict[str, Any]:
    """Return {key_nodes, top_influencers, platform_chain} for one event's post docs."""
    if not docs:
        return {"key_nodes": [], "top_influencers": [], "platform_chain": {"nodes": [], "links": []}}

    by_time = sorted(docs, key=lambda d: d.publish_time)

    # ── role timeline (dedup by doc so the same post isn't listed under two roles) ──
    key_nodes: list[dict[str, Any]] = []
    seen: set[str] = set()

    def _add(doc: Document | None, role: str) -> None:
        if doc is not None and doc.doc_id not in seen:
            seen.add(doc.doc_id)
            key_nodes.append(_node(doc, role))

    # 初始爆料 is a grassroots leak: prefer the earliest ordinary-user post; if the event is
    # entirely official/verified coverage, fall back to the earliest post of any kind.
    grassroots = _first_where(by_time, lambda d: (d.verification_type or "普通用户") == "普通用户")
    _add(grassroots or by_time[0], "初始爆料")
    _add(_first_where(by_time, lambda d: (d.verification_type or "") in _BIGV_TIERS), "首次大V发声")
    _add(_first_where(by_time, lambda d: (d.verification_type or "") in _OFFICIAL_TIERS), "首次官方媒体介入")
    _add(max(docs, key=_influence) if any(_influence(d) > 0 for d in docs) else None, "传播高峰")
    key_nodes.sort(key=lambda n: n["publish_time"])

    # ── influence hubs ──
    ranked = sorted(docs, key=_influence, reverse=True)
    top_influencers = [
        {
            "author": d.author or "匿名",
            "platform": d.platform,
            "verification_type": d.verification_type or "普通用户",
            "publish_time": d.publish_time.isoformat(),
            "influence": round(_influence(d), 1),
            "repost_count": d.repost_count,
            "like_count": d.like_count,
            "comment_count": d.comment_count,
            "title": (d.title or d.content)[:40],
        }
        for d in ranked[:top_k] if _influence(d) > 0
    ]

    # ── platform-level spread path: order platforms by first appearance ──
    first_seen: dict[str, Any] = {}
    counts: dict[str, int] = defaultdict(int)
    for doc in by_time:
        counts[doc.platform] += 1
        first_seen.setdefault(doc.platform, doc.publish_time)
    ordered = sorted(first_seen, key=lambda p: first_seen[p])
    nodes = [{"name": p, "count": counts[p], "first_seen": first_seen[p].isoformat()} for p in ordered]
    links = [
        {"source": ordered[i], "target": ordered[i + 1], "value": counts[ordered[i + 1]]}
        for i in range(len(ordered) - 1)
    ]

    return {"key_nodes": key_nodes, "top_influencers": top_influencers,
            "platform_chain": {"nodes": nodes, "links": links}}
