# -*- coding: utf-8 -*-
"""P183: 市级检察院补全——省检察院官网 select 下拉/锚点提取
「XX市人民检察院」链接（山东省院 select 形态实锤）。"""
import json, os, re, sys
sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开")
sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开/util")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from smart_fetch import smart_fetch

tree = json.load(open("tree.json", encoding="utf-8"))
blk = next(g for g in tree["ks"] if g["n"].startswith("省级"))

PORTS = {"北京市": "http://www.bjjc.gov.cn/bjoweb/", "天津市": "http://www.tj.jcy.gov.cn/",
 "河北省": "http://www.he.jcy.gov.cn/", "山西省": "http://www.sx.jcy.gov.cn/",
 "内蒙古自治区": "http://www.nm.jcy.gov.cn", "辽宁省": "http://www.ln.jcy.gov.cn/",
 "吉林省": "http://www.jl.jcy.gov.cn/", "黑龙江省": "https://www.hljjcy.gov.cn/",
 "上海市": "https://www.sh.jcy.gov.cn/", "江苏省": "http://www.jsjc.gov.cn/",
 "浙江省": "http://www.zjjcy.gov.cn/", "安徽省": "http://www.ah.jcy.gov.cn",
 "福建省": "http://www.fj.jcy.gov.cn/", "江西省": "http://www.jx.jcy.gov.cn/",
 "山东省": "http://www.sdjcy.gov.cn/", "河南省": "http://www.ha.jcy.gov.cn/",
 "湖北省": "http://www.hbjc.gov.cn/", "湖南省": "http://www.hn.jcy.gov.cn/",
 "广东省": "http://www.gd.jcy.gov.cn/", "广西壮族自治区": "http://www.gx.jcy.gov.cn",
 "海南省": "http://www.hi.jcy.gov.cn/", "重庆市": "http://www.cq.jcy.gov.cn/",
 "四川省": "http://www.sc.jcy.gov.cn/", "贵州省": "http://www.gz.jcy.gov.cn/",
 "云南省": "http://www.yn.jcy.gov.cn/", "西藏自治区": "http://www.xz.jcy.gov.cn/",
 "陕西省": "http://www.sn.jcy.gov.cn/", "甘肃省": "http://www.jcy.gansu.gov.cn/",
 "青海省": "http://www.qh.jcy.gov.cn/", "宁夏回族自治区": "http://www.nx.jcy.gov.cn/QJCY/index.html",
 "新疆维吾尔自治区": "http://www.xj.jcy.gov.cn/"}

# 省 → {市名: 节点}
prov_cities = {}
for p in blk["ks"]:
    cities = {}
    for city in p.get("ks", []):
        if city.get("c") != "地级市人民政府":
            continue
        for jg in city.get("ks", []):
            if jg.get("k") != "分组":
                continue
            for o in jg.get("ks", []):
                if o.get("n") == "市人民检察院" and not o.get("u"):
                    cities[city["n"]] = o
    if cities:
        prov_cities[p["n"]] = cities

STATE_F = "jc_shi_prov_state.json"
state = json.load(open(STATE_F, encoding="utf-8")) if os.path.exists(STATE_F) \
    else {"done": [], "found": {}}
done = set(state["done"])

OPT = re.compile(r'<option[^>]+value=["\']([^"\']+)["\'][^>]*>\s*([^<]{4,30}?)\s*</option>', re.S)
A = re.compile(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>\s*([^<]{4,30}?)\s*</a>', re.S)
hit_total = 0
for pn, cities in prov_cities.items():
    if pn in done:
        continue
    u = PORTS.get(pn, "")
    if not u:
        done.add(pn); continue
    html, m = smart_fetch(u, timeout=25)
    found_here = 0
    if html and len(html) > 2000:
        pairs = []
        for uu, txt in OPT.findall(html):
            pairs.append((re.sub(r"\s+", "", txt), uu))
        for uu, txt in A.findall(html):
            pairs.append((re.sub(r"\s+", "", txt), uu))
        for txt, uu in pairs:
            m2 = re.match(r"^([一-龥]{2,8}市)人民检察院$", txt)
            if not m2:
                continue
            cname = m2.group(1)
            node = cities.get(cname)
            if not node:
                continue
            if not uu.startswith("http") or "javascript" in uu:
                continue
            node["u"] = uu
            node["s"] = "P183 省检察院官网「市州分院」下拉/导航真实提取"
            state["found"].setdefault(pn, {})[cname] = uu
            found_here += 1
    if found_here:
        hit_total += found_here
        print(f"✓ {pn[:9]}: +{found_here}", flush=True)
    else:
        print(f"✗ {pn[:9]}: 0 ({m})", flush=True)
    done.add(pn)
    state["done"] = sorted(done)
    json.dump(state, open(STATE_F, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    json.dump(tree, open("tree.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"P183 完成: 总命中 {hit_total}", flush=True)
