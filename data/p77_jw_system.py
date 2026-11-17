# -*- coding: utf-8 -*-
"""P77: 纪委系统（纪检监察）条模块构建 —— 基于块数据映射。

结构：中央纪委国家监委（ccdi.gov.cn，内设15 复制块树）→ 省级纪委监委
（32：13 有 URL + 19 列名）→ 市级纪委监委（333，cc_parallel 真实采集
命中填 URL，其余列名）。
回填：老系统市/县并列机关「监委」u ← cc_parallel 监委链接（真实 HTML 来源）。
"""
import json
import re


def leaf(nm, cat, u, lv):
    return {"n": nm, "l": lv, "k": cat, "c": cat, "u": u,
            "x": "", "s": "", "m": ""}


def grp(nm, cat, kids):
    return {"n": nm, "l": "条", "k": "分组", "c": cat, "u": "",
            "x": "", "s": "", "m": "", "ks": kids}


def main():
    tree = json.load(open("tree.json", encoding="utf-8"))
    rules = json.load(open("extraction_rules.json", encoding="utf-8"))
    prov_g = next(g for g in tree["ks"] if g["n"].startswith("省级"))
    central = next(g for g in tree["ks"] if g["n"].startswith("中央"))
    tiao = next(g for g in tree["ks"] if g["n"] == "条（垂直管理系统）")

    for k in [x for x in rules if x.startswith("纪委系统")]:
        del rules[k]

    # cc_parallel 监委链接（市县，真实 HTML）
    jw = {}
    if __import__("os").path.exists("cc_parallel.jsonl"):
        for l in open("cc_parallel.jsonl", encoding="utf-8"):
            r = json.loads(l)
            if r.get("org_cat") == "监委":
                jw[(r["province"], r["name"])] = r["org_url"]

    # 国家监委内设（块树）
    jw_zg = next(g for g in central["ks"] if g["n"].startswith("国家监察委员会"))
    neishe = [{"n": k["n"], "l": "中央", "k": "纪委系统", "c": "纪委系统",
               "u": k.get("u", ""), "x": "", "s": "", "m": ""}
              for g in jw_zg.get("ks", []) for k in g.get("ks", [])]
    root = leaf("中央纪委国家监委", "纪委系统", "https://www.ccdi.gov.cn/", "中央")

    # 省级 + 市级
    jw_prov = []
    for p in prov_g["ks"]:
        pname = p["n"]
        par = next((k for k in p.get("ks", []) if k.get("c") == "并列机关"), None)
        m = next((x for x in par.get("ks", []) if "监委" in x["n"]), None) if par else None
        pu = m.get("u", "") if m else ""
        # 市级
        shi_kids = []
        for top in p.get("ks", []):
            def walk(n):
                if n.get("l") == "市" and n.get("k") == "人民政府":
                    su = jw.get((pname, n["n"]), "")
                    shi_kids.append(leaf(f"{n['n']}纪委监委", "纪委系统",
                                         su, "市"))
                for k in n.get("ks", []):
                    walk(k)
            walk(top)
        jw_prov.append({"n": f"{pname}纪委监委", "l": "省",
                        "k": "纪委系统", "c": "纪委系统", "u": pu,
                        "x": "", "s": "", "m": "", "ks": shi_kids})

    sys_g = grp(f"纪委系统（{len(jw_prov) + 2}）", "纪委系统",
                [root,
                 grp(f"内设机构（{len(neishe)}）", "纪委系统", neishe),
                 grp(f"省级纪委监委（{len(jw_prov)}）", "纪委系统", jw_prov)])
    tiao["ks"] = [g for g in tiao["ks"] if not g["n"].startswith("纪委系统")]
    tiao["ks"].append(sys_g)

    # 老系统回填：市县监委 u
    filled = 0
    for p in prov_g["ks"]:
        pname = p["n"]
        for top in p.get("ks", []):
            def walk2(n):
                nonlocal filled
                if n.get("l") in ("市", "县", "地级区") and n.get("k") == "人民政府":
                    su = jw.get((pname, n["n"]))
                    if su:
                        par = next((g for g in n.get("ks", [])
                                    if g.get("c") == "并列机关"), None)
                        if par:
                            m2 = next((x for x in par.get("ks", [])
                                       if "监委" in x["n"]), None)
                            if m2:
                                m2["u"] = su
                                filled += 1
                for k in n.get("ks", []):
                    walk2(k)
            walk2(top)

    # 规则
    def add(key, portal, method, depts):
        rules[key] = {
            "portal": portal, "method": method, "sources": [portal],
            "code": f'# -*- coding: utf-8 -*-\n"""{key} 提取规则。\n'
                    f'方法：{method}\n"""\n',
            "depts": depts, "cities": [],
        }

    all_m = [root] + neishe + [x for p in jw_prov for x in
                               ([p] + p.get("ks", []))]
    add(sys_g["n"], "https://www.ccdi.gov.cn/",
        "基于块数据映射：省纪委监委（省门户 footer 提取 13/32，其余列名）；"
        "市纪委监委（市门户 footer 采集命中填 URL，多数无独立公开门户→列名——"
        "纪检监察系统特点：地方纪委监委多数不设公开网站）",
        [{"n": m["n"], "u": m["u"], "o": i} for i, m in enumerate(all_m)])

    json.dump(tree, open("tree.json", "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    json.dump(rules, open("extraction_rules.json", "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    n_prov_u = sum(1 for p in jw_prov if p["u"])
    n_shi_u = sum(1 for p in jw_prov for k in p.get("ks", []) if k["u"])
    print(f"p77 完成：省级 {len(jw_prov)}（{n_prov_u} 有 URL），"
          f"市级 {sum(len(p['ks']) for p in jw_prov)}（{n_shi_u} 有 URL），"
          f"老系统回填 {filled}，rules 总数 {len(rules)}")


if __name__ == "__main__":
    main()
