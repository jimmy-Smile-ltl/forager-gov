# -*- coding: utf-8 -*-
"""P150: 检察院条模块市级+基层节点全量重建（以老系统真实采集为准）。"""
import json
import re

tree = json.load(open("tree.json", encoding="utf-8"))
prov = next(g for g in tree["ks"] if g["n"].startswith("省级"))
tiao = next(g for g in tree["ks"] if g["n"].startswith("条"))
jc = next(g for g in tiao["ks"] if g["n"].startswith("检察院系统"))
prov_jc = next(g for g in jc["ks"] if "省级检察院" in g["n"])

MUNI = {"北京市", "天津市", "上海市", "重庆市"}

# 收集老系统：市级检察院 URL + 县检察院 URL + 县→市归属
shi_jc = {}
county_jc = {}
county_city = {}
for p in prov["ks"]:
    pn = p["n"]
    for top in p.get("ks", []):
        def walk(n, city):
            if n.get("l") == "市" and n.get("k") == "人民政府":
                city = n["n"]
                par = next((g for g in n.get("ks", []) if g.get("c") == "并列机关"), None)
                if par:
                    m = next((x for x in par.get("ks", []) if "检察" in x["n"]), None)
                    if m and m.get("u"):
                        shi_jc[(pn, n["n"])] = m["u"]
            if n.get("l") == "县" and n.get("k") == "人民政府":
                county_city[(pn, n["n"])] = city
                par = next((g for g in n.get("ks", []) if g.get("c") == "并列机关"), None)
                if par:
                    m = next((x for x in par.get("ks", []) if "检察" in x["n"]), None)
                    if m and m.get("u"):
                        county_jc[(pn, n["n"])] = m["u"]
            for k in n.get("ks", []):
                walk(k, city)
        walk(top, None)

def leaf(nm, lv, u):
    return {"n": nm, "l": lv, "k": "检察院系统", "c": "检察院系统",
            "u": u, "x": "", "s": "", "m": ""}

new_shi = new_jc = 0
for p in prov_jc["ks"]:
    pn = p["n"].replace("检察院", "")
    p_block = next((x for x in prov["ks"] if x["n"] == pn), None)
    if not p_block:
        continue
    # 市级名单
    shi_names = []
    for top in p_block.get("ks", []):
        def walk2(n):
            if n.get("l") == "市" and n.get("k") == "人民政府":
                shi_names.append(n["n"])
            for k in n.get("ks", []):
                walk2(k)
        walk2(top)
    existing = {s["n"] for s in p.get("ks", [])}
    for sn in shi_names:
        u = shi_jc.get((pn, sn), "")
        nm = f"{sn}人民检察院"
        core = re.sub(r"(自治州|市|地区)$", "", sn)
        if nm not in existing:
            # 检查相近名（老节点名「XX检察院」「XX市检察检察院」）
            node = next((s for s in p.get("ks", [])
                         if core in s["n"] and "地区" not in s["n"] and
                         re.sub(r"(检察检察院|检察院|人民检察院)$", "", s["n"]).replace("市", "") == core), None)
            if node:
                if u and not node.get("u"):
                    node["u"] = u
                    node["n"] = nm
                existing.add(nm)
                shi_node = node
            else:
                shi_node = {"n": nm, "l": "市", "k": "检察院系统",
                            "c": "检察院系统", "u": u, "x": "", "s": "", "m": "",
                            "ks": []}
                p.setdefault("ks", []).append(shi_node)
                existing.add(nm)
                new_shi += 1
        else:
            shi_node = next(s for s in p.get("ks", []) if s["n"] == nm)
        # 基层节点
        jc_existing = {k["n"] for k in shi_node.get("ks", [])}
        for (cpn, cn), city in county_city.items():
            if cpn != pn or city != sn:
                continue
            jc_nm = f"{cn}人民检察院"
            jc_u = county_jc.get((cpn, cn), "")
            if jc_nm in jc_existing:
                for k in shi_node.get("ks", []):
                    if k["n"] == jc_nm and not k.get("u") and jc_u:
                        k["u"] = jc_u
                continue
            shi_node.setdefault("ks", []).append(leaf(jc_nm, "县", jc_u))
            jc_existing.add(jc_nm)
            new_jc += 1
    # 直辖市：区检察院直接挂省院节点下
    if pn in MUNI:
        qu = []
        for top in p_block.get("ks", []):
            def walk3(n):
                if n.get("l") == "地级区" and n.get("k") == "人民政府":
                    qu.append(n["n"])
                for k in n.get("ks", []):
                    walk3(k)
            walk3(top)
        for qn in qu:
            nm = f"{qn}人民检察院"
            if nm not in existing:
                u = county_jc.get((pn, qn), "")
                p.setdefault("ks", []).append(leaf(nm, "地级区", u))
                existing.add(nm)
                new_jc += 1

json.dump(tree, open("tree.json", "w", encoding="utf-8"),
          ensure_ascii=False, separators=(",", ":"))
print(f"p150 完成: 新增市级 {new_shi}，新增基层 {new_jc}")
n_shi = n_jc = n_jcu = 0
for p in prov_jc["ks"]:
    n_shi += len(p.get("ks", []))
    for s in p.get("ks", []):
        n_jc += len(s.get("ks", []))
        n_jcu += sum(1 for k in s.get("ks", []) if k.get("u"))
print(f"检察院系统: 市级 {n_shi}，基层 {n_jc}（{n_jcu} URL）")
