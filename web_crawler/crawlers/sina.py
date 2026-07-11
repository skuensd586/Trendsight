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
import os
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
        self._cooldowns = {}          # idx -> cooldown expiry timestamp
        self._current_idx = 0         # current active account index

        # 加载多账号池（主 cookie + SINA_COOKIE_2 / _3 / ...）
        self._cookie_pool = self._load_cookie_pool(cookie)

        active = self._get_active_cookie()
        if active:
            self._cookie_header = active
            self._has_cookie = True
            log.info("使用 Cookie，长度=%d, 前缀=%s...", len(active), active[:20])
        else:
            self._cookie_header = None
            self._has_cookie = False

        if len(self._cookie_pool) > 1:
            log.info("多账号模式：共 %d 个账号", len(self._cookie_pool))

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

    # ---- 多账号池 ----

    def _load_cookie_pool(self, primary: str | None) -> list[str]:
        """从参数 + 环境变量加载多账号 cookie 池（SINA_COOKIE_2 / _3 / ...）"""
        cookies = []
        if primary:
            cookies.append(primary)
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except ImportError:
            pass
        for i in range(2, 20):
            env_c = os.getenv(f"SINA_COOKIE_{i}")
            if env_c and env_c not in cookies:
                cookies.append(env_c)
        return cookies

    def _get_active_cookie(self) -> str | None:
        """返回当前账号的完整 cookie 字符串"""
        if self._cookie_pool and self._current_idx < len(self._cookie_pool):
            return self._cookie_pool[self._current_idx]
        return None

    def _rotate_account(self) -> bool:
        """切换到下一个未冷却的账号。当前账号先标记冷却 5 分钟。"""
        if len(self._cookie_pool) <= 1:
            return False

        # 当前账号进入冷却
        self._cooldowns[self._current_idx] = time.time() + 300

        for _ in range(len(self._cookie_pool) - 1):
            self._current_idx = (self._current_idx + 1) % len(self._cookie_pool)
            if self._cooldowns.get(self._current_idx, 0) <= time.time():
                self._cookie_header = self._cookie_pool[self._current_idx]
                log.info(" -> 轮换到账号 #%d/%d", self._current_idx + 1, len(self._cookie_pool))
                return True

        # 所有账号都在冷却中
        min_cd = min(self._cooldowns.get(i, 0) for i in range(len(self._cookie_pool)))
        wait = max(0, min_cd - time.time())
        log.warning("所有账号冷却中，需等待 %.0fs", wait)
        return False

    def _all_on_cooldown(self) -> bool:
        """账号池是否全部处于冷却中（用于判断要不要临时降级到无 cookie 模式）"""
        if not self._cookie_pool:
            return False
        now = time.time()
        return all(self._cooldowns.get(i, 0) > now for i in range(len(self._cookie_pool)))

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
        """使用微博登录态调用搜索 API。
        遇到 429（限流/cookie 疑似失效）或接口返回异常 code 时，
        自动轮换到池中下一个未冷却的账号重试，直到成功或账号轮完一圈。
        """
        attempts = max(1, len(self._cookie_pool))
        for attempt in range(attempts):
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
                    log.warning("账号 #%d 疑似 cookie 已过期（429，重试后仍失败）",
                               self._current_idx + 1)
                    if self._rotate_account():
                        continue
                    return []
                log.error("搜索请求失败（已重试）: %s", e)
                return []
            except requests.RequestException as e:
                log.error("搜索请求失败（已重试）: %s", e)
                return []

            if payload.get("code") != 0:
                log.warning("账号 #%d 接口返回异常: %s",
                           self._current_idx + 1, payload.get("message"))
                if self._rotate_account():
                    continue
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
        return []

    # ────── 模式B：滚动 API（无 cookie）──────

    def _fetch_channel(self, lid: int, num: int = 50, page: int = 1) -> list[dict]:
        """从单个频道拉取新闻（滚动 API 支持 page 翻页，每页最多 50 条）"""
        params = {
            "pageid": "153",
            "lid": str(lid),
            "num": str(min(num, 50)),
            "page": str(page),
        }
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Referer": "https://www.sina.com.cn/",
        }
        try:
            resp = self._get_with_retry(ROLL_API_URL, headers=headers, params=params)
            payload = resp.json()
        except requests.RequestException as e:
            log.error("频道 %s（page=%s）请求失败（已重试）: %s", lid, page, e)
            return []
        result = payload.get("result", {})
        if result.get("status", {}).get("code") != 0:
            return []
        items = result.get("data", [])
        log.info("频道 lid=%s page=%s 拉到 %d 条", lid, page, len(items))
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

    def _search_without_cookie(self, keyword: str, size: int = 10, page: int = 1) -> list[dict]:
        """拉取指定页的各频道新闻并过滤关键词（单页，供 search_multi_page 循环调用）"""
        all_items = []
        for lid in NEWS_CHANNELS:
            items = self._fetch_channel(lid, num=50, page=page)
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
        """搜索入口：有 cookie 走搜索 API，否则走滚动 API（两种模式都支持 page 翻页）。
        若账号池全部进入冷却（短期内都被限流/失效），临时降级到滚动 API 兜底。
        """
        if self._has_cookie:
            candidates = self._search_with_cookie(keyword, page=page, size=size)
            if not candidates and self._all_on_cooldown():
                log.info("[sina] 账号池全部冷却中，本次降级到滚动 API 兜底")
                return self._search_without_cookie(keyword, size=size, page=page)
            return candidates
        else:
            return self._search_without_cookie(keyword, size=size, page=page)

    def search_multi_page(self, keyword: str, max_pages: int = 3, size: int = 50) -> list[dict]:
        """多页搜索，两种模式都会实际翻页直到 max_pages 或提前收敛"""
        all_candidates = []
        seen_urls = set()
        for page in range(1, max_pages + 1):
            page_candidates = self.search(keyword, page=page, size=size)
            if not page_candidates:
                # 该页无结果：cookie 模式下通常代表搜索已翻到底
                break
            new_count = 0
            for c in page_candidates:
                url = c.get("url")
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                all_candidates.append(c)
                new_count += 1
            if new_count == 0:
                # 无 cookie 模式下滚动 API 对 page 的支持可能不稳定，
                # 一旦某页完全没有新增候选（说明已经在重复返回同一批数据），
                # 提前停止，避免空转到 max_pages 才结束
                log.info("[sina] page=%d 无新增候选，停止翻页", page)
                break
            self._sleep()
        return all_candidates