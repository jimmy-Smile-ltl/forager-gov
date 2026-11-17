# -*- coding: utf-8 -*-
"""补采写库契约（开源后统一数据框架，2026-11-17）。

背景：开源后的数据体系以 `site_registry.json` 为主数据，键的统一形态是
`<类别>|<全名>`；`tree.json` 只保存展示字段（u/s/m/ks），健康状态与校验
日期由 registry 承载。此前 p203/p204/p207/p208 等补采脚本各自拼键
（如 `法院|市人大|石家庄市`、`人大|北京市`），造成同一机构多条记录、
块/条/registry 不一致。新补采一律走本模块。

用法：
    from site_contract import five_key, upsert_registry, base
    key = five_key(city_name, node_name)      # 例：纪委|石家庄市监委
    node["u"] = url
    node["s"] = "来源:..."
    upsert_registry(reg, key, url, name=five_name(city_name, node_name),
                    source_level="L2", source=node["s"], locations=["块"])
"""
import datetime
import re

# 块树「并列机关」市级节点 → (registry 类别, 全名后缀)
FIVE_ORGS = {
    "市人大": ("人大", "人大"),
    "市政协": ("政协", "政协"),
    "市中级人民法院": ("法院", "中级人民法院"),
    "市人民检察院": ("检察", "人民检察院"),
    "市监委": ("纪委", "监委"),
}

# 行政区/机构后缀（从长到短，避免「自治州」被先剥成「自治」）
_ADMIN_SUF = re.compile(
    r"(人民代表大会常务委员会|人民代表大会|人大常委会|人大|政协委员会|政协"
    r"|中级人民法院|人民法院|法院|中院|人民检察院|检察院|监察委员会|纪委监委|监委|纪委"
    r"|自治州|自治县|自治旗|地区|盟|市|县|区|旗)$")
_ETH = re.compile(
    r"(哈萨克族?|维吾尔族?|柯尔克孜族?|朝鲜族?|蒙古族?|藏族?|回族?|壮族?|苗族?"
    r"|黎族?|侗族?|满族?|白族?|傣族?|彝族?|哈尼族?|拉祜族?|傈僳族?|佤族?|水族?"
    r"|羌族?|布依族?|仡佬族?|仫佬族?|毛南族?|瑶族?|畲族?|土家族?|锡伯族?"
    r"|达斡尔族?|鄂温克族?|鄂伦春族?|赫哲族?|俄罗斯族?|塔塔尔族?|乌孜别克族?"
    r"|塔吉克族?|撒拉族?|保安族?|裕固族?|东乡族?|纳西族?|景颇族?|阿昌族?"
    r"|普米族?|怒族?|德昂族?|独龙族?|基诺族?|门巴族?|珞巴族?|京族?|自治)$")
_RANK = {"L1": 3, "L2": 2, "L3": 1}


def base(name):
    """地名/机构名 → 基底名（去行政区后缀与民族修饰，供匹配与校验）。

    必须幂等且逐层剥净（2026-11-17 修复）：旧实现遇到民族修饰无变化就
    break，导致「长安区法院」只剥到「长安区」（不再剥「区」），与块树
    「长安区」→「长安」对不上——p196 条→块同步只回填 27 条的根因。
    """
    x = re.sub(r"[（(][^（）)]*[）)]$", "", name or "")
    for _ in range(10):
        x0 = x
        x = _ADMIN_SUF.sub("", x)
        if not x:
            return x0
        if len(x) >= 3 and x.endswith("州"):
            x = x[:-1]   # 凉山州→凉山；两字城市名（沧州/福州/苏州）不剥防误伤
        x2 = _ETH.sub("", x)
        if len(x2) >= 2:
            x = x2
        elif x2 == "" and x.endswith("族") and len(x) > 2:
            x = x[:-1]   # 纯民族名县（东乡族自治县→东乡、鄂温克族自治旗→鄂温克）
        if x == x0:
            break
    return x


def five_name(city, org):
    """块树市级节点 → registry 全名（城市名 + 机构后缀）。"""
    if org not in FIVE_ORGS:
        raise KeyError(f"not a five-system city org: {org}")
    return f"{city}{FIVE_ORGS[org][1]}"


def five_key(city, org):
    """块树市级节点 → registry 键 `<类别>|<全名>`。"""
    cat, suf = FIVE_ORGS[org]
    return f"{cat}|{city}{suf}"


def parse_five(full_name):
    """`石家庄市人大` → (`石家庄市`, `市人大`)；非五系统/非城市名返回 None。"""
    for org, (_, suf) in FIVE_ORGS.items():
        if full_name and full_name.endswith(suf):
            city = full_name[:-len(suf)]
            if len(city) >= 2:
                return city, org
    return None


def source_level(source, default="L2"):
    """按来源留痕推断等级：L1 上级官网名录 / L2 同级门户·互链 / L3 SERP。"""
    s = source or ""
    if "SERP" in s or "搜索" in s:
        return "L3"
    if "门户" in s or "互链" in s or "友情链接" in s:
        return "L2"
    if any(k in s for k in ("官网", "名录", "省院", "高院", "P183", "P184", "REG|")):
        return "L1"
    return default


def _merge_locations(e, locations):
    locs = list(e.get("locations") or [])
    for loc in locations or ():
        if loc and loc not in locs:
            locs.append(loc)
    e["locations"] = locs


def upsert_registry(reg, key, u, *, name=None, source_level=None,
                    source="", verified_at=None, status=None,
                    locations=("块",), **extra):
    """写入/合并一条 registry（幂等、保留更高来源等级与既有元数据）。

    - 键必须是 `<类别>|<全名>`；调用方用 five_key() 生成，不手拼。
    - 同一机构重复命中时合并 locations，保留 xxgk/snapshot 等字段。
    - source_level 只升不降（L1 > L2 > L3），避免补采把权威记录降级。
    - 传 u=非空 表示一次已验证的落库，默认 status=ok、verified_at=今天。
    """
    e = dict(reg.get(key) or {})
    new_u = (u or "").strip()
    if new_u:
        e["u"] = new_u
        e["status"] = status or "ok"
    else:
        e.setdefault("u", "")
        e["status"] = status or e.get("status") or "cleared"
    if name:
        e["n"] = name
    else:
        e.setdefault("n", key.split("|", 1)[-1])
    _merge_locations(e, locations)

    lv = source_level or e.get("source_level") or source_level(source)
    if _RANK.get(lv, 0) >= _RANK.get(e.get("source_level", ""), 0):
        e["source_level"] = lv
    if verified_at or new_u:
        e["verified_at"] = verified_at or datetime.date.today().isoformat()
    e.setdefault("verified_at", "")
    e.setdefault("status", "ok" if e.get("u") else "cleared")
    e.setdefault("snapshot", "")
    for k, v in extra.items():
        if v not in (None, "") or k not in e:
            e[k] = v
    reg[key] = e
    return e
