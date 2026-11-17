# -*- coding: utf-8 -*-
"""P11c: 厅局补采第三弹 —— 首页导航发现「省直单位网站」页再提取。"""
import json
import re
import sys
from urllib.parse import urljoin, urlparse

sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
from common import fetch, curl_fetch_text, find_xxgk_url, norm_url, probe_xxgk_paths
from p2_prov_depts import extract_dept_links
from p11b_fix_depts2 import is_junk, resolve_xxgk

NAV_RE = re.compile(r"(省直单位网站|部门网站|厅局网站|直属机构网站|省政府部门|组织机构|政府机构|机构设置|机构导航|部门频道)")

TARGETS = {
    "北京": "https://www.beijing.gov.cn/",
    "天津": "https://www.tj.gov.cn/",
    "上海": "https://www.shanghai.gov.cn/",
    "重庆": "https://www.cq.gov.cn/",
    "广东": "https://www.gd.gov.cn/",
    "湖南": "https://www.hunan.gov.cn/",
}


def find_nav_pages(html, portal):
    from bs4 import BeautifulSoup
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")
    urls = []
    for a in soup.find_all("a"):
        t = re.sub(r"\s+", "", a.get_text(" ", strip=True))
        h = a.get("href") or ""
        if h.startswith(("javascript", "#")) or not t:
            continue
        if NAV_RE.search(t) and len(t) <= 12:
            u = urljoin(portal, h)
            if u not in urls and urlparse(u).netloc.endswith(".gov.cn"):
                urls.append(u)
    return urls[:6]


def main():
    depts = [json.loads(l) for l in open("prov_depts.jsonl", encoding="utf-8")]
    existing = {(r["province"], urlparse(r["portal_url"]).netloc.lower().replace("www.", ""))
                for r in depts if r.get("portal_url")}

    for pname, portal in TARGETS.items():
        home = fetch(portal) or curl_fetch_text(portal)
        navs = find_nav_pages(home, portal)
        print(f"== {pname} 导航页候选: {navs}", flush=True)
        added = 0
        for np_ in navs:
            html = fetch(np_) or curl_fetch_text(np_)
            if not html:
                continue
            for t, u in extract_dept_links(html, np_):
                host = urlparse(u).netloc.lower().replace("www.", "")
                if (pname, host) in existing or not host:
                    continue
                if is_junk({"name": t, "province": pname, "portal_url": u}):
                    continue
                rec = {"name": t, "province": pname, "category": "省政府组成部门/直属机构",
                       "portal_url": norm_url(u)}
                resolve_xxgk(rec)
                depts.append(rec)
                existing.add((pname, host))
                added += 1
        print(f"   +{added}", flush=True)

    # 去重
    by_host = {}
    for r in depts:
        h = urlparse(r["portal_url"]).netloc.lower().replace("www.", "") if r.get("portal_url") else ""
        if h and h not in by_host:
            by_host[h] = r
    final = list(by_host.values()) + [r for r in depts if not r.get("portal_url")]
    with open("prov_depts.jsonl", "w", encoding="utf-8") as f:
        for r in sorted(final, key=lambda x: (x["province"], x["name"])):
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"厅局总数: {len(final)}", flush=True)


if __name__ == "__main__":
    main()
