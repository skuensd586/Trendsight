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
