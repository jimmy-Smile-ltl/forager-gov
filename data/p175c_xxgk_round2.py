# -*- coding: utf-8 -*-
"""P175c: 信息公开专栏第二轮（curl 静态）——修复 p173 缺陷：
(1) './' 相对路径拼接 (2) 关键词扩充（法定主动公开/指南/xxgk 路径）
(3) 失败站点重试。只针对仍缺 x 的有官网叶子。断点续跑。"""
import json, os, re, subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
STATE_F = "xxgk_round2_state.json"
state = json.load(open(STATE_F, encoding="utf-8")) if os.path.exists(STATE_F) \
    else {"done": [], "found": {}}
done = set(state["done"]); found = state["found"]

tree = json.load(open("tree.json", encoding="utf-8"))
jobs = []
def walk(n):
    if n.get("u") and not n.get("ks") and not n.get("x"):
        jobs.append(n)
    for k in n.get("ks", []): walk(k)
walk(tree)
jobs = [j for j in jobs if j["u"] not in done and j["u"] not in found]
print(f"待采集: {len(jobs)} 站点", flush=True)

KW = ("政府信息公开", "政务公开", "信息公开", "司法公开", "检务公开",
      "法定主动公开", "公开指南", "xxgk", "zfxxgk")

def probe(j):
    u = j["u"]
    try:
        r = subprocess.run(["curl", "-s", "--compressed", "-L", "--max-time", "12",
                            "-A", UA, u], capture_output=True, timeout=15)
        raw = r.stdout
        t = None
        for enc in ("utf-8", "gb18030"):
            try: t = raw.decode(enc); break
            except UnicodeDecodeError: continue
        if t is None: t = raw.decode("utf-8", errors="replace")
        best = None
        for uu, txt in re.findall(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>\s*([^<]{2,24}?)\s*</a>', t):
            t2 = txt.strip()
            if any(k in t2 for k in KW):
                if uu.startswith(("http", "/", "./")):
                    best = urljoin(u, uu)
                    break
        return u, best
    except Exception:
        return u, None

found_new = {}
with ThreadPoolExecutor(max_workers=10) as ex:
    futs = {ex.submit(probe, j): j for j in jobs}
    for f in as_completed(futs):
        u, best = f.result()
        done.add(u)
        if best:
            found_new[u] = best
            found[u] = best
        if len(done) % 400 == 0:
            print(f"{len(done)}/{len(jobs)+len(done)}", flush=True)
state["done"] = sorted(done); state["found"] = found
json.dump(state, open(STATE_F, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
print(f"p175c 完成: 命中 {len(found_new)} 个", flush=True)
