# -*- coding: utf-8 -*-
"""P177: 从「直属机构」页快照提取 42 直属海关真实链接 → 落库树 + registry。"""
import json, re, os

SNAP = "snapshots/other/中央/海关总署/20261109_zsjg.html"
if not os.path.exists(SNAP):
    print("快照不存在, 先跑 P176d")
    raise SystemExit(0)

html = open(SNAP, encoding="utf-8", errors="replace").read()
print("快照长度:", len(html))

# 提取: 锚文本以「海关」结尾（如 北京海关/上海海关/中华人民共和国XX海关）
links = {}
for uu, txt in re.findall(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>\s*([^<]{2,30}?)\s*</a>', html):
    t2 = re.sub(r"\s+", "", txt)
    if re.search(r"海关$", t2) and not re.search(r"/202[0-9]-|/202[0-9]/", uu):
        # 排除新闻文章页
        links[t2] = uu
print(f"提取 {len(links)} 个")
for n, u in sorted(links.items()):
    print(f"  {n}: {u[:75]}")

if not links:
    print("无命中——检查页面形态")
    raise SystemExit(0)

tree = json.load(open("tree.json", encoding="utf-8"))
reg = json.load(open("site_registry.json", encoding="utf-8"))

matched = []
def w(n):
    if n.get("ks"):
        for k in n.get("ks", []): w(k)
        return
    if not n.get("u") and n["n"] in links:
        n["u"] = links[n["n"]]
        n["s"] = "P177 海关总署官网「直属机构」页真实 HTML 提取"
        matched.append((n["n"], links[n["n"]]))
w(tree)

for k, v in reg.items():
    if not v.get("u") and v.get("n") in links:
        v["u"] = links[v["n"]]
        v["source_level"] = "L1"
        v["verified_at"] = "2026-11-09"
        v["status"] = "ok"

json.dump(tree, open("tree.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
json.dump(reg, open("site_registry.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"P177: 落库 {len(matched)} 个")
unm = [n for n in links if n not in [m[0] for m in matched]]
if unm:
    print("未匹配:", unm)
