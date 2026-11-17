# -*- coding: utf-8 -*-
"""P175k: p175h 渲染轮结果（u → x）落回树节点 x + registry xxgk。"""
import json
state = json.load(open("xxgk_render_state.json", encoding="utf-8"))
found = state.get("found", {})
tree = json.load(open("tree.json", encoding="utf-8"))
reg = json.load(open("site_registry.json", encoding="utf-8"))

assigned = 0
def w(n):
    global assigned
    if n.get("u") and not n.get("ks") and not n.get("x"):
        rec = found.get(n["u"])
        if rec and rec.get("x"):
            n["x"] = rec["x"]
            n["s"] = "p175h 渲染轮真实 HTML 提取"
            assigned += 1
    for k in n.get("ks", []): w(k)
w(tree)

rx = 0
u2x = {}
def w2(n):
    if n.get("x"): u2x[n["u"]] = n["x"]
    for k in n.get("ks", []): w2(k)
w2(tree)
for k, v in reg.items():
    if v.get("u") in u2x and not v.get("xxgk"):
        v["xxgk"] = u2x[v["u"]]
        v["xxgk_src"] = "p175h"
        rx += 1

json.dump(tree, open("tree.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
json.dump(reg, open("site_registry.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"p175k: 树 x 赋 {assigned} 个, registry xxgk {rx} 条")
