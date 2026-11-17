# -*- coding: utf-8 -*-
"""P63: 法院系统三级树构建 + 老系统回填（合规 HTML 提取数据）。

法院系统模块：高院（32）→ 中院（159）→ 基层法院（473）。
  中院名与 tree 市名匹配（太原市中院→太原市中级人民法院）；未匹配的
  专门法院（铁路中院等）挂高院下。
  基层法院与 tree 区县名匹配（平城区法院→平城区人民法院）；未匹配挂中院下。
老系统回填：县规则 depts「县人民法院」u + 市并列机关「市中级人民法院」u。
"""
import json
import re

MUNICIPAL = {"北京市", "天津市", "上海市", "重庆市"}


def strip_zy(t, prov):
    """中院名 → 城市 base；直辖市返回 None（中院直接挂高院）。"""
    core = re.sub(r"网$", "", t)
    core = re.sub(r"(中级人民法院|中级法院|中院)$", "", core)
    core = re.sub(r"第[一二三四五六七八九十]+$", "", core)
    if prov in MUNICIPAL:
        return None
    return re.sub(r"(自治州|地区|盟|市)$", "", core)


def strip_jc(t, prov, city_idx):
    """基层法院名 → 区县 base（与 city_idx 键对齐：剥省/市前缀与行政后缀）。"""
    core = re.sub(r"(人民法院|法院)$", "", t)
    short = re.sub(r"(维吾尔|壮族|回族)?自治区$|省$|市$", "", prov)
    if core.startswith(short):
        core = core[len(short):]
    core = re.sub(r"^市", "", core)
    if (prov, core) in city_idx:
        return core
    # 剥市级前缀（贵阳市南明区 → 南明区）
    for (p, base), (full, lv) in city_idx.items():
        if p != prov:
            continue
        if core.startswith(base + "市") and len(core) > len(base) + 1:
            cand = core[len(base) + 1:]
            if (prov, cand) in city_idx:
                return cand
    # 剥行政后缀（三穗县→三穗，与 city_idx 键对齐）
    core = re.sub(r"(自治州|地区|盟|市|区|县|旗)$", "", core)
    if (prov, core) in city_idx:
        return core
    return core


def main():
    rows = [json.loads(l) for l in open("court_hierarchy.jsonl", encoding="utf-8")]
    tree = json.load(open("tree.json", encoding="utf-8"))
    rules = json.load(open("extraction_rules.json", encoding="utf-8"))
    prov_g = next(g for g in tree["ks"] if g["n"].startswith("省级"))
    tiao = next(g for g in tree["ks"] if g["n"] == "条（垂直管理系统）")

    # 市县名索引
    city_idx = {}   # base名 → (全名, level)
    for p in prov_g["ks"]:
        for top in p.get("ks", []):
            def walk(n):
                if n.get("l") in ("市", "地级区", "县") and n.get("k") == "人民政府":
                    base = re.sub(r"(自治州|地区|盟|市|区|县)$", "", n["n"])
                    city_idx.setdefault((p["n"], base), (n["n"], n["l"]))
                for k in n.get("ks", []):
                    walk(k)
            walk(top)

    fy_sys = next(g for g in tiao["ks"] if g["n"].startswith("法院系统"))
    gy_grp = next(g for g in fy_sys["ks"] if g["n"].startswith("高级人民法院"))
    gy_nodes = {g["n"]: g for g in gy_grp["ks"]}

    # 挂载：中院
    zy_by_gy = {}
    for r in rows:
        if r["level"] == "中院":
            zy_by_gy.setdefault(r["province"], []).append(r)
    zy_nodes = {}   # (province, name) → node
    for pname, zlist in zy_by_gy.items():
        gyn = f"{pname}高级人民法院"
        if gyn not in gy_nodes:
            continue
        gy = gy_nodes[gyn]
        gy.setdefault("ks", [])
        existing = {k["n"] for k in gy["ks"]}
        for r in zlist:
            base = strip_zy(r["name"], pname)
            if base is None:
                # 直辖市中院：直接挂高院（全称）
                nm = re.sub(r"网$", "", r["name"])
                if nm not in existing:
                    node = {"n": nm, "l": "市", "k": "法院系统", "c": "法院系统",
                            "u": r["url"], "x": "", "s": "", "m": "", "ks": []}
                    gy["ks"].append(node)
                    zy_nodes[(pname, r["name"])] = node
                    existing.add(nm)
                else:
                    zy_nodes[(pname, r["name"])] = next(
                        k for k in gy["ks"] if k["n"] == nm)
                continue
            hit = city_idx.get((pname, base))
            if hit and hit[0] + "中级人民法院" not in existing:
                nm = hit[0] + "中级人民法院"
                node = {"n": nm, "l": "市", "k": "法院系统", "c": "法院系统",
                        "u": r["url"], "x": "", "s": "", "m": "", "ks": []}
                gy["ks"].append(node)
                zy_nodes[(pname, r["name"])] = node
                existing.add(nm)
            elif hit and hit[0] + "中级人民法院" in existing:
                zy_nodes[(pname, r["name"])] = next(
                    k for k in gy["ks"] if k["n"] == hit[0] + "中级人民法院")
            elif not hit:
                nm = re.sub(r"网$", "", r["name"])
                if nm not in existing:
                    node = {"n": nm, "l": "省", "k": "法院系统", "c": "法院系统",
                            "u": r["url"], "x": "", "s": "", "m": "", "ks": []}
                    gy["ks"].append(node)
                    zy_nodes[(pname, r["name"])] = node
                    existing.add(nm)
                else:
                    zy_nodes[(pname, r["name"])] = next(
                        k for k in gy["ks"] if k["n"] == nm)

    # 挂载：基层
    jc_added = jc_old = 0
    for r in rows:
        if r["level"] != "基层":
            continue
        zn = zy_nodes.get((r["province"], r["parent"]))
        if not zn:
            continue
        base = strip_jc(r["name"], r["province"], city_idx)
        hit = city_idx.get((r["province"], base))
        nm = hit[0] + "人民法院" if hit else r["name"]
        if nm not in {k["n"] for k in zn.get("ks", [])}:
            zn.setdefault("ks", []).append(
                {"n": nm, "l": hit[1] if hit else "县",
                 "k": "法院系统", "c": "法院系统", "u": r["url"],
                 "x": "", "s": "", "m": ""})
            jc_added += 1
        # 老系统回填：县级规则 depts 县人民法院
        if hit and hit[1] in ("县", "地级区"):
            cd = None
            for p in prov_g["ks"]:
                if p["n"] != r["province"]:
                    continue
                for top in p.get("ks", []):
                    def walk2(n):
                        nonlocal cd
                        if n.get("l") in ("县", "地级区") and n["n"] == hit[0]:
                            cd = n.get("cd", "")
                        for k in n.get("ks", []):
                            walk2(k)
                    walk2(top)
            if cd and cd in rules:
                for d in rules[cd]["depts"]:
                    if "法院" in d["n"]:
                        d["u"] = r["url"]
                        jc_old += 1

    json.dump(tree, open("tree.json", "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    json.dump(rules, open("extraction_rules.json", "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    print(f"p63 完成：中院挂载 {len(zy_nodes)}，基层挂载 {jc_added}，"
          f"老系统县法院回填 {jc_old}")


if __name__ == "__main__":
    main()
