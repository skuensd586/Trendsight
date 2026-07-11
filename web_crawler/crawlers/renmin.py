# -*- coding: utf-8 -*-
"""
人民网新闻爬虫。
"""
import random
import re
import time
import requests
from crawlers import register
from utils.logger import get_logger
from utils.retry import retry_with_backoff

log = get_logger("renmin")

SEARCH_URL = "http://search.people.cn/search-platform/front/search"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    " AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
    " AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
]

_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html_tags(text: str) -> str:
    """人民网搜索接口返回的 title/content 里带高亮 <em> 等标签，需要剥离"""
    if not text:
        return ""
    return _TAG_RE.sub("", text).replace("&nbsp;", " ").strip()


@register("renmin")
class RenminCrawler:
    """人民网新闻爬虫"""
    display_name = "人民网"
    extractor_type = "news"
    platform_code = "RM"

    def __init__(self, request_interval: float = 2.0):
        self.request_interval = request_interval
        self.session = requests.Session()

    def _sleep(self):
        time.sleep(
            max(0.5, self.request_interval + random.uniform(-0.5, 1))
        )

    @retry_with_backoff(max_attempts=3, base_delay=2)
    def _post(self, url, payload, timeout=15):
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json;charset=UTF-8",
            "Origin": "http://search.people.cn",
            "Referer": "http://search.people.cn/",
        }
        resp = self.session.post(url, json=payload, headers=headers, timeout=timeout)
        resp.raise_for_status()
        return resp.json()

    def _parse_search_json(self, data):
        results = []
        records = (data or {}).get("data", {}).get("records")
        if records is None:
            # 接口没有像新浪/澎湃那样统一的 code 字段，records 缺失就视为结构异常
            log.warning("人民网接口返回结构异常，原始返回: %s", data)
            return results

        for item in records:
            url = item.get("url")
            if not url:
                continue
            title = _strip_html_tags(item.get("title") or "")
            summary = _strip_html_tags(item.get("content") or "")
            author = _strip_html_tags(item.get("author") or "") or None
            display_time_ms = item.get("displayTime")
            ctime = display_time_ms / 1000 if isinstance(display_time_ms, (int, float)) else display_time_ms
            # originName 是转载来源（如"新华社""广西日报"），belongsName 只是栏目分类，
            # 不应作为来源填充；originalName 实测长期为 null，放最后兜底
            results.append({
                "url": url,
                "title": title,
                "content": summary,
                "ctime": ctime,
                "author": author,
                "media_show": item.get("originName") or item.get("originalName") or item.get("belongsName") or "人民网",
            })
        log.info("解析人民网搜索结果 %d 条", len(results))
        return results

    def search(self, keyword: str, page: int = 1, size: int = 10):
        payload = {
            "endTime": 0,
            "hasContent": True,
            "hasTitle": True,
            "isFuzzy": True,
            "key": keyword,
            "limit": size,
            "page": page,
            "sortType": 0,
            "startTime": 0,
            "type": 0,
        }
        try:
            data = self._post(SEARCH_URL, payload)
            return self._parse_search_json(data)
        except Exception as e:
            log.error("人民网搜索失败: %s", e)
            return []

    def search_multi_page(self, keyword: str, max_pages: int = 3, size: int = 100):
        results = []
        seen = set()
        for page in range(1, max_pages + 1):
            items = self.search(keyword, page, size)
            if not items:
                break
            for item in items:
                url = item.get("url")
                if url and url not in seen:
                    seen.add(url)
                    results.append(item)
                if len(results) >= size:
                    return results
            self._sleep()
        return results