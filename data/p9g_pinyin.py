# -*- coding: utf-8 -*-
"""P9g: 拼音候选 + smart_fetch 验证（pypinyin 缺失修复版）。

对仍无门户的真实区县：拼音域名候选（含例外表）→ smart_fetch 抓取验证标题。
运行方式: uv run --with pypinyin python p9g_pinyin.py
"""
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

from common import norm_url  # noqa: E402
from p7_browser_final import candidates_for, PSEUDO  # noqa: E402
from p3b_fallback import short_name  # noqa: E402

PSEUDO_RE = re.compile(
    r"(市辖区|开发区|高新区|管理区|园区|工业区|示范区|合作区|保税区|实验区|管委会|循环化工园区|风景名胜区|新城)")


def sf(url):
    try:
        from util.smart_fetch import smart_fetch
        html, method = smart_fetch(url, timeout=25)
        return html
    except Exception:
        return None


def sf_verify(url, name):
    html = sf(url)
    if not html or len(html) < 800:
        return False
    m = re.search(r"<title>(.*?)</title>", html, re.S | re.I)
    if not m:
        return False
    title = re.sub(r"[\s|·\-—]", "", m.group(1))
    sn = short_name(name)
    return bool(sn and sn in title and "政务服" not in title)


def main():
    cc = [json.loads(l) for l in open("city_county_final.jsonl", encoding="utf-8")]
    todo = [r for r in cc if not r.get("portal_url") and not PSEUDO_RE.search(r["name"])]
    print(f"p9g 目标 {len(todo)}", flush=True)
    lock = threading.Lock()
    ok = 0

    def worker(r):
        for host in candidates_for(r["name"]):
            if not host:
                continue
            for scheme in ("https", "http"):
                if sf_verify(f"{scheme}://{host}/", r["name"]):
                    r["portal_url"] = norm_url(f"{scheme}://{host}/")
                    r["how"] = "p9g拼音(smart_fetch)"
                    return True
        return False

    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = {ex.submit(worker, r): r for r in todo}
        for i, f in enumerate(as_completed(futs)):
            r = f.result()
            with lock:
                ok += 1 if r else 0
                if (i + 1) % 30 == 0:
                    print(f"[p9g] {i+1}/{len(todo)} ok={ok}", flush=True)
    print(f"[p9g] done ok={ok}/{len(todo)}", flush=True)

    with open("city_county_final.jsonl", "w", encoding="utf-8") as f:
        for r in sorted(cc, key=lambda x: x["code"]):
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print("p9g 回写完成", flush=True)


if __name__ == "__main__":
    main()
