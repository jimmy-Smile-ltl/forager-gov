# -*- coding: utf-8 -*-
"""P66: 拼音探测数据全面清除（用户明令：绝对不认可拼音）。

清除范围（探测=拼音/缩写+后缀组合或 DNS 试探）：
  1. 条模块 海关系统 42 直属海关 u → 列名
  2. 条模块 税务系统 31 / 邮政系统 29 / 人民银行系统 33 → 列名
  3. 条模块 检察院系统 市级 188（p40 探测）→ 列名（节点保留，基层 63 为
     真实 HTML 提取，保留）
  4. 块树 国务院海关总署下 42 直属海关 u → 列名
  5. 老系统县级规则 depts：检察院 u 来自 p40 探测者清空（jc_hierarchy 的
     62 个真实 HTML 来源保留）；法院 u 非 court_hierarchy 真实来源者清空
规则：method 更新为「列名（官方名录页 HTML 提取待补）」。
"""
import json
import re

TIAO_KEYS = ("海关系统", "税务系统", "邮政系统", "人民银行系统")
JCY_RE = re.compile(r"\.jcy\.gov\.cn")


def main():
    tree = json.load(open("tree.json", encoding="utf-8"))
    rules = json.load(open("extraction_rules.json", encoding="utf-8"))
    tiao = next(g for g in tree["ks"] if g["n"] == "条（垂直管理系统）")

    jc_real = set()
    if __import__("os").path.exists("jc_hierarchy.jsonl"):
        for l in open("jc_hierarchy.jsonl", encoding="utf-8"):
            jc_real.add(json.loads(l)["url"])
    court_real = set()
    for l in open("court_hierarchy.jsonl", encoding="utf-8"):
        court_real.add(json.loads(l)["url"])

    cleared = 0
    # 1-3 条模块
    for g in tiao["ks"]:
        gn = g["n"]
        if gn.startswith(TIAO_KEYS):
            for m in g.get("ks", []):
                if m.get("u"):
                    m["u"] = ""
                    cleared += 1
        elif gn.startswith("检察院系统"):
            gy = next((x for x in g["ks"] if x["n"].startswith("省级检察院")), None)
            if gy:
                for pnode in gy["ks"]:
                    for m in pnode.get("ks", []):
                        # 市级（探测）清空；基层（真实提取）保留
                        if m.get("u") and m["u"] not in jc_real:
                            m["u"] = ""
                            cleared += 1
    # 4 块树海关
    central = next(g for g in tree["ks"] if g["n"].startswith("中央"))
    gw = next(g for g in central["ks"] if g["n"].startswith("国务院"))
    zsj = next(g for g in gw["ks"] if g["n"].startswith("国务院直属机构"))
    hg = next(n for n in zsj["ks"] if n["n"] == "海关总署")
    for g in hg.get("ks", []):
        for k in g.get("ks", []):
            if k.get("u"):
                k["u"] = ""
                cleared += 1
    # 5 老系统 depts
    dept_cleared = 0
    for k in [k for k in rules if k.isdigit() and len(k) == 6]:
        for d in rules[k].get("depts", []):
            u = d.get("u", "")
            if not u:
                continue
            if "检察院" in d["n"] and u not in jc_real:
                d["u"] = ""
                dept_cleared += 1
            elif "法院" in d["n"] and u not in court_real:
                d["u"] = ""
                dept_cleared += 1

    # 规则 method 同步
    for rk, r in rules.items():
        if rk.startswith(TIAO_KEYS) or rk.startswith("检察院系统"):
            if "域名探测" in (r.get("method") or "") or "拼音" in (r.get("method") or ""):
                r["method"] = (r.get("method") or "").split("（来源")[0] + \
                    "（官方名录页 HTML 提取待补，现有 URL 已按合规要求清除）"

    json.dump(tree, open("tree.json", "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    json.dump(rules, open("extraction_rules.json", "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    print(f"p66 完成：清除树节点 {cleared} 个 URL，清空 depts {dept_cleared} 处")


if __name__ == "__main__":
    main()
