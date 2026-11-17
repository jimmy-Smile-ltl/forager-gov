#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""p224 条树 → 块树 五系统县级 URL 同步（2026-11-17）。

背景：五系统县级缺失严重（人大 98%、政协 98.5%、监委 93.7%），而条树里
已有大量真实采集的基层机构 URL（法院系统 3083 条、检察院、人大、政协、
纪委）。这些 URL 全部来自官方渠道（省院/省人大官网名录、elink 统一平台、
省纪委 subsite 等），属 L1 权威来源，应优先回填块树县级并列机关节点。

p196 的匹配 bug：`base("云南省高级人民法院")` → "云南省高级"（base 只剥
「人民法院/法院」不剥「高级」），省级 key 全部对不上块树省名，只回填了
27 条。本脚本用 `org_base()`（多轮剥 高级/中级/人民 后缀）重建索引。

匹配规则（块树县级节点 ← 条树叶子）：
  (省基底, 县区基底) 唯一命中 → 填；
  多候选时用市基底（中院/市院名）消歧，仍歧义则跳过（不猜）。
只填空节点（p78 纪律），已有 URL 不动。

用法：
  cd data && uv run python p224_tiao2kuai_5sys.py          # 写库
  cd data && uv run python p224_tiao2kuai_5sys.py --dry    # 只看统计
"""
import datetime
import json
import os
import re
import shutil
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BASE_DIR)
sys.path.insert(0, BASE_DIR)
from site_contract import base as _base, upsert_registry
from p223_county_5sys_fill import COUNTY_C, ORG5, unwrap  # 复用县区判定与 URL 解码

TREE_F = os.path.join(BASE_DIR, "tree.json")
REG_F = os.path.join(BASE_DIR, "site_registry.json")
TODAY = datetime.date.today().isoformat()
DRY = "--dry" in sys.argv

SYS2ORG = {
    "法院系统": "县人民法院",
    "检察院系统": "县人民检察院",
    "人大系统": "县人大",
    "政协系统": "县政协",
    "纪委系统": "县监委",
}
ORG2CAT = {k: v["cat"] for k, v in ORG5.items()}


def org_base(nm):
    """机构名 → 地名基底（云南省高级人民法院→云南、北京一中院→北京?）。

    注意：「北京一中院」这类含序号的中院名保留序号（北京一中），匹配市名时
    走前缀包含兜底。
    """
    x = _base(nm or "")
    for _ in range(4):
        x0 = x
        for suf in ("高级人民", "高级", "中级人民", "中级", "人民", "省", "市"):
            if x.endswith(suf) and len(x) > len(suf):
                x = x[:-len(suf)]
                break
        if x == x0:
            break
    return x


def geo_eq(a, b):
    return bool(a) and bool(b) and a == b


def nu(u):
    """URL 归一（尾斜杠/大小写主机）——同一站的多条条树记录须折叠成一条。"""
    u = (u or "").strip().rstrip("/")
    m = re.match(r"(https?://[^/]+)(/.*)?$", u, re.I)
    return (m.group(1).lower() + (m.group(2) or "")) if m else u


def walk(n, path):
    yield n, path
    for c in n.get("ks") or []:
        yield from walk(c, path + [n])


def main():
    tree = json.load(open(TREE_F, encoding="utf-8"))
    reg = json.load(open(REG_F, encoding="utf-8"))
    blk = next(g for g in tree["ks"] if g["n"].startswith("省级"))
    tiao = next(g for g in tree["ks"] if g["n"].startswith("条"))

    prov_names = {p["n"]: p for p in blk["ks"]}
    prov_bases = {org_base(n): n for n in prov_names}

    # ── 1. 块树县级五系统节点 ──
    targets = {}   # (prov, city, county) -> {org_name: node}
    for p in blk["ks"]:
        prov = p["n"]

        def scan(n, city):
            if n.get("k") == "人民政府" and n.get("c") in COUNTY_C:
                grp = next((g for g in n.get("ks") or [] if g.get("c") == "并列机关"), None)
                if grp:
                    for o in grp.get("ks") or []:
                        if o.get("n") in SYS2ORG.values():
                            targets.setdefault((prov, city, n["n"]), {})[o["n"]] = o
            nc = n["n"] if (n.get("k") == "人民政府" and n.get("l") in ("市", "地级区")) else city
            for c in n.get("ks") or []:
                scan(c, nc)

        for c in p.get("ks") or []:
            scan(c, prov)

    # ── 2. 条树叶子索引 (prov_base, leaf_base) -> [(mid_base, url, leaf_name)] ──
    index = {}
    for sys_name, org_name in SYS2ORG.items():
        node = next((s for s in tiao["ks"] if s["n"].startswith(sys_name)), None)
        if not node:
            continue
        for leaf, path in walk(node, [node]):
            if leaf.get("ks"):
                continue
            u = unwrap((leaf.get("u") or "").strip())
            if not u.startswith("http"):
                continue
            # 定位省级祖先（第一个基底能对上块树省名的祖先）
            prov_b = None
            mid_b = None
            for a in path[1:]:
                ab = org_base(a["n"])
                if ab in prov_bases:
                    prov_b = ab
                elif prov_b is not None:
                    mid_b = ab
            if not prov_b:
                continue
            leaf_b = org_base(leaf["n"])
            if not leaf_b or len(leaf_b) < 2:
                continue
            # 按系统分桶：每个系统只回填自己的块树节点（防法院 URL 填到人大）
            index.setdefault((org_name, prov_b, leaf_b), []).append(
                (mid_b, u, leaf["n"], sys_name))

    # 省内同基底县区计数（新华区×2、鼓楼区×2…）——多义时必须市名消歧
    base_count = {}
    for (prov, city, county) in targets:
        k = (org_base(prov), org_base(county))
        base_count.setdefault(k, set()).add(city)

    # ── 3. 匹配回填 ──
    filled = skipped_amb = no_cand = 0
    per_sys = {}
    for (prov, city, county), orgs in targets.items():
        pb = org_base(prov)
        cb = org_base(city)
        cb2 = re.sub(r"(省|市)$", "", _base(city or ""))
        for org_name, nd in orgs.items():
            if (nd.get("u") or "").strip():
                continue
            kb = org_base(county)
            cands = index.get((org_name, pb, kb)) or []
            if not cands:
                no_cand += 1
                continue
            urls = {nu(c[1]) for c in cands}
            ambiguous_county = len(base_count.get((pb, kb), ())) > 1
            chosen = None
            if len(urls) == 1 and not ambiguous_county:
                chosen = cands[0]
            else:
                # 市基底消歧：中院/市院名的基底与块树市名互含
                hit = [c for c in cands if c[0] and (
                    c[0] == cb or c[0].startswith(cb) or cb.startswith(c[0])
                    or (cb2 and (c[0] == cb2 or c[0].startswith(cb2)) or c[0] == cb2))]
                hit_urls = {nu(c[1]) for c in hit}
                if len(hit_urls) == 1:
                    chosen = hit[0]
            if chosen and cb and geo_eq(org_base(chosen[2]), cb) and \
                    geo_eq(kb, cb) and county != city:
                chosen = None   # 叶子=市机构却要填县（承德市人民法院↔承德县）
            if not chosen:
                skipped_amb += 1
                continue
            _, u, leaf_name, sys_name = chosen
            if not DRY:
                nd["u"] = u
                nd["s"] = f"来源:{sys_name}条树同源回填（p224, 叶节点「{leaf_name}」）"
                key = f"县级{org_name[1:]}|{county}"
                upsert_registry(reg, key, u, name=county, source_level="L1",
                                source=nd["s"], verified_at=TODAY, locations=["块", "条"])
            if DRY and filled < 40:
                print(f"  [DRY] {prov}/{city}/{county} {org_name} <- {leaf_name} {u[:64]}")
            filled += 1
            per_sys[org_name] = per_sys.get(org_name, 0) + 1

    print(f"p224 条→块县级同步: 回填 {filled}, 歧义跳过 {skipped_amb}, 无候选 {no_cand}"
          f"{'（DRY 未写库）' if DRY else ''}")
    for k, v in sorted(per_sys.items(), key=lambda x: -x[1]):
        print(f"  {k}: +{v}")

    if not DRY and filled:
        today_dir = os.path.join(ROOT, "backups", TODAY)
        os.makedirs(today_dir, exist_ok=True)
        ts = datetime.datetime.now().strftime("%H%M%S")
        shutil.copy2(TREE_F, os.path.join(today_dir, f"tree_before_p224_{ts}.json"))
        shutil.copy2(REG_F, os.path.join(today_dir, f"registry_before_p224_{ts}.json"))
        json.dump(tree, open(TREE_F, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        json.dump(reg, open(REG_F, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("  已写 tree.json / site_registry.json")


if __name__ == "__main__":
    main()
