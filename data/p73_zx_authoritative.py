# -*- coding: utf-8 -*-
"""P73: 政协系统权威化重建（全国政协官网「地方政协」块真实 HTML）。

省级政协 31（权威 URL）+ 副省级城市政协 15（南京/厦门/哈尔滨/大连/宁波/
广州/成都/杭州/武汉/沈阳/济南/深圳/西安/长春/青岛）。
同步：块树省政协、政协系统模块、老系统市并列机关（副省级市）。
"""
import json
import re

VICE = {"南京": "南京市", "厦门": "厦门市", "哈尔滨": "哈尔滨市", "大连": "大连市",
        "宁波": "宁波市", "广州": "广州市", "成都": "成都市", "杭州": "杭州市",
        "武汉": "武汉市", "沈阳": "沈阳市", "济南": "济南市", "深圳": "深圳市",
        "西安": "西安市", "长春": "长春市", "青岛": "青岛市"}


def leaf(nm, cat, u, lv):
    return {"n": nm, "l": lv, "k": cat, "c": cat, "u": u,
            "x": "", "s": "", "m": ""}


def grp(nm, cat, kids):
    return {"n": nm, "l": "条", "k": "分组", "c": cat, "u": "",
            "x": "", "s": "", "m": "", "ks": kids}


def main():
    auth = json.load(open("zx_prov_auth.json", encoding="utf-8"))
    tree = json.load(open("tree.json", encoding="utf-8"))
    rules = json.load(open("extraction_rules.json", encoding="utf-8"))
    prov_g = next(g for g in tree["ks"] if g["n"].startswith("省级"))
    tiao = next(g for g in tree["ks"] if g["n"] == "条（垂直管理系统）")

    for k in [x for x in rules if x.startswith("政协系统")]:
        del rules[k]

    # 块树省政协权威化
    for p in prov_g["ks"]:
        pname = p["n"]
        if pname not in auth:
            continue
        par = next((k for k in p.get("ks", []) if k.get("c") == "并列机关"), None)
        if not par:
            continue
        m = next((x for x in par.get("ks", []) if "政协" in x["n"]), None)
        if m:
            m["u"] = auth[pname]
            mkey = f"{pname}·{m['n']}"
            if mkey in rules:
                rules[mkey]["portal"] = auth[pname]
                rules[mkey]["sources"] = [auth[pname]]
                rules[mkey]["method"] = ("独立门户（全国政协官网「地方政协」链接块"
                                         "真实 HTML 提取）")
    # 副省级市政协回填老系统
    for short, full in VICE.items():
        u = auth.get(short)
        if not u:
            continue
        prov = {"南京": "江苏省", "厦门": "福建省", "哈尔滨": "黑龙江省",
                "大连": "辽宁省", "宁波": "浙江省", "广州": "广东省",
                "成都": "四川省", "杭州": "浙江省", "武汉": "湖北省",
                "沈阳": "辽宁省", "济南": "山东省", "深圳": "广东省",
                "西安": "陕西省", "长春": "吉林省", "青岛": "山东省"}[short]
        pnode = next(p for p in prov_g["ks"] if p["n"] == prov)
        for top in pnode.get("ks", []):
            def walk(n):
                if n.get("l") == "市" and n["n"] == full:
                    par = next((g for g in n.get("ks", [])
                                if g.get("c") == "并列机关"), None)
                    if par:
                        m = next((x for x in par.get("ks", []) if "政协" in x["n"]), None)
                        if m:
                            m["u"] = u
                for k in n.get("ks", []):
                    walk(k)
            walk(top)

    def prov_of(full):
        return {"南京市": "江苏省", "厦门市": "福建省", "哈尔滨市": "黑龙江省",
                "大连市": "辽宁省", "宁波市": "浙江省", "广州市": "广东省",
                "成都市": "四川省", "杭州市": "浙江省", "武汉市": "湖北省",
                "沈阳市": "辽宁省", "济南市": "山东省", "深圳市": "广东省",
                "西安市": "陕西省", "长春市": "吉林省", "青岛市": "山东省"}[full]

    zx_prov = []
    prov_names = {p["n"] for p in prov_g["ks"]}
    for pname, u in sorted(auth.items()):
        if pname not in prov_names:
            continue    # 副省级城市简称（南京/厦门等）跳过，挂省级下
        kids = [leaf(f"{full}政协", "政协系统", auth[short], "市")
                for short, full in VICE.items()
                if auth.get(short) and prov_of(full) == pname]
        zx_prov.append({"n": f"{pname}政协", "l": "省",
                        "k": "政协系统", "c": "政协系统", "u": u,
                        "x": "", "s": "", "m": "", "ks": kids})

    central = next(g for g in tree["ks"] if g["n"].startswith("中央"))
    zgzx = next(g for g in central["ks"] if g["n"].startswith("中国人民政治协商会议"))
    zhuan = [{"n": k["n"], "l": "中央", "k": "政协系统", "c": "政协系统",
              "u": k.get("u", ""), "x": "", "s": "", "m": ""}
             for g in zgzx.get("ks", []) for k in g.get("ks", [])]
    root = leaf("中国人民政治协商会议全国委员会", "政协系统",
                "https://www.cppcc.gov.cn/", "中央")
    sys_g = grp(f"政协系统（{len(zx_prov) + 2}）", "政协系统",
                [root,
                 grp(f"专门委员会（{len(zhuan)}）", "政协系统", zhuan),
                 grp(f"省级政协（{len(zx_prov)}）", "政协系统", zx_prov)])
    tiao["ks"] = [g for g in tiao["ks"] if not g["n"].startswith("政协系统")]
    tiao["ks"].append(sys_g)

    def add(key, portal, method, depts):
        rules[key] = {
            "portal": portal, "method": method, "sources": [portal],
            "code": f'# -*- coding: utf-8 -*-\n"""{key} 提取规则。\n'
                    f'方法：{method}\n"""\n',
            "depts": depts, "cities": [],
        }

    all_m = [root] + zhuan + [x for p in zx_prov for x in ([p] + p.get("ks", []))]
    add(sys_g["n"], "https://www.cppcc.gov.cn/",
        "全国政协官网「地方政协」链接块真实 HTML 提取：31 省级政协 + "
        "15 副省级城市政协；市级政协待省政协官网「地方政协」导航提取",
        [{"n": m["n"], "u": m["u"], "o": i} for i, m in enumerate(all_m)])

    json.dump(tree, open("tree.json", "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    json.dump(rules, open("extraction_rules.json", "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    print(f"p73 完成：省级政协 {len(zx_prov)}，副省级市政协 15，"
          f"rules 总数 {len(rules)}")


if __name__ == "__main__":
    main()
