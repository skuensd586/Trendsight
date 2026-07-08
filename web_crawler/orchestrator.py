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
    save_comment,
)
import os

_CONFIG_FILE = "crawl_config.json"
_REQUEST_INTERVAL = 1.5
_DEFAULT_MAX_COMMENTS = 25
_DEFAULT_MAX_ARTICLES = 20


def run(keyword: str,
        platform: str = "sina",
        limit: int = _DEFAULT_MAX_ARTICLES,
        max_comments: int = _DEFAULT_MAX_COMMENTS,
        dry_run: bool = False,
        engine=None,
        cookie: str | None = None) -> dict:
    """
    对一个平台的单个关键词执行完整爬取流水线。

    keyword      — 搜索关键词
    platform     — 注册的平台名
    limit        — 最多处理条数
    max_comments — 每篇帖子最多拉取评论数（仅社交平台）
    dry_run      — 仅测试不入库
    engine       — 外部传入的 SQLAlchemy engine
    cookie       — 微博 Cookie（仅 weibo 平台使用）
    """
    ptag = platform
    print(f"\n[{ptag}] keyword=\"{keyword}\", limit={limit}, "
          f"max_comments={max_comments}, dry_run={dry_run}")

    # 构造爬虫实例（cookie 仅在微博平台时传入）
    crawler_kwargs = {}
    if cookie is not None and platform == "weibo":
        crawler_kwargs["cookie"] = cookie
    crawler = get_crawler(platform, **crawler_kwargs)

    extractor = EXTRACTOR_MAP.get(crawler.extractor_type)
    pages_needed = max(1, (limit // 15) + 2)
    candidates = crawler.search_multi_page(keyword, max_pages=pages_needed)
    if not candidates:
        print(f"[{ptag}] 未搜索到任何候选")
        return {"success": 0, "skip": 0, "fail": 0}
    print(f"[{ptag}] 搜索到 {len(candidates)} 条候选，处理前 {limit} 条\n")

    own_engine = False
    if engine is None and not dry_run:
        engine = create_db_engine()
        own_engine = True

    success = skip = fail = 0
    for i, candidate in enumerate(candidates[:limit], 1):
        url = candidate["url"]
        print(f"[{i}/{min(limit, len(candidates))}] {url}")
        if engine is not None and (reason := check_url(engine, url)):
            print(f"  {reason}，跳过")
            skip += 1
            continue
        raw = extractor.extract(url)
        if raw is None:
            fail += 1
            time.sleep(_REQUEST_INTERVAL)
            continue
        doc = build_document(raw, candidate, platform=crawler.display_name)
        if not dry_run and engine is not None:
            if reason := check_content(engine, doc["content"]):
                print(f"  {reason}，跳过")
                skip += 1
                time.sleep(_REQUEST_INTERVAL)
                continue
        if dry_run:
            print(f"  [dry-run] 标题: {doc['title']}")
            print(f"  [dry-run] 来源: {doc['author']}")
            print(f"  [dry-run] 正文前50字: {doc['content'][:50]}...")
        else:
            save_document(engine, doc)
            print(f"  已入库: {doc['title']}")
        success += 1

        # -- 评论爬取（仅社交平台，如微博） --
        if not dry_run and hasattr(crawler, "fetch_comments") and engine is not None:
            tweet_id = candidate.get("tweet_id")
            uid = candidate.get("uid")
            if tweet_id and uid:
                try:
                    tweet_mid = url_to_mid(tweet_id)
                    comment_list = crawler.fetch_comments(
                        tweet_mid, uid, max_count=max_comments)
                    if comment_list:
                        print(f"  [评论] 拉取到 {len(comment_list)} 条评论")
                    for cm in comment_list:
                        cm["source_platform"] = crawler.display_name
                        cm["crawl_time"] = datetime.now()
                        cm["content_hash"] = str(Simhash(
                            cm.get("content", "")).value)
                        cm["clean_status"] = "raw"
                        if reason := check_comment_url(engine, cm["source_url"]):
                            continue
                        if reason := check_comment_content(
                                engine, cm["content"]):
                            continue
                        save_comment(engine, cm)
                except Exception as e:
                    print(f"  [评论拉取异常] {e}")
        # -------------------------------
        time.sleep(_REQUEST_INTERVAL)

    print(f"[{ptag}] 完成。成功 {success} 条，跳过 {skip} 条，失败 {fail} 条")
    return {"success": success, "skip": skip, "fail": fail}


def run_all_from_config(dry_run: bool = False,
                        platforms_override: list[str] | None = None) -> dict:
    """
    从 crawl_config.json 读取配置，运行所有已启用的平台。

    参数:
        dry_run            — 仅测试不入库
        platforms_override — 可选，只运行指定的平台名列表
    返回:
        {平台名: {关键词: {success, skip, fail}, ...}, ...}
    """
    with open(_CONFIG_FILE, "r", encoding="utf-8") as f:
        cfg = json.load(f)["crawler"]

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

    for pname in platform_names:
        pc = cfg.get(pname)
        if not isinstance(pc, dict) or not pc.get("enabled", True):
            print(f"[编排器] 平台 '{pname}' 未启用或不存在，跳过")
            continue

        keywords = pc.get("keywords", [])
        limit = pc.get("max_articles_per_keyword", _DEFAULT_MAX_ARTICLES)
        max_comments = pc.get("max_comments_per_article", _DEFAULT_MAX_COMMENTS)
        cookie = os.getenv("WEIBO_COOKIE")
        platform_results = {}

        print(f"\n{'='*60}")
        print(f"[编排器] 平台={pname}, 关键词数={len(keywords)}, "
              f"limit={limit}, max_comments={max_comments}")
        print(f"{'='*60}")

        for kw in keywords:
            result = run(
                keyword=kw,
                platform=pname,
                limit=limit,
                max_comments=max_comments,
                dry_run=dry_run,
                engine=engine,
                cookie=cookie,
            )
            platform_results[kw] = result

        results[pname] = platform_results

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
        run_all_from_config(dry_run=args.dry_run)
    elif args.keyword:
        # 单平台单关键词：从配置读取该平台的默认值，CLI 参数可覆盖
        _platform = args.platform or "sina"
        _limit = args.limit
        _max_comments = args.max_comments
        _cookie = None

        try:
            with open(_CONFIG_FILE, "r", encoding="utf-8") as _f:
                _cfg = json.load(_f)["crawler"]
            _pc = _cfg.get(_platform, {})
            if _limit is None:
                _limit = _pc.get("max_articles_per_keyword", _DEFAULT_MAX_ARTICLES)
            if _max_comments is None:
                _max_comments = _pc.get("max_comments_per_article", _DEFAULT_MAX_COMMENTS)
            _cookie = os.getenv("WEIBO_COOKIE")
        except Exception:
            if _limit is None:
                _limit = _DEFAULT_MAX_ARTICLES
            if _max_comments is None:
                _max_comments = _DEFAULT_MAX_COMMENTS

        run(args.keyword, platform=_platform,
            limit=_limit, max_comments=_max_comments,
            dry_run=args.dry_run, cookie=_cookie)
    else:
        parser.print_help()
