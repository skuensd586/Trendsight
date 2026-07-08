# -*- coding: utf-8 -*-
"""
crawler_sina.py

新浪新闻爬虫主脚本。
流程：搜索关键词 -> 拿到文章URL列表 -> 抓取详情页正文 -> 清洗 -> 生成标准字段 -> 入库

运行前准备：
    1. pip install -r requirements.txt
    2. 先跑 explore_sina.py 确认页面结构，按需调整下面 parse_search_result() 里的选择器
    3. 执行 schema.sql 建好数据库表
    4. 修改下面 DB_CONFIG 里的数据库连接信息

用法：
     python crawler_sina.py "交通事故" --limit 10 --dry-run   # 先只测试不入库
     python crawler_sina.py "交通事故" --limit 10             # 正式抓取并入库
"""

import argparse
import hashlib
import html
import json
import os
import re
import time
import uuid
from datetime import datetime
from urllib.parse import quote

from dotenv import load_dotenv

import requests
from bs4 import BeautifulSoup
from newspaper import Article
from simhash import Simhash
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.exc import SQLAlchemyError

load_dotenv()

# ============================================
# 配置区域 —— 按你的实际环境修改
# ============================================
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# 数据库连接信息，改成你自己的账号密码
DB_CONFIG = {
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "database": os.getenv("DB_DATABASE", "public_opinion_system"),
}

REQUEST_INTERVAL = 1.5  # 每次请求间隔秒数，避免请求过快被封

# -*- coding: utf-8 -*-
# 模板块：噪音过滤 + 任务日志，会被 crawler_sina.py 的补丁脚本读取插入
# 各平台已知的模板化尾部声明（可扩展）
BOILERPLATE_PATTERNS = {
    "新浪新闻": [
        "特别声明：以上文章内容仅代表作者本人观点，不代表新浪网观点或立场。如有关于作品内容、版权或其它问题请于作品发表后的30日内与新浪网联系。",
        "特别声明：以上文章内容仅代表作者本人观点，不代表新浪网观点或立场。如关于作品内容、版权或其它问题请于作品发表后的30日内与新浪网联系。",
        "声明：本文内容仅代表作者个人观点，与新浪网无关。",
    ],
}
# 3 个以上连续空行
_EXCESS_NEWLINES = re.compile(r'\n{3,}')


def clean_content(text: str, platform: str = "新浪新闻") -> str:
    """
    内容噪音过滤：
      1. 还原遗漏的 HTML 实体
      2. 去除零宽字符
      3. 去除平台特定的 boilerplate 尾部声明
      4. 归一化换行（段落保留双换行）
      5. 去除每行首尾空白
    """
    if not text or not text.strip():
        return ""

    # 1. HTML 实体还原（newspaper3k 偶有遗漏）
    text = html.unescape(text)

    # 2. 零宽字符
    text = re.sub(r'[\u200b\u200c\u200d\u200e\u200f\ufeff]', '', text)

    # 3. 去掉已知 boilerplate
    for pattern in BOILERPLATE_PATTERNS.get(platform, []):
        text = text.replace(pattern, "")

    # 4. 合并多余空行（保留段落间的双换行）
    text = _EXCESS_NEWLINES.sub('\n\n', text)

    # 5. 逐行 trim -> 去掉首尾空行
    lines = [line.strip() for line in text.split('\n')]
    text = '\n'.join(lines).strip()

    return text



# ============================================
# 第一步：搜索关键词，调用新浪的JSON搜索接口
# ============================================
SEARCH_API_URL = "https://search.sina.com.cn/api/search"

# 只保留真正的图文新闻，过滤掉视频/图集类内容
VALID_DOC_TYPES = {"news"}

def search_sina_news(keyword: str, page: int = 1, size: int = 10) -> list:
    """
    调用新浪搜索JSON接口，返回结构化的候选文章列表
    （包含 title / url / ctime / media_show，但 content 还需要去详情页抓取）
    """
    params = {
        "q": keyword,
        "tp": "news",
        "sort": "0",
        "page": page,
        "size": size,
        "from": "search_result",
    }

    # referer 必须带上，新浪服务器靠这个字段判断请求是否来自其官网页面
    request_headers = dict(HEADERS)
    request_headers.update({
        "accept": "application/json, text/plain, */*",
        "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
        "referer": f"https://search.sina.com.cn/search?q={quote(keyword)}&tp=news",
    })

    resp = requests.get(
        SEARCH_API_URL, headers=request_headers, params=params, timeout=10
    )
    resp.raise_for_status()
    payload = resp.json()

    if payload.get("code") != 0:
        print(f"  接口返回异常: {payload.get('message')}")
        return []

    items = payload.get("data", {}).get("list", [])

    candidates = []
    for item in items:
        doc_type = item.get("docType")
        if doc_type not in VALID_DOC_TYPES:
            continue  # 跳过视频、图集类内容，只保留图文新闻

        candidates.append({
            "url": item.get("url"),
            "title": item.get("title"),
            "ctime": item.get("ctime"),          # unix时间戳，秒级
            "media_show": item.get("media_show"),  # 来源账号/媒体名
        })

    return candidates


def search_sina_news_multi_page(keyword: str, max_pages: int = 3, size: int = 50) -> list:
    """翻页拉取多页结果，凑够足够的候选新闻数量"""
    all_candidates = []
    for page in range(1, max_pages + 1):
        page_candidates = search_sina_news(keyword, page=page, size=size)
        if not page_candidates:
            break
        all_candidates.extend(page_candidates)
        time.sleep(REQUEST_INTERVAL)
    return all_candidates


# ============================================
# 第二步：抓取详情页正文
# ============================================
def fetch_article(url: str) -> dict | None:
    """用 newspaper3k 抓取文章标题、正文、发布时间、作者"""
    try:
        article = Article(url, language="zh")
        article.download()
        article.parse()

        if not article.text or len(article.text) < 30:
            # 正文太短大概率是提取失败，丢弃
            return None

        return {
            "title": article.title.strip(),
            "content": article.text.strip(),
            "publish_time": article.publish_date,
            "authors": article.authors,
        }
    except Exception as e:
        print(f"  [失败] 抓取文章出错: {url}\n  错误信息: {e}")
        return None


# ============================================
# 第三步：清洗 + 格式标准化，生成标准字段
# ============================================
def build_document(raw: dict, candidate: dict) -> dict:
    """
    raw: fetch_article() 抓取详情页拿到的完整正文等信息
    candidate: search_sina_news() 返回的候选条目（含更可靠的ctime/media_show）
    """
    # 在构建文档前先过噪音过滤
    content = clean_content(raw["content"])

    # 优先用搜索接口返回的 ctime（更可靠），详情页解析失败时才用兜底值
    if candidate.get("ctime"):
        publish_time = datetime.fromtimestamp(candidate["ctime"])
    else:
        publish_time = raw.get("publish_time") or datetime.now()

    # 优先用接口返回的 media_show 作为来源标注，详情页没提取到作者时用它兜底
    author = ", ".join(raw.get("authors", [])) or candidate.get("media_show") or None

    return {
        "doc_id": str(uuid.uuid4()),
        "source_platform": "新浪新闻",
        "source_url": candidate["url"],
        "title": raw["title"] or candidate.get("title"),
        "content": content,
        "author": author,
        "publish_time": publish_time,
        "crawl_time": datetime.now(),
        "content_hash": str(Simhash(content).value),
        "event_id": None,
    }


# ============================================
# 第四步：去重（基于 source_url 的完全去重，
#         近似重复可以用 content_hash 后续再做批量比对）
# ============================================
def is_duplicate(engine, source_url: str) -> bool:
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT 1 FROM raw_documents WHERE source_url = :url LIMIT 1"),
            {"url": source_url},
        )
        return result.first() is not None


# ============================================
# 第五步：入库
# ============================================
def save_document(engine, doc: dict):
    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO raw_documents
                (doc_id, source_platform, source_url, title, content,
                 author, publish_time, crawl_time, content_hash, event_id)
                VALUES
                (:doc_id, :source_platform, :source_url, :title, :content,
                 :author, :publish_time, :crawl_time, :content_hash, :event_id)
            """),
            doc,
        )


# ============================================
# 主流程
# ============================================
def run(keyword: str, limit: int = 10, dry_run: bool = False,
        engine=None) -> dict:
    """
    参数：
        keyword     : 搜索关键词
        limit       : 本次最多处理多少条
        dry_run     : 仅测试不入库
        engine      : 外部传入的 SQLAlchemy engine（None 则内部创建）
    返回：
        {"success": int, "skip": int, "fail": int}
    """
    print(f"开始搜索关键词: {keyword}")
    # 新浪API每页最多返回约15条，按需要的limit计算翻页数（多翻1页留余量）
    pages_needed = max(1, (limit // 15) + 2)
    candidates = search_sina_news_multi_page(keyword, max_pages=pages_needed)
    print(f"搜索到 {len(candidates)} 条图文新闻（已过滤视频/图集），本次限制处理前 {limit} 条\n")


    if not candidates:
        print("没有搜到任何候选新闻，请检查接口URL/参数是否正确，或该关键词下确实没有图文类型结果")
        return

    own_engine = False
    if engine is None and not dry_run:
        own_engine = True
        conn_str = (
            f"mysql+pymysql://{DB_CONFIG['user']}:{DB_CONFIG['password']}"
            f"@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
        )
        engine = create_engine(conn_str)
    elif engine is None and dry_run:
        engine = None

    success_count = 0
    skip_count = 0
    fail_count = 0

    for i, candidate in enumerate(candidates[:limit], 1):
        url = candidate["url"]
        print(f"[{i}/{min(limit, len(candidates))}] 处理: {url}")

        if engine is not None and is_duplicate(engine, url):
            print("  已存在，跳过（去重）")
            skip_count += 1
            continue

        raw = fetch_article(url)
        if raw is None:
            fail_count += 1
            time.sleep(REQUEST_INTERVAL)
            continue

        doc = build_document(raw, candidate)

        if dry_run:
            print(f"  [dry-run] 标题: {doc['title']}")
            print(f"  [dry-run] 来源: {doc['author']}")
            print(f"  [dry-run] 发布时间: {doc['publish_time']}")
            print(f"  [dry-run] 正文前50字: {doc['content'][:50]}...")
        else:
            save_document(engine, doc)
            print(f"  已入库: {doc['title']}")

        success_count += 1
        time.sleep(REQUEST_INTERVAL)

    print(f"\n完成。成功 {success_count} 条，跳过重复 {skip_count} 条，失败 {fail_count} 条")


    return {"success": success_count, "skip": skip_count, "fail": fail_count}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="新浪新闻爬虫")
    parser.add_argument("keyword", type=str, help="搜索关键词")
    parser.add_argument("--limit", type=int, default=10, help="本次最多处理多少条")
    parser.add_argument("--dry-run", action="store_true", help="只测试不入库")
    args = parser.parse_args()

    run(args.keyword, limit=args.limit, dry_run=args.dry_run)
