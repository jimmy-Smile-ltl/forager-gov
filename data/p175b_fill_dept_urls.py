# -*- coding: utf-8 -*-
"""P175b: 对 p175a 清空的厅局节点，从「XX省·省政府部门」权威规则回填正确 URL。"""
import json, re

tree = json.load(open("tree.json", encoding="utf-8"))
rules = json.load(open("extraction_rules.json", encoding="utf-8"))

def prov_of(node_n):
    m = re.match(r"^(北京市|天津市|上海市|重庆市|河北省|山西省|辽宁省|吉林省|黑龙江省|江苏省|浙江省|安徽省|福建省|江西省|山东省|河南省|湖北省|湖南省|广东省|海南省|四川省|贵州省|云南省|陕西省|甘肃省|青海省|宁夏回族自治区|内蒙古自治区|广西壮族自治区|西藏自治区|新疆维吾尔自治区)", node_n)
    return m.group(1) if m else ""

filled = []
def w(parent, pn="", gp=""):
    for k in parent.get("ks", []):
        if k.get("ks"):
            w(k, prov_of(k["n"]) or pn, pn); continue
        if not k.get("u") and not k.get("x") and k.get("s") and "175a" in k["s"]:
            pn = prov_of(parent["n"]) or gp
            keys = [rk for rk in rules if rk.startswith(f"{pn}·省政府部门") or rk == pn]
            hit = None
            for rk in keys:
                for d in rules[rk].get("depts", []):
                    if not isinstance(d, dict) or not d.get("u"): continue
                    if d["n"] == k["n"] or k["n"].endswith(d["n"]):
                        hit = (d["u"], rk); break
                if hit: break
            if hit:
                k["u"] = hit[0]
                k["s"] = f"P175b URL回填: 规则[{hit[1]}]"
                filled.append((pn, k["n"], hit[0]))
            else:
                k["s"] = "P175a 错配URL清除，权威规则无纠正"
w(tree)
json.dump(tree, open("tree.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"p175b: 回填 {len(filled)} 个")
for pn, n, u in filled:
    print(f"  ✓ {pn}{n}: {u}")
