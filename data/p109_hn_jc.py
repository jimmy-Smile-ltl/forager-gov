# -*- coding: utf-8 -*-
"""P109: 湖南检察院全量挂载（省院 szylj 频道页真实 HTML）。

13 市州栏目（缺益阳）+ 119 基层检察院 → 湖南省检察院节点下。
市级节点名修正「XX市检察检察院」→「XX市检察院」。
老系统县人民检察院并列机关回填。
"""
import json
import re

COLS = ["cs", "zz", "xt", "hy", "sy", "yy", "cd", "zjj", "cz", "yz", "hh", "ld", "xx"]

def load_col(shi):
    t = open(f"/tmp/hn_{shi}.html", encoding="utf-8", errors="replace").read()
    d = {}
    for u, txt in re.findall(
            r'<a[^>]+href="([^"]+)"[^>]*>\s*([^<]{3,24}?)\s*</a>', t):
        t2 = txt.strip()
        if re.search(r'(检察院|检察)', t2) and 'szylj' in u:
            d[t2] = u
    return d

def main():
    tree = json.load(open("tree.json", encoding="utf-8"))
    rules = json.load(open("extraction_rules.json", encoding="utf-8"))
    prov_g = next(g for g in tree["ks"] if g["n"].startswith("省级"))
    tiao = next(g for g in tree["ks"] if g["n"].startswith("条"))
    jc = next(g for g in tiao["ks"] if g["n"].startswith("检察院系统"))
    prov_jc = next(g for g in jc["ks"] if "省级检察院" in g["n"])
    hn = next(p for p in prov_jc["ks"] if p["n"].startswith("湖南省"))

    # 树里湖南县级名单（回填用）
    hn_prov = next(p for p in prov_g["ks"] if p["n"] == "湖南省")
    counties = {}
    for top in hn_prov.get("ks", []):
        def walk(n):
            if n.get("l") == "县" and n.get("k") == "人民政府":
                counties[n["n"]] = ""
            for k in n.get("ks", []):
                walk(k)
        walk(top)

    leaf = lambda nm, u: {"n": nm, "l": "县", "k": "检察院系统",
                          "c": "检察院系统", "u": u, "x": "", "s": "", "m": ""}

    # 树里湖南市州名单（权威）
    shi_set = set()
    for top in hn_prov.get("ks", []):
        def walk2(n):
            if n.get("l") == "市" and n.get("k") == "人民政府":
                shi_set.add(re.sub(r"市$", "", n["n"]))
            for k in n.get("ks", []):
                walk2(k)
        walk2(top)

    new_shi = filled_jc = 0
    for shi in COLS:
        d = load_col(shi)
        # 市级条目 = 名称核心在树里市州名单中
        shi_entries = {}
        for k, v in d.items():
            core = re.sub(r"(人民检察院|检察院|检察网)$", "", k)
            core = core.replace("市", "")
            if core in shi_set:
                shi_entries[k] = v
        jc_entries = {k: v for k, v in d.items() if k not in shi_entries}
        if not shi_entries:
            continue
        for shi_nm, shi_u in shi_entries.items():
            core = re.sub(r'(人民检察院|检察院)$', '', shi_nm)
            # 匹配现有市级节点（修正名字）
            node = None
            for s in hn.get("ks", []):
                s_core = s["n"].replace("检察检察院", "").replace("检察院", "")
                s_core = s_core.replace("市", "")
                if s_core and (s_core in core or core in s_core):
                    node = s
                    break
            if node is None:
                nm = f"{core}检察院"
                node = {"n": nm, "l": "市", "k": "检察院系统", "c": "检察院系统",
                        "u": shi_u, "x": "", "s": "", "m": "", "ks": []}
                hn["ks"].append(node)
                new_shi += 1
            else:
                if not node.get("u"):
                    node["u"] = shi_u
                if "检察检察院" in node["n"]:
                    node["n"] = f"{core}检察院"
            # 挂基层
            existing = {k["n"] for k in node.get("ks", [])}
            for jc_nm, jc_u in jc_entries.items():
                nm = jc_nm.replace("检察网", "人民检察院")
                if nm in existing:
                    continue
                node.setdefault("ks", []).append(leaf(nm, jc_u))
                existing.add(nm)
                filled_jc += 1
                # 老系统回填
                for top in hn_prov.get("ks", []):
                    def wfill(n):
                        if n.get("l") == "县" and n.get("k") == "人民政府" \
                                and n["n"] == nm.replace("人民检察院", ""):
                            par = next((g for g in n.get("ks", [])
                                        if g.get("c") == "并列机关"), None)
                            if par:
                                m = next((x for x in par.get("ks", [])
                                          if "检察院" in x["n"]), None)
                                if m:
                                    m["u"] = jc_u
                                    return True
                        for k in n.get("ks", []):
                            if wfill(k):
                                return True
                        return False
                    if wfill(top):
                        break

    json.dump(tree, open("tree.json", "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    total_jc = sum(len(s.get("ks", [])) for s in hn.get("ks", []))
    print(f"p109 完成：新增市级 {new_shi}，基层 {total_jc} 个（本轮挂 {filled_jc}）")

if __name__ == "__main__":
    main()
