# -*- coding: utf-8 -*-
"""p246 成果导出：把 zzjg_pages.json 摊平成一张可直接交付的清单（只读）。

产物（均在 data/ 下）：
  zzjg_links.csv   每行 = 一个门户的一个「机构/单位/企业/公积金/高校」栏目
                  列：省级归属/层级/单位/类别/栏目标题/URL/采集方式/验证日期
  zzjg_links.md    同上，按省分组的 Markdown 表（便于人眼复核）

用法：cd data && uv run python p246_export.py
"""
import csv
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
KINDS = ["机构设置", "内设机构", "直属单位", "事业单位", "直属企业", "公积金", "高校"]


def main():
    tree = json.load(open(os.path.join(HERE, "tree.json"), encoding="utf-8"))
    out = json.load(open(os.path.join(HERE, "zzjg_pages.json"), encoding="utf-8"))

    rows = []

    def walk(n, prov=""):
        for ch in n.get("ks") or []:
            lvl = ch.get("l")
            p = ch.get("n") if lvl == "省" else prov
            if ch.get("k") == "人民政府" and lvl in ("省", "市") and ch.get("u"):
                key = f"{lvl}|{ch.get('n')}"
                rec = out.get(key)
                if rec:
                    links = rec.get("links") or [rec]
                    for l in links:
                        if not l.get("u"):
                            continue
                        rows.append(dict(
                            prov=(prov or p), level=lvl, name=ch.get("n"),
                            kind=l.get("kind", ""), title=l.get("title", ""),
                            u=l["u"], method=l.get("method", ""),
                            verified_at=l.get("verified_at") or rec.get("verified_at", ""),
                        ))
            walk(ch, p)

    walk(tree)

    order = {k: i for i, k in enumerate(KINDS)}
    rows.sort(key=lambda r: (r["prov"], 0 if r["level"] == "省" else 1, r["name"],
                             order.get(r["kind"], 99), r["u"]))

    csv_f = os.path.join(HERE, "zzjg_links.csv")
    with open(csv_f, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["prov", "level", "name", "kind",
                                          "title", "u", "method", "verified_at"])
        w.writeheader()
        w.writerows(rows)

    # Markdown：按省分组
    md_f = os.path.join(HERE, "zzjg_links.md")
    lines = ["# 省市门户「组织机构类」栏目清单", "",
             f"> 共 {len(rows)} 条栏目 · 覆盖 {len({(r['level'], r['name']) for r in rows})} 个门户", ""]
    cur = None
    for r in rows:
        if r["prov"] != cur:
            cur = r["prov"]
            lines.append(f"\n## {cur}\n")
            lines.append("| 单位 | 层级 | 类别 | 栏目 | URL |")
            lines.append("|---|---|---|---|---|")
        lines.append(f"| {r['name']} | {r['level']} | {r['kind']} | "
                     f"{r['title'][:40]} | {r['u']} |")
    with open(md_f, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"写入 {csv_f} / {md_f}：{len(rows)} 条栏目，"
          f"{len({(r['level'], r['name']) for r in rows})} 个门户")


if __name__ == "__main__":
    main()
