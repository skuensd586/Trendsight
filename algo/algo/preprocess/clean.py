"""Turn a raw crawler record into a standardized Document: strip markup/boilerplate, normalize fields."""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from ..schema import Document
from .text_type import resolve_text_type

_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")
_BOILERPLATE_PATTERNS = [
    re.compile(r"责任编辑[:：].*"),
    re.compile(r"免责声明[:：].*"),
    re.compile(r"点击(进入|查看|阅读)[^\s]{0,10}"),
    re.compile(r"扫描二维码.*"),
]


def strip_boilerplate(text: str) -> str:
    """Remove HTML tags and common Chinese news boilerplate (editor credits, disclaimers, share prompts)."""
    text = _TAG_RE.sub(" ", text)
    for pattern in _BOILERPLATE_PATTERNS:
        text = pattern.sub("", text)
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
    """Map a raw crawler record (arbitrary key casing/format) onto the standard Document schema."""
    platform = raw.get("platform", "")
    return Document(
        doc_id=str(raw["doc_id"]),
        title=strip_boilerplate(raw.get("title", "")),
        content=strip_boilerplate(raw.get("content", "")),
        publish_time=parse_publish_time(raw["publish_time"]),
        source=raw.get("source", ""),
        platform=platform,
        url=raw.get("url", ""),
        author=raw.get("author", ""),
        text_type=resolve_text_type(platform),
    )
