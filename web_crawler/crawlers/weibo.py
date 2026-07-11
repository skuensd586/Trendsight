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
from datetime import datetime
from urllib.parse import quote
import os

import requests
from crawlers import register
from utils import get_logger, request_with_retry

log = get_logger("weibo")

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


def _classify_credibility(user: dict) -> str:
    """根据微博用户信息判断认证类型。
    返回认证类型字符串：官方平台 / 头部认证个人 / 认证个人 / 认证机构 / 普通用户
    """
    if not user:
        return "普通用户"
    _OFFICIAL_NEWS_ACCOUNTS = {
        "人民日报", "央视新闻", "新华社",
        "人民网", "光明网"
    }
    screen_name = user.get("screen_name", "")
    if screen_name in _OFFICIAL_NEWS_ACCOUNTS:
        return "官方平台"
    verified_type = user.get("verified_type", -1)
    verified_type_ext = user.get("verified_type_ext", -1)

    # 橙V（verified_type_ext=2）和金V（verified_type_ext=1）属于头部认证个人
    if verified_type == 0 and verified_type_ext ==2 :
        return "头部认证个人"
    if verified_type in (200, 220):
        return "头部认证个人"
    if verified_type == 0:
        return "认证个人"
    if 1 <= verified_type <= 8:  # 企业/政府/媒体/校园/网站/应用/团体/待审企业
        return "认证机构"
    return "普通用户"  # 覆盖 -1（普通用户）和 400（已故V用户）等其余取值

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
    platform_code = "WB"

    def __init__(self, request_interval: float = DEFAULT_INTERVAL, cookie: str = None):
        self.request_interval = request_interval
        self._cooldowns = {}          # idx -> cooldown expiry timestamp
        self._current_idx = 0         # current active account index

        # 加载多账号池（主 cookie + WEIBO_COOKIE_2 / _3 / ...）
        self._cookie_pool = self._load_cookie_pool(cookie)

        active = self._get_active_cookie()
        if active:
            log.info("使用 Cookie，长度=%d, 前缀=%s...", len(active), active[:20])
        else:
            log.warning("未传入 Cookie，将仅依赖自动访客 Cookie")

        if len(self._cookie_pool) > 1:
            log.info("多账号模式：共 %d 个账号", len(self._cookie_pool))

        self.session = self._init_session(active)

    # ---- Session / Cookie ----

    def _init_session(self, cookie: str | None) -> requests.Session:
        session = requests.Session()
        if cookie:
            for item in cookie.split(";"):
                item = item.strip()
                if "=" in item:
                    name, value = item.split("=", 1)
                    name = name.strip()
                    value = value.strip()
                    # 同时设置到两个域，确保 m.weibo.cn 和 s.weibo.com 都能用
                    session.cookies.set(name, value, domain=".weibo.com")
                    session.cookies.set(name, value, domain=".weibo.cn")
        return session

    # ---- 多账号池 ----

    def _load_cookie_pool(self, primary: str | None) -> list[str]:
        """从参数 + 环境变量加载多账号 cookie 池。"""
        cookies = []
        if primary:
            cookies.append(primary)
        # 加载 WEIBO_COOKIE_2, WEIBO_COOKIE_3, ...
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except ImportError:
            pass
        for i in range(2, 20):
            env_c = os.getenv(f"WEIBO_COOKIE_{i}")
            if env_c and env_c not in cookies:
                cookies.append(env_c)
        return cookies

    def _get_active_cookie(self) -> str | None:
        """返回当前账号的完整 cookie 字符串。"""
        if self._cookie_pool and self._current_idx < len(self._cookie_pool):
            return self._cookie_pool[self._current_idx]
        return None
    def _apply_cookie_to_session(self, session, cookie: str | None):
        """清除 session 中的所有 cookie，重新设置指定的 cookie 到两个域。"""
        session.cookies.clear()
        if cookie:
            for item in cookie.split(";"):
                item = item.strip()
                if "=" in item:
                    name, value = item.split("=", 1)
                    name = name.strip()
                    value = value.strip()
                    session.cookies.set(name, value, domain=".weibo.com")
                    session.cookies.set(name, value, domain=".weibo.cn")

    def _rotate_account(self) -> bool:
        """切换到下一个未冷却的账号。当前账号先标记冷却 5 分钟。"""
        if len(self._cookie_pool) <= 1:
            return False

        # 当前账号进入冷却
        self._cooldowns[self._current_idx] = time.time() + 300

        for _ in range(len(self._cookie_pool) - 1):
            self._current_idx = (self._current_idx + 1) % len(self._cookie_pool)
            if self._cooldowns.get(self._current_idx, 0) <= time.time():
                cookie = self._cookie_pool[self._current_idx]
                self._apply_cookie_to_session(self.session, cookie)
                log.info(" -> 轮换到账号 #%d/%d", self._current_idx + 1, len(self._cookie_pool))
                return True

        # 所有账号都在冷却中
        min_cd = min(self._cooldowns.get(i, 0) for i in range(len(self._cookie_pool)))
        wait = max(0, min_cd - time.time())
        log.warning("所有账号冷却中，需等待 %.0fs", wait)
        return False

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
            resp = request_with_retry(
                self.session.get, url, params=params,
                headers=self._headers(referer), timeout=15,
            )
            resp.raise_for_status()
            return resp.json()
        except (requests.RequestException, json.JSONDecodeError) as e:
            log.warning("%s -> %s", url, e)
            return None
        ver_type = _classify_credibility(user)
    # ---- 访客 Cookie 自动刷新 ----

    def _try_refresh_visitor_cookie(self) -> bool:
        """通过新浪访客系统获取临时 cookie（无需手动登录）。

        真实流程是两步，缺一不可：
          1. genvisitor  -> 只拿到一个 tid（令牌，不是可用的 cookie）
          2. visitor?a=incarnate&t=<tid> -> 该请求的响应 Set-Cookie 头
             里才会真正种下有效的 SUB / SUBP，requests.Session 会自动
             把它们写入 cookiejar。
        旧实现只做了第 1 步，并试图直接从 genvisitor 的 JSON 里解析出
        一个 "sub" 字段当 cookie 用，这在服务端并不生效，所以刷新永远
        失败。
        """
        try:
            headers = self._headers("https://passport.weibo.com/")
            headers["Content-Type"] = "application/x-www-form-urlencoded"

            # 第 1 步：genvisitor，拿 tid
            fp = json.dumps({
                "os": "1",
                "browser": "Chrome136,0,0,0",
                "fonts": "undefined",
                "screenInfo": "1920*1080*24",
                "plugins": "",
            })
            gen_resp = request_with_retry(
                self.session.post,
                "https://passport.weibo.com/visitor/genvisitor",
                data={"cb": "gen_callback", "fp": fp},
                headers=headers, timeout=10,
            )
            m = re.search(r"gen_callback\((.*)\)\s*;?\s*$", gen_resp.text.strip())
            if not m:
                log.warning("genvisitor 响应解析失败")
                return False
            payload = json.loads(m.group(1))
            tid = payload.get("data", {}).get("tid")
            if not tid:
                log.warning("genvisitor 未返回 tid")
                return False

            # 第 2 步：incarnate，真正种下 SUB / SUBP
            incarnate_resp = request_with_retry(
                self.session.get,
                "https://passport.weibo.com/visitor/visitor",
                params={
                    "a": "incarnate", "t": tid, "w": 2, "c": "095",
                    "gc": "", "cb": "cross_domain", "from": "weibo",
                    "_rand": random.random(),
                },
                headers=self._headers("https://passport.weibo.com/"),
                timeout=10,
            )
            got_sub = "SUB" in self.session.cookies.get_dict(domain=".weibo.com")
            if not got_sub:
                # 部分情况下 Set-Cookie 写在 .weibo.cn 域下，兜底同步一次
                sub_val = self.session.cookies.get("SUB", domain=".weibo.cn")
                if sub_val:
                    self.session.cookies.set("SUB", sub_val, domain=".weibo.com")
                    got_sub = True
            if not got_sub:
                log.warning("incarnate 未种下 SUB，HTTP %s", incarnate_resp.status_code)
                return False

            new_sub = self.session.cookies.get("SUB", domain=".weibo.com")
            new_subp = self.session.cookies.get("SUBP", domain=".weibo.com")
            for domain in (".weibo.com", ".weibo.cn"):
                if new_sub:
                    self.session.cookies.set("SUB", new_sub, domain=domain)
                if new_subp:
                    self.session.cookies.set("SUBP", new_subp, domain=domain)
            return True
        except Exception as e:
            log.warning("访客 cookie 获取失败: %s", e)
            return False

    # ---- 卡片解析 ----

    def _mblog_to_candidate(self, mblog: dict) -> dict | None:
        mblogid = mblog.get("mblogid")
        user = mblog.get("user", {})
        uid = user.get("id", "")
        if not mblogid or not uid:
            return None
        ver_type = _classify_credibility(user)
        return {
            "url": f"https://weibo.com/{uid}/{mblogid}",
            "tweet_id": mblogid,
            "uid": str(uid),
            "verification_type": ver_type,
        }

    def _cards_to_candidates(self, cards: list[dict]) -> list[dict]:
        """m.weibo.cn getIndex 接口的 cards 结构里，帖子有时直接在
        card.mblog，有时嵌套在 card.card_group[].mblog（比如搜索结果
        卡片组）里，两种都要解析，否则会漏掉大量结果。"""
        candidates = []
        seen = set()
        for card in cards:
            mblog = card.get("mblog")
            sub_mblogs = [s.get("mblog") for s in card.get("card_group", []) if s.get("mblog")]
            for mb in ([mblog] if mblog else []) + sub_mblogs:
                c = self._mblog_to_candidate(mb)
                if c and c["tweet_id"] not in seen:
                    seen.add(c["tweet_id"])
                    candidates.append(c)
        return candidates

    # ---- 搜索入口 ----

    def search(self, keyword: str, page: int = 1,mode: str = "hot") -> list[dict]:
        """使用 m.weibo.cn 移动端 API 搜索。
        自动检测 cookie 过期并尝试访客 cookie 刷新 / 多账号轮换。
        """
        url = "https://m.weibo.cn/api/container/getIndex"
        params = {"type": "all", "query": keyword, "page": page}
        headers = self._headers(referer=f"https://m.weibo.cn/search?q={quote(keyword)}")
        headers["X-Requested-With"] = "XMLHttpRequest"

        if mode == "time":
            containerid = f"100103type=61&q={keyword}&t="
        else:
            containerid = f"100103type=1&q={keyword}"

        params = {
            "containerid": containerid,
            "page_type": "searchall",
            "page": page
        }

        data = None
        for attempt in range(3):
            try:
                resp = request_with_retry(self.session.get, url, params=params,
                                          headers=headers, timeout=15)
                resp.raise_for_status()
                data = resp.json()
            except (requests.RequestException, json.JSONDecodeError) as e:
                log.warning("m.weibo.cn 搜索失败: %s", e)
                return []

            if data.get("ok") == 1 and "data" in data:
                # 搜索成功：解析 cards 并返回，不再往下走 cookie 刷新分支
                cards = data.get("data", {}).get("cards", [])
                candidates = self._cards_to_candidates(cards)
                return candidates

            log.warning("搜索返回异常: ok=%s, msg=%s",
                        data.get("ok"), data.get("msg", data.get("msgLite", "")))

            if data.get("ok") == -100 and attempt == 0:
                # ok=-100 通常意味着访客 cookie 失效/缺失，先尝试自动刷新
                # 一次访客 cookie 再重试，避免直接放弃、退化到低命中率的
                # s.weibo.com 桌面版降级方案。
                log.info("尝试刷新访客 cookie...")
                if self._try_refresh_visitor_cookie():
                    log.info("刷新完成，等待 4s 后重试")
                    time.sleep(4)
                    continue

            # ok=0 / ok=-100 刷新失败 / 其他异常状态：不再重试，
            # 交给 search_multi_page 走 s.weibo.com 降级
            return []
        return []

    def _search_desktop_fallback(self, keyword: str, page: int = 1) -> list[dict]:
        """s.weibo.com 桌面版降级（浏览器请求头伪装）"""
        try:
            resp = request_with_retry(
                self.session.get,
                "https://s.weibo.com/weibo",
                params={"q": keyword, "page": page},
                headers={
                    "User-Agent": random.choice(USER_AGENTS),
                    "Referer": "https://s.weibo.com/",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                    "Connection": "keep-alive",
                },
                timeout=15,
            )
            resp.raise_for_status()
            html = resp.text
        except requests.RequestException as e:
            log.warning("s.weibo.com 请求失败: %s", e)
            return []

        if not html:
            log.warning("s.weibo.com 返回空页面")
            return []

        candidates, seen = [], set()

        # 方案一: 从 <div class="from">...</div> 容器内解析
        for div_from in re.finditer(r'<div class="from"[^>]*>(.*?)</div>', html, re.DOTALL):
            for m in re.finditer(r'weibo\.com/(\d+)/([a-zA-Z0-9]+)', div_from.group(1)):
                uid, mid = m.group(1), m.group(2)
                if mid not in seen:
                    seen.add(mid)
                    candidates.append({"url": f"https://weibo.com/{uid}/{mid}",
                                       "tweet_id": mid, "uid": uid})

        # 方案二: 全量正则解析
        if not candidates:
            for m in re.finditer(r'weibo\.com/(\d+)/([a-zA-Z0-9]+)', html):
                uid, mid = m.group(1), m.group(2)
                if mid not in seen:
                    seen.add(mid)
                    candidates.append({"url": f"https://weibo.com/{uid}/{mid}",
                                       "tweet_id": mid, "uid": uid})

        if not candidates:
            log.warning("s.weibo.com 页面未解析到帖子链接")
        return candidates

    def search_multi_page(self, keyword: str, max_pages: int = 3, mode: str = "hot") -> list[dict]:
        all_candidates = []

        # 方案一: m.weibo.cn 移动端 API（search 内部已有 cookie 刷新 + 账号轮换）
        for page in range(1, max_pages + 1):
            candidates = self.search(keyword, page=page, mode=mode)
            if not candidates:
                break
            all_candidates.extend(candidates)
            self._sleep()

        if all_candidates:
            return all_candidates

        # 方案二: s.weibo.com 桌面版兜底（m.weibo.cn API 不可用时直接降级）
        log.info("降级到 s.weibo.com...")
        for page in range(1, max_pages + 1):
            candidates = self._search_desktop_fallback(keyword, page=page)
            if not candidates:
                break
            all_candidates.extend(candidates)
            self._sleep()

        if all_candidates:
            return all_candidates

        # 方案三: 循环轮换账号，逐个用 s.weibo.com 兜底
        while self._rotate_account():
            log.info("轮换到账号 #%d/%d，降级 s.weibo.com...",
                     self._current_idx + 1, len(self._cookie_pool))
            self._sleep(2.0)
            account_candidates = []
            for page in range(1, max_pages + 1):
                candidates = self._search_desktop_fallback(keyword, page=page)
                if not candidates:
                    break
                account_candidates.extend(candidates)
                self._sleep()
            if account_candidates:
                return account_candidates

        return all_candidates

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
