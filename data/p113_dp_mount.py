# -*- coding: utf-8 -*-
"""P113: 民主党派省级组织挂载（民盟/民建/民进/农工/致公/九三 + 九三市级）。

来源：各党派中央官网首页「省级组织」区块真实 HTML 提取。
缺失省份（西藏等无该党派组织的省份）列名。
"""
import json
import re

dp_prov = json.load(open("/tmp/dp_prov.json", encoding="utf-8"))
j93 = json.load(open("/tmp/93_data.json", encoding="utf-8"))
# 九三省级修正（上海宝山/重庆渝中 误入省级 → 市级）
j93_prov = {k: v for k, v in j93["prov"].items()
            if not re.search(r'(宝山|渝中|交通大学)', k)}
for k in list(j93_prov):
    if k in ("上海宝山", "重庆渝中"):
        j93_prov.pop(k)
j93_shi = j93["shi"]
j93_shi.update({"上海宝山": "http://93.baoshan.sh.cn/",
                "重庆渝中": "http://www.cqyz93.com"})

PROV_FULL = ["北京市", "天津市", "河北省", "山西省", "内蒙古自治区", "辽宁省",
             "吉林省", "黑龙江省", "上海市", "江苏省", "浙江省", "安徽省",
             "福建省", "江西省", "山东省", "河南省", "湖北省", "湖南省",
             "广东省", "广西壮族自治区", "海南省", "重庆市", "四川省",
             "贵州省", "云南省", "西藏自治区", "陕西省", "甘肃省", "青海省",
             "宁夏回族自治区", "新疆维吾尔自治区"]
SHORT = {"北京": "北京市", "天津": "天津市", "河北": "河北省", "山西": "山西省",
         "内蒙古": "内蒙古自治区", "辽宁": "辽宁省", "吉林": "吉林省",
         "黑龙江": "黑龙江省", "上海": "上海市", "江苏": "江苏省",
         "浙江": "浙江省", "安徽": "安徽省", "福建": "福建省", "江西": "江西省",
         "山东": "山东省", "河南": "河南省", "湖北": "湖北省", "湖南": "湖南省",
         "广东": "广东省", "广西": "广西壮族自治区", "海南": "海南省",
         "重庆": "重庆市", "四川": "四川省", "贵州": "贵州省",
         "云南": "云南省", "西藏": "西藏自治区", "陕西": "陕西省",
         "甘肃": "甘肃省", "青海": "青海省", "宁夏": "宁夏回族自治区",
         "新疆": "新疆维吾尔自治区"}

def j93_name_of(key):
    for s, f in SHORT.items():
        if key.startswith(s):
            return f
    return None

PARTY_NAME = {"民盟": "中国民主同盟", "民建": "中国民主建国会", "民进": "中国民主促进会",
              "农工党": "中国农工民主党", "致公党": "中国致公党", "九三": "九三学社"}

tree = json.load(open("tree.json", encoding="utf-8"))
prov_g = next(g for g in tree["ks"] if g["n"].startswith("省级"))
central = next(g for g in tree["ks"] if g["n"].startswith("中央"))
dp_grp = next(x for x in central["ks"] if "民主党派" in x["n"])

# 树里各省市级名单（九三市级匹配用）
city_by_prov = {}
for p in prov_g["ks"]:
    s = set()
    for top in p.get("ks", []):
        def walk(n):
            if n.get("l") in ("市", "地级区", "县") and n.get("k") == "人民政府":
                s.add(n["n"])
            for k in n.get("ks", []):
                walk(k)
        walk(top)
    city_by_prov[p["n"]] = s

def leaf(nm, lv, u):
    return {"n": nm, "l": lv, "k": "民主党派", "c": "民主党派",
            "u": u, "x": "", "s": "", "m": ""}

added = 0
# 1) 五个党派省级（列名补齐缺失省）
for key, party in [("民盟", "中国民主同盟"), ("民建", "中国民主建国会"),
                   ("民进", "中国民主促进会"), ("农工党", "中国农工民主党"),
                   ("致公党", "中国致公党")]:
    node = next(x for x in dp_grp["ks"] if x["n"].startswith(party))
    d = dp_prov[key]
    kids = []
    for pf in PROV_FULL:
        u = d.get(pf, "")
        kids.append(leaf(f"{pf}{party.replace('中国', '')}省委会" if "中国" in party else f"{pf}九三学社省委会", "省", u))
    # 九三单独
    node["ks"] = kids
    added += len(kids)

# 2) 九三省级 + 市级
node93 = next(x for x in dp_grp["ks"] if x["n"].startswith("九三学社"))
kids93 = []
for k, u in j93_prov.items():
    full = j93_name_of(k)
    if not full:
        continue
    kids93.append(leaf(f"{full}九三学社委员会", "省", u))
# 市级
prov_of = {}
for k, u in j93_shi.items():
    full = j93_name_of(k)
    if not full:
        continue
    prov_of.setdefault(full, []).append((k, u))
for pf, items in prov_of.items():
    pnode = next((x for x in kids93 if x["n"].startswith(pf)), None)
    if pnode is None:
        continue
    pnode["ks"] = []
    for k, u in items:
        pnode["ks"].append(leaf(f"{k}九三学社委员会", "市", u))
node93["ks"] = kids93
added += len(kids93) + len(j93_shi)

json.dump(tree, open("tree.json", "w", encoding="utf-8"),
          ensure_ascii=False, separators=(",", ":"))
n_shi = len(j93_shi)
print(f"p113 完成：5 党派省级 {31*5}，九三省级 {len(kids93)} + 市级 {n_shi}")
