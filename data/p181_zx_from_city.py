# -*- coding: utf-8 -*-
"""P181: 市级政协补全——从市政府门户首页/组织机构页提取「政协」链接
（权威源第 2 档：同级政府门户导航）。断点续跑。"""
import json, os, re, sys
from urllib.parse import urljoin
sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开")
sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开/util")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from smart_fetch import smart_fetch

tree = json.load(open("tree.json", encoding="utf-8"))
blk = next(g for g in tree["ks"] if g["n"].startswith("省级"))
jobs = []  # (省名, 市名, 门户URL, 市政协节点引用)
for p in blk["ks"]:
    pn = p["n"]
    for city in p.get("ks", []):
        if city.get("c") not in ("地级市人民政府", "市辖区（地级行政区划）", "省直辖县级市/县/林区", "直辖市辖县（县级行政区划）"):
            continue
        if not city.get("u"):
            continue
        for jg in city.get("ks", []):
            if jg.get("k") != "分组":
                continue
            for o in jg.get("ks", []):
                if o.get("n") in ("县政协", "市政协") and not o.get("u"):
                    jobs.append({"pn": pn, "cn": city["n"], "portal": city["u"], "node": o})
print(f"待补: {len(jobs)} 个市政协", flush=True)

STATE_F = "zx_city3_state.json"
state = json.load(open(STATE_F, encoding="utf-8")) if os.path.exists(STATE_F) \
    else {"done": [], "found": {}}
done = set(state["done"])

LINK = re.compile(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>\s*([^<]{2,30}?)\s*</a>', re.S)
for i, j in enumerate(jobs):
    key = j["cn"]
    if key in done:
        continue
    html, m = smart_fetch(j["portal"], timeout=25)
    hit = ""
    if html and len(html) > 2000:
        for uu, txt in LINK.findall(html):
            t2 = re.sub(r"\s+", "", txt)
            if "政协" in t2 and not any(b in uu for b in ("javascript", "void", "#")):
                hit = urljoin(j["portal"], uu) if not uu.startswith("http") else uu
                break
    if hit:
        state["found"][key] = {"u": hit, "portal": j["portal"]}
        j["node"]["u"] = hit
        j["node"]["s"] = "P181 市政府门户首页「政协」导航真实链接提取"
        print(f"✓ {j['pn'][:6]}{key}: {hit}", flush=True)
    else:
        print(f"✗ {j['pn'][:6]}{key}: 门户首页无政协链接 ({m})", flush=True)
    done.add(key)
    if (i + 1) % 20 == 0:
        state["done"] = sorted(done)
        state["found"] = {**state["found"]}
        json.dump(state, open(STATE_F, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
        json.dump(tree, open("tree.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
state["done"] = sorted(done)
json.dump(state, open(STATE_F, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
json.dump(tree, open("tree.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"P181 完成: 命中 {len(state['found'])}", flush=True)
