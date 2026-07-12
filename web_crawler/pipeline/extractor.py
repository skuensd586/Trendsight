# -*- coding: utf-8 -*-
"""
正文内容提取器
统一接口: extract(url, html=None) -> dict | None
新闻  | NewspaperExtractor (newspaper3k)
通用  | ReadabilityExtractor (readability-lxml)
微博  | WeiboExtractor
知乎  | ZhihuExtractor
"""
from newspaper import Article
from crawlers.weibo import _classify_credibility
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
    """基于 newspaper3k 的正文抽取器"""
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
    """基于 readability-lxml 的正文抽取器"""
    def __init__(self, headers: dict | None = None):
        self.headers = headers or _DEFAULT_HEADERS
        try:
            from readability import Document as _RDoc
        except ImportError:
            raise ImportError("????: pip install readability-lxml")
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
    """微博正文抽取器: URL → ajax/statuses/show → 获取帖子内容"""

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
                "verification_type": _classify_credibility(user),
                "publish_date": None,
                "repost_count": data.get("reposts_count"),
                "like_count": data.get("attitudes_count"),
                "comment_count": data.get("comments_count"),
            }
        except Exception as e:
            print(f"  [WeiboExtractor] {url}: {e}")
            return None

class ZhihuExtractor:
    """知乎回答/文章正文抽取。
    优先使用 crawler.fetch_answers() 里已经带回的 _raw 数据（html 参数传入，
    避免重复请求）；没有时才回退到单条回答详情接口。
    """

    def __init__(self, headers: dict | None = None):
        self.headers = headers or _DEFAULT_HEADERS
        self._session = None

    def set_session(self, session: requests.Session):
        """注入爬虫的 session，实现 cookie 共享（与 WeiboExtractor 一致）"""
        self._session = session

    def _load_session(self) -> requests.Session:
        if self._session is not None:
            return self._session
        self._session = requests.Session()
        try:
            from dotenv import load_dotenv
            _env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
            load_dotenv(dotenv_path=_env_path)
            cookie = os.getenv("ZHIHU_COOKIE", "")
            if cookie:
                for item in cookie.split(";"):
                    item = item.strip()
                    if "=" in item:
                        name, value = item.split("=", 1)
                        self._session.cookies.set(name.strip(), value.strip(), domain=".zhihu.com")
                print(f"  [ZhihuExtractor] 已加载 Cookie，长度={len(cookie)}")
        except Exception as e:
            print(f"  [ZhihuExtractor] Cookie 加载失败: {e}")
        return self._session

    @staticmethod
    def _strip_html(html: str) -> str:
        text = re.sub(r"<[^>]+>", "", html or "")
        return text.replace("&nbsp;", " ").strip()

    def extract(self, url: str, html: str | None = None) -> dict | None:
        try:
            # ── 专栏文章（zhuanlan.zhihu.com/p/xxx）──
            m_article = re.search(r"zhuanlan\.zhihu\.com/p/(\d+)", url)
            if m_article:
                article_id = m_article.group(1)
                session = self._load_session()
                page_headers = self.headers.copy()
                page_headers["Referer"] = url
                resp = session.get(url, headers=page_headers, timeout=15)
                resp.raise_for_status()
                page_html = resp.text
                reader = ReadabilityExtractor()
                result = reader.extract(url, html=page_html)
                if result and result.get("content"):
                    text = self._strip_html(result["content"])
                    text = re.sub(r"</?p[^>]*>", "\n", text)
                    text = re.sub(r"<br\s*/?>", "\n", text)
                    text = self._strip_html(text)
                    text = re.sub(r"\n{3,}", "\n\n", text).strip()

                    # 从页面内嵌的 initialState 里取互动数据，避免额外请求触发 403
                    like_count, comment_count = None, None
                    try:
                        m_data = re.search(r'<script id="js-initialData"[^>]*>(.*?)</script>', page_html, re.DOTALL)
                        if m_data:
                            initial_data = json.loads(m_data.group(1))
                            articles = initial_data.get("initialState", {}).get("entities", {}).get("articles", {})
                            article_data = articles.get(article_id, {})
                            like_count = article_data.get("voteupCount")
                            comment_count = article_data.get("commentCount")
                    except Exception as e:
                        print(f"  [ZhihuExtractor] 页面互动数据解析失败 {url}: {e}")

                    return {
                        "title": result["title"],
                        "content": text,
                        "authors": result.get("authors", []),
                        "verification_type": "普通用户",
                        "publish_date": None,
                        "like_count": like_count,
                        "comment_count": comment_count,
                    }
                return None

            # html 参数复用 crawler 里带回的 _raw 字典（kind=answer 的 candidate["_raw"]）
            if html and isinstance(html, dict):
                item = html
            else:
                m = re.search(r"answer/(\d+)", url)
                if not m:
                    return None
                answer_id = m.group(1)
                session = self._load_session()
                api_url = f"https://www.zhihu.com/api/v4/answers/{answer_id}"
                api_headers = self.headers.copy()
                api_headers["Referer"] = "https://www.zhihu.com/"
                resp = session.get(api_url, params={"include": "content,author"},
                                   headers=api_headers, timeout=15)
                resp.raise_for_status()
                item = resp.json()

            content = self._strip_html(item.get("content", ""))
            if not content or len(content) < 10:
                return None

            author = item.get("author", {})
            question = item.get("question", {})
            title = question.get("title") or content[:50]

            from crawlers.zhihu import _classify_credibility, _parse_zhihu_time
            return {
                "title": title,
                "content": content,
                "authors": [author.get("name", "")] if author.get("name") else [],
                "verification_type": _classify_credibility(author),
                "publish_date": _parse_zhihu_time(item.get("created_time")),
                "like_count": item.get("voteup_count"),
                "comment_count": item.get("comment_count"),
            }
        except Exception as e:
            print(f"  [ZhihuExtractor] {url}: {e}")
            return None

EXTRACTOR_MAP = {
    "news":   NewspaperExtractor(),
    "social": ReadabilityExtractor(),
    "weibo":  WeiboExtractor(),
    "zhihu":  ZhihuExtractor(),
}
