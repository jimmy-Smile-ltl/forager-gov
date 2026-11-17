# -*- coding: utf-8 -*-
"""P186: 本级政府门户提取并列机关全套——用户方法论:
「本级人民政府网站一般有本级人大政协」。
市政府门户 → 市人大/市政协/市法院/市检察院/市监委 通用提取器一把抓。"""
import json, os, sys
sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开")
sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开/util")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from smart_fetch import smart_fetch
from extract_org import extract

tree = json.load(open("tree.json", encoding="utf-8"))
blk = next(g for g in tree["ks"] if g["n"].startswith("省级"))
KW_MAP = {"市人大": ("人大常委会", "人大"), "县人大": ("人大常委会", "人大"),
          "县政协": ("政协",), "市政协": ("政协",),
          "县监委": ("监察委", "监委"), "县人民法院": ("法院",),
          "县人民检察院": ("检察院",), "市人民检察院": ("检察院",)}
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
print(f"待扫市门户: {len(tasks)}", flush=True)

STATE_F = "city_orgs_state.json"
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
        r = extract(html, url, orgs,
                    ("人大常委会", "人大", "政协", "法院", "检察院", "监委"))
        for full_name, (uu, conf, node) in r.items():
            if node is None or node.get("u"):
                continue
            node["u"] = uu
            node["s"] = f"P186 本级政府门户导航提取 置信{conf:.2f}"
            state["found"].setdefault(cname, {})[full_name] = uu
            found_here += 1
        # 短名兜底: 页面锚文本「市人大/市政协」等 → 该市唯一缺 URL 机关
        import re as _re
        SHORT = {"市人大常委会": "人大", "市人大": "人大", "市政协": "政协",
                 "市中级人民法院": "法院", "市法院": "法院",
                 "市人民检察院": "检察院", "市检察院": "检察院", "市监委": "监委"}
        # 该市缺 URL 的机关节点
        want = {}
        for fn, node in orgs.items():
            for sn, cat in SHORT.items():
                if fn.endswith(sn):
                    want.setdefault(cat, node)
        for uu, tt in _re.findall(
                r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>\s*([^<]{2,20}?)\s*</a>', html, _re.S):
            tt2 = _re.sub(r"\s+", "", tt)
            cat = SHORT.get(tt2)
            if not cat or cat not in want:
                continue
            node = want[cat]
            if node.get("u") or not uu.startswith(("http", "/")):
                continue
            from urllib.parse import urljoin as _uj
            full = _uj(url, uu) if not uu.startswith("http") else uu
            node["u"] = full
            node["s"] = "P186 本级政府门户短名导航提取"
            state["found"].setdefault(cname, {})[tt2] = full
            found_here += 1
            del want[cat]
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
print(f"P186 完成: 总命中 {hit_total}", flush=True)
