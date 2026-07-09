# -*- coding: utf-8 -*-
"""
定时调度器。
基于 APScheduler 的 BlockingScheduler，按 crawl_config.json 配置的间隔
周期性地运行 orchestrator 的全平台/全关键词爬取任务。

用法：
    python scheduler.py              # 启动周期性调度（按配置间隔）
    python scheduler.py --run-once   # 执行一次全部任务后退出
"""
import argparse, json, sys, time
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from orchestrator import run, run_all_from_config
import os

_CONFIG_FILE = "crawl_config.json"


def load_config(path=_CONFIG_FILE):
    """加载 crawl_config.json"""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def run_crawl_job(engine, keyword, limit=10, platform="sina", dry_run=False, cookie=""):
    """供 APScheduler 调度的单次爬取包装，捕获异常避免调度中断"""
    print(f"\n{'='*50}")
    print(f"[{datetime.now()}] 开始 {platform}/{keyword}")
    try:
        stats = run(keyword, platform=platform, limit=limit,
                    dry_run=dry_run, engine=engine, cookie=cookie or None)
        print(f"[{datetime.now()}] {platform}/{keyword} 完成: {stats}")
        return stats
    except Exception as e:
        print(f"[{datetime.now()}] {platform}/{keyword} 异常: {e}")
        return dict(success=0, skip=0, fail=0)


def crawl_all_keywords(config, dry_run=False):
    """遍历所有启用的平台+关键词，执行一次完整爬取"""
    print(f"[{datetime.now()}] 开始多平台爬取...")
    results = run_all_from_config(dry_run=dry_run)
    total = dict(success=0, skip=0, fail=0)
    for pdata in results.values():
        for stats in pdata.values():
            for k in total:
                total[k] += stats[k]
    print(f"总计: 成功 {total['success']} 条, 跳过 {total['skip']} 条, 失败 {total['fail']} 条")
def main():
    """入口：--run-once 执行一次后退出，否则进入周期性调度"""
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-once", action="store_true")
    parser.add_argument("--keyword", default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--config", default=_CONFIG_FILE)
    args = parser.parse_args()
    config = load_config(args.config)
    platforms = [
        n for n, p in config["crawler"].items()
        if isinstance(p, dict) and p.get("enabled", True) and "keywords" in p
    ]
    if args.run_once or args.keyword:
        # 一次性模式
        if args.keyword:
            total = dict(success=0, skip=0, fail=0)
            for p in platforms:
                pc = config["crawler"][p]
                s = run_crawl_job(None, args.keyword,
                                  pc.get("max_articles_per_keyword", 10),
                                  p, args.dry_run,
                                  os.getenv("WEIBO_COOKIE") or "")
                for k in total:
                    total[k] += s[k]
                time.sleep(2)
            print(f"关键词 '{args.keyword}' 全部完成: {total}")
        else:
            crawl_all_keywords(config, args.dry_run)
        return
    # 周期性模式
    sc = config["scheduler"]
    sched = BlockingScheduler(timezone="Asia/Shanghai")
    sched.add_job(crawl_all_keywords, "interval",
                  hours=sc.get("interval_hours", 2), args=[config])
    print(f"调度器已启动, 平台: {len(platforms)}")
    for p in platforms:
        print(f"  [{p}] {config['crawler'][p].get('keywords',[])}")
    try:
        if sc.get("run_at_start", True):
            crawl_all_keywords(config)
        sched.start()
    except KeyboardInterrupt:
        sched.shutdown()
if __name__ == "__main__":
    main()
