# -*- coding: utf-8 -*-
"""P4: 市/县门户的信息公开专栏 URL 解析。

输入: city_portals.jsonl / county_portals.jsonl
输出: city_county_xxgk.jsonl（在门户行上补 xxgk_url/xxgk_src）
"""
import json
import sys

sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
from common import fetch, find_xxgk_url, probe_xxgk_paths, norm_url, map_parallel


def resolve(r):
    if not r.get("portal_url"):
        return False
    html = fetch(r["portal_url"])
    if html:
        u = find_xxgk_url(html, r["portal_url"])
        if u:
            r["xxgk_url"] = norm_url(u)
            r["xxgk_src"] = "导航链接"
            return True
    u = probe_xxgk_paths(r["portal_url"])
    if u:
        r["xxgk_url"] = norm_url(u)
        r["xxgk_src"] = "路径探测"
        return True
    return False


def main():
    rows = []
    for fn in ("city_portals.jsonl", "county_portals.jsonl"):
        rows += [json.loads(l) for l in open(fn, encoding="utf-8")]
    todo = [r for r in rows if r.get("portal_url")]
    print(f"待解析 {len(todo)} 个门户（共 {len(rows)} 行）", flush=True)
    map_parallel(todo, resolve, workers=20, batch_label="市县xxgk")

    with open("city_county_xxgk.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    hit = sum(1 for r in rows if r.get("xxgk_url"))
    print(f"信息公开URL命中 {hit}/{len(rows)}（含无门户未匹配行）", flush=True)


if __name__ == "__main__":
    main()
