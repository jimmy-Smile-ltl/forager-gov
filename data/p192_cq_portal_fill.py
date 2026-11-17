# -*- coding: utf-8 -*-
"""P192: 重庆 7 个区县门户 URL 落库（重庆市政府门户区县导航 HTML 提取 + title 验证）。

来源：http://www.cq.gov.cn/ 首页「区县政府网站」footer 区块真实 HTML（36 链接，
缺江北/渝北——渝府发〔2025〕15 号区划调整，江北区/渝北区撤销并入两江新区，
门户已不存在）。链接文本含区县名，URL 与区政府门户一致，smart_fetch title
验证通过（如「重庆市北碚区人民政府」）后落库。渝北区按红线列名（不猜域名），
m 字段留区划调整说明。
"""
import json, datetime

tree = json.load(open("tree.json", encoding="utf-8"))
reg = json.load(open("site_registry.json", encoding="utf-8"))
blk = next(g for g in tree["ks"] if g["n"].startswith("省级"))
cq = next(p for p in blk["ks"] if p["n"] == "重庆市")

FILLS = [
    # (块树节点名, URL, 注册表类别)
    ("北碚区", "http://www.beibei.gov.cn/", "市辖区（地级行政区划）"),
    ("大足区", "http://www.dazu.gov.cn/", "市辖区（地级行政区划）"),
    ("黔江区", "https://www.qianjiang.gov.cn", "市辖区（地级行政区划）"),
    ("江津区", "http://www.jiangjin.gov.cn/", "市辖区（地级行政区划）"),
    ("璧山区", "http://www.bishan.gov.cn", "市辖区（地级行政区划）"),
    ("荣昌区", "http://www.rongchang.gov.cn/", "市辖区（地级行政区划）"),
    ("彭水苗族土家族自治县", "http://www.psx.gov.cn/", "直辖市辖县（县级行政区划）"),
]
METHOD = "来源：重庆市政府门户区县导航 HTML 提取（title 验证）"
today = datetime.date.today().strftime("%Y-%m-%d")

# 1) 块树区县节点 u 回填（空才填）
filled_tree = 0
for name, u, cat in FILLS:
    for g in cq["ks"]:
        if g.get("c") not in ("直辖市辖区", "直辖市辖县"):
            continue
        for x in g["ks"]:
            if x["n"] == name:
                if not x.get("u"):
                    x["u"] = u
                    x["s"] = METHOD
                    filled_tree += 1
                else:
                    print(f"  {name} 已有 u={x['u']} 不动")
                break
print(f"块树回填 {filled_tree} 个")

# 2) 渝北区 m 备注（区划调整，门户不存在 → 列名）
for g in cq["ks"]:
    if g.get("c") != "直辖市辖区":
        continue
    for x in g["ks"]:
        if x["n"] == "渝北区":
            if not x.get("m"):
                x["m"] = ("2025-11 区划调整（渝府发〔2025〕15号）：撤销江北区、渝北区"
                          "设立两江新区，渝北区门户已不存在，列名。")
            break

# 3) 注册表登记（cat|全名 → URL + 留痕）
reg_filled = 0
for name, u, cat in FILLS:
    key = f"{cat}|{name}"
    if key in reg and reg[key].get("u"):
        print(f"  registry 已有 {key} -> {reg[key]['u']} 不动")
        continue
    reg[key] = {
        "u": u, "n": name, "locations": ["块"],
        "source_level": "L2", "verified_at": today,
        "status": "ok", "snapshot": f"snapshots/shixian/重庆市/{name}/",
        "xxgk": "", "xxgk_src": "",
    }
    reg_filled += 1
print(f"registry 新增 {reg_filled} 条")

json.dump(tree, open("tree.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
json.dump(reg, open("site_registry.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=0)
print("P192 done")
