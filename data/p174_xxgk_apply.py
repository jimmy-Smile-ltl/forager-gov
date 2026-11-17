# -*- coding: utf-8 -*-
"""P174: 把 p173 采集到的信息公开专栏 URL 落回树节点 x 字段 + registry xxgk 字段。

消歧规则：p173 的 found 以机构名为 key（同名机构跨省冲突），
用「x URL 域名 == 节点 u 域名」唯一匹配来归属；
同域名多候选（省内共享频道域）→ 不赋值，进 remainder 留给 p175。
"""
import json, os, re
from urllib.parse import urlparse

state = json.load(open("xxgk_patch_state.json", encoding="utf-8"))
found = state.get("found", {})
tree = json.load(open("tree.json", encoding="utf-8"))
reg = json.load(open("site_registry.json", encoding="utf-8"))

def domain(u):
    try:
        return urlparse(u).netloc.split(":")[0]
    except Exception:
        return ""

# 1) 索引：name -> [(node_ref, u, dom)]
from collections import defaultdict
idx = defaultdict(list)
def walk(n, cat):
    if n.get("u") and not n.get("ks") and not n.get("x"):
        idx[n["n"]].append((n, cat))
    for k in n.get("ks", []):
        walk(k, cat)
walk(tree, "")

assigned = 0
remainder = []
for name, v in found.items():
    x_url = v.get("u", "")
    cands = idx.get(name, [])
    if not cands:
        remainder.append((name, x_url, "树中无此名或无u无x"))
        continue
    xdom = domain(x_url)
    dm = [(n, cat, domain(n["u"])) for n, cat in cands if domain(n["u"]) == xdom]
    if len(dm) == 1:
        n, cat, _ = dm[0]
        n["x"] = x_url
        n["s"] = "p173 官网首页真实提取"
        assigned += 1
    else:
        remainder.append((name, x_url, f"同名同域候选{len(dm)}个" if dm else "域名不匹配"))

# 2) registry 回填 xxgk（按 u 匹配）
rx = 0
u2x = {}
for name, v in found.items():
    u2x[v.get("u", "")] = v.get("u", "")
# 直接从树拿：u -> x
def walk2(n):
    if n.get("x"):
        u2x[n["u"]] = n["x"]
    for k in n.get("ks", []):
        walk2(k)
walk2(tree)
for k, v in reg.items():
    if v.get("u") and v["u"] in u2x and not v.get("xxgk"):
        v["xxgk"] = u2x[v["u"]]
        v["xxgk_src"] = "p173"
        rx += 1

json.dump(tree, open("tree.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
json.dump(reg, open("site_registry.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
json.dump(remainder, open("xxgk_remainder.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print(f"p174 完成: 树节点 x 赋值 {assigned} 个, registry xxgk {rx} 条, 余留 {len(remainder)} 待p175")
