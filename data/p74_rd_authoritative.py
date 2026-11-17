# -*- coding: utf-8 -*-
"""P74: 人大系统权威化重建（中国人大网「地方人大网站」页真实 HTML）。

来源：http://www.npc.gov.cn/npc/c191/c2602/c2558/（31 省级人大；兵团无→列名）。
同步：块树省人大、人大系统模块、规则。
"""
import json

AUTH = {
    "北京市": "http://www.bjrd.gov.cn/",
    "天津市": "http://www.tjrd.gov.cn/",
    "河北省": "http://www.hbrd.gov.cn/index.shtml",
    "山西省": "http://www.sxpc.gov.cn/",
    "内蒙古自治区": "http://www.nmgrd.gov.cn/",
    "辽宁省": "http://www.lnrd.gov.cn/",
    "吉林省": "http://www.jlrd.gov.cn/",
    "黑龙江省": "https://www.hljrd.gov.cn/",
    "上海市": "http://www.shrd.gov.cn/",
    "江苏省": "http://www.jsrd.gov.cn/",
    "浙江省": "http://www.zjrd.gov.cn/",
    "安徽省": "http://www.ahrd.gov.cn/",
    "福建省": "http://www.fjrd.gov.cn/",
    "江西省": "http://www.jxrd.gov.cn/",
    "山东省": "http://www.sdrd.gov.cn/",
    "河南省": "http://www.henanrd.gov.cn/",
    "湖北省": "http://www.hppc.gov.cn/",
    "湖南省": "http://www.hnrd.gov.cn/",
    "广东省": "http://www.rd.gd.cn/",
    "广西壮族自治区": "http://dhzt.gxrd.gov.cn/",
    "海南省": "http://www.hainanpc.gov.cn/",
    "重庆市": "https://www.cqrd.gov.cn/",
    "四川省": "http://www.scspc.gov.cn/",
    "贵州省": "http://www.gzrd.gov.cn/",
    "云南省": "http://www.ynrd.gov.cn/",
    "西藏自治区": "http://www.xizangrd.gov.cn/",
    "陕西省": "http://www.sxrd.gov.cn/",
    "甘肃省": "http://www.gsrdw.gov.cn/",
    "青海省": "http://www.qhrd.gov.cn",
    "宁夏回族自治区": "http://www.nxrd.gov.cn/",
    "新疆维吾尔自治区": "http://www.xjpcsc.gov.cn/",
}


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

    for k in [x for x in rules if x.startswith("人大系统")]:
        del rules[k]

    for p in prov_g["ks"]:
        pname = p["n"]
        if pname not in AUTH:
            continue
        par = next((k for k in p.get("ks", []) if k.get("c") == "并列机关"), None)
        if not par:
            continue
        m = next((x for x in par.get("ks", []) if "人大" in x["n"]), None)
        if m:
            m["u"] = AUTH[pname]
            mkey = f"{pname}·{m['n']}"
            if mkey in rules:
                rules[mkey]["portal"] = AUTH[pname]
                rules[mkey]["sources"] = [AUTH[pname]]
                rules[mkey]["method"] = ("独立门户（中国人大网「地方人大网站」页"
                                         "真实 HTML 提取）")

    central = next(g for g in tree["ks"] if g["n"].startswith("中央"))
    zgrd = next(g for g in central["ks"] if g["n"].startswith("全国人民代表大会"))
    zhuan = [{"n": k["n"], "l": "中央", "k": "人大系统", "c": "人大系统",
              "u": k.get("u", ""), "x": "", "s": "", "m": ""}
             for g in zgrd.get("ks", []) for k in g.get("ks", [])]
    root = leaf("全国人民代表大会", "人大系统", "https://www.npc.gov.cn/", "中央")
    rd_prov = [{"n": f"{p}人大", "l": "省", "k": "人大系统", "c": "人大系统",
                "u": u, "x": "", "s": "", "m": ""}
               for p, u in sorted(AUTH.items())]
    sys_g = grp(f"人大系统（{len(rd_prov) + 2}）", "人大系统",
                [root,
                 grp(f"专门委员会（{len(zhuan)}）", "人大系统", zhuan),
                 grp(f"省级人大（{len(rd_prov)}）", "人大系统", rd_prov)])
    tiao["ks"] = [g for g in tiao["ks"] if not g["n"].startswith("人大系统")]
    tiao["ks"].append(sys_g)

    def add(key, portal, method, depts):
        rules[key] = {
            "portal": portal, "method": method, "sources": [portal],
            "code": f'# -*- coding: utf-8 -*-\n"""{key} 提取规则。\n'
                    f'方法：{method}\n"""\n',
            "depts": depts, "cities": [],
        }

    all_m = [root] + zhuan + rd_prov
    add(sys_g["n"], "https://www.npc.gov.cn/",
        "中国人大网「地方人大网站」页真实 HTML 提取：31 省级人大权威 URL"
        "（兵团无独立门户→列名）；市级人大待省人大官网「市县人大」导航提取",
        [{"n": m["n"], "u": m["u"], "o": i} for i, m in enumerate(all_m)])

    json.dump(tree, open("tree.json", "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    json.dump(rules, open("extraction_rules.json", "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    print(f"p74 完成：省级人大 {len(rd_prov)}，rules 总数 {len(rules)}")


if __name__ == "__main__":
    main()
