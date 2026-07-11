# -*- coding: utf-8 -*-
"""
数据清洗流水线。
职责：将提取器产出的原始正文转为标准化文档。

主要功能：
  - HTML 实体还原与零宽字符过滤
  - 平台特定 boilerplate 去除（文末声明等）
  - 多余空行归并
  - 组装标准化文档字典（含 SimHash 指纹）
"""
import html
import hashlib
import re
from datetime import datetime
from simhash import Simhash
BOILERPLATE_PATTERNS: dict[str, list[str]] = {
    "新浪新闻": [
        "特别声明：以上文章内容仅代表作者本人观点，不代表新浪网观点或立场。"
        "如有关于作品内容、版权或其它问题请于作品发表后的30日内与新浪网联系。",
        "特别声明：以上文章内容仅代表作者本人观点，不代表新浪网观点或立场。"
        "如关于作品内容、版权或其它问题请于作品发表后的30日内与新浪网联系。",
        "声明：本文内容仅代表作者个人观点，与新浪网无关。",
    ],
}
_EXCESS_NEWLINES = re.compile(r'\n{3,}')
def clean_content(text: str, platform: str = "新浪新闻") -> str:
    """噪音过滤：HTML实体还原、零宽字符、boilerplate、空行归一化"""
    if not text or not text.strip():
        return ""
    text = html.unescape(text)
    text = re.sub(r'[\u200b\u200c\u200d\u200e\u200f\ufeff]', '', text)
    for pattern in BOILERPLATE_PATTERNS.get(platform, []):
        text = text.replace(pattern, "")
    text = _EXCESS_NEWLINES.sub('\n\n', text)
    lines = [line.strip() for line in text.split('\n')]
    return '\n'.join(lines).strip()
def _parse_publish_time(value) -> datetime | None:
    """Parse publish_time from various formats to a datetime object.

    Supports:
    - datetime object: returned as-is
    - int or float: treated as Unix timestamp
    - numeric str: treated as Unix timestamp after int conversion
    - str like "20260710084820": parsed as YYYYmmddHHMMSS
    - str like "2024-06-18 13:43:00": parsed as ISO format
    - str like "2024-06-18 13:43": parsed as ISO format without seconds
    - None / unparseable: returns None (caller falls through to datetime.now())
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value)
    s = str(value).strip()
    if s.isdigit():
        try:
            return datetime.fromtimestamp(int(s))
        except (OSError, ValueError, OverflowError):
            pass
    for fmt in ("%Y%m%d%H%M%S", "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def build_document(raw: dict, candidate: dict, platform: str = "新浪新闻", platform_code: str = "XX") -> dict:
    """
    组装标准文档字典。
    raw — extractor.extract() 输出
    candidate — crawler.search() 输出
    """
    content = clean_content(raw["content"], platform=platform)
    if candidate.get("ctime"):
        parsed = _parse_publish_time(candidate["ctime"])
        publish_time = parsed if parsed is not None else (raw.get("publish_date") or datetime.now())
    else:
        publish_time = raw.get("publish_date") or datetime.now()
    author = (
        ", ".join(raw.get("authors", []))
        or candidate.get("media_show")
        or (candidate.get("_raw") or {}).get("author", {}).get("name")
        or None
    )
    url_hash = hashlib.md5(candidate["url"].encode()).hexdigest()[:8]
    ts = publish_time.strftime("%Y%m%d%H%M%S")
    return {
        "doc_id": f"{platform_code}{ts}{url_hash}",
        "source_platform": platform,
        "source_url": candidate["url"],
        "title": raw["title"] or candidate.get("title"),
        "content": content,
        "author": author,
        "publish_time": publish_time,
        "crawl_time": datetime.now(),
        "content_hash": str(Simhash(content).value),
        "clean_status": "raw",
         "verification_type": candidate.get("verification_type") or raw.get("verification_type"),
        "event_id": None,
    }
