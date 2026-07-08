# -*- coding: utf-8 -*-
"""
scheduler.py

舆情爬虫定时调度器。
依赖 APScheduler，按 crawl_config.json 中的配置定时执行爬虫任务。

用法：
    python scheduler.py                    # 启动调度器，按间隔执行
    python scheduler.py --run-once         # 立即执行一次全部关键词后退出
    python scheduler.py --run-once --keyword 交通事故   # 仅测试单个关键词
    python scheduler.py --dry-run          # 测试模式，不写入数据库
"""

import argparse
import json
import sys
import time
from datetime import datetime

from apscheduler.schedulers.blocking import BlockingScheduler
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

# 从当前目录导入爬虫模块
from crawler_sina import run, DB_CONFIG


def load_config(path: str = "crawl_config.json") -> dict:
    """读取调度配置文件"""
    with open(path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    return cfg


def create_db_engine(db_cfg: dict):
    """根据配置创建数据库引擎"""
    conn_str = (
        f"mysql+pymysql://{db_cfg['user']}:{db_cfg['password']}"
        f"@{db_cfg['host']}:{db_cfg['port']}/{db_cfg['database']}"
    )
    return create_engine(conn_str)


def run_crawl_job(engine, keyword: str, limit: int = 10, request_interval: float = 1.5,
                  dry_run: bool = False):
    """
    单个关键词的爬取任务。
    由调度器定时回调或 --run-once 模式调用。
    """
    print(f"\n{'='*50}")
    print(f"[{datetime.now()}] 开始爬取关键词: {keyword}")
    print(f"{'='*50}")


    try:
        # 调用 crawler_sina.run()
        stats = run(
            keyword,
            limit=limit,
            dry_run=dry_run,
            engine=engine,
        )
        print(f"[{datetime.now()}] 关键词 '{keyword}' 完成: {stats}")
        return stats
    except Exception as e:
        print(f"[{datetime.now()}] 关键词 '{keyword}' 异常: {e}")
        return {"success": 0, "skip": 0, "fail": 0}


def crawl_all_keywords(config: dict, dry_run: bool = False):
    """遍历配置中的所有关键词，逐一执行爬取"""
    engine = create_db_engine(DB_CONFIG) if not dry_run else None
    crawler_cfg = config["crawler"]
    keywords = crawler_cfg.get("keywords", [])
    limit = crawler_cfg.get("max_articles_per_keyword", 10)
    req_interval = crawler_cfg.get("request_interval", 1.5)

    if not keywords:
        print("[调度器] 没有配置任何关键词，请修改 crawl_config.json")
        return

    total_stats = {"success": 0, "skip": 0, "fail": 0}
    for kw in keywords:
        stats = run_crawl_job(engine, kw, limit, req_interval, dry_run)
        for k in total_stats:
            total_stats[k] += stats[k]
        # 关键词之间留间隔
        time.sleep(2)

    print(f"\n{'='*50}")
    print(f"[{datetime.now()}] 全部关键词爬取完成")
    print(f"总计: 成功 {total_stats['success']} 条, "
          f"跳过 {total_stats['skip']} 条, 失败 {total_stats['fail']} 条")
    print(f"{'='*50}\n")


def main():
    parser = argparse.ArgumentParser(description="舆情爬虫定时调度器")
    parser.add_argument("--run-once", action="store_true",
                        help="立即执行一次所有关键词后退出")
    parser.add_argument("--keyword", type=str, default=None,
                        help="--run-once 时指定单个关键词（可选）")
    parser.add_argument("--dry-run", action="store_true",
                        help="测试模式，不写入数据库")
    parser.add_argument("--config", type=str, default="crawl_config.json",
                        help="配置文件路径（默认 crawl_config.json）")
    args = parser.parse_args()

    # 加载配置
    try:
        config = load_config(args.config)
    except FileNotFoundError:
        print(f"[错误] 找不到配置文件: {args.config}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"[错误] 配置文件格式错误: {e}")
        sys.exit(1)

    # --run-once 模式：执行一次后退出
    if args.run_once or args.keyword:
        if args.keyword:
            # 单个关键词测试
            engine = create_db_engine(DB_CONFIG) if not args.dry_run else None
            run_crawl_job(
                engine, args.keyword,
                limit=config["crawler"].get("max_articles_per_keyword", 10),
                request_interval=config["crawler"].get("request_interval", 1.5),
                dry_run=args.dry_run,
            )
        else:
            crawl_all_keywords(config, dry_run=args.dry_run)
        return

    # 定时调度模式
    scheduler_cfg = config["scheduler"]
    interval_hours = scheduler_cfg.get("interval_hours", 2)
    run_at_start = scheduler_cfg.get("run_at_start", True)

    # --dry-run 不能与定时调度同时使用
    if args.dry_run:
        print("[错误] --dry-run 只能与 --run-once 同时使用")
        sys.exit(1)

    # 启动调度器
    scheduler = BlockingScheduler(timezone="Asia/Shanghai")

    # 添加定时任务
    job = scheduler.add_job(
        crawl_all_keywords,
        trigger="interval",
        hours=interval_hours,
        args=[config],
        id="crawl_all_keywords",
        name=f"每 {interval_hours} 小时爬取所有关键词",
        misfire_grace_time=300,
    )

    print(f"\n{'='*50}")
    print(f"舆情爬虫调度器已启动")
    print(f"  配置文件: {args.config}")
    print(f"  关键词列表: {config['crawler']['keywords']}")
    print(f"  调度间隔: 每 {interval_hours} 小时")
    print(f"  启动后立即执行: {run_at_start}")
    print(f"{'='*50}\n")

    try:
        if run_at_start:
            print("[调度器] 首次执行（run_at_start=True）...")
            crawl_all_keywords(config)
        scheduler.start()
    except KeyboardInterrupt:
        print("\n[调度器] 收到中断信号，正在退出...")
        scheduler.shutdown(wait=False)
        print("[调度器] 已安全退出")


if __name__ == "__main__":
    main()
