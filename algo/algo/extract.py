"""Extractive event-detail fields: summary / location / cause / people.

These populate the events table's summary / location / cause / people columns that
the backend detail endpoint (`get_event_detail`) returns to the frontend event-detail
page.  Everything here is fully offline — jieba part-of-speech tagging only, no LLM
dependency — so it can run inside the same pipeline as clustering and sentiment.

Strategy (heuristic, tune as real data accumulates):
  summary  — extractive: rank post sentences by event-keyword coverage, keep the top
             few in their original order (a lead-3 style abstract).
  cause    — the earliest post's opening sentence; the first report of an event usually
             describes the triggering incident (起因).
  location — most frequent place names (jieba `ns`) across post titles + leads.
  people   — most frequent person names (jieba `nr` / `nrt`) across post titles + leads.

Output shape (added to each event report):
  {"summary": str, "cause": str, "location": str | None, "people": list[str]}
"""
from __future__ import annotations

import re
from collections import Counter
from typing import TYPE_CHECKING, Any

import jieba.posseg as pseg

if TYPE_CHECKING:
    from .schema import Document

# Sentence boundaries for Chinese + latin punctuation and newlines.
_SENT_SPLIT = re.compile(r"[。！？!?；;\n]+")
# How much of each post body to scan for NER — titles + leads carry the entities;
# scanning full bodies of hundreds of posts is slow and adds tail noise.
_NER_CHARS = 200
# Place/person names shorter than this are almost always false positives (single chars).
_MIN_NAME_LEN = 2
# jieba POS tags treated as place / person names.
_PLACE_TAGS = {"ns"}
_PERSON_TAGS = {"nr", "nrt"}
# Author strings that are outlets, not people — never surface these as "涉及人物".
_MEDIA_AUTHORS = frozenset({
    "央视新闻", "新华社", "人民日报", "澎湃新闻", "环球时报", "中国新闻网",
    "光明网", "人民网", "新浪新闻", "参考消息", "观察者网",
})

# Common Chinese surnames (百家姓 top ~100). A real personal name starts with one of
# these; requiring it filters most of jieba's `nr` false positives (晋级、加时赛、海基核…)
# without a heavyweight NER model.  Foreign names transliterated by jieba (特朗普、梅西)
# are kept via the length rule below, which is why the surname gate is OR-ed with a
# short-transliteration allowance rather than applied alone.
_SURNAMES = set(
    "王李张刘陈杨黄赵吴周徐孙马朱胡郭何高林罗郑梁谢宋唐许韩冯邓曹彭曾萧田董袁潘于蒋蔡余杜"
    "叶程苏魏吕丁任沈姚卢姜崔钟谭陆汪范金石廖贾夏韦付方白邹孟熊秦邱江尹薛闫段雷侯龙史陶黎"
    "贺顾毛郝龚邵万钱严覃武戴莫孔向汤"
)

# Characters that overwhelmingly appear in transliterated foreign names (梅西、特朗普、
# 恩佐、萨拉、姆巴佩…).  A token with ≥2 of these that doesn't start with a CJK surname is
# almost certainly a foreign personal name rather than a domain term (晋级、加时赛、海基核).
_TRANSLIT_CHARS = set(
    "阿埃奥巴贝比波博布戴德迪蒂多恩尔法佛夫弗盖戈格哈赫吉贾杰喀卡凯科克库拉莱兰勒雷里丽利连"
    "琳卢鲁伦罗洛马迈曼梅蒙米姆穆娜纳内尼诺帕佩皮普齐乔萨塞森莎沙圣斯苏塔泰特提汤特图瓦万威"
    "维沃乌西夏休雅亚扬耶伊尤泽扎佐朗普桑塔"
)


def _looks_foreign(word: str) -> bool:
    return sum(ch in _TRANSLIT_CHARS for ch in word) >= 2


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENT_SPLIT.split(text or "") if len(s.strip()) >= 6]


def _summary(docs: list[Document], keyword_words: list[str], max_sentences: int) -> str:
    """Lead-N extractive summary: score candidate sentences by how many event keywords
    they contain, return the top `max_sentences` joined by 。 (ties broken by order)."""
    keyset = set(keyword_words)
    candidates: list[tuple[int, int, str]] = []  # (-score, order, sentence)
    order = 0
    seen: set[str] = set()
    for doc in docs:
        for sent in _sentences(doc.title + "。" + doc.content):
            if sent in seen:
                continue
            seen.add(sent)
            score = sum(1 for kw in keyset if kw in sent)
            candidates.append((-score, order, sent))
            order += 1
    if not candidates:
        return docs[0].title if docs else ""
    # Best-scoring first; keep only those with any keyword hit, else fall back to lead.
    candidates.sort()
    picked = [c for c in candidates if -c[0] > 0][:max_sentences]
    if not picked:
        picked = candidates[:max_sentences]
    # Restore reading order (by original position) for a coherent abstract.
    picked.sort(key=lambda c: c[1])
    return "。".join(s for _, _, s in picked) + "。"


def _cause(docs: list[Document]) -> str:
    """Opening sentence of the earliest-published post — the triggering report."""
    if not docs:
        return ""
    earliest = min(docs, key=lambda d: d.publish_time)
    sents = _sentences(earliest.title + "。" + earliest.content)
    return sents[0] + "。" if sents else earliest.title


def _entities(docs: list[Document]) -> tuple[Counter, Counter]:
    """Frequency of place names and person names across post titles + leads."""
    places: Counter[str] = Counter()
    people: Counter[str] = Counter()
    for doc in docs:
        text = (doc.title + " " + doc.content)[: _NER_CHARS]
        for word, flag in pseg.cut(text):
            if len(word) < _MIN_NAME_LEN:
                continue
            if flag in _PLACE_TAGS:
                places[word] += 1
            elif flag in _PERSON_TAGS and word not in _MEDIA_AUTHORS:
                people[word] += 1
    return places, people


def _dedupe_substrings(names: list[str]) -> list[str]:
    """Drop a name if it is a substring of one already kept (frequency-ordered input),
    so "广西南宁" suppresses the redundant "南宁" / "广西" that follow it."""
    kept: list[str] = []
    for name in names:
        if any(name in other or other in name for other in kept):
            continue
        kept.append(name)
    return kept


def extract_event_details(
    docs: list[Document],
    keywords: list[dict[str, Any]] | None = None,
    max_summary_sentences: int = 3,
    top_locations: int = 3,
    top_people: int = 5,
) -> dict[str, Any]:
    """Return {summary, cause, location, people} for one event cluster's post docs."""
    if not docs:
        return {"summary": "", "cause": "", "location": None, "people": []}

    keyword_words = [kw["word"] for kw in (keywords or [])]
    places, people = _entities(docs)

    location_list = _dedupe_substrings([w for w, _ in places.most_common()])[:top_locations]
    people_list = _select_people(people, places, set(keyword_words), top_people)

    return {
        "summary": _summary(docs, keyword_words, max_summary_sentences),
        "cause": _cause(docs),
        "location": "、".join(location_list) if location_list else None,
        "people": people_list,
    }


def _select_people(
    people: Counter,
    places: Counter,
    keyword_set: set[str],
    top_people: int,
) -> list[str]:
    """Filter jieba's noisy `nr` candidates into a clean 涉及人物 list.

    jieba routinely mistags domain terms (洪水、白银、强降雨) and org names as person
    names.  Two cheap, general filters remove most of the noise:
      * drop candidates that are event keywords (topic terms, never "people"), and
      * drop candidates jieba also tagged as a place (ambiguous → treat as location).
    Prefer names mentioned in ≥2 posts (one-off mistags rarely repeat); fall back to
    single mentions only if that leaves nothing.
    """
    def _is_name(w: str) -> bool:
        if w in keyword_set or w in places:
            return False
        # Chinese personal name: 2–3 chars starting with a common surname.
        if 2 <= len(w) <= 3 and w[0] in _SURNAMES:
            return True
        # Transliterated foreign name (梅西/特朗普/恩佐): no CJK surname, so allow short
        # all-CJK tokens that jieba tagged nr but that aren't dictionary-like place words.
        return 2 <= len(w) <= 4 and w[0] not in _SURNAMES and _looks_foreign(w)

    def _pick(min_count: int) -> list[str]:
        return [w for w, c in people.most_common() if c >= min_count and _is_name(w)]

    return (_pick(2) or _pick(1))[:top_people]
