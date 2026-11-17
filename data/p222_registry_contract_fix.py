#!/usr/bin/env python
# p222 registry 写库契约迁移（开源后统一数据框架，2026-11-17）
"""把历史补采脚本写入的 registry 脏键归一为 `<类别>|<全名>`，并让
块树五系统市级节点与 registry 双向对齐。

历史问题（p203/p204/p207/p208）：
  - 键写成 `法院|市人大|石家庄市`（类别恒为法院）
  - 键写成 `人大|北京市`（全名缺机构后缀）
  - p206 只写树不写 registry
  - 同一机构重复条目、n 字段出现「石家庄市市人大」
本脚本以树为事实源、registry 为主数据：
  ① 解析脏键 → 标准键（five_key）
  ② 合并重复条目（保留 xxgk/snapshot，locations 取并集）
  ③ 树有 URL 但 registry 无记录 → 补登
  ④ 树为空但脏键有 URL → 不复活（p205 审计已清除的错误 URL）
  ⑤ canonical 条目与树 URL 不一致 → 以树为准并记录冲突
用法：
  cd data && uv run python p222_registry_contract_fix.py --dry   # 预演
  cd data && uv run python p222_registry_contract_fix.py         # 落库
  cd data && uv run python p222_registry_contract_fix.py --check # 只校验
"""
import collections
import datetime
import json
import os
import shutil
import sys
import tempfile
import time

DATA = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(DATA)
sys.path.insert(0, DATA)
from site_contract import (FIVE_ORGS, base, five_key, five_name,
                           source_level, upsert_registry)

TREE_F = os.path.join(DATA, "tree.json")
REG_F = os.path.join(DATA, "site_registry.json")
BAK_DIR = os.path.join(ROOT, "backups", datetime.date.today().isoformat())
DRY = "--dry" in sys.argv
CHECK = "--check" in sys.argv

CITY_C = ("地级市人民政府", "市辖区（地级行政区划）")
# 树已审计为「无官网」但 registry 仍留旧 URL 的已知项：清空但保留记录
STALE_EMPTY = {
    "人大|秦皇岛市人大": "p205 审计：mzfzw.net 民主法制网非机构官网",
    "人大|保定市人大": "p205 审计：mzfzw.net 民主法制网非机构官网",
    "人大|七台河市人大": "p205 审计：qth.gov.cn 为市政府门户非人大官网",
    "法院|吐鲁番市中级人民法院": "p220 死链治理：旧 chinacourt 域已失效",
    "法院|喀什地区中级人民法院": "p220 死链治理：elink 目标不可达",
    "法院|塔城地区中级人民法院": "p220 死链治理：elink 目标不可达",
    "法院|阿勒泰地区中级人民法院": "p220 死链治理：elink 目标不可达",
}
ALIAS = {
    "人大": "市人大",
    "政协": "市政协",
    "法院": "市中级人民法院",
    "检察": "市人民检察院",
    "检察院": "市人民检察院",
    "检察院系统": "市人民检察院",
    "人民检察院": "市人民检察院",
    "纪委": "市监委",
    "监委": "市监委",
    "纪委系统": "市监委",
}


def atomic(obj, path):
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def collect_tree_five(tree):
    """返回 (key -> {node,city,org,prov}, 城市名集合, 基底名索引)。"""
    blk = next((g for g in tree.get("ks") or []
                if (g.get("n") or "").startswith("省级")), None)
    out = {}
    city_names = set()
    city_base = collections.defaultdict(list)
    dup = []
    for p in (blk.get("ks") or []) if blk else []:
        for c in (p.get("ks") or []):
            if c.get("c") not in CITY_C:
                continue
            city = c.get("n", "")
            city_names.add(city)
            city_base[base(city)].append(city)
            for jg in (c.get("ks") or []):
                if jg.get("c") != "并列机关":
                    continue
                for o in (jg.get("ks") or []):
                    org = o.get("n", "")
                    if org not in FIVE_ORGS:
                        continue
                    k = five_key(city, org)
                    if k in out and out[k]["prov"] != p.get("n"):
                        dup.append(k)
                    out[k] = {"node": o, "city": city, "org": org,
                              "prov": p.get("n", "")}
    return out, city_names, city_base, dup


def resolve_city(name, city_names, city_base):
    if not name:
        return None
    if name in city_names:
        return name
    cands = city_base.get(base(name)) or []
    return cands[0] if len(cands) == 1 else None


def resolve_key(key, city_names, city_base):
    """脏键/别名键 → 标准五系统键；不能解析返回 None（保持原样）。"""
    seg = key.split("|")
    # p204/p207/p208 形态：法院|<市机构名>|<城市>
    if len(seg) >= 3 and seg[0] == "法院" and seg[1] in FIVE_ORGS:
        city = resolve_city(seg[2], city_names, city_base)
        return five_key(city, seg[1]) if city else None
    if len(seg) == 2:
        cat, name = seg
        # 已经是标准键（类别正确、全名带机构后缀）
        for org, (c, suf) in FIVE_ORGS.items():
            if cat == c and name.endswith(suf):
                city = resolve_city(name[:-len(suf)], city_names, city_base)
                if city:
                    return five_key(city, org)
        # p203 形态：人大|北京市 / 人民检察院|北京市 / 监委|北京市
        org = ALIAS.get(cat)
        if org:
            suf = FIVE_ORGS[org][1]
            city_name = name[:-len(suf)] if name.endswith(suf) else name
            city = resolve_city(city_name, city_names, city_base)
            if city:
                return five_key(city, org)
    return None


def tree_level(info):
    return source_level(info["node"].get("s", ""), default="L2")


def tree_date(info):
    return info["node"].get("verified_at") or datetime.date.today().isoformat()


def keep_meta(dst, src):
    """合并时保留 registry 既有专栏/快照等元数据。"""
    for f in ("xxgk", "xxgk_src", "snapshot"):
        if not dst.get(f) and src.get(f):
            dst[f] = src[f]


def merge_locations(dst, src):
    locs = list(dst.get("locations") or [])
    for loc in src.get("locations") or []:
        if loc and loc not in locs:
            locs.append(loc)
    dst["locations"] = locs


def normalize_entry(e, key, info=None, src=None):
    """补全 canonical 条目字段，n 统一为全名。"""
    if info:
        e["n"] = five_name(info["city"], info["org"])
    e.setdefault("n", key.split("|", 1)[-1])
    e.setdefault("u", "")
    e.setdefault("locations", [])
    if info:
        merge_locations(e, {"locations": ["块"]})
        lv = tree_level(info)
        if not e.get("source_level"):
            e["source_level"] = lv
        e.setdefault("verified_at", tree_date(info))
    e.setdefault("source_level", "L2")
    e.setdefault("verified_at", "")
    e.setdefault("status", "ok" if e.get("u") else "cleared")
    e.setdefault("snapshot", "")
    if src:
        keep_meta(e, src)
        merge_locations(e, src)
    return e


HARD = ("tree-url-no-registry", "url-mismatch", "malformed-key")


def do_check(reg, tree_five):
    issues = []
    for key, info in tree_five.items():
        u = (info["node"].get("u") or "").strip()
        e = reg.get(key)
        if u and not e:
            issues.append(("tree-url-no-registry", key, u))
        elif u and e and (e.get("u") or "").strip() != u:
            issues.append(("url-mismatch", key, f"{(e.get('u') or '')[:60]} != {u[:60]}"))
        elif not u and e and (e.get("u") or "").strip():
            issues.append(("registry-url-tree-empty", key, e["u"][:60]))
    bad = [k for k in reg
           if k.count("|") > 1
           and k.split("|")[0] == "法院"
           and k.split("|")[1] in FIVE_ORGS]
    for k in bad:
        issues.append(("malformed-key", k, (reg[k].get("u") or "")[:60]))
    hard = [x for x in issues if x[0] in HARD]
    print(f"p222 check: 五系统市级节点 {len(tree_five)} | 问题 {len(issues)}"
          f"（硬问题 {len(hard)}，软告警 {len(issues) - len(hard)}）")
    by = collections.Counter(x[0] for x in issues)
    for t, n in by.most_common():
        print(f"  {t}: {n}")
    for x in (hard[:20] + [i for i in issues if i[0] not in HARD][:10]):
        print("   ", x)
    return issues, hard


def main():
    tree = json.load(open(TREE_F, encoding="utf-8"))
    reg = json.load(open(REG_F, encoding="utf-8"))
    tree_five, city_names, city_base, dup = collect_tree_five(tree)
    print(f"树五系统市级节点 {len(tree_five)} | 城市 {len(city_names)}"
          + (f" | 同名键 {len(dup)}" if dup else ""))

    if CHECK:
        issues, hard = do_check(reg, tree_five)
        sys.exit(1 if hard else 0)

    stats = collections.Counter()
    conflicts = []
    unresolved = []
    dropped = []

    # ── ① 脏键/别名键归一 ──
    for key in list(reg.keys()):
        target = resolve_key(key, city_names, city_base)
        if not target:
            # 无法解析的多段键：p201 旧新闻标题/「|--XX中院」节点，无有效 URL
            if key.count("|") > 1:
                e = reg[key]
                name = key.split("|")[-1]
                if not (e.get("u") or "").strip() and (
                        name.startswith("--") or ".." in name
                        or any(t in key for t in ("我为群众办实事", "教育整顿",
                                                  "新闻", "原创", "MV"))):
                    dropped.append(key)
                    del reg[key]
                    stats["drop_junk"] += 1
                else:
                    unresolved.append(key)
            continue
        if target == key:
            continue
        src = reg[key]
        info = tree_five.get(target)
        src_u = (src.get("u") or "").strip()
        tree_u = (info["node"].get("u") or "").strip() if info else ""

        tgt = reg.get(target)
        if tgt is None:
            # 树已明确无官网 → 脏键里的 URL 是审计前遗留，不复活
            if info is not None and not tree_u:
                stats["drop_stale"] += 1
                del reg[key]
                continue
            if not src_u and not tree_u:
                stats["drop_empty"] += 1
                del reg[key]
                continue
            e = dict(src)
            e["u"] = tree_u or src_u
            normalize_entry(e, target, info, src)
            e["status"] = "ok" if e.get("u") else "cleared"
            reg[target] = e
            del reg[key]
            stats["rename"] += 1
            continue

        # 目标已存在：合并元数据；树有 URL 时以树为准
        merge_locations(tgt, src)
        keep_meta(tgt, src)
        if info is not None:
            if tree_u and (tgt.get("u") or "").strip() != tree_u:
                if (tgt.get("u") or "").strip():
                    conflicts.append((target, tgt.get("u", ""), tree_u))
                tgt["u"] = tree_u
                tgt["status"] = "ok"
                tgt["source_level"] = tree_level(info)
                tgt["verified_at"] = tree_date(info)
                stats["url_fixed"] += 1
            elif tree_u:
                tgt["status"] = "ok"
                stats["merge"] += 1
            else:
                if (tgt.get("u") or "").strip():
                    stats["tree_empty_keep_registry"] += 1
                stats["merge"] += 1
            tgt["n"] = five_name(info["city"], info["org"])
        else:
            if not (tgt.get("u") or "").strip() and src_u:
                tgt["u"] = src_u
                tgt["status"] = "ok"
                stats["merge_orphan_url"] += 1
            stats["merge"] += 1
        normalize_entry(tgt, target, info, src)
        del reg[key]

    # ── ② 树有 URL、registry 缺 canonical 记录 → 补登 ──
    for key, info in tree_five.items():
        u = (info["node"].get("u") or "").strip()
        if not u:
            continue
        e = reg.get(key)
        if e is None:
            upsert_registry(reg, key, u,
                            name=five_name(info["city"], info["org"]),
                            source_level=tree_level(info),
                            source=info["node"].get("s", ""),
                            verified_at=tree_date(info), locations=["块"])
            stats["add"] += 1
            continue
        if (e.get("u") or "").strip() != u:
            conflicts.append((key, e.get("u", ""), u))
            e["u"] = u
            e["status"] = "ok"
            e["source_level"] = tree_level(info)
            e["verified_at"] = tree_date(info)
            stats["url_fixed"] += 1
        normalize_entry(e, key, info)

    # ── ③ 树已审计无官网的历史 URL → 清空（不删除记录）──
    today = datetime.date.today().isoformat()
    for key, reason in STALE_EMPTY.items():
        info = tree_five.get(key)
        e = reg.get(key)
        if not info or (info["node"].get("u") or "").strip() or not e:
            continue
        if (e.get("u") or "").strip():
            e["u"] = ""
            e["status"] = "cleared"
            e["verified_at"] = today
            e["note"] = reason
            stats["clear_stale"] += 1

    # ── ④ canonical 条目字段补齐 ──
    for key, info in tree_five.items():
        e = reg.get(key)
        if e is not None:
            normalize_entry(e, key, info)

    print(f"迁移统计: {dict(stats)} | 冲突 {len(conflicts)} | 未解析脏键 {len(unresolved)}")
    for c in conflicts[:15]:
        print("  CONFLICT", c[0], "\n    registry:", c[1][:90], "\n    tree    :", c[2][:90])
    for k in unresolved[:15]:
        print("  UNRESOLVED", k, (reg.get(k, {}).get("u") or "")[:80])
    for k in dropped[:15]:
        print("  DROP-JUNK", k)

    if DRY:
        print("（--dry 未落库）")
        return

    os.makedirs(BAK_DIR, exist_ok=True)
    ts = time.strftime("%H%M%S")
    shutil.copy2(TREE_F, os.path.join(BAK_DIR, f"tree_before_p222_{ts}.json"))
    shutil.copy2(REG_F, os.path.join(BAK_DIR, f"registry_before_p222_{ts}.json"))
    atomic(reg, REG_F)
    atomic({"stats": dict(stats), "conflicts": conflicts,
            "unresolved": unresolved, "dropped": dropped},
           os.path.join(DATA, "p222_state.json"))

    # 落库后自检（不再写盘）
    issues, hard = do_check(reg, tree_five)
    print("p222 完成；自检问题:", len(issues), "硬问题:", len(hard))


if __name__ == "__main__":
    main()
