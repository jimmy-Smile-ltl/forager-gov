# -*- coding: utf-8 -*-
"""P182: 县级检察院补全——市检察院官网首页提取基层院链接
（锚文本=纯区县名, 石家庄院实锤模式: 长安区/藁城区/正定县...）。
锚文本匹配该市下辖县级行政区划名 + 域名 jcy.gov.cn 优先。"""
import json, os, re, sys
from urllib.parse import urljoin
sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开")
sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开/util")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from smart_fetch import smart_fetch

tree = json.load(open("tree.json", encoding="utf-8"))
blk = next(g for g in tree["ks"] if g["n"].startswith("省级"))

# 任务: 市 → (市院URL, {县级名: 县检察院节点})
jobs = []
for p in blk["ks"]:
    for city in p.get("ks", []):
        if city.get("c") != "地级市人民政府":
            continue
        shiyuan = ""
        for jg in city.get("ks", []):
            if jg.get("k") != "分组":
                continue
            for o in jg.get("ks", []):
                if o.get("n") == "市人民检察院" and o.get("u"):
                    shiyuan = o["u"]
        if not shiyuan:
            continue
        counties = {}
        for x in city.get("ks", []):
            if x.get("c") != "县级人民政府":
                continue
            for jg in x.get("ks", []):
                if jg.get("k") != "分组":
                    continue
                for o in jg.get("ks", []):
                    if o.get("n") == "县人民检察院" and not o.get("u"):
                        counties[x["n"]] = o
        if counties:
            jobs.append({"city": city["n"], "u": shiyuan, "counties": counties})
print(f"待扫市院: {len(jobs)} 个", flush=True)

STATE_F = "jc_jiceng_state.json"
state = json.load(open(STATE_F, encoding="utf-8")) if os.path.exists(STATE_F) \
    else {"done": [], "found": {}}
done = set(state["done"])
LINK = re.compile(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>\s*([^<]{2,20}?)\s*</a>', re.S)

hit_total = 0
for i, j in enumerate(jobs):
    if j["city"] in done:
        continue
    html, m = smart_fetch(j["u"], timeout=25)
    found_here = 0
    if html and len(html) > 2000:
        for uu, txt in LINK.findall(html):
            t2 = re.sub(r"\s+", "", txt)
            node = j["counties"].get(t2)
            if not node:
                continue
            if "javascript" in uu or uu in ("#", ""):
                continue
            full = urljoin(j["u"], uu) if not uu.startswith("http") else uu
            node["u"] = full
            node["s"] = "P182 市检察院官网基层院链接（纯地名锚文本）真实提取"
            state["found"].setdefault(j["city"], {})[t2] = full
            found_here += 1
    if found_here:
        hit_total += found_here
        print(f"✓ {j['city']}: +{found_here}", flush=True)
    done.add(j["city"])
    if (i + 1) % 15 == 0:
        state["done"] = sorted(done)
        json.dump(state, open(STATE_F, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
        json.dump(tree, open("tree.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"  进度 {i+1}/{len(jobs)} 累计命中 {hit_total}", flush=True)
state["done"] = sorted(done)
json.dump(state, open(STATE_F, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
json.dump(tree, open("tree.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"P182 完成: 总命中 {hit_total}", flush=True)
