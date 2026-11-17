# -*- coding: utf-8 -*-
"""P175i: 清除非政府系统的 x 字段（用户口径：人大/政协/法院/检察院/
纪委/群团/民主党派不是政府，无政府信息公开专栏，x 不适用）。"""
import json

tree = json.load(open("tree.json", encoding="utf-8"))
reg = json.load(open("site_registry.json", encoding="utf-8"))
tiao = next(g for g in tree["ks"] if g["n"].startswith("条"))
NONGOV = ("人大", "政协", "法院", "检察", "纪委", "群团", "民主党派")

cleared_u = set()
cnt = 0
for g in tiao["ks"]:
    if not any(s in g["n"] for s in NONGOV):
        continue
    def w(x):
        global cnt
        if x.get("x"):
            cleared_u.add(x.get("u"))
            x["x"] = ""
            if x.get("s") and "p17" in x.get("s", ""):
                x["s"] = ""  # 本轮加的来源标记一并清
            cnt += 1
        for k in x.get("ks", []): w(k)
    w(g)

# registry 同步清除 xxgk
rcnt = 0
for k, v in reg.items():
    if v.get("u") in cleared_u and v.get("xxgk"):
        v.pop("xxgk", None); v.pop("xxgk_src", None)
        rcnt += 1

json.dump(tree, open("tree.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
json.dump(reg, open("site_registry.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"p175i: 清除树 x {cnt} 个, registry xxgk {rcnt} 条")
