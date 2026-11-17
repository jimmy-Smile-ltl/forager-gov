# -*- coding: utf-8 -*-
"""P55: 烟草市级子站回填条模块（省局网站栏目真实 HTML 提取）。
节点：省级单位节点下新增「{城市}烟草专卖局」（l=市，u=省局子站栏目 URL）。
"""
import json
import re


def main():
    rows = [json.loads(l) for l in open("tobacco_city.jsonl", encoding="utf-8")]
    tree = json.load(open("tree.json", encoding="utf-8"))
    rules = json.load(open("extraction_rules.json", encoding="utf-8"))

    tiao = next(g for g in tree["ks"] if g["n"] == "条（垂直管理系统）")
    yc = next(g for g in tiao["ks"] if g["n"].startswith("烟草系统"))
    prov_grp = next(g for g in yc["ks"] if g["n"].startswith("省级单位"))

    by_prov = {}
    for r in rows:
        by_prov.setdefault(r["province"], []).append(r)

    added = 0
    for pnode in prov_grp["ks"]:
        pname = pnode["n"].replace("烟草专卖局", "")
        if pname not in by_prov:
            continue
        existing = {k["n"] for k in pnode.get("ks", [])}
        for r in by_prov[pname]:
            nm = f"{r['city']}烟草专卖局"
            if nm in existing:
                continue
            pnode.setdefault("ks", []).append(
                {"n": nm, "l": "市", "k": "烟草系统", "c": "烟草系统",
                 "u": r["url"], "x": "", "s": "", "m": ""})
            added += 1
            # 成员规则
            rules[f"{pnode['n']}·{nm}"] = {
                "portal": r["url"],
                "method": f"{pnode['n']}官网城市子站栏目真实 HTML 提取（相对路径 urljoin）",
                "sources": [r["url"]],
                "code": (f'# -*- coding: utf-8 -*-\n"""{nm} 提取规则。\n'
                         f'门户：{r["url"]}\n'
                         f'方法：{pnode["n"]}官网城市子站栏目 HTML 提取。\n"""\n'
                         'import requests\n\n'
                         f'resp = requests.get("{r["url"]}", timeout=15, verify=False, '
                         'headers={"User-Agent": "Mozilla/5.0"})\n'
                         'print("页面长度:", len(resp.content))\n'),
                "depts": [{"n": nm, "u": r["url"], "o": 0}],
                "cities": [],
            }
        # 省级单位节点规则 depts 补充
        rkey = f"{prov_grp['n']}·{pnode['n']}"
        if rkey in rules:
            cur = {d["n"] for d in rules[rkey]["depts"]}
            for r in by_prov[pname]:
                nm = f"{r['city']}烟草专卖局"
                if nm not in cur:
                    rules[rkey]["depts"].append(
                        {"n": nm, "u": r["url"], "o": len(rules[rkey]["depts"])})
                    cur.add(nm)

    json.dump(tree, open("tree.json", "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    json.dump(rules, open("extraction_rules.json", "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    print(f"p55 完成：新增 {added} 个市级烟草节点，rules 总数 {len(rules)}")


if __name__ == "__main__":
    main()
