# -*- coding: utf-8 -*-
"""P187: 市级人大补全——上级对口（省人大官网）通用提取器。"""
import json, os, sys
sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开")
sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开/util")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from smart_fetch import smart_fetch
from extract_org import extract

tree = json.load(open("tree.json", encoding="utf-8"))
blk = next(g for g in tree["ks"] if g["n"].startswith("省级"))
# 省人大官网（从块树省人大节点拿）
PORTS = {}
for p in blk["ks"]:
    for jg in p.get("ks", []):
        if jg.get("k") == "分组":
            for o in jg.get("ks", []):
                if o.get("n") == "省人大" and o.get("u"):
                    PORTS[p["n"]] = o["u"]
tasks = []
for p in blk["ks"]:
    pn = p["n"]
    if not PORTS.get(pn):
        continue
    orgs = {}
    for c in p.get("ks", []):
        if c.get("c") != "地级市人民政府":
            continue
        for jg in c.get("ks", []):
            if jg.get("k") != "分组":
                continue
            for o in jg.get("ks", []):
                if o.get("n") in ("县人大", "市人大") and not o.get("u"):
                    orgs[c["n"] + "人大"] = o
    if orgs:
        tasks.append((pn, PORTS[pn], orgs))
print(f"省人大待扫: {len(tasks)}", flush=True)
STATE_F = "rd_prov_state.json"
state = json.load(open(STATE_F, encoding="utf-8")) if os.path.exists(STATE_F) \
    else {"done": [], "found": {}}
done = set(state["done"])
hit_total = 0
for i, (pn, url, orgs) in enumerate(tasks):
    if pn in done:
        continue
    html, m = smart_fetch(url, timeout=25)
    found_here = 0
    if html and len(html) > 1500:
        r = extract(html, url, orgs, ("人大常委会", "人大"))
        for full_name, (uu, conf, node) in r.items():
            if node is None or node.get("u"):
                continue
            node["u"] = uu
            node["s"] = f"P187 省人大官网提取 置信{conf:.2f}"
            state["found"].setdefault(pn, {})[full_name] = uu
            found_here += 1
    if found_here:
        hit_total += found_here
        print(f"✓ {pn[:9]}: +{found_here}", flush=True)
    else:
        print(f"✗ {pn[:9]}: 0", flush=True)
    done.add(pn)
    state["done"] = sorted(done)
    json.dump(state, open(STATE_F, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    json.dump(tree, open("tree.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"P187 完成: 总命中 {hit_total}", flush=True)
