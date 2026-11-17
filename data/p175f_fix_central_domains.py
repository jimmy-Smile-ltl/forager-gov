# -*- coding: utf-8 -*-
"""P175f: 厅局节点 u 为中央部委域名错配（64 个，通管局除外）
→ 从「XX省·省政府部门」权威规则回填正确 u。"""
import json, re
from urllib.parse import urlparse

tree = json.load(open("tree.json", encoding="utf-8"))
rules = json.load(open("extraction_rules.json", encoding="utf-8"))
prov = next(g for g in tree["ks"] if g["n"].startswith("省级"))
CENTRAL = ("most.gov.cn","mohrss.gov.cn","natcm.gov.cn","mva.gov.cn","neac.gov.cn",
           "miit.gov.cn","mof.gov.cn","moe.gov.cn","mwr.gov.cn","nmpa.gov.cn",
           "www.gov.cn","samr.gov.cn","mps.gov.cn","mohurd.gov.cn","moa.gov.cn",
           "mee.gov.cn","mot.gov.cn","nhc.gov.cn","nhsa.gov.cn","lswz.gov.cn",
           "mct.gov.cn","mca.gov.cn","gov.cn/yaowen")
def prov_of(n):
    m = re.match(r"^(北京市|天津市|上海市|重庆市|河北省|山西省|辽宁省|吉林省|黑龙江省|江苏省|浙江省|安徽省|福建省|江西省|山东省|河南省|湖北省|湖南省|广东省|海南省|四川省|贵州省|云南省|陕西省|甘肃省|青海省|宁夏回族自治区|内蒙古自治区|广西壮族自治区|西藏自治区|新疆维吾尔自治区)", n)
    return m.group(1) if m else ""

fixed = 0
for p in prov["ks"]:
    pn = prov_of(p["n"])
    keys = [rk for rk in rules if rk.startswith(f"{pn}·省政府部门") or rk == pn]
    for top in p.get("ks", []):
        if top.get("k") != "分组" or not ("部门" in top.get("n") or "厅" in top.get("n")): continue
        for x in top.get("ks", []):
            u = x.get("u","")
            if not u or x.get("ks") or "shca.miit" in u: continue
            if not any(c in u for c in CENTRAL): continue
            for rk in keys:
                for d in rules[rk].get("depts", []):
                    if isinstance(d, dict) and d.get("u") and (d["n"]==x["n"] or x["n"].endswith(d["n"])):
                        x["u"] = d["u"]
                        x["s"] = f"P175f URL纠错: 规则[{rk}]"
                        fixed += 1
                        break
                else: continue
                break
json.dump(tree, open("tree.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"p175f: 修复 {fixed} 个")
