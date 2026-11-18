# -*- coding: utf-8 -*-
"""p246 结果报告：覆盖率 + 类别分布 + 缺口清单（只读，不改任何数据）。

产物 data/zzjg_pages_report.md：
  - 总览（命中/缺口、按省分组覆盖率）
  - 类别分布（机构设置/内设机构/直属单位/事业单位/直属企业/公积金/高校）
  - 缺口清单（含各阶段失败原因，便于人工挑拣）

用法：cd data && uv run python p246_report.py
"""
import datetime
import json
import os
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_F = os.path.join(HERE, "zzjg_pages.json")
STATE_F = os.path.join(HERE, "p246_state.json")
REP_F = os.path.join(HERE, "zzjg_pages_report.md")
KINDS = ["机构设置", "内设机构", "直属单位", "事业单位", "直属企业", "公积金", "高校"]


def main():
    tree = json.load(open(os.path.join(HERE, "tree.json"), encoding="utf-8"))
    out = json.load(open(OUT_F, encoding="utf-8")) if os.path.exists(OUT_F) else {}
    st = json.load(open(STATE_F, encoding="utf-8")) if os.path.exists(STATE_F) else {"fail": {}}

    targets = []

    def walk(n, prov=""):
        for ch in n.get("ks") or []:
            lvl = ch.get("l")
            p = ch.get("n") if lvl == "省" else prov
            if ch.get("k") == "人民政府" and lvl in ("省", "市") and ch.get("u"):
                targets.append(dict(key=f"{ch.get('l')}|{ch.get('n')}",
                                    level=lvl, name=ch.get("n"),
                                    prov=(prov or p), url=ch["u"]))
            walk(ch, p)

    walk(tree)

    hit = [t for t in targets if t["key"] in out]
    miss = [t for t in targets if t["key"] not in out]
    kind_cnt = Counter()
    for rec in out.values():
        for l in (rec.get("links") or ([rec] if rec.get("u") else [])):
            kind_cnt[l.get("kind", "?")] += 1
    n_partial = sum(1 for rec in out.values() if rec.get("partial"))
    n_homeblock = sum(1 for rec in out.values()
                      if any(l.get("homeblock") for l in (rec.get("links") or [])))

    lines = ["# 省市门户「组织机构类」栏目采集报告（p246）", ""]
    lines.append(f"> 生成于 {datetime.date.today().isoformat()} · "
                 f"目标 {len(targets)} · 命中 {len(hit)} · 缺口 {len(miss)} "
                 f"（{len(hit) / max(1, len(targets)) * 100:.1f}%）· "
                 f"其中仅公积金/高校外链（partial）{n_partial} 个 · "
                 f"机构名录内嵌首页、无独立栏目页（homeblock）{n_homeblock} 个")
    lines.append("")
    lines.append("## 类别分布（一个门户可命中多类）")
    lines.append("")
    lines.append("| 类别 | 条目数 |")
    lines.append("|---|---:|")
    for k in KINDS:
        lines.append(f"| {k} | {kind_cnt.get(k, 0)} |")
    lines.append("")

    by_prov = defaultdict(lambda: [0, 0])
    for t in targets:
        by_prov[t["prov"] or "（未归属）"][1] += 1
        if t["key"] in out:
            by_prov[t["prov"] or "（未归属）"][0] += 1
    lines.append("## 分省覆盖率")
    lines.append("")
    lines.append("| 省 / 单位 | 命中 | 目标 | 覆盖率 |")
    lines.append("|---|---:|---:|---:|")
    for prov, (h, n) in sorted(by_prov.items(),
                               key=lambda kv: (kv[1][0] / kv[1][1], kv[0])):
        lines.append(f"| {prov} | {h} | {n} | {h / n * 100:.0f}% |")
    lines.append("")

    lines.append(f"## 缺口清单（{len(miss)}）")
    lines.append("")
    lines.append("| key | 门户 | 失败记录 |")
    lines.append("|---|---|---|")
    for t in miss:
        reasons = [f"{k.split(':', 1)[0]}:{v}" for k, v in st.get("fail", {}).items()
                   if k.endswith(":" + t["key"])]
        reason = "；".join(reasons[-2:]) if reasons else "（未处理）"
        lines.append(f"| {t['key']} | {t['url']} | {reason.replace('|', '/')} |")
    lines.append("")

    with open(REP_F, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"写入 {REP_F}: 命中 {len(hit)}/{len(targets)}，缺口 {len(miss)}")


if __name__ == "__main__":
    main()
