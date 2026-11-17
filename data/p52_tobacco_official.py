# -*- coding: utf-8 -*-
"""P52: 从国家烟草专卖局官网导航提取下属单位（真实 HTML 提取，合规）。

栏目：司局子站 ▼ / 省级单位 ▼ / 工业企业 ▼ / 其他直属机构 ▼
输出 tobacco_official.json：{section: {名称: url}}
"""
import json
import re
import sys
from urllib.parse import urljoin

sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开")
sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开/util")

BASE = "http://www.tobacco.gov.cn/"
XXGK = "http://www.tobacco.gov.cn/gjyc/jgzn/xxgk_gknr_list.shtml"


def main():
    from util.smart_fetch import smart_fetch
    html, method = smart_fetch(BASE, timeout=25)
    print("method:", method, "| 长度:", len(html) if html else 0)
    if not html:
        return
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "lxml")
    out = {}
    for li in soup.find_all("li", class_="m"):
        a = li.find("a")
        if not a:
            continue
        title = re.sub(r"\s+", "", a.get_text(" ", strip=True)).replace("▼", "")
        if title not in ("司局子站", "省级单位", "工业企业", "其他直属机构"):
            continue
        ul = li.find("ul")
        if not ul:
            continue
        items = []
        for sub in ul.find_all("a"):
            t = re.sub(r"\s+", "", sub.get_text(" ", strip=True))
            h = sub.get("href") or ""
            if not t:
                continue
            u = urljoin(BASE, h) if not h.startswith(("http://", "https://")) else h
            items.append({"n": t, "u": u})
        out[title] = items
        print(f"{title}: {len(items)} 项")
        for it in items[:6]:
            print(f"   {it['n']} -> {it['u'][:60]}")

    out["_国家局"] = {"u": BASE, "xxgk": XXGK, "method": method}
    json.dump(out, open("tobacco_official.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=0)
    print("p52 完成")


if __name__ == "__main__":
    main()
