# -*- coding: utf-8 -*-
"""
新浪新闻爬虫。
双模式：
  1. 有微博登录 cookie → 走搜索 API（精准搜索）
  2. 无 cookie → 走滚动 API + 关键词过滤（回退）
"""
import random
from urllib.parse import quote
import time
import requests
from crawlers import register
from utils.logger import get_logger
from utils.retry import retry_with_backoff

log = get_logger("sina")

SEARCH_API_URL = "https://search.sina.com.cn/api/search"
ROLL_API_URL = "https://feed.mix.sina.com.cn/api/roll/get"

# 滚动 API 新闻频道配置
NEWS_CHANNELS = {
    2509: "综合新闻",
    2510: "国内要闻",
    2511: "国际要闻",
    2512: "社会新闻",
}

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36 Edg/150.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 14; SM-S9180) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.113 Mobile/Safari/537.36",
]


@register("sina")
class SinaCrawler:
    """新浪新闻爬虫"""
    display_name = "新浪新闻"
    extractor_type = "news"
    platform_code = "SN"

    def __init__(self, request_interval: float = 2.0, cookie: str | None = None):
        self.request_interval = request_interval
        self.session = requests.Session()
        if cookie:
            self._cookie_header = cookie
            self._has_cookie = True
        else:
            self._cookie_header = None
            self._has_cookie = False

    @staticmethod
    def _parse_cookie(cookie_str: str) -> dict:
        """解析 cookie 字符串为字典"""
        result = {}
        for part in cookie_str.split(";"):
            part = part.strip()
            if "=" in part:
                key, value = part.split("=", 1)
                result[key.strip()] = value.strip()
        return result

    def _sleep(self, multiplier: float = 1.0):
        base = self.request_interval * multiplier
        jitter = random.uniform(-0.3, 0.6)
        time.sleep(max(0.3, base + jitter))

    # ────── 模式A：搜索 API（有 cookie）──────

    @retry_with_backoff(max_attempts=3, base_delay=2.0)
    def _get_with_retry(self, url, headers=None, params=None, timeout=15):
        """带指数退避重试的 GET 请求；429/5xx/超时/连接错误会自动重试"""
        resp = self.session.get(url, headers=headers, params=params, timeout=timeout)
        resp.raise_for_status()
        return resp

    def _search_with_cookie(self, keyword: str, page: int = 1, size: int = 10) -> list[dict]:
        """使用微博登录态调用搜索 API"""
        params = {
            "q": keyword, "tp": "mix", "sort": "0",
            "page": page, "size": size, "from": "search_result",
        }
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Cookie": self._cookie_header,
            "Referer": f"https://search.sina.com.cn/search?q={quote(keyword)}&tp=mix&sort=0&page={page}&size={size}&from=search_result",
        }
        try:
            resp = self._get_with_retry(SEARCH_API_URL, headers=headers, params=params)
            payload = resp.json()
        except requests.HTTPError as e:
            status = getattr(e.response, "status_code", None)
            if status == 429:
                log.warning("cookie 可能已过期，重试后仍返回 429")
            else:
                log.error("搜索请求失败（已重试）: %s", e)
            return []
        except requests.RequestException as e:
            log.error("搜索请求失败（已重试）: %s", e)
            return []

        if payload.get("code") != 0:
            log.warning("接口返回异常: %s", payload.get("message"))
            return []

        items = payload.get("data", {}).get("list", []) or []
        candidates = []
        for item in items:
            candidates.append({
                "url": item.get("url"),
                "title": item.get("title"),
                "ctime": item.get("ctime"),
                "media_show": item.get("media_show"),
            })
        return candidates

    # ────── 模式B：滚动 API（无 cookie）──────

    def _fetch_channel(self, lid: int, num: int = 50) -> list[dict]:
        """从单个频道拉取最新新闻"""
        params = {
            "pageid": "153",
            "lid": str(lid),
            "num": str(min(num, 50)),
        }
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Referer": "https://www.sina.com.cn/",
        }
        try:
            resp = self._get_with_retry(ROLL_API_URL, headers=headers, params=params)
            payload = resp.json()
        except requests.RequestException as e:
            log.error("频道 %s 请求失败（已重试）: %s", lid, e)
            return []
        result = payload.get("result", {})
        if result.get("status", {}).get("code") != 0:
            return []
        items = result.get("data", [])
        log.info("频道 lid=%s 拉到 %d 条", lid, len(items))
        return items

    def _keyword_match(self, keyword: str, item: dict) -> bool:
        """检查文章是否匹配关键词"""
        title = item.get("title", "") or ""
        kw_field = item.get("keywords", "") or ""
        summary = item.get("summary", "") or ""
        keyword_lower = keyword.lower()
        if keyword_lower in title.lower():
            return True
        if keyword_lower in kw_field.lower():
            return True
        if keyword_lower in summary.lower():
            return True
        return False

    def _search_without_cookie(self, keyword: str, size: int = 10) -> list[dict]:
        """通过批量获取最新新闻并过滤关键词"""
        all_items = []
        for lid in NEWS_CHANNELS:
            items = self._fetch_channel(lid, num=50)
            all_items.extend(items)
            self._sleep(multiplier=1.0)
        seen_urls = set()
        candidates = []
        for item in all_items:
            url = item.get("url", "")
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            if not self._keyword_match(keyword, item):
                continue
            candidates.append({
                "url": url,
                "title": item.get("title", ""),
                "ctime": item.get("ctime", ""),
                "media_show": item.get("media_name", ""),
            })
            if len(candidates) >= size:
                break
        return candidates

    # ────── 统一入口 ──────

    def search(self, keyword: str, page: int = 1, size: int = 10) -> list[dict]:
        """搜索入口：有 cookie 走搜索 API，否则走滚动 API"""
        if self._has_cookie:
            return self._search_with_cookie(keyword, page=page, size=size)
        else:
            # 无 cookie 时忽略 page 参数，直接批量返回最多 size 条匹配
            return self._search_without_cookie(keyword, size=size)

    def search_multi_page(self, keyword: str, max_pages: int = 3, size: int = 50) -> list[dict]:
        """多页搜索"""
        if self._has_cookie:
            all_candidates = []
            for page in range(1, max_pages + 1):
                candidates = self.search(keyword, page=page, size=size)
                if not candidates:
                    break
                all_candidates.extend(candidates)
                self._sleep()
            return all_candidates
        else:
            return self.search(keyword, page=1, size=size)
