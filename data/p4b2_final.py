# -*- coding: utf-8 -*-
"""P4b2: 终版合并 + 增量解析。

合并 city_portals/county_portals（最新门户 + p7 直写 xxgk）与
city_county_xxgk（p4 快照 xxgk）；对「有门户无 xxgk」行做最终解析。
输出 city_county_final.jsonl。
"""
import json
import sys

sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
from common import fetch, find_xxgk_url, probe_xxgk_paths, norm_url, map_parallel
from curl_cffi import requests as creq


def resolve(r):
    if not r.get("portal_url"):
        return False
    html = fetch(r["portal_url"])
    if not html:
        for imp in ("chrome124", "chrome110"):
            try:
                resp = creq.get(r["portal_url"], timeout=15, impersonate=imp, verify=False)
                if resp.status_code == 200 and len(resp.content) > 500:
                    for enc in ("utf-8", "gb18030"):
                        try:
                            html = resp.content.decode(enc)
                            break
                        except UnicodeDecodeError:
                            continue
                    if html:
                        break
            except Exception:
                continue
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
    # 1) 合并两源
    merged = {}
    for fn in ("city_portals.jsonl", "county_portals.jsonl"):
        for line in open(fn, encoding="utf-8"):
            r = json.loads(line)
            merged[r["code"]] = r
    for line in open("city_county_xxgk.jsonl", encoding="utf-8"):
        r = json.loads(line)
        m = merged.get(r["code"])
        if m and not m.get("xxgk_url") and r.get("xxgk_url"):
            m["xxgk_url"] = r["xxgk_url"]
            m["xxgk_src"] = r["xxgk_src"]

    rows = list(merged.values())
    todo = [r for r in rows if r.get("portal_url") and not r.get("xxgk_url")]
    print(f"p4b2 增量 {len(todo)}", flush=True)
    map_parallel(todo, resolve, workers=16, batch_label="p4b2")

    rows.sort(key=lambda r: r["code"])
    with open("city_county_final.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    hit_p = sum(1 for r in rows if r.get("portal_url"))
    hit_x = sum(1 for r in rows if r.get("xxgk_url"))
    print(f"门户 {hit_p}/{len(rows)} | xxgk {hit_x}/{len(rows)}", flush=True)


if __name__ == "__main__":
    main()
