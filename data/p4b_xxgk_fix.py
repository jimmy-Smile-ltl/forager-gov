# -*- coding: utf-8 -*-
"""P4b: xxgk 增量补 —— 对 p4 未命中的行（含 p3c 后新填门户的行）再解析。"""
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
        # curl_cffi 多指纹重试
        for imp in ("chrome124", "chrome110"):
            try:
                resp = creq.get(r["portal_url"], timeout=15, impersonate=imp, verify=False)
                if resp.status_code == 200:
                    for enc in ("utf-8", "gb18030"):
                        try:
                            html = resp.content.decode(enc)
                            break
                        except UnicodeDecodeError:
                            continue
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
    rows = [json.loads(l) for l in open("city_county_xxgk.jsonl", encoding="utf-8")]
    todo = [r for r in rows if r.get("portal_url") and not r.get("xxgk_url")]
    print(f"p4b 目标 {len(todo)}", flush=True)
    map_parallel(todo, resolve, workers=16, batch_label="p4b")
    with open("city_county_xxgk.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    hit = sum(1 for r in rows if r.get("xxgk_url"))
    print(f"总命中 {hit}/{len(rows)}", flush=True)


if __name__ == "__main__":
    main()
