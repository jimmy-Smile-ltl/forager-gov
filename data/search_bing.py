# -*- coding: utf-8 -*-
"""search_bing: 本地抓取 cn.bing.com 搜索结果，返回 (标题, cite路径, 直达URL) 列表。

用法: python search_bing.py "查询词" [条数]
"""
import re
import sys
import time
import urllib.parse

import httpx
from bs4 import BeautifulSoup

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
HEADERS = {"User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"}


def search(query: str, count: int = 8, sleep: float = 1.2):
    url = "https://cn.bing.com/search?" + urllib.parse.urlencode({
        "q": query, "setlang": "zh-CN", "ensearch": "0", "count": str(count),
    })
    try:
        resp = httpx.get(url, headers=HEADERS, timeout=20, follow_redirects=True, verify=False)
    except Exception as e:
        print("FETCH ERR", e, file=sys.stderr)
        return []
    soup = BeautifulSoup(resp.content.decode("utf-8", errors="replace"), "lxml")
    out = []
    for li in soup.select("li.b_algo"):
        h2 = li.find("h2")
        cite = li.find("cite")
        a = h2.find("a") if h2 else None
        out.append({
            "title": h2.get_text(strip=True) if h2 else "",
            "cite": cite.get_text(strip=True) if cite else "",
            "url": a.get("href", "") if a else "",
        })
    time.sleep(sleep)
    return out


if __name__ == "__main__":
    q = sys.argv[1] if len(sys.argv) > 1 else ""
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 8
    for r in search(q, n):
        print(f"{r['title'][:60]} | {r['cite'][:90]} | {r['url'][:110]}")
