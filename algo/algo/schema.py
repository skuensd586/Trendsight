"""Shared data structures passed between algorithm pipeline stages."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Document:
    """Standardized document produced by preprocessing, consumed by every later stage."""

    doc_id: str
    title: str
    content: str
    publish_time: datetime
    source: str
    platform: str
    url: str
    author: str = ""
    tokens: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    sentiment_label: str | None = None
    sentiment_score: float | None = None
    event_id: str | None = None
    # Set once by preprocess.text_type.resolve_text_type from `platform` (see that module);
    # "comment" or "article" if the platform is known, else "auto" as a degraded fallback.
    # Downstream sentiment code should read this rather than re-deriving text_type itself.
    text_type: str = "auto"
    # Source credibility tier, populated from the crawler's verification_type field.
    # Values: 官方平台 / 认证机构 / 头部认证个人 / 认证个人 / 普通用户 / None
    # None means the crawler didn't supply this field (treated as 普通用户 in authenticity scoring).
    verification_type: str | None = None
    # Engagement counts (转赞评), populated by the crawler for social posts (微博/知乎);
    # news-site articles carry no engagement and default to 0.  Used by propagation.py to
    # score a post's influence as a propagation hub.
    repost_count: int = 0
    like_count: int = 0
    comment_count: int = 0
