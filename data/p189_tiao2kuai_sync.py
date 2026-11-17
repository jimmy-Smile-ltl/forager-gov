# -*- coding: utf-8 -*-
"""P189: 条板块法检人大政协纪委 5 系统的 URL 回填块树并列机关节点。
块树县级节点（p157 建设）未继承条系统的 elink 法院/检察院等 URL——
地图（块视图）法院全灰的根因。"""
import json, re

tree = json.load(open("tree.json", encoding="utf-8"))
blk = next(g for g in tree["ks"] if g["n"].startswith("省级"))
tiao = next(g for g in tree["ks"] if g["n"].startswith("条"))

# 1) 块树索引: 区划名 → 层级 → 类型节点
#    层级: 1=省(直接子) 2=市 3=县
block_idx = {}   # (区划名, 类型) → 节点
TYPE_NODE = {"fy": ("高级人民法院", "人民法院"), "jcy": ("人民检察院", "人民检察院"),
             "rd": ("人大", "人大"), "zx": ("政协", "政协"), "jw": ("监委", "监委")}
for p in blk["ks"]:
    def reg(area_name, node_name, node):
        if not node_name:
            return
        for ty, (prov_suf, sub_suf) in TYPE_NODE.items():
            if node_name.endswith(sub_suf) or node_name.endswith(prov_suf):
                block_idx[(area_name, ty)] = node
                break
    # 省并列机关
    for jg in p.get("ks", []):
        if jg.get("k") != "分组":
            continue
        for o in jg.get("ks", []):
            reg(p["n"], o.get("n", ""), o)
    for c in p.get("ks", []):
        if c.get("c") not in ("地级市人民政府", "市辖区（地级行政区划）"):
            continue
        for jg in c.get("ks", []):
            if jg.get("k") != "分组":
                continue
            for o in jg.get("ks", []):
                reg(c["n"], o.get("n", ""), o)
        for x in c.get("ks", []):
            if x.get("c") != "县级人民政府":
                continue
            for jg in x.get("ks", []):
                if jg.get("k") != "分组":
                    continue
                for o in jg.get("ks", []):
                    reg(x["n"], o.get("n", ""), o)

# 2) 条树 5 系统叶子 → 区划名+类型 → 回填
STRIP = re.compile(r"(高级)?人民法院$|人民检察院$|人大$|政协$|监察委员会$|监委$")
filled = 0
for g in tiao["ks"]:
    gn = g.get("n", "")
    sys_ty = None
    for ty in ("fy", "jcy", "rd", "zx", "jw"):
        if gn.startswith({"fy":"法院","jcy":"检察","rd":"人大","zx":"政协","jw":"纪委"}[ty]):
            sys_ty = ty
            break
    if not sys_ty:
        continue
    def walk(n):
        global filled
        if not n.get("ks") and n.get("u"):
            nn = n.get("n", "")
            area = STRIP.sub("", nn)
            key = (area, sys_ty)
            node = block_idx.get(key)
            if node and not node.get("u"):
                node["u"] = n["u"]
                node["s"] = "P189 条系统 URL 回填（法院elink/检察院等统一平台）"
                filled += 1
        for k in n.get("ks", []):
            walk(k)
    walk(g)

json.dump(tree, open("tree.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"P189: 回填 {filled} 个块树节点 URL")
