# -*- coding: utf-8 -*-
"""P167: 建统一网站注册表 site_registry.json + 条块差异审计。

核心：一个机构一个采集结果，块树/条模块共同引用。
key = <类别>|<全名>（类别：人大/政协/法院/检察院/监委/政府/群团/系统名）
来源留痕：树路径（块/条）+ URL。
"""
import json
import re

tree = json.load(open("tree.json", encoding="utf-8"))
rules = json.load(open("extraction_rules.json", encoding="utf-8"))

registry = {}   # key -> {u, locations: [块/条路径], sources}
conflicts = []  # 同 key 不同 URL

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
    # 条系统名
    for sysn in ("工会", "海关", "税务", "邮政", "烟草", "人民银行", "铁路",
                 "金融监管", "证监会", "移民", "自然资源督察", "药监",
                 "气象", "地震", "财经", "外交", "垂直管理"):
        if sysn in (c + k):
            return sysn
    return c or "其他"

def full_name(n, path, view):
    """块树节点名归一化：无地名前缀的（县人大/市公安局）拼祖先地名。"""
    nm = n["n"]
    if view == "块" and re.match(r"^(市|县|省|区)", nm):
        for p in reversed(path):
            if p.get("k") == "人民政府":
                base = p["n"]
                suffix = re.sub(r"^(市|省|县|区)", "", nm)
                return f"{base}{suffix}"
    return nm

# 遍历（块树 + 条模块全树）
def walk(n, path, view):
    if not n.get("ks") and n.get("u"):
        cat = cat_of(n)
        if cat:
            key = f"{cat}|{full_name(n, path, view)}"
            if key in registry:
                if registry[key]["u"] != n["u"]:
                    conflicts.append((key, registry[key]["u"], n["u"],
                                      registry[key]["locations"], view))
            else:
                registry[key] = {"u": n["u"], "locations": [view],
                                 "n": n["n"]}
            if view not in registry[key]["locations"]:
                registry[key]["locations"].append(view)
    for k in n.get("ks", []):
        walk(k, path + [n], view)

walk(tree, [], "块")
tiao = next(g for g in tree["ks"] if g["n"].startswith("条"))
for g in tiao["ks"]:
    walk(g, [], "条")

json.dump(registry, open("site_registry.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=0)
print(f"注册表条目: {len(registry)}")
print(f"块条均出现: {sum(1 for v in registry.values() if len(v['locations'])>1)}")
print(f"URL 冲突（两边不一致）: {len(conflicts)}")
for key, u1, u2, loc1, loc2 in conflicts[:15]:
    print(f"  ✗ {key}")
    print(f"      {loc1}: {u1[:55]}")
    print(f"      {loc2}: {u2[:55]}")
