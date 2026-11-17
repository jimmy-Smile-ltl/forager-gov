# -*- coding: utf-8 -*-
"""P127: 青海省政府门户「各州县政府网站」区块 → 市/县门户落库。

权威第 1 档：省政府门户官方导航真实 HTML。县级 URL 按采集规则
「只记录不访问」直接落库。
"""
import json
import re

t = open("snapshots/shixian/青海省/青海省政府门户/20261105_home.html",
         encoding="utf-8", errors="replace").read()
i = t.find("huangnan.gov.cn")
seg = t[max(0, i-10000):i+12000]

# 提取全部链接（含州和县）
links = {}
for u, txt in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>\s*([^<]{2,24}?)\s*</a>', seg):
    t2 = txt.strip()
    if u.startswith("http") and ".gov.cn" in u:
        links.setdefault(t2, u)
print("青海区块链接:", len(links))

# 州市名映射
SHI_MAP = {"西宁": "西宁市", "海东": "海东市", "海北州": "海北藏族自治州",
           "海南州": "海南藏族自治州", "海西州": "海西蒙古族藏族自治州",
           "黄南州": "黄南藏族自治州", "果洛州": "果洛藏族自治州",
           "玉树州": "玉树藏族自治州"}
tree = json.load(open("tree.json", encoding="utf-8"))
prov = next(g for g in tree["ks"] if g["n"].startswith("省级"))
qh = next(p for p in prov["ks"] if p["n"] == "青海省")

fixed_shi = fixed_xian = 0
for top in qh.get("ks", []):
    def walk(n):
        global fixed_shi, fixed_xian
        if n.get("k") == "人民政府" and n.get("l") in ("市", "县"):
            nm = n["n"]
            # 州名匹配
            key = None
            for k, full in SHI_MAP.items():
                if full == nm:
                    key = k
                    break
            if key is None:
                key = re.sub(r"(自治县|县|市)$", "", nm)
            if key in links and not n.get("u"):
                n["u"] = links[key]
                if n["l"] == "市":
                    fixed_shi += 1
                else:
                    fixed_xian += 1
        for k in n.get("ks", []):
            walk(k)
    walk(top)

json.dump(tree, open("tree.json", "w", encoding="utf-8"),
          ensure_ascii=False, separators=(",", ":"))
print(f"p127 完成：青海补市 {fixed_shi}，补县 {fixed_xian}")
