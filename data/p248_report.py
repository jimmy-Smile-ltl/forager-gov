# -*- coding: utf-8 -*-
"""p248 县级结果报告：覆盖率 + 类别分布 + 剔除/漏采清单（只读，不改数据）。

产物 data/zzjg_county_report.md

用法：cd data && uv run python p248_report.py
"""
import json
import os
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))

import p248_county_zzjg as M   # 目标口径与产物路径的单一来源


def main():
    targets = M.load_county_targets()
    out = json.load(open(M.OUT_F, encoding="utf-8")) if os.path.exists(M.OUT_F) else {}
    st = json.load(open(M.STATE_F, encoding="utf-8")) if os.path.exists(M.STATE_F) else {"fail": {}}
    rej = json.load(open(M.REJ_F, encoding="utf-8")) if os.path.exists(M.REJ_F) else {}

    by_prov = defaultdict(lambda: [0, 0])      # prov -> [total, hit]
    by_city = defaultdict(lambda: [0, 0])
    kinds = Counter()
    methods = Counter()
    for t in targets:
        by_prov[t["prov"]][0] += 1
        by_city[(t["prov"], t["city"])][0] += 1
        rec = out.get(t["key"])
        if rec and any(l.get("kind") in M.P.CORE_KINDS for l in rec.get("links") or []):
            by_prov[t["prov"]][1] += 1
            by_city[(t["prov"], t["city"])][1] += 1
            for l in rec.get("links") or []:
                kinds[l.get("kind")] += 1
            methods[(rec.get("method") or "").split("/")[0]] += 1

    hit = sum(v[1] for v in by_prov.values())
    total = len(targets)
    L = []
    L.append("# 县级人民政府「组织机构 / 部门」栏目采集报告\n")
    L.append(f"- 目标县级：**{total}**；已采：**{hit}**（{hit * 100.0 / max(1, total):.1f}%）")
    L.append(f"- 剔除（复核不通过）：**{len(rej)}**；记录文件：{M.OUT_F}")
    L.append(f"- 类别分布：" + "、".join(f"{k} {v}" for k, v in kinds.most_common()))
    L.append(f"- 渠道分布：" + "、".join(f"{k} {v}" for k, v in methods.most_common()))
    L.append("\n## 按省\n")
    L.append("| 省 | 已采 | 目标 | 覆盖率 |")
    L.append("|---|---|---|---|")
    for p, (tt, hh) in sorted(by_prov.items(), key=lambda x: -x[1][0]):
        L.append(f"| {p} | {hh} | {tt} | {hh * 100.0 / max(1, tt):.1f}% |")

    L.append("\n## 覆盖率最低的地级市（<40%，前 40）\n")
    L.append("| 省 | 市 | 已采 | 目标 |")
    L.append("|---|---|---|---|")
    low = [(k, v) for k, v in by_city.items()
           if v[0] >= 5 and v[1] * 1.0 / v[0] < 0.4]
    low.sort(key=lambda kv: kv[1][1] * 1.0 / kv[1][0])
    for (p, c), (tt, hh) in low[:40]:
        L.append(f"| {p} | {c} | {hh} | {tt} |")

    if rej:
        L.append("\n## 复核剔除清单\n")
        L.append("| 县 | URL | 原因 |")
        L.append("|---|---|---|")
        for k, v in list(rej.items())[:200]:
            L.append(f"| {k} | {v.get('url', '')} | {(v.get('why') or [''])[0][:70]} |")

    miss = [t for t in targets
            if not (out.get(t["key"]) and any(
                l.get("kind") in M.P.CORE_KINDS
                for l in out[t["key"]].get("links") or []))]
    fails = Counter()
    for t in miss:
        for ph in ("sc", "static", "deep", "xxgk", "click"):
            msg = st["fail"].get(f"{ph}:{t['key']}")
            if msg:
                fails[msg.split("(")[0].strip()] += 1
                break
    L.append("\n## 漏采失败原因（Top 15）\n")
    for r, n in fails.most_common(15):
        L.append(f"- {r}：{n}")

    open(os.path.join(HERE, "zzjg_county_report.md"), "w",
         encoding="utf-8").write("\n".join(L) + "\n")
    print(f"报告已写入 zzjg_county_report.md（目标 {total}，已采 {hit}，剔除 {len(rej)}）")


if __name__ == "__main__":
    main()
