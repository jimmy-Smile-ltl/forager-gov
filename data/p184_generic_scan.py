# -*- coding: utf-8 -*-
"""P184: 通用提取器统一重扫——三通道:
A. 31 省检察院官网 → 该省市县检察院（检察门户/级联/锚点/任意形态）
B. 361 市检察院官网 → 该市县检察院（纯地名锚文本等任意形态）
C. 135 缺口市的政府门户 → 市政协（导航任意形态）
全部走 util/extract_org.extract() 结构自适应提取, 置信度留痕。"""
import json, os, sys
sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开")
sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开/util")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from smart_fetch import smart_fetch
from extract_org import extract

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

# 建任务清单
tasks = []  # (key, url, org_names{全名: 节点}, kw)
for p in blk["ks"]:
    pn = p["n"]
    prov_names = {}   # 全省市县检察院
    prov_cities = []  # (市名, 市院节点, 市门户URL)
    for c in p.get("ks", []):
        if c.get("c") != "地级市人民政府":
            continue
        shi_node = xian_map = None
        for jg in c.get("ks", []):
            if jg.get("k") != "分组":
                continue
            for o in jg.get("ks", []):
                if o.get("n") == "市人民检察院":
                    shi_node = o
        counties = {}
        for x in c.get("ks", []):
            if x.get("c") != "县级人民政府":
                continue
            for jg in x.get("ks", []):
                if jg.get("k") != "分组":
                    continue
                for o in jg.get("ks", []):
                    if o.get("n") == "县人民检察院":
                        counties[x["n"]] = o
        prov_names[c["n"] + "人民检察院"] = shi_node
        for xn, xo in counties.items():
            prov_names[xn + "人民检察院"] = xo
        prov_cities.append((c["n"], c.get("u", ""), counties))
    # A 通道: 省院官网
    if PORTS.get(pn):
        tasks.append(("A", pn, PORTS[pn], prov_names, ("人民检察院", "检察院")))
    # B 通道: 市院官网
    for cname, portal, counties in prov_cities:
        shi = None
        for jg in [k for k in p.get("ks", []) if 0]:
            pass
        # 找市院URL
        shiyuan = ""
        for c in p.get("ks", []):
            if c["n"] != cname:
                continue
            for jg in c.get("ks", []):
                if jg.get("k") != "分组":
                    continue
                for o in jg.get("ks", []):
                    if o.get("n") == "市人民检察院" and o.get("u"):
                        shiyuan = o["u"]
        if shiyuan and counties:
            orgs = {xn + "人民检察院": xo for xn, xo in counties.items()}
            tasks.append(("B", cname, shiyuan, orgs, ("人民检察院", "检察院")))
    # C 通道: 市门户 → 市政协
    for c in p.get("ks", []):
        if c.get("c") != "地级市人民政府" or not c.get("u"):
            continue
        for jg in c.get("ks", []):
            if jg.get("k") != "分组":
                continue
            for o in jg.get("ks", []):
                if o.get("n") == "县政协" and not o.get("u"):
                    tasks.append(("C", c["n"], c["u"], {c["n"] + "政协": o}, ("政协",)))

print(f"任务总数: {len(tasks)} (A 省院/B 市院/C 市门户政协)", flush=True)
STATE_F = "generic_scan_state.json"
state = json.load(open(STATE_F, encoding="utf-8")) if os.path.exists(STATE_F) \
    else {"done": [], "found": {}}
done = set(state["done"])

hit_total = 0
for i, (ch, key, url, orgs, kw) in enumerate(tasks):
    if key in done:
        continue
    html, m = smart_fetch(url, timeout=25)
    if not html or len(html) < 1500:
        done.add(key)
        continue
    r = extract(html, url, orgs, kw)
    found_here = 0
    for full_name, (uu, conf, node) in r.items():
        if node is None or node.get("u"):
            continue
        node["u"] = uu
        node["s"] = f"P184 通用提取器 {ch}通道 置信{conf:.2f}"
        state["found"].setdefault(key, {})[full_name] = uu
        found_here += 1
    if found_here:
        hit_total += found_here
        print(f"✓[{ch}] {key[:14]}: +{found_here}", flush=True)
    done.add(key)
    if (i + 1) % 30 == 0:
        state["done"] = sorted(done)
        json.dump(state, open(STATE_F, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
        json.dump(tree, open("tree.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"  进度 {i+1}/{len(tasks)} 累计 {hit_total}", flush=True)
state["done"] = sorted(done)
json.dump(state, open(STATE_F, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
json.dump(tree, open("tree.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"P184 完成: 总命中 {hit_total}", flush=True)
