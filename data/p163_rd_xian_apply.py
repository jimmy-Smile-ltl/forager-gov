# -*- coding: utf-8 -*-
"""P163: p162 渲染结果验证+落库（连通性 title 验证防死链）。"""
import json
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")

rows = [json.loads(l) for l in open("rd_xian_render.jsonl", encoding="utf-8")]
tree = json.load(open("tree.json", encoding="utf-8"))
tiao = next(g for g in tree["ks"] if g["n"].startswith("条"))
rd = next(g for g in tiao["ks"] if g["n"].startswith("人大系统"))
gy = next(x for x in rd["ks"] if x["n"].startswith("省级人大"))

# 收集候选（渲染轮命中 + 已有）
cands = {}
for r in rows:
    for cn, u in r["hits"].items():
        if u:
            cands[(r["province"], r["shi"], cn)] = u

# 已有 URL 的节点不重复验证
have = set()
for p in gy["ks"]:
    for s in p.get("ks", []):
        for k in s.get("ks", []):
            if k.get("u"):
                have.add((p["n"].replace("人大", ""), s["n"], k["n"].replace("人大", "")))
cands = {k: v for k, v in cands.items() if k not in have}
print(f"候选: {len(cands)}")

def verify(key_u):
    key, u = key_u
    pn, shiname, cn = key
    try:
        r = subprocess.run(["curl", "-s", "--compressed", "-L", "--max-time", "9",
                            "-A", UA, u], capture_output=True, timeout=12)
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
        if len(raw) < 200:
            return key, None
        m = re.search(r"<title>([^<]*)</title>", t)
        title = m.group(1).strip() if m else ""
        core = re.sub(r'(自治县|区|县|旗|市)$', '', cn)
        if len(core) >= 2 and core in title and ("人大" in title or "人大" in t[:3000]):
            return key, u
        return key, None
    except Exception:
        return key, None

ok = []
with ThreadPoolExecutor(max_workers=8) as ex:
    futs = {ex.submit(verify, kv): kv for kv in cands.items()}
    for f in as_completed(futs):
        key, u = f.result()
        if u:
            ok.append((key, u))
print(f"验证通过: {len(ok)}")

# 落库
filled = 0
for (pn, shiname, cn), u in ok:
    p = next((x for x in gy["ks"] if x["n"].replace("人大", "") == pn), None)
    if not p:
        continue
    shi = next((s for s in p.get("ks", []) if s["n"] == shiname), None)
    if not shi:
        continue
    nm = f"{cn}人大"
    for k in shi.get("ks", []):
        if k["n"] == nm and not k.get("u"):
            k["u"] = u
            filled += 1
            break
json.dump(tree, open("tree.json", "w", encoding="utf-8"),
          ensure_ascii=False, separators=(",", ":"))
print(f"落库 {filled}")
n = u_n = 0
for p in gy["ks"]:
    for s in p.get("ks", []):
        n += len(s.get("ks", []))
        u_n += sum(1 for k in s.get("ks", []) if k.get("u"))
print(f"人大县级: {u_n}/{n}")
