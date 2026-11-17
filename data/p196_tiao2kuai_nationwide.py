# -*- coding: utf-8 -*-
"""P196: 全国法院/检察院/人大/政协/监委 条→块 URL 同步。

背景（2026-11-12 用户报地图异常）: 普洱市县级地图全单色——块树各县
「并列机关」的 县人民法院/县人民检察院 u 全空（全国填充率 54%/42%）,
综合覆盖聚合值全县相同 → 分位数单色。楚雄州有部分县填充 → 彩色。
根因 = 条→块同步只做过重庆(p193), 未全国推广; 条树法院系统 2301 基层
叶子全有 URL(elink 统一平台), 检察院 600+。

流程: 条树各系统叶子 (省高院子树内) → 基底名归一(行政区/民族后缀) →
块树区县「县人民法院/县人民检察院/县人大/县政协/县监委」空节点回填
（空才填, 已有不动——p78 纪律; 同省内基底名撞车(桥西×3)歧义不填）。
写 tree.json + registry。幂等可重复跑。
"""
import json, os, re

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(BASE)

ETH_PY = re.compile(
    r"(哈萨克族?|维吾尔族?|柯尔克孜族?|蒙古族?|藏族?|回族|壮族|苗族|黎族"
    r"|侗族|满族|白族|傣族|彝族|哈尼族?|拉祜族?|傈僳族?|佤族?|水族"
    r"|羌族|布依族?|仡佬族?|仫佬族?|毛南族?|瑶族?|畲族|土家族?|土族"
    r"|锡伯族?|达斡尔族?|鄂温克族?|鄂伦春族?|赫哲族?|俄罗斯族?|塔塔尔族?|乌孜别克族?"
    r"|塔吉克族?|撒拉族?|保安族?|裕固族?|东乡族?|纳西族?|景颇族?|阿昌族?"
    r"|普米族?|怒族|德昂族?|独龙族?|基诺族?|门巴族?|珞巴族?|京族"
    r"|朝鲜族?|各族|自治)$")
SUF = re.compile(
    r"(自治州|自治县|自治旗|地区|盟|市|县|区|旗|行政委员会|行委|管委会|管理委员会|管理区"
    r"|高新技术产业开发区|经济技术开发区|经济开发区|开发区|新区|工业园区|园区|示范区"
    r"|高级人民法院|人民法院|法院|人民检察院|检察院|人大|政协|监察委员会|监委)$")


def base(nm):
    t = nm or ""
    for _ in range(10):
        t0 = t
        t = SUF.sub("", t)
        if not t:
            return re.sub(r"族$", "", t0) or t0
        pre = t
        t = ETH_PY.sub("", t)
        if not t:
            return re.sub(r"族$", "", pre) or pre
        if t == t0:
            break
    return t


def walk(n, path):
    yield n, path
    for k in n.get("ks", []) or []:
        yield from walk(k, path + [n])


tree = json.load(open("data/tree.json", encoding="utf-8"))
reg = json.load(open("data/site_registry.json", encoding="utf-8"))
blk = next(g for g in tree["ks"] if g["n"].startswith("省级"))
gat = next(g for g in tree["ks"] if g["n"].startswith("港澳台"))
tiao = next(g for g in tree["ks"] if g["n"].startswith("条"))

CT = {"县级人民政府", "市辖区（地级行政区划）", "直辖市辖县（县级行政区划）",
      "省直辖县级市/县/林区", "兵团直辖县级市（自治区直辖县级市）",
      "直辖市辖区", "直辖市辖县", "功能区", "县级单位"}

# ── 1. 条树索引: (省名, 基底名/父+基底名) → URL ──
ORG_MAP = {  # 块树并列机关节点名 → 条树系统名 与 机构后缀
    "县人民法院": ("法院系统", ("人民法院", "法院")),
    "县人民检察院": ("检察院系统", ("人民检察院", "检察院")),
    "县人大": ("人大系统", ("人大常委会", "人大")),
    "县政协": ("政协系统", ("政协",)),
    "县监委": ("纪委系统", ("监察委员会", "监委")),
}

tiao_sys = {}
for s in tiao.get("ks", []):
    tiao_sys[s.get("n", "")[:4]] = s


def build_index(system, suf):
    """(prov_name, base_key) → {url}（省内 base 撞车 → 跳过该 base）"""
    idx = {}
    sys_node = next((s for s in tiao.get("ks", []) if system in s.get("n", "")), None)
    if not sys_node:
        return idx
    # 省级持有者 = 子级数最多的分组（高级人民法院（32）/省级检察院（31）…）
    prov_holder = max(sys_node.get("ks", []) or [],
                      key=lambda c: len(c.get("ks", []) or []), default=None)
    for prov in (prov_holder.get("ks", []) if prov_holder else []) or []:
        pn = base(prov.get("n", ""))   # 云南省高级人民法院 → 云南省（与块树省名对齐）
        for mid in prov.get("ks", []) or []:
            mid_base = base(mid.get("n", ""))
            # 直辖市扁平形态: 省检直接挂区县院叶子（东城区人民检察院 无子级有 u）
            leaves = mid.get("ks", []) or []
            if not leaves and mid.get("u"):
                leaves = [mid]
            for leaf in leaves:
                ln = leaf.get("n", "")
                u = leaf.get("u")
                if not u:
                    continue
                lb = base(ln)
                keys = {lb}
                # 张家口桥西法院 → 桥西（剥中院前缀）; 三河市法院 → 三河
                if mid_base and lb.startswith(mid_base) and len(lb) > len(mid_base) + 1:
                    keys.add(lb[len(mid_base):])
                for k in keys:
                    if k:
                        idx.setdefault((pn, k), set()).add(u)
    return idx


# ── 2. 块树区县 → 并列机关节点 ──
block_org = {}   # (prov, county_name) -> {org_name: node}
for prov in blk.get("ks", []):
    pn = prov.get("n", "")
    for n, path in walk(prov, [prov]):
        if n.get("k") != "人民政府":
            continue
        if n.get("c") not in CT:
            continue
        for grp in n.get("ks", []) or []:
            if grp.get("k") != "分组":
                continue
            for o in grp.get("ks", []) or []:
                for org_name in ORG_MAP:
                    if o.get("n", "") == org_name:
                        block_org.setdefault((pn, n["n"]), {})[org_name] = o
                        break

filled = 0
skipped_amb = 0
for system, org_name, suf in [("法院系统", "县人民法院", ("人民法院", "法院")),
                              ("检察院系统", "县人民检察院", ("人民检察院", "检察院")),
                              ("人大系统", "县人大", ("人大常委会", "人大")),
                              ("政协系统", "县政协", ("政协",)),
                              ("纪委系统", "县监委", ("监察委员会", "监委"))]:
    idx = build_index(system, suf)
    for (pn, cname), orgs in block_org.items():
        node = orgs.get(org_name)
        if not node or node.get("u"):
            continue
        cb = base(cname)
        pbase = base(pn)
        cand = set()
        for k in (cb,):
            cand |= idx.get((pbase, k), set())
        if not cand and cb:
            # 兜底模糊: 全省范围内叶子基底以县基底结尾（长度差 ≤4, 同省异市
            # 重名兜底）——仅当全省该 base 唯一才采用
            allm = {k: v for (p, k), v in idx.items()
                    if p == pbase and (k == cb or (len(k) > 2 and k.endswith(cb) and len(k) <= len(cb) + 4))}
            cand = set().union(*allm.values()) if allm else set()
        if not cand:
            continue
        if len(cand) > 1:
            skipped_amb += 1
            continue
        u = cand.pop()
        node["u"] = u
        node["s"] = f"来源：{system}条系统同源回填（p196）"
        key = f"县级{org_name[1:]}|{cname}"
        if key in reg and reg[key].get("u"):
            pass
        else:
            reg[key] = {"u": u, "n": cname, "locations": ["块"],
                        "source_level": "L1", "verified_at": "2026-11-12",
                        "status": "ok", "snapshot": "", "xxgk": "", "xxgk_src": ""}
        filled += 1

json.dump(tree, open("data/tree.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
json.dump(reg, open("data/site_registry.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0)
print(f"P196 条→块同步: 回填 {filled} 个并列机关 URL, 歧义跳过 {skipped_amb}")
