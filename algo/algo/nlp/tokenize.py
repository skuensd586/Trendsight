"""Chinese tokenization: jieba when available, falling back to per-character splitting otherwise."""
from __future__ import annotations

import re

from .stopwords import STOPWORDS

# Chinese has no whitespace between words, so without jieba's dictionary-based
# segmentation the best a regex can do is split CJK into single characters
# while keeping runs of Latin/digits (e.g. "COVID-19") as one token.
_TOKEN_RE = re.compile(r"[一-鿿]|[\w]+")

try:
    import jieba

    _HAS_JIEBA = True
except ImportError:
    _HAS_JIEBA = False


def _fallback_tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text)


def tokenize(text: str, remove_stopwords: bool = True) -> list[str]:
    """Split `text` into tokens, dropping punctuation/whitespace and (by default) stopwords."""
    if _HAS_JIEBA:
        tokens = [t.strip() for t in jieba.cut(text) if t.strip()]
    else:
        tokens = _fallback_tokenize(text)

    if remove_stopwords:
        tokens = [t for t in tokens if t not in STOPWORDS]
    return tokens
