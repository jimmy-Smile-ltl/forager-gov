# -*- coding: utf-8 -*-
"""P9a: 用 college teacher/util 的 smart_fetch（五级降级含瑞数）补齐
「有门户但无 xxgk」的行。

只读共享浏览器池（9222/9333/DrissionPage 由 college teacher watchdog 管理），
本脚本不启动/不杀任何浏览器。低并发（4 worker）避免挤占采集管线。
"""
import json
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

_UTIL = "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开/util"
_ROOT = "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开"
sys.path.insert(0, _ROOT)
sys.path.insert(0, _UTIL)
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))

from common import find_xxgk_url, norm_url  # noqa: E402


def sf_fetch(url):
    """smart_fetch 封装：返回 html 或 None。异常兜底。"""
    try:
        from smart_fetch import smart_fetch
        html, method = smart_fetch(url, timeout=20)
        return html
    except Exception:
        return None


def resolve(r):
    """r 有 portal_url 无 xxgk_url → smart_fetch 首页找专栏链接。"""
    html = sf_fetch(r["portal_url"])
    if html:
        u = find_xxgk_url(html, r["portal_url"])
        if u:
            r["xxgk_url"] = norm_url(u)
            r["xxgk_src"] = "smart_fetch导航"
            return True
    return False


def load_rows(fn):
    return [json.loads(l) for l in open(fn, encoding="utf-8")]


def save_rows(fn, rows):
    with open(fn, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def main():
    targets = []
    for fn in ("city_county_final.jsonl",):
        targets += [r for r in load_rows(fn) if r.get("portal_url") and not r.get("xxgk_url")]
    targets += [r for r in load_rows("prov_depts.jsonl")
                if r.get("portal_url") and not r.get("xxgk_url")]
    targets += [r for r in load_rows("central.jsonl") if not r.get("xxgk_url")]
    print(f"p9a 目标 {len(targets)}", flush=True)

    ok = 0
    lock = threading.Lock()
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = {ex.submit(resolve, r): r for r in targets}
        for i, f in enumerate(as_completed(futs)):
            r = f.result()
            with lock:
                ok += 1 if r else 0
                if (i + 1) % 15 == 0:
                    print(f"[p9a] {i+1}/{len(targets)} ok={ok}", flush=True)
    print(f"[p9a] done ok={ok}/{len(targets)}", flush=True)

    # 回写
    for fn in ("city_county_final.jsonl",):
        rows = load_rows(fn)
        by_code = {r["code"]: r for r in rows}
        for r in targets:
            if r.get("code") and r["code"] in by_code:
                by_code[r["code"]].update(r)
        save_rows(fn, sorted(by_code.values(), key=lambda x: x["code"]))

    rows = load_rows("prov_depts.jsonl")
    by_key = {(r["province"], r["name"]): r for r in rows}
    for r in targets:
        k = (r.get("province", ""), r["name"])
        if k in by_key:
            by_key[k].update(r)
    save_rows("prov_depts.jsonl", sorted(rows, key=lambda x: (x["province"], x["name"])))

    rows = load_rows("central.jsonl")
    by_name = {r["name"]: r for r in rows}
    for r in targets:
        if r["name"] in by_name:
            by_name[r["name"]].update(r)
    save_rows("central.jsonl", rows)

    print("p9a 回写完成", flush=True)


if __name__ == "__main__":
    main()
