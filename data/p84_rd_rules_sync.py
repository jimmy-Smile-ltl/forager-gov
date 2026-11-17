# -*- coding: utf-8 -*-
"""P84: 人大系统 rules depts 同步市级挂载 + method 更新。"""
import json

tree = json.load(open("tree.json", encoding="utf-8"))
rules = json.load(open("extraction_rules.json", encoding="utf-8"))
tiao = next(g for g in tree["ks"] if g["n"] == "条（垂直管理系统）")
rd = next(g for g in tiao["ks"] if g["n"].startswith("人大系统"))
rk = next(k for k in rules if k.startswith("人大系统"))

all_m = []

def walk(n):
    if not n.get("ks"):
        all_m.append(n)
        return
    if all(x.get("l") != "省" for x in n["ks"]):
        all_m.append(n)
    for k in n["ks"]:
        walk(k)

walk(rd)

rules[rk]["depts"] = [{"n": m["n"], "u": m.get("u", ""), "o": i}
                      for i, m in enumerate(all_m)]
rules[rk]["method"] = (
    "全国人大 npc.gov.cn「地方人大网站」页真实 HTML 提取 31 省级权威 URL；"
    "市级人大来自各省人大官网「市县人大/各地人大/地方人大」导航真实提取："
    "四川 map.js cityLinkMap、陕西隐藏层 xqrd、黑龙江 select 下拉、辽宁 select 下拉、"
    "青海首页底部链接、福建 szrd 首页 footer、重庆首页区县人大区块；"
    "无官网的市/区人大列名展示（u 为空）。")
json.dump(rules, open("extraction_rules.json", "w", encoding="utf-8"),
          ensure_ascii=False, separators=(",", ":"))
print(f"p84 完成：人大系统 depts {len(all_m)} 条（"
      f"{sum(1 for m in all_m if m.get('u'))} 有 URL）")
