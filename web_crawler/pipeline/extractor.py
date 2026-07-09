# -*- coding: utf-8 -*-
"""
正文抽取策略。
所有策略统一实现同一接口: extract(url, html=None) -> dict | None
新闻站点 → NewspaperExtractor (newspaper3k)
社交页面 → ReadabilityExtractor (readability-lxml)
微博     → WeiboExtractor (weibo.com/ajax/statuses/show)
"""
from newspaper import Article
import requests
import re
import json
import os

_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


class NewspaperExtractor:
    """新闻站点正文抽取，基于 newspaper3k"""
    def __init__(self, headers: dict | None = None):
        self.headers = headers or _DEFAULT_HEADERS

    def extract(self, url: str, html: str | None = None) -> dict | None:
        try:
            article = Article(url, language="zh")
            if html:
                article.download(input_html=html)
            else:
                article.download()
            article.parse()
            if not article.text or len(article.text) < 30:
                return None
            return {
                "title": article.title.strip(),
                "content": article.text.strip(),
                "authors": article.authors,
                "publish_date": article.publish_date,
            }
        except Exception as e:
            print(f"  [NewspaperExtractor] {url}: {e}")
            return None


class ReadabilityExtractor:
    """社交页面正文抽取，基于 readability-lxml"""
    def __init__(self, headers: dict | None = None):
        self.headers = headers or _DEFAULT_HEADERS
        try:
            from readability import Document as _RDoc
        except ImportError:
            raise ImportError("需要安装: pip install readability-lxml")
        self._Document = _RDoc

    def extract(self, url: str, html: str | None = None) -> dict | None:
        try:
            if html is None:
                resp = requests.get(url, headers=self.headers, timeout=10)
                resp.raise_for_status()
                html = resp.text
            doc = self._Document(html)
            content = doc.summary()
            if not content or len(content) < 20:
                return None
            return {
                "title": doc.title(),
                "content": content,
                "authors": [],
                "publish_date": None,
            }
        except Exception as e:
            print(f"  [ReadabilityExtractor] {url}: {e}")
            return None


class WeiboExtractor:
    """微博正文抽取：帖子 URL → 调用 ajax/statuses/show → 返回结构化数据"""

    def __init__(self, headers: dict | None = None):
        self.headers = headers or {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/136.0.0.0 Safari/537.36 Edg/136.0.0.0"
            ),
        }
        self._session = None

    def set_session(self, session: requests.Session):
        """注入外部 session（例如爬虫的 session），实现 cookie 共享。

        注入后 _load_session() 优先返回此 session，不再加载 .env 中的 cookie。
        当爬虫主动刷新访客 cookie 或轮换账号时，正文提取器自动受益。
        """
        self._session = session

    def _load_session(self) -> requests.Session:
        """加载 Weibo cookie，用于 ajax/statuses/show 内容提取"""
        if self._session is not None:
            return self._session
        self._session = requests.Session()
        try:
            from dotenv import load_dotenv
            _env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
            load_dotenv(dotenv_path=_env_path)
            cookie = os.getenv("WEIBO_COOKIE", "")
            if cookie:
                for item in cookie.split(";"):
                    item = item.strip()
                    if "=" in item:
                        name, value = item.split("=", 1)
                        name = name.strip()
                        value = value.strip()
                        self._session.cookies.set(name, value, domain=".weibo.com")
                        self._session.cookies.set(name, value, domain=".weibo.cn")
                print(f"  [WeiboExtractor] 已加载 Cookie，长度={len(cookie)}")
            else:
                print("  [WeiboExtractor] 未读到 WEIBO_COOKIE，"
                      "ajax/statuses/show 将以未登录状态请求")
        except Exception as e:
            # 之前这里是 except Exception: pass，会把 NameError 等
            # 加载期间的真实错误静默吞掉，导致 session 悄悄变成无 cookie
            # 状态却毫无提示。改成打印出来，方便下次一眼看到问题。
            print(f"  [WeiboExtractor] Cookie 加载失败: {e}")
        return self._session

    def extract(self, url: str, html: str | None = None) -> dict | None:
        """从微博帖子 URL 中提取正文"""
        try:
            m = re.search(r'weibo\.com/\d+/([a-zA-Z0-9]+)', url)
            if not m:
                return None
            tweet_id = m.group(1)

            api_headers = self.headers.copy()
            api_headers["Referer"] = "https://weibo.com/"
            api_headers["Accept"] = "application/json, text/plain, */*"
            api_headers["Accept-Language"] = "zh-CN,zh;q=0.9,en;q=0.8"

            if html:
                data = json.loads(html) if isinstance(html, str) else html
            else:
                session = self._load_session()
                api_url = f"https://weibo.com/ajax/statuses/show?id={tweet_id}"
                resp = session.get(api_url, headers=api_headers, timeout=15)
                resp.raise_for_status()
                data = resp.json()

            if not data or "id" not in data:
                return None

            user = data.get("user", {})
            content = data.get("text_raw", "").replace("\u200b", "")
            if not content:
                return None
            return {
                "title": content[:50],
                "content": content,
                "authors": [user.get("screen_name", "")] if user.get("screen_name") else [],
                "publish_date": None,
            }
        except Exception as e:
            print(f"  [WeiboExtractor] {url}: {e}")
            return None


EXTRACTOR_MAP = {
    "news":   NewspaperExtractor(),
    "social": ReadabilityExtractor(),
    "weibo":  WeiboExtractor(),
}
