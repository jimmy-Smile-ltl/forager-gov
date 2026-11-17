# -*- coding: utf-8 -*-
"""P59: 构建 人大系统 + 政协系统 两条垂直系统模块。

数据（合规来源）：
  全国人大 npc.gov.cn / 全国政协 cppcc.gov.cn（块树并列机关权威 URL）
  专门委员会 10+10（块树已有）
  省级人大/政协 32+32（省门户 footer 真实链接提取）
市级人大/政协：待从省级人大/政协官网「地方人大/政协」栏目提取（后续）。
"""
import json

CODE = '''# -*- coding: utf-8 -*-
"""{title} 提取规则。

方法：{method}
来源页：{sources}
"""
import requests

URL = "{url}"
resp = requests.get(URL, timeout=15, verify=False,
                    headers={{"User-Agent": "Mozilla/5.0"}})
print("页面长度:", len(resp.content))
'''


def leaf(nm, cat, u, lv, x=""):
    return {"n": nm, "l": lv, "k": cat, "c": cat, "u": u, "x": x,
            "s": "", "m": ""}


def grp(nm, cat, kids):
    return {"n": nm, "l": "条", "k": "分组", "c": cat, "u": "",
            "x": "", "s": "", "m": "", "ks": kids}


def main():
    tree = json.load(open("tree.json", encoding="utf-8"))
    rules = json.load(open("extraction_rules.json", encoding="utf-8"))
    central = next(g for g in tree["ks"] if g["n"].startswith("中央"))
    prov_g = next(g for g in tree["ks"] if g["n"].startswith("省级"))
    tiao = next(g for g in tree["ks"] if g["n"] == "条（垂直管理系统）")

    for pre in ("人大系统", "政协系统"):
        for k in [x for x in rules if x.startswith(pre)]:
            del rules[k]

    rd = next(g for g in central["ks"] if g["n"].startswith("全国人民代表大会"))
    zx = next(g for g in central["ks"] if g["n"].startswith("中国人民政治协商会议"))
    rd_zhuan = [{"n": k["n"], "l": "中央", "k": "人大系统", "c": "人大系统",
                 "u": k.get("u", ""), "x": "", "s": "", "m": ""}
                for g in rd.get("ks", []) for k in g.get("ks", [])]
    zx_zhuan = [{"n": k["n"], "l": "中央", "k": "政协系统", "c": "政协系统",
                 "u": k.get("u", ""), "x": "", "s": "", "m": ""}
                for g in zx.get("ks", []) for k in g.get("ks", [])]

    rd_prov = []
    zx_prov = []
    for p in prov_g["ks"]:
        par = next((k for k in p.get("ks", []) if k.get("c") == "并列机关"), None)
        if not par:
            continue
        m_rd = next((x for x in par.get("ks", []) if "人大" in x["n"]), None)
        m_zx = next((x for x in par.get("ks", []) if "政协" in x["n"]), None)
        if m_rd:
            rd_prov.append({"n": f"{p['n']}人大", "l": "省",
                            "k": "人大系统", "c": "人大系统",
                            "u": m_rd.get("u", ""), "x": "", "s": "", "m": ""})
        if m_zx:
            zx_prov.append({"n": f"{p['n']}政协", "l": "省",
                            "k": "政协系统", "c": "政协系统",
                            "u": m_zx.get("u", ""), "x": "", "s": "", "m": ""})

    rd_root = leaf("全国人民代表大会", "人大系统", "https://www.npc.gov.cn/", "中央")
    zx_root = leaf("中国人民政治协商会议全国委员会", "政协系统",
                   "https://www.cppcc.gov.cn/", "中央")
    rd_sys = grp(f"人大系统（{len(rd_prov) + 2}）", "人大系统",
                 [rd_root,
                  grp(f"专门委员会（{len(rd_zhuan)}）", "人大系统", rd_zhuan),
                  grp(f"省级人大（{len(rd_prov)}）", "人大系统", rd_prov)])
    zx_sys = grp(f"政协系统（{len(zx_prov) + 2}）", "政协系统",
                 [zx_root,
                  grp(f"专门委员会（{len(zx_zhuan)}）", "政协系统", zx_zhuan),
                  grp(f"省级政协（{len(zx_prov)}）", "政协系统", zx_prov)])

    tiao["ks"] = [g for g in tiao["ks"]
                  if not g["n"].startswith(("人大系统", "政协系统"))]
    tiao["ks"].extend([rd_sys, zx_sys])

    def add(key, portal, method, depts, url):
        rules[key] = {
            "portal": portal, "method": method, "sources": [portal],
            "code": CODE.format(title=key, method=method, sources=portal, url=url),
            "depts": depts, "cities": [],
        }

    rd_all = [rd_root] + rd_zhuan + rd_prov
    zx_all = [zx_root] + zx_zhuan + zx_prov
    add(f"人大系统（{len(rd_prov) + 2}）", "https://www.npc.gov.cn/",
        "全国人大官网 + 专门委员会（块树）+ 省级人大（省门户 footer 真实提取）；"
        "市级人大待省人大官网地方人大栏目提取",
        [{"n": m["n"], "u": m["u"], "o": i} for i, m in enumerate(rd_all)],
        "https://www.npc.gov.cn/")
    add(f"政协系统（{len(zx_prov) + 2}）", "https://www.cppcc.gov.cn/",
        "全国政协官网 + 专门委员会（块树）+ 省级政协（省门户 footer 真实提取）；"
        "市级政协待省政协官网地方政协栏目提取",
        [{"n": m["n"], "u": m["u"], "o": i} for i, m in enumerate(zx_all)],
        "https://www.cppcc.gov.cn/")
    for m in rd_prov + zx_prov:
        add(f"{m['k'] == '人大系统' and '省级人大' or '省级政协'}（{len(rd_prov) if m['k']=='人大系统' else len(zx_prov)}）·{m['n']}",
            m["u"] or ("https://www.npc.gov.cn/" if m["k"] == "人大系统" else "https://www.cppcc.gov.cn/"),
            "省门户 footer 真实链接提取" + ("；无独立公开门户 → 列名" if not m["u"] else ""),
            [{"n": m["n"], "u": m["u"], "o": 0}],
            m["u"] or "https://www.npc.gov.cn/")

    json.dump(tree, open("tree.json", "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    json.dump(rules, open("extraction_rules.json", "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    print(f"p59 完成：人大系统 {len(rd_all)} 成员，政协系统 {len(zx_all)} 成员，"
          f"rules 总数 {len(rules)}")


if __name__ == "__main__":
    main()
