# -*- coding: utf-8 -*-
"""P109b: 湖南检察节点从零重建（省院 szylj 栏目数据）。"""
import json
import re

COLS = ["cs", "zz", "xt", "hy", "sy", "yy", "cd", "zjj", "cz", "yz", "hh", "ld", "xx"]

def load_col(shi):
    t = open(f"/tmp/hn_{shi}.html", encoding="utf-8", errors="replace").read()
    d = {}
    for u, txt in re.findall(
            r'<a[^>]+href="([^"]+)"[^>]*>\s*([^<]{3,24}?)\s*</a>', t):
        t2 = txt.strip()
        if re.search(r'(检察院|检察)', t2) and 'szylj' in u:
            d[t2] = u
    return d

tree = json.load(open("tree.json", encoding="utf-8"))
prov_g = next(g for g in tree["ks"] if g["n"].startswith("省级"))
tiao = next(g for g in tree["ks"] if g["n"].startswith("条"))
jc = next(g for g in tiao["ks"] if g["n"].startswith("检察院系统"))
prov_jc = next(g for g in jc["ks"] if "省级检察院" in g["n"])
hn = next(p for p in prov_jc["ks"] if p["n"].startswith("湖南省"))
hn_prov = next(p for p in prov_g["ks"] if p["n"] == "湖南省")

# 市州名单（树）
shi_set = {}
for top in hn_prov.get("ks", []):
    ETH = "(土家族苗族|土家族|苗族)"
    def walk(n):
        if n.get("l") == "市" and n.get("k") == "人民政府":
            c = re.sub(rf"{ETH}?自治州$|市$", "", n["n"])
            shi_set[c] = n["n"]
        for k in n.get("ks", []):
            walk(k)
    walk(top)

# 县级名单（老系统回填用）
counties = {}
for top in hn_prov.get("ks", []):
    def walk2(n):
        if n.get("l") == "县" and n.get("k") == "人民政府":
            counties[n["n"]] = ""
        for k in n.get("ks", []):
            walk2(k)
    walk2(top)

leaf = lambda nm, u: {"n": nm, "l": "县", "k": "检察院系统",
                      "c": "检察院系统", "u": u, "x": "", "s": "", "m": ""}

hn["ks"] = []
total_jc = 0
filled = 0
for shi in COLS:
    d = load_col(shi)
    # 找市级条目
    shi_entry = None
    for k in d:
        core = re.sub(r"(人民检察院|检察院|检察网)$", "", k)
        core = re.sub(r"市$", "", core)
        if core in shi_set:
            shi_entry = (k, d[k])
            break
    if not shi_entry:
        print(f"栏目 {shi} 无市级条目")
        continue
    shi_k, shi_u = shi_entry
    core = re.sub(r"(人民检察院|检察院|检察网)$", "", shi_k)
    core = re.sub(r"市$", "", core)
    node = {"n": f"{shi_set[core]}检察院", "l": "市", "k": "检察院系统",
            "c": "检察院系统", "u": shi_u, "x": "", "s": "", "m": "", "ks": []}
    for k, v in d.items():
        if k == shi_k:
            continue
        nm = k.replace("检察网", "人民检察院")
        node["ks"].append(leaf(nm, v))
        total_jc += 1
        # 老系统回填
        cn = nm.replace("人民检察院", "").replace("市", "县")  # 县级市
        cand = [nm.replace("人民检察院", ""), cn,
                re.sub(r"(自治县|区|县|市)$", "", nm.replace("人民检察院", ""))]
        for top in hn_prov.get("ks", []):
            def wfill(n):
                if n.get("l") == "县" and n.get("k") == "人民政府" and \
                        (n["n"] in cand or re.sub(r"(自治县|区|县|市)$", "", n["n"]) in cand):
                    par = next((g for g in n.get("ks", [])
                                if g.get("c") == "并列机关"), None)
                    if par:
                        m = next((x for x in par.get("ks", [])
                                  if "检察院" in x["n"]), None)
                        if m:
                            m["u"] = v
                            return True
                for k2 in n.get("ks", []):
                    if wfill(k2):
                        return True
                return False
            if wfill(top):
                filled += 1
                break
    hn["ks"].append(node)

json.dump(tree, open("tree.json", "w", encoding="utf-8"),
          ensure_ascii=False, separators=(",", ":"))
print(f"p109b 完成：湖南 {len(hn['ks'])} 市州，基层 {total_jc}，老系统回填 {filled}")
