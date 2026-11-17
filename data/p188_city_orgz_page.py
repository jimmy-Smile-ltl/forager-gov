# -*- coding: utf-8 -*-
"""P188: 市门户首页无并列机关导航 → 进「组织机构/机构设置」页提取。
入口从首页真实链接找（机构/组织/概况 关键词），不猜路径。"""
import json, os, re, sys
from urllib.parse import urljoin
sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开")
sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开/util")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from smart_fetch import smart_fetch
from extract_org import extract

tree = json.load(open("tree.json", encoding="utf-8"))
blk = next(g for g in tree["ks"] if g["n"].startswith("省级"))
KW_MAP = {"市人大": ("人大常委会", "人大"), "县人大": ("人大常委会", "人大"),
          "县政协": ("政协",), "市政协": ("政协",),
          "县监委": ("监察委", "监委"),
          "县人民检察院": ("检察院",), "市人民检察院": ("检察院",)}
ENTRY = re.compile(r"机构设置|组织机构|机构概况|市政府机构|部门机构")
tasks = []
for p in blk["ks"]:
    for c in p.get("ks", []):
        if c.get("c") != "地级市人民政府" or not c.get("u"):
            continue
        orgs = {}
        for jg in c.get("ks", []):
            if jg.get("k") != "分组":
                continue
            for o in jg.get("ks", []):
                if o.get("n") in KW_MAP and not o.get("u"):
                    orgs[c["n"] + o["n"].replace("县", "").replace("市", "")] = o
        if orgs:
            tasks.append((c["n"], c["u"], orgs))
print(f"待扫市门户(组织机构页): {len(tasks)}", flush=True)
STATE_F = "city_orgz_state.json"
state = json.load(open(STATE_F, encoding="utf-8")) if os.path.exists(STATE_F) \
    else {"done": [], "found": {}}
done = set(state["done"])
hit_total = 0
for i, (cname, url, orgs) in enumerate(tasks):
    if cname in done:
        continue
    html, m = smart_fetch(url, timeout=25)
    found_here = 0
    if html and len(html) > 1500:
        # 1) 首页再试一次（P186 落库后剩余缺口可能首页就有）
        r = extract(html, url, orgs, ("人大常委会", "人大", "政协", "法院", "检察院", "监委"))
        for full_name, (uu, conf, node) in r.items():
            if node is None or node.get("u"):
                continue
            node["u"] = uu
            node["s"] = f"P188 市门户首页提取 置信{conf:.2f}"
            state["found"].setdefault(cname, {})[full_name] = uu
            found_here += 1
        # 2) 找机构页入口
        entry_url = ""
        for uu, tt in re.findall(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>\s*([^<]{2,30}?)\s*</a>', html, re.S):
            if ENTRY.search(tt) and uu.startswith(("http", "/")):
                entry_url = urljoin(url, uu)
                break
        if entry_url and entry_url != url:
            h2, m2 = smart_fetch(entry_url, timeout=25)
            if h2 and len(h2) > 1500:
                r2 = extract(h2, entry_url, orgs, ("人大常委会", "人大", "政协", "法院", "检察院", "监委"))
                for full_name, (uu, conf, node) in r2.items():
                    if node is None or node.get("u"):
                        continue
                    node["u"] = uu
                    node["s"] = f"P188 组织机构页提取 置信{conf:.2f}"
                    state["found"].setdefault(cname, {})[full_name] = uu
                    found_here += 1
    if found_here:
        hit_total += found_here
        print(f"✓ {cname}: +{found_here}", flush=True)
    done.add(cname)
    if (i + 1) % 25 == 0:
        state["done"] = sorted(done)
        json.dump(state, open(STATE_F, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
        json.dump(tree, open("tree.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"  进度 {i+1}/{len(tasks)} 累计 {hit_total}", flush=True)
state["done"] = sorted(done)
json.dump(state, open(STATE_F, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
json.dump(tree, open("tree.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"P188 完成: 总命中 {hit_total}", flush=True)
