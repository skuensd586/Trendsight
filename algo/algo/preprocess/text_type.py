"""Maps a document's `platform` to a sentiment text_type ("comment" vs "article").

This is the primary way text_type gets decided — during preprocessing, once per
document — so downstream code (sentiment.ml_sentiment.predict_sentiment) can just read
`doc.text_type` instead of re-guessing it from the raw text on every call.

Platforms not in this table resolve to "auto": ml_sentiment's length-based heuristic is
only meant as a degraded fallback for that case, not a primary classification method.
"""
from __future__ import annotations

# 微博/论坛类是短评论/发帖；新闻客户端和官方网站/官网发的是长篇正文报道。
# Extend this table as new platforms show up in crawler output.
PLATFORM_TEXT_TYPES: dict[str, str] = {
    "微博": "comment",
    "论坛": "comment",
    "知乎": "comment",
    "新闻客户端": "article",
    "官方网站": "article",
    "官网": "article",
}

AUTO_TEXT_TYPE = "auto"


def resolve_text_type(platform: str) -> str:
    """Look up `platform` in PLATFORM_TEXT_TYPES; unknown platforms get AUTO_TEXT_TYPE,
    which tells ml_sentiment to fall back to its (weaker) length-based heuristic."""
    return PLATFORM_TEXT_TYPES.get(platform, AUTO_TEXT_TYPE)
