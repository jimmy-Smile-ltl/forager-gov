# -*- coding: utf-8 -*-
"""P159: URL 质量抽查——分层随机抽样 + 连通性 + title 身份验证。"""
import json
import random
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
random.seed(42)

tree = json.load(open("tree.json", encoding="utf-8"))
prov = next(g for g in tree["ks"] if g["n"].startswith("省级"))
tiao = next(g for g in tree["ks"] if g["n"].startswith("条"))

# 分层抽样
samples = {}

# 1. 省级门户
samples["省级政府门户"] = [(p["n"], p["u"]) for p in prov["ks"] if p.get("u")]

# 2. 市级人大
rd = next(g for g in tiao["ks"] if g["n"].startswith("人大系统"))
gy = next(x for x in rd["ks"] if x["n"].startswith("省级人大"))
shi_rd = [(s["n"], s["u"]) for p in gy["ks"] for s in p.get("ks", []) if s.get("u")]
samples["市级人大"] = shi_rd

# 3. 市级政协
zx = next(g for g in tiao["ks"] if g["n"].startswith("政协系统"))
gyz = next(x for x in zx["ks"] if x["n"].startswith("省级政协"))
shi_zx = [(s["n"], s["u"]) for p in gyz["ks"] for s in p.get("ks", []) if s.get("u")]
samples["市级政协"] = shi_zx

# 4. 市级检察院（本轮 SERP 补的）
jc = next(g for g in tiao["ks"] if g["n"].startswith("检察院系统"))
prov_jc = next(g for g in jc["ks"] if "省级检察院" in g["n"])
shi_jc = [(s["n"], s["u"]) for p in prov_jc["ks"] for s in p.get("ks", []) if s.get("u")]
samples["市级检察院"] = shi_jc

# 5. 群团省级
qt = next(g for g in tiao["ks"] if "群团" in g["n"])
quntuan = [(k["n"], k["u"]) for g in qt["ks"] for k in g.get("ks", [])
           if k.get("u") and k.get("l") == "省"]
samples["群团省级"] = quntuan

# 6. 县级人大（本轮新采）
xian_rd = [(k["n"], k["u"]) for p in gy["ks"] for s in p.get("ks", [])
           for k in s.get("ks", []) if k.get("u")]
samples["县级人大"] = xian_rd

# 7. 法院
fy = next(g for g in tiao["ks"] if g["n"].startswith("法院系统"))
fayuan = []
def walk_fy(n):
    if n.get("u") and n.get("l") in ("市", "县"):
        fayuan.append((n["n"], n["u"]))
    for k in n.get("ks", []):
        walk_fy(k)
walk_fy(fy)
samples["法院"] = fayuan

def verify(nm, u):
    try:
        r = subprocess.run(["curl", "-s", "--compressed", "-L", "--max-time", "10",
                            "-A", UA, u], capture_output=True, timeout=14)
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
        m = re.search(r"<title>([^<]*)</title>", t)
        title = m.group(1).strip() if m else ""
        # 身份核验：机构名核心 2 字在 title
        core = re.sub(r"(人民政府|人民代表大会常务委员会|人大常委会|政协|检察院|人民法院|工会|妇联|团委|委员会|联合会|协会|学会)$", "", nm)
        core = re.sub(r"(省|市|自治区|自治州|地区|盟|县|区|旗)$", "", core)
        core = core[-2:] if len(core) > 2 else core
        ok = bool(core) and core in title
        return ok, title[:45], len(t)
    except Exception as e:
        return False, str(e)[:30], 0

print("== URL 质量抽查（随机抽样）==")
total_bad = 0
for cat, pool in samples.items():
    if not pool:
        print(f"{cat}: 无样本")
        continue
    n = min(10, len(pool))
    picks = random.sample(pool, n)
    ok_n = 0
    print(f"\n【{cat}】抽 {n}/{len(pool)} 个:")
    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = {ex.submit(verify, nm, u): (nm, u) for nm, u in picks}
        for f in as_completed(futs):
            nm, u = futs[f]
            ok, title, size = f.result()
            if ok:
                ok_n += 1
            else:
                total_bad += 1
                print(f"  ✗ {nm}: {u[:55]}")
                print(f"      title={title} size={size}")
    print(f"  通过 {ok_n}/{n}")
print(f"\n总异常: {total_bad}")
