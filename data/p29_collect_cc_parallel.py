# -*- coding: utf-8 -*-
"""P29: 县/市 并列机关门户采集（人大/政协/监委/法院/检察院）。

对每个有门户的市(333)/县(2978)：smart_fetch 抓首页 → 提取 并列机关链接
（复用 p18 的匹配法）。断点续跑：weekend_state.json 记录已处理门户。
"""
import json
import os
import re
import sys
from urllib.parse import urlparse

_ROOT = "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开"
_UTIL = _ROOT + "/util"
sys.path.insert(0, _ROOT)
sys.path.insert(0, _UTIL)
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))

CAT_RE = re.compile(r"(人大|政协|监委|监察委|纪委|法院|检察院|检察)")
EXCLUDE = re.compile(r"(最高|全国|新闻|报告|会议|要闻|工作|平台|网)")


def sf(url):
    try:
        from util.smart_fetch import smart_fetch
        html, method = smart_fetch(url, timeout=20)
        return html
    except Exception:
        return None


def extract(html, base):
    """提取并列机关链接 [(类别, 名称, URL)]。"""
    from bs4 import BeautifulSoup
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")
    out, seen = [], set()
    for a in soup.find_all("a"):
        text = re.sub(r"\s+", "", (a.get("title") or a.get_text(" ", strip=True)).strip())
        href = a.get("href") or ""
        if not text or not href.startswith(("http://", "https://")):
            continue
        if not CAT_RE.search(text) or EXCLUDE.search(text) or len(text) > 22:
            continue
        if not urlparse(href).netloc.lower().endswith(".gov.cn"):
            continue
        cat = ("人大" if "人大" in text else "政协" if "政协" in text else
               "监委" if ("监察委" in text or "纪委" in text) else
               "法院" if "法院" in text else "检察院")
        if (cat, href) in seen:
            continue
        seen.add((cat, href))
        out.append((cat, text, href))
    return out


def main(limit=400):
    state_f = "weekend_state.json"
    state = {}
    if os.path.exists(state_f):
        state = json.load(open(state_f, encoding="utf-8"))
    done_ports = set(state.get("cc_parallel_done", []))
    rows = state.get("cc_parallel_rows", [])

    cc = [json.loads(l) for l in open("city_county_final.jsonl", encoding="utf-8")]
    todo = [r for r in cc if r.get("portal_url") and r["portal_url"] not in done_ports]
    todo = todo[:limit]
    print(f"本轮 {len(todo)} 个门户（累计完成 {len(done_ports)}）", flush=True)

    def save(final=False):
        state["cc_parallel_done"] = sorted(done_ports)
        state["cc_parallel_rows"] = rows
        json.dump(state, open(state_f, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=0)
        with open("cc_parallel.jsonl", "w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        if final:
            print(f"p29 完成：累计 {len(rows)} 条并列机关记录", flush=True)

    for i, r in enumerate(todo):
        portal = r["portal_url"]
        html = sf(portal)
        hits = extract(html, portal)
        for cat, name, url in hits:
            rows.append({"code": r["code"], "name": r["name"], "level": r["level"],
                         "province": r["province"], "parent": r.get("parent", ""),
                         "portal_url": r["portal_url"], "org_cat": cat,
                         "org_name": name, "org_url": url})
        done_ports.add(portal)
        if (i + 1) % 50 == 0:
            save()
            print(f"  进度 {i+1}/{len(todo)}，命中 {len(rows)} 条", flush=True)

    save(final=True)


if __name__ == "__main__":
    main(limit=int(sys.argv[1]) if len(sys.argv) > 1 else 400)
