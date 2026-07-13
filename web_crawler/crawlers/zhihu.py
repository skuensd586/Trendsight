# -*- coding: utf-8 -*-
"""
知乎爬虫。

使用知乎 Web 端公开接口，支持：
  - 关键词搜索（问题 / 回答 / 文章）
  - 问题下回答列表拉取
  - 回答评论拉取
  - 多账号 cookie 池 + 冷却轮换（沿用 weibo.py 的做法）

注意（务必先读）：
  知乎核心搜索接口 `api/v4/search_v3` 对部分请求会校验 `x-zse-96`
  签名头，这是知乎自有的加密保护机制，本模块不实现该签名算法的
  逆向/伪造。因此：
    1. 搜索优先走公开可用、不需要签名的路径；一旦命中签名校验
       （表现为 HTTP 403 / 有效 payload 里带 captcha 提示），
       直接判定失败并降级，不做重试破解。
    2. 如果你需要更完整的搜索覆盖率，建议用 Playwright/Selenium
       跑一个真实登录态的浏览器，让浏览器自己算签名、自己发请求，
       你只需要拦截 XHR 拿数据即可——这条路完全走的是"模拟用户
       正常使用"，不涉及破解加密算法。

  账号风险提示：知乎对自动化访问的封号/风控比微博更敏感，
  建议：cookie 池账号数量 >= 3，request_interval 拉到 3~6 秒，
  且只抓取公开可见内容。
"""
import json
import random
import re
import time
from datetime import datetime
import os

from urllib.parse import quote

import requests
from crawlers import register
from utils import get_logger, request_with_retry

log = get_logger("zhihu")

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36 Edg/136.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
]
DEFAULT_INTERVAL = 4.0  # 知乎风控更敏感，间隔比微博大


def _classify_credibility(author: dict) -> str:
    """根据知乎用户信息粗分认证类型（对齐 DB 约束）。
    返回：官方平台 / 头部认证个人 / 认证个人 / 认证机构 / 普通用户
    """
    if not author:
        return "普通用户"
    badge = author.get("badge") or []
    badge_types = {b.get("type") for b in badge if isinstance(b, dict)}
    # 头部认证个人：优秀答主、高盐值、海盐计划核心创作者等平台级认证
    if badge_types & {"best_answerer", "high_salt", "sea_salt_creator"}:
        return "头部认证个人"
    # 认证个人：学历认证 / 职业资格认证 / 在职认证等身份类 badge
    if "identity" in badge_types:
        return "认证个人"
    headline = author.get("headline", "") or ""
    # 根据简介关键词推断知乎官方号（无专有 badge 时的折中方案）
    if any(k in headline for k in ("官方", "客服", "小编")):
        return "官方平台"
    if author.get("type") == "org":
        return "认证机构"
    return "普通用户"

def _parse_zhihu_time(ts) -> datetime | None:
    try:
        return datetime.fromtimestamp(int(ts))
    except (ValueError, TypeError, OSError):
        return None


@register("zhihu")
class ZhihuCrawler:
    """知乎爬虫"""

    display_name = "知乎"
    extractor_type = "zhihu"
    platform_code = "ZH"

    def __init__(self, request_interval: float = DEFAULT_INTERVAL, cookie: str = None):
        self.request_interval = request_interval
        self._cooldowns = {}
        self._current_idx = 0
        self._cookie_pool = self._load_cookie_pool(cookie)
        active = self._get_active_cookie()
        if active:
            log.info("使用 Cookie，长度=%d, 前缀=%s...", len(active), active[:20])
        else:
            log.warning("未传入 Cookie，知乎未登录态下大量内容不可见，建议配置 ZHIHU_COOKIE")

        if len(self._cookie_pool) > 1:
            log.info("多账号模式：共 %d 个账号", len(self._cookie_pool))

        self.session = self._init_session(active)

    # ---- Session / Cookie（与 weibo.py 一致的模式）----

    def _init_session(self, cookie: str | None) -> requests.Session:
        session = requests.Session()
        if cookie:
            self._apply_cookie_to_session(session, cookie)
        return session

    def _apply_cookie_to_session(self, session, cookie: str | None):
        session.cookies.clear()
        if cookie:
            session.headers["Cookie"] = cookie

    def _load_cookie_pool(self, primary: str | None) -> list[str]:
        cookies = []
        if primary:
            cookies.append(primary)
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except ImportError:
            pass
        main = os.getenv("ZHIHU_COOKIE")
        if main and main not in cookies:
            cookies.append(main)
        for i in range(2, 20):
            env_c = os.getenv(f"ZHIHU_COOKIE_{i}")
            if env_c and env_c not in cookies:
                cookies.append(env_c)
        return cookies

    def _get_active_cookie(self) -> str | None:
        if self._cookie_pool and self._current_idx < len(self._cookie_pool):
            return self._cookie_pool[self._current_idx]
        return None

    def _rotate_account(self) -> bool:
        if len(self._cookie_pool) <= 1:
            return False
        self._cooldowns[self._current_idx] = time.time() + 300
        for _ in range(len(self._cookie_pool) - 1):
            self._current_idx = (self._current_idx + 1) % len(self._cookie_pool)
            if self._cooldowns.get(self._current_idx, 0) <= time.time():
                self._apply_cookie_to_session(self.session, self._cookie_pool[self._current_idx])
                log.info(" -> 轮换到账号 #%d/%d", self._current_idx + 1, len(self._cookie_pool))
                return True
        min_cd = min(self._cooldowns.get(i, 0) for i in range(len(self._cookie_pool)))
        log.warning("所有账号冷却中，需等待 %.0fs", max(0, min_cd - time.time()))
        return False

    def _sleep(self, multiplier: float = 1.0):
        base = self.request_interval * multiplier
        jitter = random.uniform(-0.5, 1.0)
        time.sleep(max(1.0, base + jitter))

    def _headers(self, referer: str | None = None) -> dict:
        return {
            "User-Agent": random.choice(USER_AGENTS),
            "Referer": referer or "https://www.zhihu.com/",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "x-requested-with": "fetch",
        }

    def _get_json(self, url: str, params: dict | None = None,
                   referer: str | None = None) -> dict | None:
        try:
            resp = request_with_retry(
                self.session.get, url, params=params,
                headers=self._headers(referer), timeout=15,
            )
            resp.raise_for_status()
            return resp.json()
        except (requests.RequestException, json.JSONDecodeError) as e:
            log.warning("%s -> %s", url, e)
            return None

    # ---- 搜索 ----

    def search(self, keyword: str, page: int = 1, page_size: int = 20,  mode: str = "time") -> list[dict]:
        """搜索问题/回答/文章。命中签名校验（403 或返回体带 captcha 字段）
        时直接返回空列表，交给上层 search_multi_page 判断是否继续。
        """
        url = "https://www.zhihu.com/api/v4/search_v3"
        params = {
            "t": "general",
            "q": keyword,
            "correction": 1,
            "offset": (page - 1) * page_size,
            "limit": page_size,
            "show_all_topics": 0,
        }

        if mode == "time":
            params["sort"] = "created_time"
            params["search_source"] = "Filter"
        else:
            params["search_source"] = "Normal"
            
        data = self._get_json(url, params=params,
                               referer=f"https://www.zhihu.com/search?q={quote(keyword, safe='')}")
        if not data:
            return []
        if "error" in data or data.get("captcha"):
            log.warning("疑似触发风控/签名校验，本次搜索放弃: %s", str(data)[:200])
            return []

        candidates = []
        for item in data.get("data", []):
            obj = item.get("object", {})
            obj_type = obj.get("type")
            if obj_type == "answer":
                q = obj.get("question", {})
                candidates.append({
                    "kind": "answer",
                    "id": str(obj.get("id")),
                    "question_id": str(q.get("id", "")),
                    "url": f"https://www.zhihu.com/question/{q.get('id')}/answer/{obj.get('id')}",
                    "verification_type": _classify_credibility(obj.get("author", {})),
                     "_raw": obj,
                })
            elif obj_type == "article":
                candidates.append({
                    "kind": "article",
                    "id": str(obj.get("id")),
                    "url": f"https://zhuanlan.zhihu.com/p/{obj.get('id')}",
                    "verification_type": _classify_credibility(obj.get("author", {})),
                     "_raw": obj,
                })
            elif obj_type == "question":
                candidates.append({
                    "kind": "question",
                    "id": str(obj.get("id")),
                    "question_id": str(obj.get("id")),
                    "url": f"https://www.zhihu.com/question/{obj.get('id')}",
                    "verification_type": "普通用户",
                })
        return candidates

    def _expand_questions(self, candidates: list[dict],
                          answers_per_question: int = 3) -> list[dict]:
        """search() 命中的是"问题"本身时，还不能直接提取正文——把它换成该
        问题下点赞最高的若干条回答，让返回给 orchestrator 的候选统一是
        "可直接提取"的 answer/article，orchestrator 不需要关心 kind。"""
        expanded = []
        for c in candidates:
            if c["kind"] == "question":
                answers = self.fetch_answers(c["question_id"],
                                             max_answers=answers_per_question)
                if answers:
                    expanded.extend(answers)
                    self._sleep(0.5)
                # 该问题下暂无回答（或拉取失败）：直接丢弃，不放回原始
                # question candidate，因为 extractor 没有对应的提取逻辑
            else:
                expanded.append(c)
        return expanded

    def search_multi_page(self, keyword: str, max_pages: int = 3) -> list[dict]:
        all_candidates, seen = [], set()
        for page in range(1, max_pages + 1):
            candidates = self.search(keyword, page=page)
            if not candidates:
                break
            new = [c for c in candidates if c["id"] not in seen]
            if not new:
                break
            seen.update(c["id"] for c in new)
            all_candidates.extend(new)
            self._sleep()

        while not all_candidates and self._rotate_account():
            log.info("轮换到账号 #%d/%d，重试搜索...",
                     self._current_idx + 1, len(self._cookie_pool))
            self._sleep(1.5)
            account_candidates = []
            for page in range(1, max_pages + 1):
                candidates = self.search(keyword, page=page)
                if not candidates:
                    break
                new = [c for c in candidates if c["id"] not in seen]
                if not new:
                    break
                seen.update(c["id"] for c in new)
                account_candidates.extend(new)
                self._sleep()
            all_candidates = account_candidates

        return self._expand_questions(all_candidates)

    # ---- 问题下的回答列表（公开接口，不需要签名）----

    def fetch_answers(self, question_id: str, max_answers: int = 20) -> list[dict]:
        """拉取某问题下的回答，返回结构对齐 search() 里 kind=answer 的 candidate"""
        url = f"https://www.zhihu.com/api/v4/questions/{question_id}/answers"
        params = {
            "include": "data[*].id,content,voteup_count,author,created_time",
            "limit": min(max_answers, 20),
            "offset": 0,
            "sort_by": "default",
        }
        results = []
        while len(results) < max_answers:
            data = self._get_json(url, params=params,
                                   referer=f"https://www.zhihu.com/question/{question_id}")
            if not data or not data.get("data"):
                break
            for item in data["data"]:
                results.append({
                    "kind": "answer",
                    "id": str(item.get("id")),
                    "question_id": str(question_id),
                    "url": f"https://www.zhihu.com/question/{question_id}/answer/{item.get('id')}",
                    "verification_type": _classify_credibility(item.get("author", {})),
                    "_raw": item,  # 直接带上原始数据，extractor 可以不用二次请求
                })
                if len(results) >= max_answers:
                    break
            paging = data.get("paging", {})
            if paging.get("is_end"):
                break
            params["offset"] = params["offset"] + params["limit"]
            self._sleep()
        return results

    # ---- 评论 ----

    def fetch_comments(self, answer_id: str, max_count: int = 20) -> list[dict]:
        """拉取回答下的评论。返回字段对齐 storage.save_comment() 需要的 key。"""
        comments = []
        offset = 0
        page_size = 20
        url = f"https://www.zhihu.com/api/v4/answers/{answer_id}/root_comments"

        while len(comments) < max_count:
            params = {"order": "normal", "limit": page_size, "offset": offset}
            data = self._get_json(url, params=params,
                                   referer=f"https://www.zhihu.com/answer/{answer_id}")
            if not data or "data" not in data:
                break
            items = data["data"]
            if not items:
                break

            for item in items:
                if len(comments) >= max_count:
                    break
                author = item.get("author", {}).get("member", {})
                comments.append({
                    "comment_id": str(item.get("id")),
                    "content": re.sub(r"<[^>]+>", "", item.get("content", "")),
                    "author": author.get("name", ""),
                    "user_id": str(author.get("id", "")),
                    "publish_time": _parse_zhihu_time(item.get("created_time")),
                    "likes_count": item.get("vote_count", 0),
                    "commenter_ip": item.get("address_text", "") or "",
                    "source_url": f"https://www.zhihu.com/answer/{answer_id}/comment/{item.get('id')}",
                })

            paging = data.get("paging", {})
            if paging.get("is_end"):
                break
            offset += page_size
            self._sleep()

        return comments
