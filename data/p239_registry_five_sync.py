#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""p239 五系统 registry 同步（2026-11-17，审计清理后的主数据对齐）。

背景：p228/p238 审计把错配 URL 从 tree.json 清掉后，site_registry.json 里
仍留着同一条 URL（p222 只覆盖「五系统市级节点」，且规则是
「树为空则保留 registry」，本意是防历史 p206 只写 registry 的 URL 丢失）。
结果是：审计清掉的错配 URL 会被 p22 的来源等级/健康状态统计继续计入，
下一次任何「registry → 树」的同步还会把它复活。

本脚本对**省级/市级/县级全部五系统叶子**做三件事（tree 为事实源）：
  ① 树有 URL、registry 不同 → registry 以树为准（url_fixed）
  ② 树已清空、registry 仍有 URL、且树的 s 字段带审计清除留痕 → registry 置
     u="" / status="cleared"（clear_stale）。没有审计留痕的一概不动——
     历史「只写 registry 未写树」的 URL 不能被误杀。
  ③ 树有 URL、registry 无记录 → 补登（add）

用法：
  cd data && uv run python p239_registry_five_sync.py --dry
  cd data && uv run python p239_registry_five_sync.py
"""
import datetime
import json
import os
import shutil
import sys
from collections import Counter

DATA = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(DATA)
sys.path.insert(0, DATA)
sys.path.insert(0, os.path.join(ROOT, "util"))
import p223_county_5sys_fill as P  # noqa: E402
from site_contract import five_key, five_name, source_level, upsert_registry  # noqa: E402

TREE_F = os.path.join(DATA, "tree.json")
REG_F = os.path.join(DATA, "site_registry.json")
TODAY = datetime.date.today().isoformat()
DRY = "--dry" in sys.argv
# 审计清除留痕（s 字段）。只有带这些标记的空节点才会同步清 registry
AUDIT_MARKS = ("p228 审计", "p228 人工复核", "p228F", "p238 审计",
               "p238 人工复核", "SERP变体轮复核", "S2 门户轮复核")


def collect_all(tree):
    """返回 [(key, node, name, org_name)]，覆盖市/县五系统叶子。"""
    blk = next(g for g in tree["ks"] if g["n"].startswith("省级"))
    county_names = Counter()
    for prov in blk["ks"]:
        for city in prov.get("ks") or []:
            for county in city.get("ks") or []:
                county_names[county.get("n")] += 1
    dup_names = {n for n, c in county_names.items() if c > 1}
    rows = []
    for prov in blk["ks"]:
        for city in prov.get("ks") or []:
            grp = next((g for g in city.get("ks") or []
                        if g.get("c") == "并列机关"), None)
            if grp and city.get("k") == "人民政府" and city.get("l") in CITY_L:
                for o in grp.get("ks") or []:
                    cn = o.get("n")
                    if cn not in CITY_ORGS:
                        continue
                    try:
                        k = five_key(city.get("n"), cn)
                        nm = five_name(city.get("n"), cn)
                    except KeyError:
                        continue
                    rows.append((k, o, nm, cn))
            # 县级
            for county in city.get("ks") or []:
                g2 = next((g for g in county.get("ks") or []
                           if g.get("c") == "并列机关"), None)
                if not g2:
                    continue
                for o in g2.get("ks") or []:
                    if o.get("n") in P.COUNTY_KEY:
                        k = P.county_key(prov.get("n"), county, o["n"], dup_names)
                        rows.append((k, o, k.split("|", 1)[1], o["n"]))
    return rows


CITY_L = ("市", "地级区")
CITY_ORGS = {"市人大", "市政协", "市监委", "市人民法院", "市人民检察院"}


def main():
    tree = json.load(open(TREE_F, encoding="utf-8"))
    reg = json.load(open(REG_F, encoding="utf-8"))
    rows = collect_all(tree)
    print(f"p239 五系统叶子 {len(rows)}")
    stats = Counter()
    conflicts, cleared = [], []
    seen = set()
    for key, node, name, org_name in rows:
        if key in seen:
            continue
        seen.add(key)
        u = (node.get("u") or "").strip()
        s = node.get("s") or ""
        e = reg.get(key)
        if u:
            if e is None:
                if not DRY:
                    # 补登沿用树内 URL，未重新复验 → verified_at 留空（不冒充今日复验）
                    reg[key] = {"u": u, "n": name, "status": "ok",
                                "source_level": source_level(s, "L2"),
                                "source": s, "verified_at": "",
                                "locations": ["块"], "snapshot": "",
                                "note": "p239 补登（沿用树内 URL）"}
                stats["add"] += 1
            elif (e.get("u") or "").strip() != u:
                if (e.get("u") or "").strip():
                    conflicts.append((key, e.get("u", ""), u))
                if not DRY:
                    e["u"] = u
                    e["status"] = "ok"
                    e["source_level"] = source_level(s, e.get("source_level") or "L2")
                    e["verified_at"] = TODAY
                stats["url_fixed"] += 1
            else:
                stats["same"] += 1
        else:
            if e and (e.get("u") or "").strip():
                if any(m in s for m in AUDIT_MARKS):
                    cleared.append((key, e["u"]))
                    if not DRY:
                        e["u"] = ""
                        e["status"] = "cleared"
                        e["verified_at"] = TODAY
                        e["note"] = "p228/p238 审计清除：" + s.split("审计")[-1][:60]
                    stats["clear_stale"] += 1
                else:
                    stats["keep_no_audit"] += 1
            else:
                stats["empty"] += 1
    print("统计:", dict(stats))
    for c in conflicts[:10]:
        print("  CONFLICT", c[0], "\n    registry:", c[1][:80], "\n    tree    :", c[2][:80])
    for k, u in cleared[:10]:
        print("  CLEAR", k, u[:80])
    if DRY:
        print("（--dry 未落库）")
        return
    d = os.path.join(ROOT, "backups", TODAY)
    os.makedirs(d, exist_ok=True)
    ts = datetime.datetime.now().strftime("%H%M%S")
    shutil.copy2(REG_F, os.path.join(d, f"registry_before_p239_{ts}.json"))
    json.dump(reg, open(REG_F, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("p239 已写 site_registry.json")


if __name__ == "__main__":
    main()
