# -*- coding: utf-8 -*-
"""P50: p49 渲染提取的市级/区级工会回填（真实 HTML 来源）。

1. 工会系统模块：{省名}总工会节点下合并市级工会节点（用官网栏目里的官方名称）；
   直辖市下挂区级工会节点。
2. 老系统：市节点新增/更新「市总工会」；直辖市地级区节点新增「区总工会」。
3. 规则同步（组 depts + 成员规则）。
"""
import json
import re

MUNICIPAL = {"北京市", "天津市", "上海市", "重庆市"}


def main():
    rows = [json.loads(l) for l in open("union_city2.jsonl", encoding="utf-8")]
    tree = json.load(open("tree.json", encoding="utf-8"))
    rules = json.load(open("extraction_rules.json", encoding="utf-8"))
    prov_g = next(g for g in tree["ks"] if g["n"].startswith("省级"))

    by_prov = {}
    for r in rows:
        by_prov.setdefault(r["province"], []).append(r)

    tiao = next(g for g in tree["ks"] if g["n"] == "条（垂直管理系统）")
    union = next(g for g in tiao["ks"] if g["n"].startswith("工会系统"))
    acftu = next(g for g in union["ks"] if g["n"] == "中华全国总工会")
    pgrp = next(g for g in acftu["ks"] if g["n"].startswith("省级工会"))

    mod_added = sys_added = 0
    # ---- 模块 ----
    for pnode in pgrp["ks"]:
        pname = pnode["n"].replace("总工会", "")
        if pname not in by_prov:
            continue
        existing = {k["n"] for k in pnode.get("ks", [])}
        for r in by_prov[pname]:
            nm = r["label"] or f"{r['city']}总工会"
            if nm in existing:
                # 更新 URL（渲染来源更权威）
                for k in pnode["ks"]:
                    if k["n"] == nm:
                        k["u"] = r["url"]
                continue
            lv = "地级区" if r["level"] == "区" else "市"
            pnode.setdefault("ks", []).append(
                {"n": nm, "l": lv, "k": "工会系统", "c": "工会系统",
                 "u": r["url"], "x": "", "s": "", "m": ""})
            mod_added += 1
        # 组规则 depts 同步
        rkey = f"工会系统·{pnode['n']}"
        if rkey in rules:
            cur = {d["n"] for d in rules[rkey]["depts"]}
            for r in by_prov[pname]:
                nm = r["label"] or f"{r['city']}总工会"
                if nm in cur:
                    continue
                rules[rkey]["depts"].append(
                    {"n": nm, "u": r["url"], "o": len(rules[rkey]["depts"])})
                cur.add(nm)

    # ---- 老系统 ----
    def find_city(p, name):
        for top in p.get("ks", []):
            def walk(n):
                if n.get("l") in ("市", "地级区") and n.get("k") == "人民政府" \
                        and n["n"] == name:
                    return n
                for k in n.get("ks", []):
                    r2 = walk(k)
                    if r2:
                        return r2
                return None
            r2 = walk(top)
            if r2:
                return r2
        return None

    for p in prov_g["ks"]:
        pname = p["n"]
        if pname not in by_prov:
            continue
        for r in by_prov[pname]:
            node = find_city(p, r["city"])
            if not node:
                continue
            if r["level"] == "区":
                child = next((x for x in node.get("ks", []) if x["n"] == "区总工会"), None)
                cname = "区总工会"
                ckey = f"{r['city']}·区总工会"
            else:
                child = next((x for x in node.get("ks", []) if x["n"] == "市总工会"), None)
                cname = "市总工会"
                ckey = f"{r['city']}·市总工会"
            if child:
                child["u"] = r["url"]
            else:
                node.setdefault("ks", []).insert(0, {
                    "n": cname, "l": node["l"], "k": "群团组织", "c": "群团组织",
                    "u": r["url"], "x": "", "s": "", "m": ""})
                sys_added += 1
            rules[ckey] = {
                "portal": r["url"],
                "method": "省级工会官网「州市/区工会网站」栏目真实 HTML 提取（渲染后 DOM）",
                "sources": [r["url"]],
                "code": (f'# -*- coding: utf-8 -*-\n"""\n{pname} {r["city"]} {cname} 提取规则。\n'
                         f'门户：{r["url"]}\n方法：省级工会官网栏目 HTML 提取。\n"""\n'
                         'import requests\n\n'
                         f'resp = requests.get("{r["url"]}", timeout=15, verify=False, '
                         'headers={"User-Agent": "Mozilla/5.0"})\n'
                         'print("页面长度:", len(resp.content))\n'),
                "depts": [{"n": cname, "u": r["url"], "o": 0}],
                "cities": [],
            }

    json.dump(tree, open("tree.json", "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    json.dump(rules, open("extraction_rules.json", "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    print(f"p50 完成：模块新增 {mod_added}，老系统新增 {sys_added}，"
          f"rules 总数 {len(rules)}")


if __name__ == "__main__":
    main()
