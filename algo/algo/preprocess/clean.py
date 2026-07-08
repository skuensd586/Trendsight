"""Turn a raw crawler record into a standardized Document, normalizing its fields.

Noise removal (HTML entity decoding, zero-width characters, platform-specific boilerplate
like editor credits/disclaimers/share prompts, newline normalization) is the crawler's job
now -- see e.g. sina_crawler/crawler_sina.py's clean_content(). strip_boilerplate here is
just a cheap defensive pass (HTML tag stripping + whitespace collapse), a safety net for
sources that don't clean as thoroughly, not B's primary cleaning duty.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from ..schema import Document
from .text_type import resolve_text_type

_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")


def strip_boilerplate(text: str) -> str:
    """Defensive cleanup: strip any leftover HTML tags and collapse whitespace."""
    text = _TAG_RE.sub(" ", text)
    return _WHITESPACE_RE.sub(" ", text).strip()


def parse_publish_time(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value)
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(value), fmt)
        except ValueError:
            continue
    raise ValueError(f"unrecognized publish_time format: {value!r}")


def normalize_document(raw: dict[str, Any]) -> Document:
    """Map a raw crawler record onto the standard Document schema.

    Field names accept both sina_crawler's real `raw_documents` columns
    (source_platform/source_url, per sina_crawler/docs/data_interface.md) and this
    module's own shorter names (platform/url, used by sample_data.py and tests) --
    the crawler doesn't have a separate "outlet name" field distinct from platform, so
    `source` falls back to platform too when not given explicitly.
    """
    platform = raw.get("source_platform") or raw.get("platform", "")
    url = raw.get("source_url") or raw.get("url", "")
    source = raw.get("source") or platform
    return Document(
        doc_id=str(raw["doc_id"]),
        title=strip_boilerplate(raw.get("title", "")),
        content=strip_boilerplate(raw.get("content", "")),
        publish_time=parse_publish_time(raw["publish_time"]),
        source=source,
        platform=platform,
        url=url,
        author=raw.get("author", ""),
        text_type=resolve_text_type(platform),
    )
