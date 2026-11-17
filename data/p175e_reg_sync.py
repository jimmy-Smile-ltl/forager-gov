# -*- coding: utf-8 -*-
"""P175e: tree.json 变更同步到 site_registry.json。
(1) u 变更：按 n 匹配同名条目更新 u（p175a/b 纠错）
(2) x 回填：树节点 x → registry xxgk/xxgk_src
(3) 失效旧 u 条目的 locations 保留。"""
import json
from collections import defaultdict

tree = json.load(open("tree.json", encoding="utf-8"))
reg = json.load(open("site_registry.json", encoding="utf-8"))

# tree 节点索引: u -> node, n -> [nodes]
by_u = defaultdict(list); by_n = defaultdict(list)
def w(n):
    if n.get("u") and not n.get("ks"):
        by_u[n["u"]].append(n); by_n[n["n"]].append(n)
    for k in n.get("ks", []): w(k)
w(tree)

upd_u = upd_x = 0
for key, v in reg.items():
    u, vn = v.get("u", ""), v.get("n", "")
    # (1) u 已失效（tree 无此 u 的节点）但同名节点有新 u → 更新
    if u and u not in by_u and vn and vn in by_n:
        new_u = by_n[vn][0].get("u")
        if new_u and new_u != u:
            v["u"] = new_u
            upd_u += 1
    # (2) xxgk 回填
    if u in by_u or v.get("u") in by_u:
        cur = v.get("u", "")
        xnode = by_u.get(cur, [None])[0]
        if xnode and xnode.get("x") and not v.get("xxgk"):
            v["xxgk"] = xnode["x"]
            v["xxgk_src"] = xnode.get("s", "")
            upd_x += 1

json.dump(reg, open("site_registry.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print(f"p175e: registry u 更新 {upd_u} 条, xxgk 回填 {upd_x} 条")
