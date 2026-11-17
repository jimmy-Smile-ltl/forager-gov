# -*- coding: utf-8 -*-
"""P173: 信息公开专栏增量采集——有官网无专栏 URL 的机构。

关键词：政府信息公开/政务公开（行政机关）；司法公开（法院）；
检务公开（检察院）；人大/政协/纪委信息公开。断点续跑。
"""
import json
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
STATE_F = "xxgk_patch_state.json"
import os
state = json.load(open(STATE_F, encoding="utf-8")) if os.path.exists(STATE_F) \
    else {"done": [], "found": {}}
done = set(state["done"])
found = state["found"]

tree = json.load(open("tree.json", encoding="utf-8"))
# 收集目标：有 u 无 x 的叶子
jobs = []
def walk(n, cat):
    if n.get("u") and not n.get("ks") and not n.get("x"):
        k = n.get("k", "")
        c = n.get("c", "")
        kw = []
        if "法院" in (k + c):
            kw = ["司法公开", "信息公开"]
        elif "检察" in (k + c):
            kw = ["检务公开", "信息公开"]
        else:
            kw = ["政府信息公开", "政务公开", "信息公开"]
        jobs.append({"name": n["n"], "u": n["u"], "kw": kw, "cat": cat})
    for k in n.get("ks", []):
        walk(k, cat)
walk(tree, "")
jobs = [j for j in jobs if j["name"] not in done and j["name"] not in found]
print(f"待采集: {len(jobs)} 机构", flush=True)

def probe(j):
    """抓首页找专栏链接。"""
    u = j["u"]
    try:
        r = subprocess.run(["curl", "-s", "--compressed", "-L", "--max-time", "10",
                            "-A", UA, u], capture_output=True, timeout=13)
        raw = r.stdout
        t = None
        for enc in ("utf-8", "gb18030"):
            try:
                t = raw.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        if t is None:
            t = raw.decode("utf-8", errors="replace")
        best = None
        for uu, txt in re.findall(
                r'<a[^>]+href="([^"]+)"[^>]*>\s*([^<]{2,20}?)\s*</a>', t):
            t2 = txt.strip()
            if any(kw in t2 for kw in j["kw"]):
                if uu.startswith("http"):
                    best = uu
                elif uu.startswith("/"):
                    m = re.match(r'https?://[^/]+', u)
                    best = (m.group(0) if m else u.rstrip("/")) + uu
                break
        return j, best
    except Exception:
        return j, None

found_new = {}
with ThreadPoolExecutor(max_workers=10) as ex:
    futs = {ex.submit(probe, j): j for j in jobs}
    for f in as_completed(futs):
        j, best = f.result()
        done.add(j["name"])
        if best:
            found_new[j["name"]] = best
            found[j["name"]] = {"u": best, "cat": j["cat"]}
        if len(done) % 300 == 0:
            print(f"{len(done)}/{len(jobs) + len(done)}", flush=True)
state["done"] = sorted(done)
state["found"] = found
json.dump(state, open(STATE_F, "w", encoding="utf-8"),
          ensure_ascii=False, indent=0)
print(f"p173 完成: 命中 {len(found_new)} 个专栏")
