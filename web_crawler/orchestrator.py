# -*- coding: utf-8 -*-
"""
编排器：统一流水线入口。
选择爬虫 → 搜索 → 提取正文 → 清洗 → 去重 → 入库。

新平台接入三步：
  1. 在 crawlers/ 下新建模块，@register("平台名")，声明 display_name / extractor_type
  2. 如有需要，在 pipeline/extractor.py 中新增抽取策略并注册到 EXTRACTOR_MAP
  3. 在 pipeline/cleaner.py 的 BOILERPLATE_PATTERNS 追加平台模板

用法（单平台单关键词）：
    python orchestrator.py "广西洪灾" --platform sina
    python orchestrator.py "广西洪灾" --platform weibo

用法（从配置批量运行所有已启用的平台）：
    python orchestrator.py --config
    python orchestrator.py --config --dry-run
"""
import json
import argparse
import time
from datetime import datetime
from crawlers import get_crawler
from crawlers.weibo import url_to_mid
from pipeline.extractor import EXTRACTOR_MAP
from pipeline.cleaner import build_document
from simhash import Simhash
from storage import (
    create_db_engine,
    check_url,
    check_content,
    save_document,
    check_comment_url,
    check_comment_content,
    increase_comment_duplicate_count,
    save_comment,
)
import os
from dotenv import load_dotenv
from utils import get_logger, setup_logging, validate_config, ConfigError

load_dotenv()
setup_logging()
log = get_logger("orchestrator")

_CONFIG_FILE = "crawl_config.json"
_REQUEST_INTERVAL = 1.5
_DEFAULT_MAX_COMMENTS = 25
_DEFAULT_MAX_ARTICLES = 20
_ESTIMATED_CANDIDATES_PER_PAGE = 15
_PAGE_BUFFER = 2


def load_and_validate_config(path: str = _CONFIG_FILE) -> dict:
    """加载 crawl_config.json 并做结构校验，配置错误时给出可读报错而不是运行中途 KeyError"""
    with open(path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    try:
        validate_config(cfg)
    except ConfigError as e:
        log.error("配置文件 %s 不合法: %s", path, e)
        raise
    return cfg


def _process_comments(crawler, platform: str, candidate: dict,
                       doc: dict, engine, max_comments: int):
    """社交平台评论拉取与入库"""
    if not hasattr(crawler, "fetch_comments") or engine is None:
        return
    comment_list = []
    try:
        if platform == "weibo":
            tweet_id = candidate.get("tweet_id")
            uid = candidate.get("uid")
            if tweet_id and uid:
                tweet_mid = url_to_mid(tweet_id)
                comment_list = crawler.fetch_comments(
                    tweet_mid, uid, max_count=max_comments)
        elif platform == "zhihu":
            if candidate.get("kind") == "answer":
                comment_list = crawler.fetch_comments(
                    candidate["id"], max_count=max_comments)
        if comment_list:
            log.info("  [评论] 拉取到 %d 条评论", len(comment_list))
        for cm in comment_list:
            cm["parent_post_id"] = doc["doc_id"]
            cm["source_platform"] = crawler.display_name
            cm["crawl_time"] = datetime.now()
            cm["content_hash"] = str(Simhash(cm.get("content", "")).value)
            cm["duplicate_count"] = 1
            cm["clean_status"] = "raw"
            if reason := check_comment_url(engine, cm["source_url"]):
                log.debug("评论URL重复: %s", reason)
                continue
            duplicate = check_comment_content(engine, cm["content"])
            if duplicate:
                log.info("发现重复评论: distance=%s", duplicate["distance"])
                increase_comment_duplicate_count(engine, duplicate["content_hash"])
                continue
            save_comment(engine, cm)
    except Exception as e:
        log.error("  [评论拉取异常] %s", e)


def run(keyword: str,
        platform: str = "sina",
        limit: int = _DEFAULT_MAX_ARTICLES,
        max_comments: int = _DEFAULT_MAX_COMMENTS,
        dry_run: bool = False,
        engine=None,
        cookie: str | None = None,
        sina_cookie: str | None = None,
        zhihu_cookie: str | None = None,
        crawler=None) -> dict:
    """
    对一个平台的单个关键词执行完整爬取流水线。

    keyword      — 搜索关键词
    platform     — 注册的平台名
    limit        — 最多处理条数
    max_comments — 每篇帖子最多拉取评论数（仅社交平台）
    dry_run      — 仅测试不入库
    engine       — 外部传入的 SQLAlchemy engine
    sina_cookie  — 新浪 Cookie（仅 sina 平台使用，微博登录态）
    zhihu_cookie — 知乎 Cookie（仅 zhihu 平台使用）
    crawler      — 外部传入的爬虫实例（None 则内部创建）
    """
    ptag = platform
    log.info("[%s] keyword=\"%s\", limit=%d, max_comments=%d, dry_run=%s",
              ptag, keyword, limit, max_comments, dry_run)
    # 构造爬虫实例
    if crawler is None:
        crawler_kwargs = {}
        if cookie is not None and platform == "weibo":
            crawler_kwargs["cookie"] = cookie
        if sina_cookie is not None and platform == "sina":
            crawler_kwargs["cookie"] = sina_cookie
        if zhihu_cookie is not None and platform == "zhihu":
            crawler_kwargs["cookie"] = zhihu_cookie
        crawler = get_crawler(platform, **crawler_kwargs)
    extractor = EXTRACTOR_MAP.get(crawler.extractor_type)
    # 微博/知乎：复用爬虫 session，使 cookie 刷新 / 账号轮换自动同步到正文提取
    if platform in ("weibo", "zhihu") and hasattr(extractor, "set_session"):
        extractor.set_session(crawler.session)
    pages_needed = max(1, (limit // _ESTIMATED_CANDIDATES_PER_PAGE) + _PAGE_BUFFER)
    candidates = crawler.search_multi_page(keyword, max_pages=pages_needed)
    if not candidates:
        log.warning("[%s] 未搜索到任何候选", ptag)
        return {"success": 0, "skip": 0, "fail": 0}
    log.info("[%s] 搜索到 %d 条候选，处理前 %d 条", ptag, len(candidates), limit)

    # own_engine 标记本函数是否自己创建了 engine；只有自己创建的才在结束时释放，
    # 避免关闭调用方（scheduler / run_all_from_config）传入的共享连接池。
    own_engine = False
    if engine is None and not dry_run:
        engine = create_db_engine()
        own_engine = True

    success = skip = fail = 0
    try:
        for i, candidate in enumerate(candidates[:limit], 1):
            url = candidate["url"]
            log.info("[%d/%d] %s", i, min(limit, len(candidates)), url)
            if engine is not None and (reason := check_url(engine, url)):
                log.info("  %s，跳过", reason)
                skip += 1
                continue
            raw = extractor.extract(url, html=candidate.get("_raw"))
            if raw is None:
                fail += 1
                time.sleep(_REQUEST_INTERVAL)
                continue
            doc = build_document(raw, candidate, platform=crawler.display_name, platform_code=crawler.platform_code)
            if not dry_run and engine is not None:
                if reason := check_content(engine, doc["content"]):
                    log.info("  %s，跳过", reason)
                    skip += 1
                    time.sleep(_REQUEST_INTERVAL)
                    continue
            if dry_run:
                log.info("  [dry-run] 标题: %s", doc["title"])
                log.info("  [dry-run] 来源: %s", doc["author"])
                log.info("  [dry-run] 正文前50字: %s...", doc["content"][:50])
            else:
                save_document(engine, doc)
                log.info("  已入库: %s", doc["title"])
                # 评论爬取（仅社交平台）
                _process_comments(crawler, platform, candidate, doc, engine, max_comments)
            success += 1
            time.sleep(_REQUEST_INTERVAL)
    finally:
        # 只释放本函数自己创建的 engine；如果 engine 是调用方传入的（比如
        # run_all_from_config 里跨关键词复用的连接池），绝不在这里关闭，
        # 否则调用方后续操作会因为连接已关闭而报错。
        if own_engine and engine is not None:
            engine.dispose()

    log.info("[%s] 完成。成功 %d 条，跳过 %d 条，失败 %d 条", ptag, success, skip, fail)
    return {"success": success, "skip": skip, "fail": fail}


def run_all_from_config(dry_run: bool = False,
                        platforms_override: list[str] | None = None) -> dict:
    """
    从 crawl_config.json 读取配置，运行所有已启用的平台。
    这是批量运行的唯一入口：scheduler.py 直接复用本函数，
    避免两处维护同样的"遍历平台 + 关键词 + 汇总统计"逻辑。

    参数:
        dry_run            — 仅测试不入库
        platforms_override — 可选，只运行指定的平台名列表
    返回:
        {平台名: {关键词: {success, skip, fail}, ...}, ...}
    """
    cfg = load_and_validate_config()["crawler"]

    # 确定要运行的平台
    if platforms_override:
        platform_names = platforms_override
    else:
        platform_names = [
            name for name, pc in cfg.items()
            if isinstance(pc, dict) and pc.get("enabled", True)
            and "keywords" in pc
        ]

    results = {}
    engine = None if dry_run else create_db_engine()

    try:
        for pname in platform_names:
            pc = cfg.get(pname)
            if not isinstance(pc, dict) or not pc.get("enabled", True):
                log.info("平台 '%s' 未启用或不存在，跳过", pname)
                continue

            keywords = pc.get("keywords", [])
            limit = pc.get("max_articles_per_keyword", _DEFAULT_MAX_ARTICLES)
            max_comments = pc.get("max_comments_per_article", _DEFAULT_MAX_COMMENTS)
            weibo_cookie = os.getenv("WEIBO_COOKIE")
            sina_cookie = os.getenv("SINA_COOKIE")
            zhihu_cookie = os.getenv("ZHIHU_COOKIE")
            platform_results = {}
            # 每个平台只构造一次爬虫实例，跨关键词复用 session
            crawler_kwargs = {}
            if weibo_cookie is not None and pname == "weibo":
                crawler_kwargs["cookie"] = weibo_cookie
            if sina_cookie is not None and pname == "sina":
                crawler_kwargs["cookie"] = sina_cookie
            if zhihu_cookie is not None and pname == "zhihu":
                crawler_kwargs["cookie"] = zhihu_cookie
            crawler = get_crawler(pname, **crawler_kwargs) if pname in ("weibo", "sina", "zhihu") else None

            log.info("=" * 60)
            log.info("平台=%s, 关键词数=%d, limit=%d, max_comments=%d",
                     pname, len(keywords), limit, max_comments)
            log.info("=" * 60)

            consecutive_empty = 0
            for kw in keywords:
                result = run(
                    keyword=kw,
                    platform=pname,
                    limit=limit,
                    max_comments=max_comments,
                    dry_run=dry_run,
                    cookie=weibo_cookie,
                    sina_cookie=sina_cookie,
                    zhihu_cookie=zhihu_cookie,
                    crawler=crawler,
                )
                platform_results[kw] = result
                # 连续多个关键词都 0 成功 0 失败（即搜索直接没有候选），
                # 很可能是 cookie 失效导致的，提前预警而不是默默跑完整轮再让人发现
                if result["success"] == 0 and result["fail"] == 0 and result["skip"] == 0:
                    consecutive_empty += 1
                    if consecutive_empty >= 3:
                        log.warning("[%s] 连续 %d 个关键词均无候选结果，"
                                   "请检查该平台 Cookie 是否已过期", pname, consecutive_empty)
                else:
                    consecutive_empty = 0
                # 关键词间等待 5 秒，避免被限流
                if kw != keywords[-1]:
                    log.info("  等待 5 秒后处理下一个关键词...")
                    time.sleep(5)

            results[pname] = platform_results
    finally:
        if engine:
            engine.dispose()

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="舆情爬虫编排器")
    parser.add_argument("keyword", type=str, nargs="?", help="搜索关键词")
    parser.add_argument("--platform", type=str, default=None, help="平台名")
    parser.add_argument("--limit", type=int, default=None, help="最多处理条数")
    parser.add_argument("--max-comments", type=int, default=None,
                        help="每篇帖子最多拉取评论数（仅社交平台）")
    parser.add_argument("--dry-run", action="store_true", help="只测试不入库")
    parser.add_argument("--config", action="store_true",
                        help="从 crawl_config.json 读取平台和关键词批量运行")
    args = parser.parse_args()

    if args.config:
        try:
            run_all_from_config(dry_run=args.dry_run)
        except ConfigError as e:
            log.error("配置校验失败，已终止: %s", e)
            raise SystemExit(1)
    elif args.keyword:
        # 单平台单关键词：从配置读取该平台的默认值，CLI 参数可覆盖
        _platform = args.platform or "sina"
        _limit = args.limit
        _max_comments = args.max_comments
        _cookie = None
        _sina_cookie = None
        _zhihu_cookie = None

        try:
            _cfg = load_and_validate_config()["crawler"]
            _pc = _cfg.get(_platform, {})
            if _limit is None:
                _limit = _pc.get("max_articles_per_keyword", _DEFAULT_MAX_ARTICLES)
            if _max_comments is None:
                _max_comments = _pc.get("max_comments_per_article", _DEFAULT_MAX_COMMENTS)
            _cookie = os.getenv("WEIBO_COOKIE")
            _sina_cookie = os.getenv("SINA_COOKIE")
            _zhihu_cookie = os.getenv("ZHIHU_COOKIE")
        except ConfigError as e:
            log.error("配置校验失败，已终止: %s", e)
            raise SystemExit(1)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            log.warning("读取配置失败（%s），使用内置默认值", e)
            if _limit is None:
                _limit = _DEFAULT_MAX_ARTICLES
            if _max_comments is None:
                _max_comments = _DEFAULT_MAX_COMMENTS

        run(args.keyword, platform=_platform,
            limit=_limit, max_comments=_max_comments,
            dry_run=args.dry_run, cookie=_cookie, sina_cookie=_sina_cookie,
            zhihu_cookie=_zhihu_cookie)
    else:
        parser.print_help()
