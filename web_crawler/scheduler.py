# -*- coding: utf-8 -*-
"""
定时调度器。
基于 APScheduler 的 BlockingScheduler，按 crawl_config.json 配置的间隔
周期性地运行 orchestrator 的全平台/全关键词爬取任务。

批量运行逻辑统一收敛在 orchestrator.run_all_from_config()，本文件只负责
触发时机（一次性 / 周期性）和结果汇总打印，不再重复实现"遍历平台+关键词"。

用法：
    python scheduler.py              # 启动周期性调度（按配置间隔）
    python scheduler.py --run-once   # 执行一次全部任务后退出
    python scheduler.py --keyword "广西洪灾"   # 只跑这一个关键词（所有已启用平台）
"""
import argparse
import json
import time
from datetime import datetime

from apscheduler.schedulers.blocking import BlockingScheduler

from orchestrator import run, run_all_from_config, load_and_validate_config
from utils import get_logger, setup_logging, ConfigError

setup_logging()
log = get_logger("scheduler")

_CONFIG_FILE = "crawl_config.json"
_DEFAULT_LIMIT = 10
_DEFAULT_MAX_COMMENTS = 25
_KEYWORD_INTERVAL = 2


def crawl_all_keywords(dry_run: bool = False):
    """执行所有已启用平台 × 关键词的完整爬取，打印汇总统计"""
    log.info("开始多平台爬取...")
    try:
        results = run_all_from_config(dry_run=dry_run)
    except Exception as e:
        # BlockingScheduler 的 job 如果抛异常会静默跳过后续调度，
        # 这里兜底捕获并记录，避免一次异常导致调度器"看起来在跑但其实已经死了"
        log.error("本轮爬取出现未捕获异常: %s", e, exc_info=True)
        return
    total = dict(success=0, skip=0, fail=0)
    for pdata in results.values():
        for stats in pdata.values():
            for k in total:
                total[k] += stats[k]
    log.info("总计: 成功 %d 条, 跳过 %d 条, 失败 %d 条",
             total["success"], total["skip"], total["fail"])


def crawl_single_keyword(keyword: str, dry_run: bool = False):
    """对单个关键词在所有已启用平台上执行爬取"""
    cfg = load_and_validate_config()["crawler"]
    platforms = [
        n for n, p in cfg.items()
        if isinstance(p, dict) and p.get("enabled", True) and "keywords" in p
    ]
    total = dict(success=0, skip=0, fail=0)
    for p in platforms:
        pc = cfg[p]
        try:
            stats = run(
                keyword,
                platform=p,
        limit=pc.get("max_articles_per_keyword", _DEFAULT_LIMIT),
        max_comments=pc.get("max_comments_per_article", _DEFAULT_MAX_COMMENTS),
                dry_run=dry_run,
            )
        except Exception as e:
            log.error("[%s/%s] 异常: %s", p, keyword, e, exc_info=True)
            stats = dict(success=0, skip=0, fail=0)
        for k in total:
            total[k] += stats[k]
        time.sleep(_KEYWORD_INTERVAL)
    log.info("关键词 '%s' 全部平台完成: %s", keyword, total)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-once", action="store_true", help="执行一次全部任务后退出")
    parser.add_argument("--keyword", default=None, help="只跑这一个关键词（所有已启用平台）")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--config", default=_CONFIG_FILE)
    args = parser.parse_args()

    try:
        cfg = load_and_validate_config(args.config)
    except ConfigError as e:
        log.error("配置校验失败，调度器无法启动: %s", e)
        raise SystemExit(1)
    except FileNotFoundError:
        log.error("找不到配置文件: %s", args.config)
        raise SystemExit(1)

    platforms = [
        n for n, p in cfg["crawler"].items()
        if isinstance(p, dict) and p.get("enabled", True) and "keywords" in p
    ]

    if args.run_once or args.keyword:
        if args.keyword:
            crawl_single_keyword(args.keyword, args.dry_run)
        else:
            crawl_all_keywords(args.dry_run)
        return

    # 周期性模式
    sc = cfg["scheduler"]
    sched = BlockingScheduler(timezone="Asia/Shanghai")
    sched.add_job(crawl_all_keywords, "interval",
                  hours=sc.get("interval_hours", 2))
    log.info("调度器已启动, 平台: %d, 间隔: %s 小时",
             len(platforms), sc.get("interval_hours", 2))
    for p in platforms:
        log.info("  [%s] %s", p, cfg["crawler"][p].get("keywords", []))
    try:
        if sc.get("run_at_start", True):
            crawl_all_keywords()
        sched.start()
    except KeyboardInterrupt:
        log.info("收到中断信号，调度器关闭中...")
        sched.shutdown()


if __name__ == "__main__":
    main()
