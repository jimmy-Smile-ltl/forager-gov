# -*- coding: utf-8 -*-
"""P110: 挂载 p105 静态轮基层检察院记录到检察系统 + 老系统回填。"""
import json
import re

rows = [json.loads(l) for l in open("jc_jc.jsonl", encoding="utf-8")]
tree = json.load(open("tree.json", encoding="utf-8"))
prov_g = next(g for g in tree["ks"] if g["n"].startswith("省级"))
tiao = next(g for g in tree["ks"] if g["n"].startswith("条"))
jc = next(g for g in tiao["ks"] if g["n"].startswith("检察院系统"))
prov_jc = next(g for g in jc["ks"] if "省级检察院" in g["n"])

added = filled = 0
for r in rows:
    pname, shiname, county, url = r["province"], r["shi"], r["county"], r["url"]
    if pname == "湖南省":
        continue  # p109b 已处理
    pj = next((x for x in prov_jc["ks"] if x["n"].startswith(pname)), None)
    if not pj:
        continue
    # 找市级节点（shiname 匹配）
    shi = None
    for s in pj.get("ks", []):
        s_core = re.sub(r"(检察检察院|检察院)$", "", s["n"]).replace("市", "")
        shi_core = re.sub(r"(检察检察院|检察院)$", "", shiname).replace("市", "")
        if s_core and (s_core in shi_core or shi_core in s_core):
            shi = s
            break
    if not shi:
        continue
    nm = f"{county}人民检察院"
    existing = {k["n"] for k in shi.get("ks", [])}
    if nm in existing:
        for k in shi.get("ks", []):
            if k["n"] == nm and not k.get("u"):
                k["u"] = url
        continue
    shi.setdefault("ks", []).append(
        {"n": nm, "l": "县", "k": "检察院系统", "c": "检察院系统",
         "u": url, "x": "", "s": "", "m": ""})
    added += 1
    # 老系统回填
    p = next(x for x in prov_g["ks"] if x["n"] == pname)
    for top in p.get("ks", []):
        def wfill(n):
            if n.get("l") == "县" and n.get("k") == "人民政府" \
                    and n["n"] == county:
                par = next((g for g in n.get("ks", [])
                            if g.get("c") == "并列机关"), None)
                if par:
                    m = next((x for x in par.get("ks", [])
                              if "检察院" in x["n"]), None)
                    if m:
                        m["u"] = url
                        return True
            for k in n.get("ks", []):
                if wfill(k):
                    return True
            return False
        if wfill(top):
            filled += 1
            break

json.dump(tree, open("tree.json", "w", encoding="utf-8"),
          ensure_ascii=False, separators=(",", ":"))
print(f"p110 完成：新增基层节点 {added}，老系统回填 {filled}")
