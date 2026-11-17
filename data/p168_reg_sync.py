# -*- coding: utf-8 -*-
"""P168: 注册表同步——registry → tree 回填（块/条两边同源）。

约定（架构铁律）：一个机构一个采集结果。新采集脚本先写 registry
再同步 tree；registry 里已有 URL 的机构不重复采集（查 registry 即知）。
"""
import json
import re
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import load_registry

tree = json.load(open("tree.json", encoding="utf-8"))
reg = load_registry()

# 反向索引：全名 → URL（取 registry 主值）
def cat_of(n):
    c = n.get("c", "")
    k = n.get("k", "")
    if "人大" in c or "人大" in k:
        return "人大"
    if "政协" in c or "政协" in k:
        return "政协"
    if "法院" in c or "法院" in k:
        return "法院"
    if "检察" in c or "检察" in k:
        return "检察"
    if "纪委" in c or "监委" in c or "纪检" in c:
        return "纪委"
    if n.get("k") == "人民政府":
        return "政府"
    if "群团" in c:
        return "群团"
    if n.get("k") == "分组":
        return None
    for sysn in ("工会", "海关", "税务", "邮政", "烟草", "人民银行", "铁路",
                 "金融监管", "证监会", "移民", "自然资源督察", "药监",
                 "气象", "地震", "财经", "外交", "垂直管理"):
        if sysn in (c + k):
            return sysn
    return c or "其他"

filled = 0
def walk(n, path, view):
    global filled
    if not n.get("ks") and not n.get("u"):
        cat = cat_of(n)
        nm = n["n"]
        if cat and view == "块" and re.match(r"^(市|县|省|区)", nm):
            for p in reversed(path):
                if p.get("k") == "人民政府":
                    nm = p["n"] + re.sub(r"^(市|省|县|区)", "", nm)
                    break
        if cat:
            key = f"{cat}|{nm}"
            if key in reg:
                n["u"] = reg[key]["u"]
                filled += 1
    for k in n.get("ks", []):
        walk(k, path + [n], view)

walk(tree, [], "块")
tiao = next(g for g in tree["ks"] if g["n"].startswith("条"))
for g in tiao["ks"]:
    walk(g, [], "条")

json.dump(tree, open("tree.json", "w", encoding="utf-8"),
          ensure_ascii=False, separators=(",", ":"))
print(f"p168 同步: {filled} 个空节点从注册表回填")
