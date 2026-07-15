"""Chinese tokenization: jieba when available, falling back to per-character splitting otherwise."""
from __future__ import annotations

import re

from .stopwords import STOPWORDS

# Chinese has no whitespace between words, so without jieba's dictionary-based
# segmentation the best a regex can do is split CJK into single characters
# while keeping runs of Latin/digits (e.g. "COVID-19") as one token.
_TOKEN_RE = re.compile(r"[一-鿿]|[\w]+")
_HAS_WORD_CHAR_RE = re.compile(r"[一-鿿\w]")

try:
    import jieba

    _HAS_JIEBA = True
except ImportError:
    _HAS_JIEBA = False


def _fallback_tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text)


_PURE_DIGIT_RE = re.compile(r"^\d+$")
# A real term carries a CJK character or a Latin letter; tokens made only of symbols or
# stray superscripts ("³", "±") are formatting debris that TF-IDF would otherwise rank.
_CJK_OR_LATIN_RE = re.compile(r"[一-鿿a-zA-Z]")


def tokenize(text: str, remove_stopwords: bool = True) -> list[str]:
    """Split `text` into tokens, dropping punctuation/whitespace and (by default) stopwords.

    Filtering order:
      1. Tokenize (jieba) or fallback per-character split
      2. Drop tokens with no letter/digit/CJK content
      3. Drop pure-digit tokens (e.g. "8", "2026")
      4. Drop single-character tokens — a lone CJK char is always noise after jieba, and
         a lone Latin char ("s") or symbol is formatting debris; without jieba the whole
         output is single chars, which is already unusable
      5. Drop tokens with neither a CJK char nor a Latin letter (e.g. "³")
      6. Drop stopwords
    """
    if _HAS_JIEBA:
        tokens = [t.strip() for t in jieba.cut(text) if t.strip()]
    else:
        tokens = _fallback_tokenize(text)

    tokens = [t for t in tokens if _HAS_WORD_CHAR_RE.search(t)]
    tokens = [t for t in tokens if not _PURE_DIGIT_RE.match(t)]
    tokens = [t for t in tokens if len(t) >= 2]
    tokens = [t for t in tokens if _CJK_OR_LATIN_RE.search(t)]

    if remove_stopwords:
        tokens = [t for t in tokens if t not in STOPWORDS]
    return tokens
