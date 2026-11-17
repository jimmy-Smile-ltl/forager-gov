# -*- coding: utf-8 -*-
"""P68: 检察院系统树重建（真实 HTML 来源）+ 老系统回填。

市级检察院：jc_shi.jsonl（省检察院官网「市州分院」区块纯市名 anchor，
79 个，真实 HTML 提取）；基层检察院：jc_hierarchy.jsonl（63 个）。
老系统：市并列机关「市人民检察院」u 回填；县规则「县人民检察院」u 回填。
"""
import json
import re

MUNICIPAL = {"北京市", "天津市", "上海市", "重庆市"}


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
    tiao = next(g for g in tree["ks"] if g["n"] == "条（垂直管理系统）")

    shi = {}
    for l in open("jc_shi.jsonl", encoding="utf-8"):
        r = json.loads(l)
        shi.setdefault(r["province"], []).append(r)
    jc_rows = [json.loads(l) for l in open("jc_hierarchy.jsonl", encoding="utf-8")]

    for k in [x for x in rules if x.startswith("检察院系统")]:
        del rules[k]

    # 市级院名称规范化：「南昌市院」→「南昌市检察院」；「阿里分院」原样
    def shi_name(p, t):
        if "铁路" in t or t.endswith(("分院", "派出院", "铁检")):
            return t
        core = re.sub(r"院$", "", t)
        if core.endswith(("市", "州", "盟", "地区")):
            return core + "检察院"
        return core + "检察院"

    jc_prov = []
    for p in prov_g["ks"]:
        par = next((k for k in p.get("ks", []) if k.get("c") == "并列机关"), None)
        m = next((x for x in par.get("ks", []) if "检察院" in x["n"]), None) if par else None
        if not m:
            continue
        pname = p["n"]
        kids = []
        for r in shi.get(pname, []):
            kids.append(leaf(shi_name(pname, r["name"]), "检察院系统",
                             r["url"], "市"))
        # 基层挂载
        jc_by_parent = {}
        for r in jc_rows:
            if r["province"] == pname:
                jc_by_parent.setdefault(r["parent"], []).append(r)
        for k in kids:
            pn = k["n"].replace("检察院", "")
            for r in jc_by_parent.get(pn, []):
                k.setdefault("ks", []).append(
                    leaf(r["name"], "检察院系统", r["url"], "县"))
        jc_prov.append({"n": f"{pname}检察院", "l": "省",
                        "k": "检察院系统", "c": "检察院系统",
                        "u": m.get("u", ""), "x": "", "s": "", "m": "",
                        "ks": kids})

    zgjc = next(g for g in next(g for g in tree["ks"]
                                if g["n"].startswith("中央"))["ks"]
                if g["n"].startswith("最高人民检察院"))
    neishe = [{"n": k["n"], "l": "中央", "k": "检察院系统", "c": "检察院系统",
               "u": k.get("u", ""), "x": "", "s": "", "m": ""}
              for g in zgjc.get("ks", []) for k in g.get("ks", [])]
    root = leaf("最高人民检察院", "检察院系统", "https://www.spp.gov.cn/", "中央")
    sys_g = grp(f"检察院系统（{len(jc_prov) + 2}）", "检察院系统",
                [root,
                 grp(f"内设机构（{len(neishe)}）", "检察院系统", neishe),
                 grp(f"省级检察院（{len(jc_prov)}）", "检察院系统", jc_prov)])
    tiao["ks"] = [g for g in tiao["ks"] if not g["n"].startswith("检察院系统")]
    tiao["ks"].append(sys_g)

    # 规则
    def add(key, portal, method, depts):
        rules[key] = {
            "portal": portal, "method": method, "sources": [portal],
            "code": f'# -*- coding: utf-8 -*-\n"""{key} 提取规则。\n'
                    f'方法：{method}\n"""\n',
            "depts": depts, "cities": [],
        }

    all_m = [root] + neishe + [x for p in jc_prov for x in
                               ([p] + p.get("ks", []))]
    add(sys_g["n"], "https://www.spp.gov.cn/",
        "省级检察院（省门户 footer 提取）；市级检察院（省检察院官网「市州分院」"
        "区块纯市名 anchor 真实 HTML 提取，7 省 79 个）；基层检察院（市级院官网"
        "「下辖检察院」区块提取）；其余省官网未挂导航 → 列名（不猜测）",
        [{"n": m["n"], "u": m["u"], "o": i} for i, m in enumerate(all_m)])
    for p in jc_prov:
        add(f"省级检察院（{len(jc_prov)}）·{p['n']}", p["u"] or "https://www.spp.gov.cn/",
            "市级院来自省检察院官网「市州分院」区块 HTML 提取；基层院来自市级院官网",
            [{"n": m["n"], "u": m["u"], "o": i} for i, m in
             enumerate([p] + p.get("ks", []))])

    # 老系统回填
    filled_shi = filled_jc = 0
    # 市检察院
    city_idx = {}
    for p in prov_g["ks"]:
        for top in p.get("ks", []):
            def walk(n):
                if n.get("l") == "市" and n.get("k") == "人民政府":
                    city_idx[(p["n"], n["n"])] = n
                for k in n.get("ks", []):
                    walk(k)
            walk(top)
    for r in [x for v in shi.values() for x in v]:
        pname = r["province"]
        base = re.sub(r"(自治州|地区|盟|市)$", "", r["name"])
        for (pp, full), node in city_idx.items():
            if pp != pname:
                continue
            if re.sub(r"(自治州|地区|盟|市)$", "", full) == base:
                par = next((g for g in node.get("ks", [])
                            if g.get("c") == "并列机关"), None)
                if par:
                    m = next((x for x in par.get("ks", []) if "检察院" in x["n"]), None)
                    if m:
                        m["u"] = r["url"]
                        filled_shi += 1
                break
    # 县检察院（jc_rows 基层）
    idx = {}
    for p in prov_g["ks"]:
        for top in p.get("ks", []):
            def walk2(n):
                if n.get("l") in ("县", "地级区") and n.get("k") == "人民政府":
                    idx[(p["n"], n["n"])] = n.get("cd", "")
                    idx[(p["n"], re.sub(r"(自治县|区|县|旗)$", "", n["n"]))] = n.get("cd", "")
                for k in n.get("ks", []):
                    walk2(k)
            walk2(top)
    for r in jc_rows:
        core = re.sub(r"(人民检察院|检察院)$", "", r["name"])
        for key in ((r["province"], core),
                    (r["province"], re.sub(r"^(北京市|天津市|上海市|重庆市)", "", core))):
            cd = idx.get(key)
            if cd and cd in rules:
                for d in rules[cd]["depts"]:
                    if "检察院" in d["n"]:
                        d["u"] = r["url"]
                        filled_jc += 1
                break

    json.dump(tree, open("tree.json", "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    json.dump(rules, open("extraction_rules.json", "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    n_shi = sum(len(p.get("ks", [])) for p in jc_prov)
    print(f"p68 完成：省级 {len(jc_prov)}，市级（合规）{n_shi}，"
          f"市检察院回填 {filled_shi}，县检察院回填 {filled_jc}，"
          f"rules 总数 {len(rules)}")


if __name__ == "__main__":
    main()
