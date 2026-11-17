# -*- coding: utf-8 -*-
"""P79: 药监系统条模块（中央—省两级体制）。

国家药监局 nmpa.gov.cn → 31 省药品监督管理局（24 个厅局存量 footer
真实采集 + 7 列名）。市县不设药监机构（职能由市县市场监管局承接）→
无市县层，这是药监体制的特殊性（非传统垂管，比垂管更彻底的上收）。
"""
import json
import re

PROV_ALIAS = {"北京": "北京市", "天津": "天津市", "河北": "河北省",
              "山西": "山西省", "内蒙古": "内蒙古自治区", "辽宁": "辽宁省",
              "吉林": "吉林省", "黑龙江": "黑龙江省", "上海": "上海市",
              "江苏": "江苏省", "浙江": "浙江省", "安徽": "安徽省",
              "福建": "福建省", "江西": "江西省", "山东": "山东省",
              "河南": "河南省", "湖北": "湖北省", "湖南": "湖南省",
              "广东": "广东省", "广西": "广西壮族自治区", "海南": "海南省",
              "重庆": "重庆市", "四川": "四川省", "贵州": "贵州省",
              "云南": "云南省", "西藏": "西藏自治区", "陕西": "陕西省",
              "甘肃": "甘肃省", "青海": "青海省", "宁夏": "宁夏回族自治区",
              "新疆": "新疆维吾尔自治区"}


def leaf(nm, cat, u, lv):
    return {"n": nm, "l": lv, "k": cat, "c": cat, "u": u,
            "x": "", "s": "", "m": ""}


def grp(nm, cat, kids):
    return {"n": nm, "l": "条", "k": "分组", "c": cat, "u": "",
            "x": "", "s": "", "m": "", "ks": kids}


def main():
    tree = json.load(open("tree.json", encoding="utf-8"))
    rules = json.load(open("extraction_rules.json", encoding="utf-8"))
    tiao = next(g for g in tree["ks"] if g["n"] == "条（垂直管理系统）")

    for k in [x for x in rules if x.startswith("药监系统")]:
        del rules[k]

    depts = [json.loads(l) for l in open("prov_depts.jsonl", encoding="utf-8")]
    yj = {}
    for r in depts:
        if "药监" in r.get("name", "") or "药品监督" in r.get("name", ""):
            yj[r["province"]] = r.get("portal_url", "")   # prov_depts 省名=简称

    prov_g = next(g for g in tree["ks"] if g["n"].startswith("省级"))
    root = leaf("国家药品监督管理局", "药监系统",
                "https://www.nmpa.gov.cn/", "中央")
    kids = []
    for p in prov_g["ks"]:
        pname = p["n"]
        if pname == "新疆生产建设兵团":
            continue
        short = re.sub(r"(维吾尔|壮族|回族)?自治区$|省$|市$", "", pname)
        kids.append(leaf(f"{pname}药品监督管理局", "药监系统",
                         yj.get(short, ""), "省"))
    sys_g = grp(f"药监系统（{len(kids) + 1}）", "药监系统", [root,
        grp(f"省级药品监督管理局（{len(kids)}）", "药监系统", kids)])
    tiao["ks"] = [g for g in tiao["ks"] if not g["n"].startswith("药监系统")]
    tiao["ks"].append(sys_g)

    def add(key, portal, method, depts):
        rules[key] = {
            "portal": portal, "method": method, "sources": [portal],
            "code": f'# -*- coding: utf-8 -*-\n"""{key} 提取规则。\n'
                    f'方法：{method}\n"""\n',
            "depts": depts, "cities": [],
        }

    n_url = sum(1 for k in kids if k["u"])
    add(sys_g["n"], "https://www.nmpa.gov.cn/",
        "药监体制=中央—省两级：国家药监局（市场监管总局管理的国家局）→ 31 省"
        "药品监督管理局（省市场监管局管理）；市县不设药监机构（职能由市县市场"
        "监管局承接）。省级 URL 来自省门户 footer 真实采集（%d/31 有官网，"
        "其余列名）；无市县层（体制使然，非采集遗漏）" % n_url,
        [{"n": m["n"], "u": m["u"], "o": i} for i, m in
         enumerate([root] + kids)])

    json.dump(tree, open("tree.json", "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    json.dump(rules, open("extraction_rules.json", "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    print(f"p79 完成：药监系统 省级 {len(kids)}（{n_url} 有官网），"
          f"rules 总数 {len(rules)}")


if __name__ == "__main__":
    main()
