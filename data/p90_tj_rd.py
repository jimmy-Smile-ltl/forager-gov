# -*- coding: utf-8 -*-
"""P90: 天津区人大（tjrd.gov.cn 首页「区人大」区块，真实 HTML）。

16 区：滨海新区/南开区/河北区 3 个有官网，其余 13 列名。
（p75 曾误匹配河北区→hbrd.gov.cn 河北省人大，已清；本轮恢复南开区
真实链接、补滨海新区、河北区正确链接 tjhb.gov.cn/tjshbqrdcwh/）
"""
import json
import re

t = open("/tmp/p87_天津市.html", encoding="utf-8", errors="replace").read()
i = t.find("bhxqrd")
seg = t[max(0, i - 600):i + 2200]
links = {}
for u, txt in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>\s*([^<]{2,10}?)\s*</a>', seg):
    links[txt.strip()] = u
print("天津区人大区块链接:", links)

# 16 区全名单（树里）
tree = json.load(open("tree.json", encoding="utf-8"))
prov_g = next(g for g in tree["ks"] if g["n"].startswith("省级"))
tj = next(x for x in prov_g["ks"] if x["n"] == "天津市")
names = []
for top in tj.get("ks", []):
    def walk(n):
        if n.get("l") in ("地级区", "县") and \
                n.get("k") in ("人民政府", "功能区") and \
                "开发区" not in n["n"]:
            names.append(n["n"])
        for k in n.get("ks", []):
            walk(k)
    walk(top)
print("天津 16 区:", len(names))

rows = []
for nm in names:
    base = nm.replace("区", "")
    u = links.get(nm, "")
    if not u and base in links:
        u = links[base]
    rows.append({"province": "天津市", "name": nm, "url": u,
                 "listed": bool(u)})

old = [json.loads(l) for l in open("rd_shi.jsonl", encoding="utf-8")]
old = [r for r in old if r["province"] != "天津市"]
with open("rd_shi.jsonl", "w", encoding="utf-8") as f:
    for r in old + rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
print(f"p90 完成：天津 {len(rows)} 区（{sum(1 for r in rows if r['listed'])} 有官网）")
