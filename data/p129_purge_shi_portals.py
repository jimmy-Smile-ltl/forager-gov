# -*- coding: utf-8 -*-
"""P129: 市县门户探测存量清除（how=拼音探测/拼音类 → 列名）。

用户红线「绝对不认可拼音」：city_county_final 里 how 含「拼音」的
910 条全部列名。bing 类保留待 p130 逐条重验。
"""
import json
import re

rows = [json.loads(l) for l in open("city_county_final.jsonl", encoding="utf-8")]
purge = []
keep_bing = []
for r in rows:
    h = r.get("how", "")
    if "拼音" in h:
        purge.append(r)
    elif "bing" in h.lower():
        keep_bing.append(r)

print(f"拼音探测清除: {len(purge)} 条")
print(f"bing 待重验: {len(keep_bing)} 条")
by_prov = {}
for r in purge:
    by_prov[r["province"]] = by_prov.get(r["province"], 0) + 1
print("按省分布:", dict(sorted(by_prov.items(), key=lambda x: -x[1])))

# 树落库：portal_url 清空
tree = json.load(open("tree.json", encoding="utf-8"))
prov = next(g for g in tree["ks"] if g["n"].startswith("省级"))
purge_names = {(r["province"], r["name"]) for r in purge}
cleared = 0
for p in prov["ks"]:
    pn = p["n"]
    for top in p.get("ks", []):
        def walk(n):
            global cleared
            if n.get("k") == "人民政府" and n.get("l") in ("市", "县", "地级区") \
                    and (pn, n["n"]) in purge_names and n.get("u"):
                n["u"] = ""
                cleared += 1
            for k in n.get("ks", []):
                walk(k)
        walk(top)
json.dump(tree, open("tree.json", "w", encoding="utf-8"),
          ensure_ascii=False, separators=(",", ":"))
print(f"树清除: {cleared} 个节点 URL")

# 更新 jsonl how 标记
for r in purge:
    r["how"] = "拼音探测(已清除)"
with open("city_county_final.jsonl", "w", encoding="utf-8") as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
print("jsonl 已标记")
