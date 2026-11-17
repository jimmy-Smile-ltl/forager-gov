# -*- coding: utf-8 -*-
"""P9d: 用 smart_fetch + find_xxgk_links v2 二次补齐「有门户无xxgk」行。"""
import json
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

_ROOT = "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开"
_UTIL = _ROOT + "/util"
sys.path.insert(0, _ROOT)
sys.path.insert(0, _UTIL)
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))

from common import find_xxgk_url, norm_url  # noqa: E402


def sf(url):
    try:
        from util.smart_fetch import smart_fetch
        html, method = smart_fetch(url, timeout=25)
        return html
    except Exception:
        return None


def resolve(r):
    html = sf(r["portal_url"])
    if html:
        u = find_xxgk_url(html, r["portal_url"])
        if u:
            r["xxgk_url"] = norm_url(u)
            r["xxgk_src"] = "smart_fetch导航v2"
            return True
    return False


def main():
    targets = []
    cc = [json.loads(l) for l in open("city_county_final.jsonl", encoding="utf-8")]
    targets += [r for r in cc if r.get("portal_url") and not r.get("xxgk_url")]
    depts = [json.loads(l) for l in open("prov_depts.jsonl", encoding="utf-8")]
    targets += [r for r in depts if r.get("portal_url") and not r.get("xxgk_url")]
    central = [json.loads(l) for l in open("central.jsonl", encoding="utf-8")]
    targets += [r for r in central if not r.get("xxgk_url") and r["name"] != "国务院研究室"]
    print(f"p9d 目标 {len(targets)}", flush=True)

    ok = 0
    lock = threading.Lock()
    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = {ex.submit(resolve, r): r for r in targets}
        for i, f in enumerate(as_completed(futs)):
            r = f.result()
            with lock:
                ok += 1 if r else 0
                if (i + 1) % 20 == 0:
                    print(f"[p9d] {i+1}/{len(targets)} ok={ok}", flush=True)
    print(f"[p9d] done ok={ok}/{len(targets)}", flush=True)

    # 回写
    by_code = {r["code"]: r for r in cc}
    for r in targets:
        if r.get("code") and r["code"] in by_code:
            by_code[r["code"]].update(r)
    with open("city_county_final.jsonl", "w", encoding="utf-8") as f:
        for r in sorted(by_code.values(), key=lambda x: x["code"]):
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    by_key = {(r["province"], r["name"]): r for r in depts}
    for r in targets:
        k = (r.get("province", ""), r["name"])
        if k in by_key:
            by_key[k].update(r)
    with open("prov_depts.jsonl", "w", encoding="utf-8") as f:
        for r in sorted(depts, key=lambda x: (x["province"], x["name"])):
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    by_name = {r["name"]: r for r in central}
    for r in targets:
        if r["name"] in by_name:
            by_name[r["name"]].update(r)
    with open("central.jsonl", "w", encoding="utf-8") as f:
        for r in central:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print("p9d 回写完成", flush=True)


if __name__ == "__main__":
    main()
