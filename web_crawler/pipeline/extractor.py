# -*- coding: utf-8 -*-
"""
正文提取策略族。
每个提取器实现同一接口: extract(url, html=None) -> dict | None
新闻网站 → NewspaperExtractor (newspaper3k)
社交平台 → ReadabilityExtractor (readability-lxml)
"""
from newspaper import Article
import requests
import re
_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}
class NewspaperExtractor:
    """新闻网站正文提取：基于 newspaper3k"""
    def __init__(self, headers: dict | None = None):
        self.headers = headers or _DEFAULT_HEADERS
    def extract(self, url: str, html: str | None = None) -> dict | None:
        """下载 + 解析，返回文章结构化数据或 None"""
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
    """社交平台正文提取：基于 readability-lxml"""
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
    """微博正文提取：解析 URL → 调 ajax/statuses/show → 返回结构化数据"""

    def __init__(self, headers: dict | None = None):
        self.headers = headers or {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/136.0.0.0 Safari/537.36 Edg/136.0.0.0"
            ),
        }
        self._session = None

    def _load_session(self) -> requests.Session:
        """从环境变量 WEIBO_COOKIE 读取 Cookie，创建带 Cookie 的会话"""
        if self._session is not None:
            return self._session
        self._session = requests.Session()
        cookie = os.getenv("WEIBO_COOKIE", "")
        if cookie:
            for pair in cookie.split(";"):
                pair = pair.strip()
                if "=" in pair:
                    k, v = pair.split("=", 1)
                    self._session.cookies.set(k.strip(), v.strip())
        return self._session

    def extract(self, url: str, html: str | None = None) -> dict | None:
        """从微博帖子 URL 中提取正文"""
        try:
            m = re.search(r'weibo\.com/\d+/([a-zA-Z0-9]+)', url)
            if not m:
                return None
            tweet_id = m.group(1)

            # 构建完整请求头（WeiboCrawler 同款）
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
