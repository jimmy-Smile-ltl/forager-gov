# -*- coding: utf-8 -*-
"""P252: 群团节点命名规范化（2026-11-19 数据巡检）。

问题一（块视图，544 个节点）：省级群团 17 个槽位一律用泛化名——「省总工会」
「团省委」「省欧美同学会」——挂在「北京市」「上海市」之下，树里读作
「北京市 › 群团组织（17）› 省总工会」，直辖市/自治区尤其不成立（「北京市省总工会」）；
列表模式把节点名单独成行，直接成了「省总工会」。同一机构在条视图里本来就是全名
（「北京市总工会」「北京市妇女联合会」），两个视图对不上。
改为 {省名}{机构全名}（16 槽 × 32 省）+ 团委统一「共青团{省名}委员会」。

问题二（条视图，77 个节点）：
  - 省级团委子节点是「北京市共青团委员会」这种倒装合成名 → 「共青团北京市委员会」
    （官方写法：中国共产主义青年团北京市委员会）；
  - 欧美同学会「省级组织（30）」子节点只有省名（「上海市」「云南」「内蒙古」），
    「副省级城市组织（15）」子节点只有市名（「南京」「厦门市」）→ 补全机构名，
    与块视图「{省名}欧美同学会」同名同键。

连带修复：registry 里 17 个省共用一个键「群团|团省委」（p167.full_name 对不以
省/市/县/区开头的名字不做前缀补全），后 30 省的团委 URL 全部丢失；欧美同学会
省级组织则以裸省名成键（「群团|上海市」）。改名后按新名迁移/合并主键。

干跑加 --dry。
"""
import json
import sys

SLOT_SUFFIX = {
    "省总工会": "总工会",
    "省妇联": "妇女联合会",
    "省科协": "科学技术协会",
    "省文联": "文学艺术界联合会",
    "省作协": "作家协会",
    "省工商联": "工商业联合会",
    "省侨联": "归国华侨联合会",
    "省台联": "台湾同胞联谊会",
    "省残联": "残疾人联合会",
    "省贸促会": "国际贸易促进委员会",
    "省红十字会": "红十字会",
    "省法学会": "法学会",
    "省记协": "新闻工作者协会",
    "省人民对外友好协会": "人民对外友好协会",
    "省计划生育协会": "计划生育协会",
    "省欧美同学会": "欧美同学会",
}
PROV_FULL = {
    "北京市": "北京市", "天津市": "天津市", "河北省": "河北省", "山西省": "山西省",
    "内蒙古": "内蒙古自治区", "内蒙古自治区": "内蒙古自治区", "辽宁省": "辽宁省",
    "吉林省": "吉林省", "黑龙江省": "黑龙江省", "上海市": "上海市", "江苏省": "江苏省",
    "浙江省": "浙江省", "安徽省": "安徽省", "安徽": "安徽省", "福建省": "福建省",
    "福建": "福建省", "江西省": "江西省", "山东省": "山东省", "河南省": "河南省",
    "河南": "河南省", "湖北省": "湖北省", "湖北": "湖北省", "湖南省": "湖南省",
    "广东省": "广东省", "广东": "广东省", "广西": "广西壮族自治区",
    "广西壮族自治区": "广西壮族自治区", "海南省": "海南省", "海南": "海南省",
    "重庆市": "重庆市", "重庆": "重庆市", "四川省": "四川省", "贵州省": "贵州省",
    "云南省": "云南省", "西藏": "西藏自治区", "西藏自治区": "西藏自治区",
    "陕西省": "陕西省", "甘肃省": "甘肃省", "甘肃": "甘肃省", "青海省": "青海省",
    "宁夏": "宁夏回族自治区", "宁夏回族自治区": "宁夏回族自治区",
    "新疆": "新疆维吾尔自治区", "新疆维吾尔自治区": "新疆维吾尔自治区",
    "新疆生产建设兵团": "新疆生产建设兵团", "河北": "河北省", "山西": "山西省",
}
CITY_SUFFIX = "市"


def walk(n):
    yield n
    for k in n.get("ks") or []:
        yield from walk(k)


def rename_block(tree, log):
    """块视图：{省} > 群团组织（17）> 17 个槽位 → 全名。"""
    prov_g = next(g for g in tree["ks"] if g["n"].startswith("省级"))
    for p in prov_g["ks"]:
        pn = p["n"]
        for g in p.get("ks") or []:
            if not (g.get("n") or "").startswith("群团"):
                continue
            for c in g.get("ks") or []:
                old = c.get("n") or ""
                if old == "团省委":
                    new = f"共青团{pn}委员会"
                elif old in SLOT_SUFFIX:
                    new = f"{pn}{SLOT_SUFFIX[old]}"
                else:
                    log.append(("跳过(非槽位)", pn, old))
                    continue
                c["n"] = new
                log.append(("块", pn, f"{old} → {new}"))


def rename_tiao(tree, log):
    """条视图：省级团委倒装名 + 欧美同学会裸地名。返回 [(旧名, 新名)] 供 registry 迁移。"""
    pairs = []
    tiao = next(g for g in tree["ks"] if g["n"].startswith("条"))
    for n in walk(tiao):
        # 1) 省级团委：{省}共青团委员会 → 共青团{省}委员会
        if (n.get("n") or "").startswith("省级团委"):
            for c in n.get("ks") or []:
                old = c.get("n") or ""
                if old.endswith("共青团委员会") and not old.startswith("共青团"):
                    pv = old[: -len("共青团委员会")]
                    new = f"共青团{pv}委员会"
                    c["n"] = new
                    pairs.append((old, new))
                    log.append(("条·团委", pv, f"{old} → {new}"))
        # 2) 欧美同学会：省级组织/副省级城市组织 裸地名
        if "欧美同学会" in (n.get("n") or ""):
            for grp in n.get("ks") or []:
                gn = grp.get("n") or ""
                if gn.startswith("省级组织"):
                    for c in grp.get("ks") or []:
                        old = c.get("n") or ""
                        if "欧美同学会" in old:
                            continue
                        full = PROV_FULL.get(old)
                        if not full:
                            log.append(("跳过(未知省名)", "", old))
                            continue
                        c["n"] = f"{full}欧美同学会"
                        pairs.append((old, c["n"]))
                        log.append(("条·欧美", old, c["n"]))
                elif gn.startswith("副省级城市组织"):
                    for c in grp.get("ks") or []:
                        old = c.get("n") or ""
                        if "欧美同学会" in old:
                            continue
                        city = old if old.endswith(CITY_SUFFIX) else old + CITY_SUFFIX
                        c["n"] = f"{city}欧美同学会"
                        pairs.append((old, c["n"]))
                        log.append(("条·欧美市", old, c["n"]))
    return pairs


def sync_rules(rules, log):
    """extraction_rules：{省}·群团组织（N） 的 depts 名与树同源。"""
    hits = 0
    for key, v in rules.items():
        prov, _, grp = key.partition("·")
        if not grp.startswith("群团组织"):
            continue
        for d in v.get("depts") or []:
            old = d.get("n") or ""
            if old == "团省委":
                d["n"] = f"共青团{prov}委员会"
            elif old in SLOT_SUFFIX:
                d["n"] = f"{prov}{SLOT_SUFFIX[old]}"
            else:
                continue
            hits += 1
    log.append(("rules", "", f"depts 改名 {hits} 条"))


def migrate_registry(reg, tree, pairs, log, conflicts):
    """registry 主键迁移。

    1) 块视图 16 个槽位：改名前后 p167.full_name 算出的键相同（「北京市总工会」），
       只需把 n 字段更新成新名；条目缺失而节点有 URL 时补建。
    2) 团省委：旧实现 31 省共用一个键「群团|团省委」（后 30 省 URL 全丢），
       按各省节点自身 URL 重建，再删掉这个全局键。
    3) 条视图改名（团委倒装名 / 欧美同学会裸地名）：{旧键 → 新键} 迁移合并。
    """
    prov_g = next(g for g in tree["ks"] if g["n"].startswith("省级"))
    moved = built = 0
    for p in prov_g["ks"]:
        for g in p.get("ks") or []:
            if not (g.get("n") or "").startswith("群团"):
                continue
            for c in g.get("ks") or []:
                nm = (c.get("n") or "").strip()
                u = (c.get("u") or "").strip()
                if not nm:
                    continue
                key = f"群团|{nm}"
                e = reg.get(key)
                if e is not None:
                    if e.get("n") != nm:
                        e["n"] = nm
                        moved += 1
                    if u and not (e.get("u") or "").strip():
                        e["u"] = u
                        e["status"] = "ok"
                        e["source_level"] = e.get("source_level") or "L2"
                        built += 1
                    elif u and not _same_site(u, e.get("u")):
                        conflicts.append((key, e.get("u", ""), u))
                elif u:
                    reg[key] = {"u": u, "locations": ["块"], "n": nm,
                                "source_level": "L2", "source": c.get("s", ""),
                                "verified_at": "", "status": "ok"}
                    built += 1
    log.append(("registry", "块槽位", f"n 更新 {moved} / 补建 {built}"))

    # 团省委：全局键 → 各省独立键
    stale = reg.pop("群团|团省委", None)
    if stale:
        log.append(("registry", "群团|团省委",
                    f"删除全局键（原 u={stale.get('u', '')[:40]}，按各省节点重建）"))
    for p in prov_g["ks"]:
        for g in p.get("ks") or []:
            if not (g.get("n") or "").startswith("群团"):
                continue
            for c in g.get("ks") or []:
                nm = (c.get("n") or "").strip()
                u = (c.get("u") or "").strip()
                if nm.startswith("共青团") and nm.endswith("委员会") and u:
                    key = f"群团|{nm}"
                    if key not in reg:
                        reg[key] = {"u": u, "locations": ["块"], "n": nm,
                                    "source_level": "L2", "source": c.get("s", ""),
                                    "verified_at": "", "status": "ok"}

    # 条视图改名
    for old, new in pairs:
        _move(reg, f"群团|{old}", f"群团|{new}", new, log, conflicts)


def _host(u):
    from urllib.parse import urlparse
    h = (urlparse((u or "").strip()).netloc or "").lower()
    return h[4:] if h.startswith("www.") else h


def _same_site(u1, u2):
    """同主机的 http/https、www、尾斜杠、子路径差异不算冲突（同站不同页）。"""
    return _host(u1) == _host(u2)


def _move(reg, old, new, new_name, log, conflicts):
    if old == new or old not in reg:
        return
    src = reg.pop(old)
    tgt = reg.get(new)
    src["n"] = new_name
    if tgt is None:
        reg[new] = src
        log.append(("registry", old, f"→ {new}"))
        return
    for loc in src.get("locations") or []:
        if loc not in (tgt.get("locations") or []):
            tgt.setdefault("locations", []).append(loc)
    for f in ("source_level", "source", "verified_at", "xxgk", "xxgk_src",
              "snapshot", "status"):
        if not tgt.get(f) and src.get(f):
            tgt[f] = src[f]
    su, tu = (src.get("u") or "").strip(), (tgt.get("u") or "").strip()
    if su and tu and su.rstrip("/") != tu.rstrip("/"):
        conflicts.append((new, tu, su))
    if su and not tu:
        tgt["u"] = su
        tgt["status"] = "ok"
        tgt["source_level"] = src.get("source_level", tgt.get("source_level", ""))
        tgt["verified_at"] = src.get("verified_at", tgt.get("verified_at", ""))
    tgt["n"] = new_name
    log.append(("registry", old, f"合并入 {new}"))


def main(dry=False):
    log, conflicts = [], []
    tree = json.load(open("tree.json", encoding="utf-8"))
    reg = json.load(open("site_registry.json", encoding="utf-8"))
    rules = json.load(open("extraction_rules.json", encoding="utf-8"))

    rename_block(tree, log)
    pairs = rename_tiao(tree, log)
    sync_rules(rules, log)
    migrate_registry(reg, tree, pairs, log, conflicts)

    kinds = {}
    for kind, a, b in log:
        kinds[kind] = kinds.get(kind, 0) + 1
    print("p252 改名统计:", kinds)
    for kind in ("块", "条·团委", "条·欧美", "条·欧美市"):
        sample = [x for x in log if x[0] == kind][:4]
        print(" ", kind, "样例:", sample)
    skipped = [x for x in log if x[0].startswith("跳过")]
    if skipped:
        print("  跳过:", skipped[:12], f"（共 {len(skipped)}）")
    if conflicts:
        print(f"  ⚠ registry URL 冲突 {len(conflicts)} 条（保留已有键，见下）:")
        for c in conflicts[:12]:
            print("   ", c)
    if dry:
        print("--dry 干跑，未写盘")
        return
    with open("tree.json", "w", encoding="utf-8") as f:
        json.dump(tree, f, ensure_ascii=False, indent=1)
        f.write("\n")
    with open("site_registry.json", "w", encoding="utf-8") as f:
        json.dump(reg, f, ensure_ascii=False, indent=1)
        f.write("\n")
    with open("extraction_rules.json", "w", encoding="utf-8") as f:
        json.dump(rules, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print("已写 tree.json / site_registry.json / extraction_rules.json")


if __name__ == "__main__":
    main(dry="--dry" in sys.argv)
