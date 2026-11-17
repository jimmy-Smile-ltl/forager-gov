# -*- coding: utf-8 -*-
"""P193: 重庆法院系统条→块 URL 回填（块树区县「县人民法院」节点）。

条树「法院系统 → 重庆市高级人民法院 → 5 中院 → 基层法院」叶子有 URL
（cqfygzfw.gov.cn 体系 / elink 统一平台），块树各区县「并列机关」下的
「县人民法院」u 全空 → 归一化后回填（空才填，已有不动）。
检察院侧：重庆市检察院 26 个区县院叶子 u 全空，无可回填；省人民检察院
已有 www.cq.jcy.gov.cn/ 不动。
"""
import json, datetime

tree = json.load(open("tree.json", encoding="utf-8"))
blk = next(g for g in tree["ks"] if g["n"].startswith("省级"))
tiao = next(g for g in tree["ks"] if g["n"].startswith("条"))
cq = next(p for p in blk["ks"] if p["n"] == "重庆市")

# 1) 块树区县节点（含功能区两江新区，p78 纪律）→ (区名, 类型) → 并列机关节点
block_idx = {}
districts = []
for g in cq["ks"]:
    if g.get("c") not in ("直辖市辖区", "直辖市辖县", "功能区"):
        continue
    for x in g["ks"]:
        districts.append(x)
        for jg in x.get("ks", []):
            if jg.get("k") != "分组":
                continue
            for o in jg.get("ks", []):
                n = o.get("n", "")
                if n.endswith("人民法院"):
                    block_idx.setdefault((x["n"], "fy"), o)
                elif n.endswith("人民检察院"):
                    block_idx.setdefault((x["n"], "jcy"), o)


def block_aliases(name):
    """自治县节点别名（彭水苗族土家族自治县 → 彭水）。"""
    al = {name}
    for suf in ("土家族苗族自治县", "苗族土家族自治县", "土家族自治县",
                "苗族自治县", "自治县"):
        if name.endswith(suf):
            al.add(name[: -len(suf)])
    return al


def find_area(base):
    """条树叶子名（去后缀）→ 块树区县节点。"""
    for d in districts:
        if base == d["n"]:
            return d
        for a in block_aliases(d["n"]):
            if base == a or base.startswith(a) or a.startswith(base):
                return d
    return None


def leaf_base(n):
    for suf in ("高级人民法院", "人民法院", "人民检察院", "法院", "检察院"):
        if n.endswith(suf):
            return n[: -len(suf)]
    return n


# 2) 条树法院/检察叶子 → 候选 URL 收集（同区多候选优先非 elink 直链）
ELINK = "elink.chinacourt.cn"
cands = {}   # (区名, 类型) → [(is_elink, url)]


def walk(n, sys_ty):
    if n.get("u"):
        base = leaf_base(n.get("n", ""))
        d = find_area(base)
        if d is not None:
            key = (d["n"], sys_ty)
            is_elink = ELINK in n["u"]
            cands.setdefault(key, []).append((is_elink, n["u"], n.get("n", "")))
    for k in n.get("ks", []):
        walk(k, sys_ty)


for g in tiao["ks"]:
    gn = g.get("n", "")
    if gn.startswith("法院"):
        walk(g, "fy")
    elif gn.startswith("检察"):
        walk(g, "jcy")

# 3) 回填块树
filled = 0
for (area, ty), lst in sorted(cands.items()):
    lst.sort(key=lambda t: (t[0],))  # False(直链) 优先
    url, tname = lst[0][1], lst[0][2]
    node = block_idx.get((area, ty))
    if node and not node.get("u"):
        node["u"] = url
        node["s"] = (f"P193 条树回填（来源：条树法院系统 {tname} 节点，"
                     f"{'elink 统一平台' if ELINK in url else 'cqfygzfw.gov.cn 体系'}）")
        filled += 1
    elif node:
        print(f"  {area} {ty}: 已有 {node['u']} 不动")

json.dump(tree, open("tree.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"P193: 回填 {filled} 个块树节点")
