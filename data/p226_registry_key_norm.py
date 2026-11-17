#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""p226 registry 县级/类别脏键归一（开源后统一数据框架，2026-11-17）。

p222 只处理「五系统市级」脏键；县级补采（p195/p223/p224）与更早的老脚本
又写出一批非规范键，同一机构多键并存会破坏「一个机构一个采集结果」铁律
（架构铁律 #1 registry 先查后采）。本脚本按名称自身的机构后缀判定归属
类别，把脏键迁移到规范键：

  人大|西城区政协            → 政协|西城区政协
  人大|石景山区监委          → 纪委|石景山区监委
  人大|石家庄市人民检察院    → 检察|石家庄市人民检察院
  县级监委|X                → 纪委|X监委
  县级人大|X                → 人大|X人大
  县级检察|X / 检察院|X     → 县级人民检察院|X
  法院|东城区人民法院        → 县级人民法院|东城区（非中级/高级/最高）
  市级政府部门|…纪委监委     → 纪委|…
  政协系统|通州区政协        → 政协|通州区政协

另外清理：类别是系统名而 u 挂着省政府门户的错配条目（如
`检察院|北京市 → beijing.gov.cn`，早期误采，p205 类审计已判错）。

合并规则：目标键已存在时保留非空 u（若两者不同，以 source_level 高者为准，
同级别保留目标），locations 取并集，verified_at 取较新。

用法：
  cd data && uv run python p226_registry_key_norm.py --dry
  cd data && uv run python p226_registry_key_norm.py        # 写库（自动备份）
"""
import datetime
import json
import os
import re
import shutil
import sys

DATA = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(DATA)
sys.path.insert(0, DATA)
from site_contract import _RANK, base  # noqa: E402

REG_F = os.path.join(DATA, "site_registry.json")
DRY = "--dry" in sys.argv
TODAY = datetime.date.today().isoformat()

# 类别字段是分组名/系统名时的兜底（按名称后缀重判）
GROUP_CATS = {"市级政府部门", "政协系统", "纪委系统", "检察院系统", "法院系统",
              "人大系统", "县委/县人大/县政协/县监委/县法院/县检察院",
              "市委/市人大/市政协/市监委/市中院/市检察院"}
# 省级门户域名（系统级键挂门户=早期误采）
PROV_PORTAL = re.compile(
    r"^https?://(www\.)?(beijing|tj|ln|sh|zj|fj|sd|ah|hb|hn|gd|gx|hi|sc|gz|yn|xz|sn|gs|qh|nx|xj)\.gov\.cn/?$")


def suffix_cat(nm):
    """按名称后缀判机构类别（只判确定的，不猜）。"""
    if nm.endswith("人民检察院") or nm.endswith("检察院"):
        return "检察"
    if nm.endswith("人民法院") or nm.endswith("法院"):
        return "法院"
    if nm.endswith("监委") or nm.endswith("纪委"):
        return "纪委"
    if nm.endswith("政协"):
        return "政协"
    if nm.endswith("人大"):
        return "人大"
    return None


def county_like(nm):
    """名称看起来是县级法院全名（非中级/高级/最高）。"""
    return (nm.endswith("人民法院") and not re.search(r"中级|高级|最高|海事|铁路|森林|知产|兵团|矿区|林区|军事|专门", nm))


def canon(cat, nm):
    """(cat, nm) → (new_cat, new_nm)；无需迁移返回 None。"""
    c = suffix_cat(nm)
    # 1. 大类字段是分组名 → 按后缀重判
    if cat in GROUP_CATS:
        return (c or cat, nm) if c and c != cat else None
    # 2. 县级前缀键
    if cat == "县级监委":
        return ("纪委", nm if nm.endswith("监委") else nm + "监委")
    if cat == "县级人大":
        return ("人大", nm if nm.endswith("人大") else nm + "人大")
    if cat in ("县级检察", "县级检察院"):
        return ("县级人民检察院", nm)
    if cat == "检察院":
        # 省级/市级检察院全名保留全称键；纯省名（无后缀）是老脏键
        if nm.endswith(("人民检察院", "检察院")):
            return ("检察", nm)
        return ("县级人民检察院", nm) if not re.search(r"省|自治区|市$", nm) else None
    # 3. 类别与名称后缀矛盾
    if c and c != cat:
        if cat == "法院" and c == "法院" and county_like(nm):
            return ("县级人民法院", base(nm))
        return (c, nm)
    # 4. 基层法院全名 → 县级人民法院（基底名）
    if cat == "法院" and county_like(nm):
        return ("县级人民法院", base(nm))
    return None


def merge(dst, src):
    """把 src 合并进 dst（就地）。"""
    if not dst.get("u") and src.get("u"):
        dst["u"] = src["u"]
        dst["status"] = src.get("status") or "ok"
    # 来源等级高者覆盖
    if _RANK.get(src.get("source_level", ""), 0) > _RANK.get(dst.get("source_level", ""), 0):
        dst["source_level"] = src["source_level"]
        if src.get("u") and not dst.get("u_from_high"):
            dst["u"] = src["u"]
    for k in ("xxgk", "xxgk_src", "snapshot", "note"):
        if not dst.get(k) and src.get(k):
            dst[k] = src[k]
    locs = list(dst.get("locations") or [])
    for l in src.get("locations") or []:
        if l not in locs:
            locs.append(l)
    dst["locations"] = locs
    if (src.get("verified_at") or "") > (dst.get("verified_at") or ""):
        dst["verified_at"] = src["verified_at"]
    return dst


def main():
    reg = json.load(open(REG_F, encoding="utf-8"))
    moves, purged = [], []
    newreg = {}
    for k, e in list(reg.items()):
        cat, nm = (k.split("|", 1) + [""])[:2]
        u = (e.get("u") or "").strip()
        # 系统级键挂省门户 = 早期误采
        if cat in ("检察院", "法院", "人大", "政协", "群团", "纪委") and PROV_PORTAL.match(u):
            purged.append((k, u))
            continue
        tgt = canon(cat, nm)
        if tgt and (tgt[0], tgt[1]) != (cat, nm):
            nk = f"{tgt[0]}|{tgt[1]}"
            e2 = dict(e)
            if "n" in e2:
                e2["n"] = e2.get("n") or tgt[1]
            e2["note"] = (e2.get("note") or "") + f"{'；' if e2.get('note') else ''}p226 迁移自 {k}"
            moves.append((k, nk))
            if nk in reg and nk not in newreg:
                merge(reg[nk], e2)
                continue
            if nk in newreg:
                merge(newreg[nk], e2)
                continue
            newreg[nk] = e2
            continue
        newreg[k] = e
    # 已被迁移走的旧键从 newreg 删除
    moved_old = {a for a, _ in moves}
    for a in moved_old:
        newreg.pop(a, None)

    print(f"p226 键归一: 迁移 {len(moves)} 条, 清理错配 {len(purged)} 条, "
          f"剩余 {len(newreg)}（原 {len(reg)}）{'（DRY 未写库）' if DRY else ''}")
    from collections import Counter
    c = Counter(f"{a.split('|')[0]} → {b.split('|')[0]}" for a, b in moves)
    for k, v in c.most_common(12):
        print(f"  {v:5d}  {k}")
    for a, b in moves[:10]:
        print(f"  {a}  ⇒  {b}")
    for k, u in purged[:6]:
        print(f"  PURGE {k} ({u[:40]})")

    if not DRY and (moves or purged):
        d = os.path.join(ROOT, "backups", TODAY)
        os.makedirs(d, exist_ok=True)
        ts = datetime.datetime.now().strftime("%H%M%S")
        shutil.copy2(REG_F, os.path.join(d, f"registry_before_p226key_{ts}.json"))
        json.dump(newreg, open(REG_F, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("  已写 site_registry.json")


if __name__ == "__main__":
    main()
