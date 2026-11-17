# -*- coding: utf-8 -*-
"""P65: 检察院系统树重建 + 老系统回填。

结构：最高检 → 内设17 → 省级检察院（32）→ 市级检察院（p40 已验证 293，
降级标注）→ 基层检察院（p64b 合规 HTML 提取 63 + 直辖市 efy 子路径）。
老系统：县规则 depts「县人民检察院」u ← 基层院 URL（合规来源覆盖探测）。
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
    p40 = json.load(open("p40_state.json", encoding="utf-8"))
    jc_rows = []
    if __import__("os").path.exists("jc_hierarchy.jsonl"):
        jc_rows = [json.loads(l) for l in open("jc_hierarchy.jsonl",
                                               encoding="utf-8")]

    # 老规则清理
    for k in [x for x in rules if x.startswith("检察院系统")]:
        del rules[k]

    jc_prov = []
    prov_urls = {}
    for p in prov_g["ks"]:
        par = next((k for k in p.get("ks", []) if k.get("c") == "并列机关"), None)
        if not par:
            continue
        m = next((x for x in par.get("ks", []) if "检察院" in x["n"]), None)
        if not m:
            continue
        prov_urls[p["n"]] = m.get("u", "")
        # 市级院
        kids = []
        for h in p40.get("hits", []):
            if h.get("verified") and h["province"] == p["n"] \
                    and h.get("level") == "市":
                kids.append(leaf(f"{h['name']}检察院", "检察院系统",
                                 h["url"], "市"))
        # 基层院挂到对应市级院下
        jc_by_parent = {}
        for r in jc_rows:
            if r["province"] == p["n"]:
                jc_by_parent.setdefault(r["parent"], []).append(r)
        for k in kids:
            pn = k["n"].replace("检察院", "")
            for r in jc_by_parent.get(pn, []):
                k.setdefault("ks", []).append(
                    leaf(r["name"], "检察院系统", r["url"], "县"))
        # 无父基层（直辖市）直接挂省院
        jc_prov.append({"n": f"{p['n']}检察院", "l": "省",
                        "k": "检察院系统", "c": "检察院系统",
                        "u": prov_urls[p["n"]], "x": "", "s": "", "m": "",
                        "ks": kids})
    # 直辖市 efy 基层直接挂（parent 未匹配市级）
    for r in jc_rows:
        if r["province"] in MUNICIPAL:
            for pn in jc_prov:
                if pn["n"] == f"{r['province']}检察院":
                    if not any(x["n"] == r["name"] for x in pn["ks"]):
                        pn["ks"].append(leaf(r["name"], "检察院系统",
                                             r["url"], "县"))

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

    # ---- 规则 ----
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
        "省级检察院（省门户 footer 提取）；市级检察院（拼音域名+标题验证，"
        "降级待官方名录替换）；基层检察院（市级院官网「下辖检察院」真实 HTML "
        "提取，检察系统基层院公开度低于法院）",
        [{"n": m["n"], "u": m["u"], "o": i} for i, m in enumerate(all_m)])
    for p in jc_prov:
        add(f"省级检察院（{len(jc_prov)}）·{p['n']}", p["u"] or "https://www.spp.gov.cn/",
            "省门户 footer 提取；市级院标题验证（降级）；基层院 HTML 提取",
            [{"n": m["n"], "u": m["u"], "o": i} for i, m in
             enumerate([p] + p.get("ks", []))])

    # ---- 老系统回填：县检察院 ----
    filled = 0
    jc_leaf = {r["name"]: r["url"] for r in jc_rows}
    for k in [k for k in rules if k.isdigit() and len(k) == 6]:
        for d in rules[k].get("depts", []):
            if "检察院" in d["n"]:
                base = re.sub(r"(人民法院|法院|人民检察院|检察院)$", "", d["n"])
                hit = None
                for nm, u in jc_leaf.items():
                    if re.sub(r"(人民检察院|检察院)$", "", nm) == base:
                        hit = u
                        break
                if hit:
                    d["u"] = hit
                    filled += 1

    json.dump(tree, open("tree.json", "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    json.dump(rules, open("extraction_rules.json", "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    n_shi = sum(len(p.get("ks", [])) for p in jc_prov)
    n_jc = sum(len(k.get("ks", [])) for p in jc_prov for k in p.get("ks", []))
    print(f"p65 完成：省级 {len(jc_prov)}，市级 {n_shi}，基层 {n_jc}，"
          f"老系统回填 {filled}，rules 总数 {len(rules)}")


if __name__ == "__main__":
    main()
