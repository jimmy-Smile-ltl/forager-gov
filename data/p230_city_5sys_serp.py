#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""p230 五系统「市级」缺口 SERP 兜底（2026-11-17，县级 p223 的市级同构版）。

省/市/县三级里，市级五系统仍有 487 个缺口（政协 162 / 监委 127 / 人大 91 /
检察 71 / 法院 35 / 政府门户 1）。上级官网名录（p203）、门户导航（p206）、
同级互链（p208）、SERP（p204）四轮已扫，剩余多为真无官网；本轮用县级
p223 同一套严格校验（域名特征 + title 双验 + 重名市上下文 + 黑名单）再扫
一遍 SERP——p204 当年有 3 个全量 0 命中的 bug（百度跳转链、http_client
并发、隧道代理被拦）已修，值得复扫。

规则：
  - 只填空 u；已有 u 不覆盖；来源留痕 s = SERP线索+title严格验证
  - registry 写「市人大|X市」类标准键（沿用 p226 归一后的键形）
  - state 记 miss，重复轮自动推进

用法：
  cd data && uv run python p230_city_5sys_serp.py --dry
  cd data && uv run python p230_city_5sys_serp.py
  P230_LIMIT=300 P230_WORKERS=6 ...
"""
import datetime
import json
import os
import re
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

DATA = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(DATA)
sys.path.insert(0, DATA)
sys.path.insert(0, os.path.join(ROOT, "util"))
from site_contract import base as _base                 # noqa: E402
from site_contract import upsert_registry               # noqa: E402
from p223_county_5sys_fill import (ORG5, ORG_ORDER, _session,  # noqa: E402
                                   _s4_q, host_ok, prov_base, serp,
                                   valid_candidate)
import p223_county_5sys_fill as P                       # noqa: E402

TREE_F = os.path.join(DATA, "tree.json")
REG_F = os.path.join(DATA, "site_registry.json")
STATE_F = os.path.join(DATA, "p230_state.json")
TODAY = datetime.date.today().isoformat()
DRY = "--dry" in sys.argv
LIMIT = int(os.environ.get("P230_LIMIT", "0")) or None
WORKERS = int(os.environ.get("P230_WORKERS", "6"))

# 块树市级并列机关节点名 → ORG5 键
NODE2ORG = {
    "市人大": "县人大",
    "市政协": "县政协",
    "市监委": "县监委",
    "市中级人民法院": "县人民法院",
    "市人民检察院": "县人民检察院",
}
# registry 类别（p226 归一后的键形）
ORG2CAT = {"县人大": "人大", "县政协": "政协", "县监委": "纪委",
           "县人民法院": "法院", "县人民检察院": "检察"}


def city_org_nodes(city):
    out = {}
    for g in city.get("ks") or []:
        kids = (g.get("ks") or []) if "并列" in (g.get("n") or "") else [g]
        for d in kids:
            nm = (d.get("n") or "").strip()
            if nm in NODE2ORG:
                out[nm] = d
    return out


def main():
    tree = json.load(open(TREE_F, encoding="utf-8"))
    reg = json.load(open(REG_F, encoding="utf-8"))
    st = json.load(open(STATE_F, encoding="utf-8")) if os.path.exists(STATE_F) else {}
    seen = st.setdefault("s4", {})
    blk = next(g for g in tree["ks"] if g["n"].startswith("省级"))
    P.ALL_PROV_BASES.update(prov_base(p.get("n") or "") for p in blk["ks"])

    tasks = []
    for prov in blk["ks"]:
        for city in prov.get("ks") or []:
            if city.get("k") != "人民政府" or city.get("l") not in ("市", "地级区"):
                continue
            for nm, node in city_org_nodes(city).items():
                if (node.get("u") or "").strip():
                    continue
                tasks.append({"prov": prov.get("n"), "parent": prov, "county": city,
                              "org_name": NODE2ORG[nm], "city_node": city,
                              "org": node, "label": nm})
    # 重名市（跨省同名，如吉林市/吉林、海南州/海南）
    name_prov = {}
    for t in tasks:
        name_prov.setdefault(_base(t["county"].get("n") or ""), set()).add(t["prov"])
    dup = {n for n, ps in name_prov.items() if len(ps) > 1}
    city_bases = {}
    for prov in blk["ks"]:
        for city in prov.get("ks") or []:
            if city.get("k") == "人民政府" and city.get("l") in ("市", "地级区"):
                city_bases.setdefault(prov.get("n"), set()).add(_base(city.get("n") or ""))
    for t in tasks:
        cb = _base(t["county"].get("n") or "")
        t["dup"] = cb in dup
        t["siblings"] = sorted(x for x in city_bases.get(t["prov"], ())
                               if x and x != cb)
        # 下辖区县基底——市级机构的 title 若含区县名，说明抓到的是下级机构
        # （实测：常州中院被填成 www.jtfy.gov.cn = 金坛区法院）
        kids = set()
        for c in t["city_node"].get("ks") or []:
            if c.get("k") == "人民政府" and (c.get("n") or "") != (t["city_node"].get("n") or ""):
                kids.add(_base(c.get("n") or ""))
        t["children"] = {k for k in kids if len(k) >= 2}

    pending = [t for t in tasks if seen.get(_s4_q(t)) != "miss"]
    pending.sort(key=lambda t: ORG_ORDER.index(t["org_name"]))
    if LIMIT:
        pending = pending[:LIMIT]
    print(f"p230 市级五系统缺口 {len(tasks)} 条，本轮查 {len(pending)}（{WORKERS} 并发）")

    def probe(t):
        h = serp(_s4_q(t))
        if not h:
            return t, "__serpfail__", ""
        for u in re.findall(r'mu="(https?://[^"]+)"', h):
            dom = urlparse(u).netloc.lower()
            if any(b in dom for b in P.S4_BAD_DOM) or not host_ok(u):
                continue
            if not re.search(ORG5[t["org_name"]]["feat"], dom, re.I):
                continue
            ok, note = valid_candidate(t, u, "")
            if not ok:
                continue
            # 市级机构：title 出现下辖区县名 = 抓到下级机构
            from p223_county_5sys_fill import page_title
            ttl = page_title(u) or ""
            hit_kid = next((k for k in t.get("children") or () if k and k in ttl), None)
            if hit_kid:
                continue
            # 中院：title 出现「XX区/县/旗/开发区人民法院」= 基层法院
            # （实测：常州中院被填成 jkfy.changzhou.gov.cn = 经开区法院）
            if t["org_name"] == "县人民法院" and re.search(
                    r"(区|县|旗|开发区|新区|园区)人民法院|(区|县|旗)法院", ttl):
                continue
            return t, u, note
        return t, None, ""

    filled = 0
    with ThreadPoolExecutor(WORKERS) as ex:
        for t, u, note in ex.map(probe, pending):
            q = _s4_q(t)
            if u == "__serpfail__":
                seen[q] = "serp-fail"
                continue
            got = False
            if u:
                src = f"来源:SERP线索+title严格验证({note})"
                if DRY:
                    print(f"  [DRY] {t['prov']}/{t['city_node'].get('n')}/{t['label']} -> {u[:70]}")
                    got = True
                else:
                    t["org"]["u"] = u
                    t["org"]["s"] = src
                    # 标准键：人大|北京市人大 · 法院|石家庄市中级人民法院 ·
                    # 纪委|松原市监委（p226/p222 归一后的形态）
                    key = f"{ORG2CAT[t['org_name']]}|{t['county'].get('n')}{t['label'][1:]}"
                    upsert_registry(reg, key, u, name=t["county"].get("n"),
                                    source_level="L3", source=src,
                                    verified_at=TODAY, locations=["块"])
                    got = True
            seen[q] = "hit" if got else "miss"
            if got:
                filled += 1
                print(f"  S4 {q} -> {u[:76]}")
    print("p230 filled:", filled)

    if not DRY and filled:
        d = os.path.join(ROOT, "backups", TODAY)
        os.makedirs(d, exist_ok=True)
        ts = datetime.datetime.now().strftime("%H%M%S")
        for f, tag in ((TREE_F, "tree"), (REG_F, "registry"), (STATE_F, "state")):
            if os.path.exists(f):
                shutil.copy2(f, os.path.join(d, f"{tag}_before_p230_{ts}.json"))
        json.dump(tree, open(TREE_F, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        json.dump(reg, open(REG_F, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        json.dump(st, open(STATE_F, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("  已写 tree.json / site_registry.json / p230_state.json")


if __name__ == "__main__":
    main()
