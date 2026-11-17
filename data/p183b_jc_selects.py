# -*- coding: utf-8 -*-
"""P183b: 省检察院官网「检察门户」级联下拉提取——select 分块,
首 option 文本=市名, 后续 option 文本=县名(纯地名), value=院 URL。
黑龙江实锤: jmsfy/jmstj(佳木斯抚远/同江)、dqsrtq(大庆萨尔图)。"""
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

# 省 → {市名: {县名: 县检察院节点, "_shi": 市检察院节点}}
prov_data = {}
for p in blk["ks"]:
    data = {}
    for city in p.get("ks", []):
        if city.get("c") != "地级市人民政府":
            continue
        shi = None
        for jg in city.get("ks", []):
            if jg.get("k") != "分组":
                continue
            for o in jg.get("ks", []):
                if o.get("n") == "市人民检察院":
                    shi = o
        counties = {}
        for x in city.get("ks", []):
            if x.get("c") != "县级人民政府":
                continue
            for jg in x.get("ks", []):
                if jg.get("k") != "分组":
                    continue
                for o in jg.get("ks", []):
                    if o.get("n") == "县人民检察院":
                        counties[x["n"]] = o
        if shi or counties:
            data[city["n"]] = {"_shi": shi, **counties}
    if data:
        prov_data[p["n"]] = data

STATE_F = "jc_select_state.json"
state = json.load(open(STATE_F, encoding="utf-8")) if os.path.exists(STATE_F) \
    else {"done": [], "found": {}}
done = set(state["done"])
OPT = re.compile(r'<option[^>]+value=["\'](https?://[^"\']+)["\'][^>]*>\s*([^<]{1,16}?)\s*</option>', re.S)
SEL = re.compile(r'<select[^>]*>(.*?)</select>', re.S)

hit_total = 0
for pn, data in prov_data.items():
    if pn in done:
        continue
    html, m = smart_fetch(PORTS.get(pn, ""), timeout=25)
    found_here = 0
    if html and len(html) > 2000:
        for sel in SEL.findall(html):
            opts = [(re.sub(r"\s+", "", t), u) for u, t in OPT.findall(sel)]
            if len(opts) < 2:
                continue
            # 首 option = 市名, 后续 = 县名
            city_name = opts[0][0]
            cdata = data.get(city_name) or data.get(city_name + "市")
            if not cdata:
                continue
            shi_node = cdata.get("_shi")
            if shi_node and not shi_node.get("u") and opts[0][1].startswith("http"):
                shi_node["u"] = opts[0][1]
                shi_node["s"] = "P183b 省院官网检察门户级联下拉真实提取"
                state["found"].setdefault(pn, {})[city_name + "_市院"] = opts[0][1]
                found_here += 1
            for t, u in opts[1:]:
                if t in ("———", "---", "—"):
                    continue
                node = cdata.get(t) or cdata.get(t + "区") or cdata.get(t + "县")
                if node and not node.get("u"):
                    node["u"] = u
                    node["s"] = "P183b 省院官网检察门户级联下拉真实提取"
                    state["found"].setdefault(pn, {})[city_name + "/" + t] = u
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
print(f"P183b 完成: 总命中 {hit_total}", flush=True)
