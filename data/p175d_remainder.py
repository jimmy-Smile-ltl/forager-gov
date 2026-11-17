# -*- coding: utf-8 -*-
"""P175d: 处理 p174 余留 315 条。
(1) 同名多节点同 u → 全赋 (2) www 差异域名 → 赋
(3) 法院统一司法公开平台（zxgk/splcgk/elink）→ 赋（真实官网链接的公共入口）
(4) 其余归属不明 → 不赋，保持 x 空。"""
import json
from urllib.parse import urlparse
from collections import defaultdict

rem = json.load(open("xxgk_remainder.json", encoding="utf-8"))
tree = json.load(open("tree.json", encoding="utf-8"))

idx = defaultdict(list)
def w(n):
    if n.get("u") and not n.get("ks") and not n.get("x"):
        idx[n["n"]].append(n)
    for k in n.get("ks", []): w(k)
w(tree)

def dom(u):
    return urlparse(u).netloc.replace("www.", "").split(":")[0]

COURT_PLATFORM = ("zxgk.court.gov.cn", "splcgk.court.gov.cn", "elink.chinacourt.cn")

assigned, skipped = [], []
for name, x_url, why in rem:
    cands = idx.get(name, [])
    if not cands: skipped.append((name, x_url, why)); continue
    xdom = dom(x_url)
    # 法院统一公开平台 → 该名所有法院节点全赋
    if any(p in x_url for p in COURT_PLATFORM):
        for n in cands:
            if "法院" in n["n"] or "法庭" in n["n"]:
                n["x"], n["s"] = x_url, "p175d 法院统一司法公开平台（官网首页真实链接）"
                assigned.append((name, n["n"], x_url))
        continue
    # 域名匹配（忽略 www）→ 全赋
    hits = [n for n in cands if dom(n["u"]) == xdom]
    if hits:
        for n in hits:
            n["x"], n["s"] = x_url, "p175d 余留消歧（域名归属）"
            assigned.append((name, n["n"], x_url))
        continue
    skipped.append((name, x_url, why))

json.dump(tree, open("tree.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"p175d: 赋 {len(assigned)} 个, 放弃 {len(skipped)} 个")
for name, nn, x in assigned[:12]:
    print(f"  ✓ {name}/{nn}: {x[:60]}")

