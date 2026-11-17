# -*- coding: utf-8 -*-
"""P177: P176 提取的海关链接落库（按名匹配树节点 u 字段 + registry）。"""
import json, os, re
links = json.load(open("hg_customs_links.json", encoding="utf-8"))
tree = json.load(open("tree.json", encoding="utf-8"))
reg = json.load(open("site_registry.json", encoding="utf-8"))

matched, unmatched = [], []
def w(n):
    if n.get("ks"):
        for k in n.get("ks", []): w(k)
        return
    if not n.get("u") and n["n"] in links:
        n["u"] = links[n["n"]]
        n["s"] = "P176 海关总署官网「直属海关」名录真实 HTML 提取"
        matched.append((n["n"], links[n["n"]]))
w(tree)

# 未匹配的链接名
for name in links:
    if name not in [m[0] for m in matched]:
        unmatched.append(name)

# registry 同步
cnt = 0
for k, v in reg.items():
    if not v.get("u") and v.get("n") and v["n"] in links:
        v["u"] = links[v["n"]]
        v["source_level"] = "L1"
        v["verified_at"] = "2026-11-09"
        v["status"] = "ok"
        cnt += 1

json.dump(tree, open("tree.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
json.dump(reg, open("site_registry.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"P177: 树 {len(matched)} 个, registry {cnt} 条")
for n, u in matched:
    print(f"  ✓ {n}: {u}")
if unmatched:
    print("未匹配:", unmatched)
