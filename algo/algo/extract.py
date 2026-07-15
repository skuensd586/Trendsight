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
from collections import Counter, defaultdict
from typing import TYPE_CHECKING, Any

import jieba.posseg as pseg

if TYPE_CHECKING:
    from .schema import Document

# Sentence boundaries for Chinese + latin punctuation and newlines.
_SENT_SPLIT = re.compile(r"[。！？!?；;\n]+")
# How much of each post body to scan for NER.  Wide enough that the tag histogram sees a
# word used several ways (雷雨 as weather, 覃塘区 as a place) so `_select_people` can reject
# it, but not the full body of hundreds of posts, which is slow and adds tail noise.
_NER_CHARS = 500
# Place/person names shorter than this are almost always false positives (single chars).
_MIN_NAME_LEN = 2
# jieba POS tags treated as place / person / organisation names.
_PLACE_TAGS = {"ns"}
_PERSON_TAGS = {"nr", "nrt"}
_ORG_TAGS = {"nt"}
# Words introducing a storm's name.  Typhoon names are transliterations (美莎克 = Maysak),
# so no spelling rule separates them from人名 — but they are always introduced by one of
# these, and the word right after is the storm, not a person.
_STORM_INTRODUCERS = ("台风", "超强台风", "强台风", "热带风暴", "飓风")
# Quotes sit between the introducer and the name (台风“美莎克”), so they must not count
# as the preceding word.
_SKIP_WHEN_TRACKING = frozenset('“”"\'‘’《》「」（）()： :')
# An administrative suffix makes a word a place regardless of how jieba tagged it.
_PLACE_SUFFIXES = ("省", "市", "区", "县", "镇", "乡", "村", "州", "路", "街道", "水库")
# Meteorological/common nouns jieba habitually mistags `nr` in disaster coverage.
_NON_PERSON_WORDS = frozenset({
    "雷雨", "雷阵雨", "厄尔尼诺", "拉尼娜", "高中生", "大学生", "小学生", "谢谢你们",
})
# Share of a word's sightings that must be person-tagged for it to count as a name.
_PERSON_TAG_DOMINANCE = 0.6
# How much of a document counts as its "lead" when scoring on-topic-ness.
_LEAD_CHARS = 300
# A cause sentence shorter than this is a slogan or a title fragment, not an explanation.
_MIN_CAUSE_LEN = 12
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


def _lead_relevance(doc: Document, keyset: set[str]) -> int:
    """How many distinct event keywords the document's lead region mentions."""
    head = (doc.title + "。" + doc.content)[:_LEAD_CHARS]
    return sum(1 for kw in keyset if kw in head)


def _news_first(docs: list[Document]) -> list[Document]:
    """News articles only, falling back to everything when the event is social-only.

    A news article's opening is a written lead; a social post's opening is a slogan, a
    hashtag or a reaction, which makes a poor summary or cause.
    """
    return [d for d in docs if d.text_type == "article"] or list(docs)


def _summary(docs: list[Document], keyword_words: list[str], max_sentences: int) -> str:
    """Use the lead paragraph of the single most on-topic news article as the summary.

    A news lead is itself a 5W1H précis, so contiguous text from one article reads as a
    coherent abstract.  (Collaging the top-scoring sentences from many documents — the
    previous approach — scored well on keyword coverage but produced a disjointed jumble
    of mid-article fragments.)
    """
    if not docs:
        return ""
    keyset = set(keyword_words)
    candidates = _news_first(docs)
    best = max(candidates, key=lambda d: (_lead_relevance(d, keyset), len(d.content)))
    sents = _sentences(best.content) or _sentences(best.title)
    return "。".join(sents[:max_sentences]) + "。" if sents else best.title


def _cause(docs: list[Document], keyword_words: list[str]) -> str:
    """Lead sentence of the earliest on-topic news report — the report that framed the event.

    Not simply the earliest post: crawler search results carry archive articles that merely
    matched the keyword, and social posts open with slogans, so both need filtering out.
    """
    if not docs:
        return ""
    keyset = set(keyword_words)
    for doc in sorted(_news_first(docs), key=lambda d: d.publish_time):
        for sent in _sentences(doc.content)[:2]:
            if len(sent) >= _MIN_CAUSE_LEN and any(kw in sent for kw in keyset):
                return sent + "。"
    earliest = min(docs, key=lambda d: d.publish_time)
    sents = _sentences(earliest.content) or _sentences(earliest.title)
    return sents[0] + "。" if sents else earliest.title


def _is_translit_fragment(word: str) -> bool:
    """A person-tagged token that starts with no Chinese surname — i.e. a piece of a
    transliterated name rather than a complete Chinese one."""
    return bool(word) and word[0] not in _SURNAMES and len(word) <= 3


def _merge_person_runs(tagged: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Rejoin transliterated names that jieba split across tokens (斯卡洛尼 → 斯卡 + 洛尼).

    Only fragments are merged, never two complete Chinese names: adjacent `nr` tokens are
    just as often two *different* people (「#王一博##肖战#」 → 王一博 + 肖战), and merging
    those fabricates a person who doesn't exist.  A Chinese name starts with a surname and
    jieba already segments it correctly, so surname-initial tokens are left alone.
    """
    merged: list[tuple[str, str]] = []
    i = 0
    while i < len(tagged):
        word, flag = tagged[i]
        if flag in _PERSON_TAGS and _is_translit_fragment(word):
            j = i + 1
            while (
                j < len(tagged)
                and tagged[j][1] in _PERSON_TAGS
                and _is_translit_fragment(tagged[j][0])
                and len(word) + len(tagged[j][0]) <= 5
            ):
                word += tagged[j][0]
                j += 1
            merged.append((word, "nr"))
            i = j
        else:
            merged.append((word, flag))
            i += 1
    return merged


def _entities(docs: list[Document]) -> tuple[Counter, Counter, dict[str, Counter]]:
    """Place/person name frequencies plus each word's full part-of-speech tag histogram.

    The tag histogram is what lets `_select_people` reject words jieba only *sometimes*
    calls a person (高盛 as an org, 覃塘区 as a place) — a single `nr` sighting is not
    enough evidence on its own.
    """
    places: Counter[str] = Counter()
    people: Counter[str] = Counter()
    tag_counts: dict[str, Counter] = defaultdict(Counter)
    for doc in docs:
        text = (doc.title + " " + doc.content)[: _NER_CHARS]
        tagged = _merge_person_runs([(w.word, w.flag) for w in pseg.cut(text)])
        previous = ""
        for word, flag in tagged:
            if word.strip() and all(ch in _SKIP_WHEN_TRACKING for ch in word):
                continue  # quotes/brackets: keep `previous` pointing at the real word
            if len(word) < _MIN_NAME_LEN:
                previous = word
                continue
            # A storm name sits right after 台风/飓风; record it as a non-person reading so
            # the tag histogram outvotes any stray `nr` sighting elsewhere.
            if previous.endswith(_STORM_INTRODUCERS):
                tag_counts[word]["storm"] += 1
            else:
                tag_counts[word][flag] += 1
                if flag in _PLACE_TAGS:
                    places[word] += 1
                elif flag in _PERSON_TAGS and word not in _MEDIA_AUTHORS:
                    people[word] += 1
            previous = word
    return places, people, tag_counts


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
    places, people, tag_counts = _entities(docs)

    location_list = _dedupe_substrings([w for w, _ in places.most_common()])[:top_locations]
    people_list = _select_people(people, places, tag_counts, set(keyword_words), top_people)

    return {
        "summary": _summary(docs, keyword_words, max_summary_sentences),
        "cause": _cause(docs, keyword_words),
        "location": "、".join(location_list) if location_list else None,
        "people": people_list,
    }


def _select_people(
    people: Counter,
    places: Counter,
    tag_counts: dict[str, Counter],
    keyword_set: set[str],
    top_people: int,
) -> list[str]:
    """Filter jieba's noisy `nr` candidates into a clean 涉及人物 list.

    jieba readily mistags domain terms (洪水、白银、利多), typhoon names, orgs (高盛) and
    places (覃塘区) as person names.  Four filters, each rejecting a distinct error class:
      * event keywords are topic terms, never "people";
      * a word jieba *ever* tagged as a place or an org is not a person, whatever it was
        tagged elsewhere;
      * `nr` must be the dominant reading of the word, not an occasional slip;
      * it must look like a name — a Chinese surname start, or a transliteration.
    Prefer names seen in ≥2 posts (one-off mistags rarely repeat), relaxing only if that
    leaves nothing.
    """
    def _is_name(w: str) -> bool:
        if w in keyword_set or w in places or w in _NON_PERSON_WORDS:
            return False
        if w.endswith(_PLACE_SUFFIXES):
            return False
        tags = tag_counts.get(w, Counter())
        if any(tags[t] for t in _ORG_TAGS | _PLACE_TAGS) or tags["storm"]:
            return False
        total = sum(tags.values())
        if total and sum(tags[t] for t in _PERSON_TAGS) / total < _PERSON_TAG_DOMINANCE:
            return False
        # Chinese personal name: 2–4 chars starting with a common surname.
        if 2 <= len(w) <= 4 and w[0] in _SURNAMES:
            return True
        # Transliterated foreign name (梅西/特朗普/斯卡洛尼): no CJK surname.
        return 2 <= len(w) <= 5 and w[0] not in _SURNAMES and _looks_foreign(w)

    def _pick(min_count: int) -> list[str]:
        return [w for w, c in people.most_common() if c >= min_count and _is_name(w)]

    return (_pick(2) or _pick(1))[:top_people]
