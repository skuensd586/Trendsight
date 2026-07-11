# -*- coding: utf-8 -*-
"""
澎湃新闻爬虫
"""

import random
import time
import requests
from crawlers import register
from utils.logger import get_logger
from utils.retry import retry_with_backoff
log = get_logger("thepaper")
SEARCH_URL = ("https://api.thepaper.cn/search/web/news")

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    " AppleWebKit/537.36 Chrome/120 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
    " AppleWebKit/605.1.15 Safari/605.1.15"
]

@register("thepaper")
class ThePaperCrawler:
    display_name = "澎湃新闻"
    extractor_type = "news"
    platform_code = "PP"

    def __init__(self,request_interval: float = 2.0):
        self.request_interval = request_interval
        self.session = requests.Session()
    def _sleep(self):
        time.sleep(
            max(0.5,self.request_interval+random.uniform(-0.5,1))
        )
    @retry_with_backoff(max_attempts=3,base_delay=2)
    def _post(self,url,payload,timeout=15):
        headers = {
            "User-Agent":random.choice(USER_AGENTS),
            "Accept":"application/json",
            "Content-Type":"application/json",
            "Client-Type":"1",
            "Origin":"https://www.thepaper.cn",
            "Referer":"https://www.thepaper.cn/"
        }
        resp = self.session.post(url,json=payload,headers=headers,timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    def _parse_search_json(self,data):
        results = []
        if data.get("code") != 200:
            log.warning("澎湃接口返回异常:%s",data)
            return results
        items = (data.get("data", {}).get("list", []))

        for item in items:
            cont_id = item.get("contId")
            if not cont_id:
                continue
            url = (
                "https://www.thepaper.cn/newsDetail_forward_"
                + str(cont_id)
            )
            title = (item.get("name")or "")
            summary = (item.get("summary")or "")
            results.append({
                "url":url,
                "title":title,
                "content":summary,
                "ctime":item.get("pubTime",""),
                "media_show":"澎湃新闻"
                })
        log.info("解析澎湃搜索结果 %d 条",len(results))
        return results

    def search(self,keyword: str,page: int = 1,size: int = 10):
        payload = {
            "word":keyword,
            "orderType":3,
            "pageNum":page,
            "pageSize":size,
            "searchType":1
        }
        try:
            data = self._post(SEARCH_URL,payload)
            return self._parse_search_json(data)
        except Exception as e:
            log.error("澎湃搜索失败:%s",e)
            return []

    def search_multi_page(self,keyword: str,max_pages: int = 3,size: int = 100):
        results=[]
        seen=set()
        for page in range(1,max_pages+1):
            items = self.search(keyword,page,size)
            if not items:
                break

            for item in items:
                url = item.get("url")
                if url and url not in seen:
                    seen.add(url)
                    results.append(item)
                if len(results)>=size:
                    return results
            self._sleep()
        return results