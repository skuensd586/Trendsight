# -*- coding: utf-8 -*-
"""
微博爬虫。
使用 m.weibo.cn 移动端 API 搜索帖子，支持：
  - 访客 Cookie 自动刷新（免手动登录）
  - 搜索结果翻页
  - 单条帖子正文提取（ajax/statuses/show）
  - 评论分页爬取（ajax/statuses/buildComments）
  - 桌面版 s.weibo.com 降级回退

注意：需要有效的 Cookie（含 SUB 字段），可通过 crawl_config.json 配置。
"""
import json
import random
import re
import time
import uuid
from datetime import datetime
from urllib.parse import quote

import requests
from crawlers import register

# 随机 UA 池，降低被反爬识别的概率
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36 Edg/136.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 14; SM-S9180) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.113 Mobile/Safari/537.36",
]
DEFAULT_INTERVAL = 1.5


def _decode_base62(b62_str: str) -> int:
    """Base62 解码（微博 mid 编码使用）"""
    charset = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    num = 0
    for c in b62_str:
        num = num * 62 + charset.index(c)
    return num


def url_to_mid(url_seg: str) -> int:
    """将微博帖子的 base62 URL 段转为数值 mid，用于评论 API"""
    result = ""
    for i in range(len(url_seg), 0, -4):
        start = max(i - 4, 0)
        segment = url_seg[start:i]
        num = str(_decode_base62(segment))
        if start != 0:
            num = num.zfill(7)
        result = num + result
    return int(result)


def _parse_weibo_time(s: str) -> str:
    """将微博 API 返回的 RFC 2822 时间格式转为 YYYY-MM-DD HH:mm:ss"""
    try:
        dt = datetime.strptime(s, "%a %b %d %H:%M:%S %z %Y")
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return s

@register("weibo")
class WeiboCrawler:
    """微博爬虫"""

    display_name = "微博"
    extractor_type = "weibo"

    def __init__(self, request_interval: float = DEFAULT_INTERVAL, cookie: str = None):
        self.request_interval = request_interval
        self.session = self._init_session(cookie)

    # ---- Session / Cookie ----

    def _init_session(self, cookie: str | None) -> requests.Session:
        session = requests.Session()
        if cookie:
            for pair in cookie.split(";"):
                pair = pair.strip()
                if "=" in pair:
                    k, v = pair.split("=", 1)
                    session.cookies.set(k.strip(), v.strip())
        try:
            session.get("https://m.weibo.cn",
                        headers=self._headers("https://m.weibo.cn/"), timeout=10)
        except requests.RequestException:
            pass
        return session

    def _sleep(self, multiplier: float = 1.0):
        """随机化休眠间隔，模拟人类行为避免触发反爬"""
        base = self.request_interval * multiplier
        jitter = random.uniform(-0.3, 0.6)
        time.sleep(max(0.3, base + jitter))

    def _headers(self, referer: str | None = None) -> dict:
        return {
            "User-Agent": random.choice(USER_AGENTS),
            "Referer": referer or "https://weibo.com/",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Connection": "keep-alive",
        }

    def _get_json(self, url: str, params: dict | None = None,
                  referer: str | None = None) -> dict | None:
        try:
            resp = self.session.get(url, params=params,
                                    headers=self._headers(referer), timeout=15)
            resp.raise_for_status()
            return resp.json()
        except (requests.RequestException, json.JSONDecodeError) as e:
            print(f"  [WeiboCrawler] {url} -> {e}")
            return None

    def _get_html(self, url: str, params: dict | None = None,
                  referer: str | None = None) -> str | None:
        try:
            resp = self.session.get(url, params=params,
                                    headers=self._headers(referer), timeout=15)
            resp.raise_for_status()
            return resp.text
        except requests.RequestException as e:
            print(f"  [WeiboCrawler] {url} -> {e}")
            return None

    # ---- 访客 Cookie 自动刷新 ----

    def _try_refresh_visitor_cookie(self) -> bool:
        """尝试通过新浪访客系统获取临时 cookie（无需手动登录）"""
        try:
            # 1. 访问 m.weibo.cn 获取初始 cookies
            self.session.get(
                "https://m.weibo.cn/",
                headers=self._headers("https://m.weibo.cn/"), timeout=10,
            )
            # 2. 生成随机 tid 模拟浏览器指纹
            tid = uuid.uuid4().hex
            # 3. POST 到访客生成接口
            post_headers = {
                **self._headers("https://m.weibo.cn/"),
                "Content-Type": "application/x-www-form-urlencoded",
                "X-Requested-With": "XMLHttpRequest",
            }
            data = (
                f"cb=visitor_gray_callback&from=weibo"
                f"&return_url=https://m.weibo.cn/&tid={tid}&ver=20250916"
            )
            resp = self.session.post(
                "https://passport.weibo.com/visitor/genvisitor2",
                data=data, headers=post_headers, timeout=10,
            )
            # 4. 从 JSONP 响应中提取 SUB cookie
            text = resp.text
            if '"retcode":20000000' in text:
                m = re.search(r'"sub"\s*:\s*"([^"]+)"', text)
                if m:
                    sub = m.group(1).encode().decode("unicode_escape")
                    self.session.cookies.set("SUB", sub, domain=".weibo.com")
                    return True
            return False
        except Exception as e:
            print(f"  [WeiboCrawler] 访客 cookie 获取失败: {e}")
            return False

    # ---- 搜索入口 ----

    def search(self, keyword: str, page: int = 1) -> list[dict]:
        """使用 m.weibo.cn 移动端 API 搜索
        自动检测 cookie 过期并尝试访客 cookie 刷新。
        """
        url = "https://m.weibo.cn/api/container/getIndex"
        params = {"type": "all", "query": keyword, "page": page}
        headers = self._headers(referer=f"https://m.weibo.cn/search?q={quote(keyword)}")
        headers["X-Requested-With"] = "XMLHttpRequest"

        data = None
        for attempt in range(2):
            try:
                resp = self.session.get(url, params=params, headers=headers, timeout=15)
                resp.raise_for_status()
                data = resp.json()
            except (requests.RequestException, json.JSONDecodeError) as e:
                print(f"  [WeiboCrawler] m.weibo.cn 搜索失败: {e}")
                return []

            if data.get("ok") == 1 and "data" in data:
                break  # 搜索成功

            if data.get("ok") == -100 and attempt == 0:
                print(f"  [WeiboCrawler] Cookie 过期，尝试自动刷新访客 cookie...")
                if self._try_refresh_visitor_cookie():
                    self._sleep(1.5)
                    continue  # 重试搜索
                print(f"  [WeiboCrawler] 访客 cookie 刷新失败")

            # 其他错误情况，不再重试
            return []

        if not data or data.get("ok") != 1:
            return []

        cards = data["data"].get("cards", [])
        candidates, seen = [], set()
        for card in cards:
            mblog = card.get("mblog")
            if mblog:
                entry = self._mblog_to_candidate(mblog)
                if entry and entry["tweet_id"] not in seen:
                    seen.add(entry["tweet_id"])
                    candidates.append(entry)
            for sub in card.get("card_group", []):
                sub_mblog = sub.get("mblog")
                if sub_mblog:
                    entry = self._mblog_to_candidate(sub_mblog)
                    if entry and entry["tweet_id"] not in seen:
                        seen.add(entry["tweet_id"])
                        candidates.append(entry)
        return candidates

    def _search_desktop_fallback(self, keyword: str, page: int = 1) -> list[dict]:
        """s.weibo.com 桌面版搜索（备选降级通道）"""
        html = self._get_html("https://s.weibo.com/weibo",
                              params={"q": keyword, "page": page},
                              referer="https://s.weibo.com/")
        if not html:
            return []
        candidates, seen = [], set()
        for m in re.finditer(r"weibo\.com/(\d+)/([a-zA-Z0-9]+)\?refer_flag=1001030103_", html):
            uid, tid = m.group(1), m.group(2)
            if tid not in seen:
                seen.add(tid)
                candidates.append({"url": f"https://weibo.com/{uid}/{tid}",
                                   "tweet_id": tid, "uid": uid})
        return candidates

    def _mblog_to_candidate(self, mblog: dict) -> dict | None:
        mblogid = mblog.get("mblogid")
        user = mblog.get("user", {})
        uid = user.get("id", "")
        if not mblogid or not uid:
            return None
        return {
            "url": f"https://weibo.com/{uid}/{mblogid}",
            "tweet_id": mblogid,
            "uid": str(uid),
        }

    def search_multi_page(self, keyword: str, max_pages: int = 3) -> list[dict]:
        all_candidates = []
        for page in range(1, max_pages + 1):
            candidates = self.search(keyword, page=page)
            if not candidates:
                if page == 1:
                    # 移动端 API 不可用，降级到桌面版
                    print(f"  [WeiboCrawler] 移动端搜索无结果，回退到 s.weibo.com...")
                    self._sleep(1.5)
                    candidates = self._search_desktop_fallback(keyword, page=page)
                    if not candidates:
                        print(f"  [WeiboCrawler] 两种搜索源均无返回，可能被限流")
                if not candidates:
                    break
            all_candidates.extend(candidates)
            self._sleep()
        return all_candidates
    # ---- 评论爬取 (ajax/statuses/buildComments) ----

    def fetch_comments(self, tweet_mid: int, uid: str,
                       max_count: int = 100) -> list[dict]:
        comments = []
        max_id = ""
        page_size = 20

        while len(comments) < max_count:
            params = {"flow": 1, "is_reload": 1, "id": tweet_mid,
                      "is_show_bulletin": 2, "is_mix": 0, "count": page_size,
                      "uid": uid, "fetch_level": 0, "locale": "zh-CN"}
            if max_id:
                params["max_id"] = max_id

            data = self._get_json("https://weibo.com/ajax/statuses/buildComments",
                                  params=params,
                                  referer=f"https://weibo.com/{uid}/")
            if not data or "data" not in data:
                break

            items = data["data"]
            if not items:
                break

            for item in items:
                if len(comments) >= max_count:
                    break
                raw_src = item.get("source", "")
                ip_loc = raw_src[2:] if raw_src.startswith("\u6765\u81ea") else raw_src

                created_at = _parse_weibo_time(item.get("created_at", ""))
                try:
                    pub_time = datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S")
                except (ValueError, TypeError):
                    pub_time = None

                comments.append({
                    "comment_id": str(item.get("id")),
                    "parent_post_id": str(item.get("mid", "")),
                    "content": item.get("text_raw", "").replace("\u200b", ""),
                    "author": item.get("user", {}).get("screen_name", ""),
                    "user_id": str(item.get("user", {}).get("id", "")),
                    "publish_time": pub_time,
                    "likes_count": item.get("like_counts", 0),
                    "commenter_ip": ip_loc,
                    "source_url": f"https://weibo.com/comment/{item.get('id')}",
                })

            max_id = data.get("max_id", 0)
            if not max_id:
                break
            self._sleep()

        return comments