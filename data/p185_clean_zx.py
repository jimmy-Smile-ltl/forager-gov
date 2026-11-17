# -*- coding: utf-8 -*-
"""P185: 清洗 P181 误匹配——门户新闻/文章页 URL 不是政协官网,
特征: /content/ /Item/ /t2026年月 新闻路径 /art_。清除后由 P184 C 通道
（通用提取器带新闻过滤）重扫。"""
import json, re
NEWS = re.compile(r"/(content|art_\d+|t\d{8}_\d+|Item/\d+|articleId)", re.I)
tree = json.load(open("tree.json", encoding="utf-8"))
blk = next(g for g in tree["ks"] if g["n"].startswith("省级"))
cleared = 0
for p in blk["ks"]:
    for c in p.get("ks", []):
        for jg in c.get("ks", []):
            if jg.get("k") != "分组":
                continue
            for o in jg.get("ks", []):
                if o.get("n") == "县政协" and o.get("u") and o.get("s", "").startswith("P181"):
                    u = o["u"]
                    if NEWS.search(u) or "aspx" in u and "/Item/" in u:
                        print(f"清除 {c['n']}县政协: {u[:60]}")
                        o["u"] = ""
                        o["s"] = ""
                        cleared += 1
json.dump(tree, open("tree.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"P185: 清除 {cleared} 个误匹配")
