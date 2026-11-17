# -*- coding: utf-8 -*-
"""P9e: 修复坏 xxgk（文章页误配）+ 二次解析剩余无 xxgk 行（article 过滤版）。"""
import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

_ROOT = "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开"
_UTIL = _ROOT + "/util"
sys.path.insert(0, _ROOT)
sys.path.insert(0, _UTIL)
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))

from common import find_xxgk_url, norm_url, is_article_url, probe_xxgk_paths  # noqa: E402


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
        if u and not is_article_url(u):
            r["xxgk_url"] = norm_url(u)
            r["xxgk_src"] = "smart_fetch导航v3"
            return True
    # 探测兜底（非文章页校验由 probe 天然满足）
    u = probe_xxgk_paths(r["portal_url"])
    if u:
        r["xxgk_url"] = norm_url(u)
        r["xxgk_src"] = "路径探测"
        return True
    return False


def main():
    cc = [json.loads(l) for l in open("city_county_final.jsonl", encoding="utf-8")]
    targets = []
    for r in cc:
        if r.get("portal_url") and (not r.get("xxgk_url") or is_article_url(r.get("xxgk_url", ""))):
            targets.append(r)
    print(f"p9e 目标 {len(targets)}", flush=True)

    ok = 0
    lock = threading.Lock()
    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = {ex.submit(resolve, r): r for r in targets}
        for i, f in enumerate(as_completed(futs)):
            r = f.result()
            with lock:
                ok += 1 if r else 0
                if (i + 1) % 20 == 0:
                    print(f"[p9e] {i+1}/{len(targets)} ok={ok}", flush=True)
    print(f"[p9e] done ok={ok}/{len(targets)}", flush=True)

    with open("city_county_final.jsonl", "w", encoding="utf-8") as f:
        for r in sorted(cc, key=lambda x: x["code"]):
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print("p9e 回写完成", flush=True)


if __name__ == "__main__":
    main()
