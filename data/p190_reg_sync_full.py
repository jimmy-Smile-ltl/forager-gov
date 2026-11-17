# -*- coding: utf-8 -*-
"""P190: registry 全量补同步——树叶子有 u 但 registry 无该 u 的条目
（p189 块条回填 1550 个 + p182-184 采集的 URL 未登记）→ 按树补登记。"""
import json

tree = json.load(open("tree.json", encoding="utf-8"))
reg = json.load(open("site_registry.json", encoding="utf-8"))
reg_us = {v["u"] for v in reg.values() if v.get("u")}

def cat_of(n, c):
    if n.get("c"): return n["c"]
    return c

added = 0
def walk(n, prefix, cat):
    global added
    full = prefix + n["n"]
    u = n.get("u", "")
    kids = n.get("ks", [])
    if u and u not in reg_us:   # 含区划门户（有子节点的政府节点）
        # 叶子机构: 补登记
        c2 = cat_of(n, cat)
        key = f"{c2}|{n['n']}"
        reg[key] = {
            "u": u, "n": n["n"], "locations": ["块"],
            "source_level": "L2",
            "verified_at": "2026-11-11",
            "status": "unknown",
        }
        if n.get("x"): reg[key]["xxgk"] = n["x"]
        reg_us.add(u)
        added += 1
    for k in kids:
        walk(k, full, cat_of(k, cat))
for g in tree["ks"]:
    walk(g, "", g.get("c", ""))

json.dump(reg, open("site_registry.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print(f"P190: registry 补登记 {added} 条")
