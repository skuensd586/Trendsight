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
