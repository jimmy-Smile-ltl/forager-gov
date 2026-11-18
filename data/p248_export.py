# -*- coding: utf-8 -*-
"""p248 县级成果导出：zzjg_county.json → 可交付清单（只读）。

产物（均在 data/ 下）：
  zzjg_county_links.csv  每行 = 一个县的一个「机构/部门/单位」栏目
  zzjg_county_links.md   同上，按省分组（人眼复核）

用法：cd data && uv run python p248_export.py
"""
import csv
import json
import os
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))

import p248_county_zzjg as M


def main():
    targets = M.load_county_targets()
    out = json.load(open(M.OUT_F, encoding="utf-8")) if os.path.exists(M.OUT_F) else {}
    rows = []
    for t in targets:
        rec = out.get(t["key"])
        if not rec:
            continue
        for l in rec.get("links") or []:
            if not l.get("u"):
                continue
            rows.append(dict(prov=t["prov"], city=t["city"], name=t["name"],
                             kind=l.get("kind", ""), title=l.get("title", ""),
                             u=l["u"], method=l.get("method", ""),
                             verified_at=rec.get("verified_at", ""),
                             src=l.get("src", "")))

    csv_f = os.path.join(HERE, "zzjg_county_links.csv")
    with open(csv_f, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["prov", "city", "name", "kind", "title",
                                          "u", "method", "verified_at", "src"])
        w.writeheader()
        w.writerows(rows)

    by_prov = defaultdict(list)
    for r in rows:
        by_prov[r["prov"]].append(r)
    L = ["# 县级人民政府「组织机构 / 部门」栏目清单\n",
         f"共 {len(rows)} 条，覆盖 {len({r['name'] for r in rows})} 个县级单位。\n"]
    for p in sorted(by_prov):
        L.append(f"\n## {p}（{len(by_prov[p])}）\n")
        L.append("| 市 | 县 | 类别 | 标题 | URL | 方式 |")
        L.append("|---|---|---|---|---|---|")
        for r in by_prov[p]:
            L.append(f"| {r['city']} | {r['name']} | {r['kind']} | "
                     f"{r['title'][:40]} | {r['u']} | {r['method']} |")
    open(os.path.join(HERE, "zzjg_county_links.md"), "w",
         encoding="utf-8").write("\n".join(L) + "\n")
    print(f"导出 {len(rows)} 条 → zzjg_county_links.csv / .md")


if __name__ == "__main__":
    main()
