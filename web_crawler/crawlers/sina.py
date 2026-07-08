# -*- coding: utf-8 -*-
"""
新浪新闻爬虫。
只负责新浪搜索接口的对接和反爬处理，不涉及内容提取和清洗。
"""
import time
from urllib.parse import quote
import requests
from crawlers import register
SEARCH_API_URL = "https://search.sina.com.cn/api/search"
VALID_DOC_TYPES = {"news"}
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}
@register("sina")
class SinaCrawler:
    """新浪新闻爬虫"""
    display_name = "新浪新闻"
    extractor_type = "news"
    def __init__(self, request_interval: float = 1.5):
        self.request_interval = request_interval
    def search(self, keyword: str, page: int = 1, size: int = 10) -> list[dict]:
        """调用新浪JSON搜索接口，返回候选文章列表"""
        params = {
            "q": keyword, "tp": "news", "sort": "0",
            "page": page, "size": size, "from": "search_result",
        }
        headers = {**HEADERS, **{
            "accept": "application/json, text/plain, */*",
            "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
            "referer": f"https://search.sina.com.cn/search?q={quote(keyword)}&tp=news",
        }}
        resp = requests.get(SEARCH_API_URL, headers=headers, params=params, timeout=10)
        resp.raise_for_status()
        payload = resp.json()
        if payload.get("code") != 0:
            print(f"  接口返回异常: {payload.get('message')}")
            return []
        items = payload.get("data", {}).get("list", []) or []
        candidates = []
        for item in items:
            if item.get("docType") not in VALID_DOC_TYPES:
                continue
            candidates.append({
                "url": item.get("url"),
                "title": item.get("title"),
                "ctime": item.get("ctime"),
                "media_show": item.get("media_show"),
            })
        return candidates
    def search_multi_page(self, keyword: str, max_pages: int = 3, size: int = 50) -> list[dict]:
        """翻页拉取"""
        all_candidates = []
        for page in range(1, max_pages + 1):
            candidates = self.search(keyword, page=page, size=size)
            if not candidates:
                break
            all_candidates.extend(candidates)
            time.sleep(self.request_interval)
        return all_candidates
