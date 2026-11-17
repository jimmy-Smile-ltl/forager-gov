# -*- coding: utf-8 -*-
"""P48: 省级工会 URL 权威化（来源：全总官网「省级工会」栏目，用户提供完整名单）。

修正拼音探测的错误（上海 shzgh.org→shszgh.cn、吉林 jlzgh.org→jlzgh.cn、
湖南 hnzgh.org→hnghw.com、福建 fjgh.org→fj12351.cn 等），
补缺（安徽 ahghw.org.cn、青海 qhszgh.com、兵团 btftu.xjbt.gov.cn）。
同步位置：tree 省群团组「省总工会」、工会系统模块省级节点、相关规则。
"""
import json

AUTH = {
    "北京市": "http://www.bjzgh.org/",
    "天津市": "http://www.ftutj.cn/",
    "河北省": "http://www.hebgh.org.cn/",
    "山西省": "http://www.sxgh.org.cn/",
    "内蒙古自治区": "http://www.nmgzgh.org.cn/",
    "辽宁省": "http://www.lnszgh.org/",
    "吉林省": "http://www.jlzgh.cn/",
    "黑龙江省": "https://www.hljgh.org.cn/",
    "上海市": "https://www.shszgh.cn/",
    "江苏省": "http://www.jsgh.org/",
    "浙江省": "https://www.zjftu.org/",
    "安徽省": "https://www.ahghw.org.cn",
    "福建省": "https://www.fj12351.cn/",
    "江西省": "https://www.jxgh.org.cn",
    "山东省": "http://www.sdgh.org.cn/",
    "河南省": "http://www.hngh.org/",
    "湖北省": "http://www.hbzgh.org.cn/",
    "湖南省": "https://www.hnghw.com/#/home",
    "广东省": "http://www.gdftu.org.cn/",
    "广西壮族自治区": "http://www.gxftu.org/",
    "海南省": "http://www.hnszgh.org/web/default/index.jsp",
    "重庆市": "http://www.cqgh.org/",
    "四川省": "https://scgh.org",
    "贵州省": "http://www.guizgh.org.cn/f",
    "云南省": "https://ynzgh.org.cn/portal/#/home",
    "陕西省": "http://www.shxgh.org/",
    "甘肃省": "https://www.gsgh.org.cn",
    "青海省": "https://www.qhszgh.com/",
    "宁夏回族自治区": "http://www.nxzgh.org.cn/",
    "新疆维吾尔自治区": "http://www.xjzgh.org.cn/",
    "新疆生产建设兵团": "http://btftu.xjbt.gov.cn/",
    "西藏自治区": "https://www.xzgh.org.cn/",   # 全总名单未列，保留域名探测结果
}


def main():
    tree = json.load(open("tree.json", encoding="utf-8"))
    rules = json.load(open("extraction_rules.json", encoding="utf-8"))
    prov_g = next(g for g in tree["ks"] if g["n"].startswith("省级"))

    fixed = added = 0
    # 1) 省群团组「省总工会」
    for p in prov_g["ks"]:
        pname = p["n"]
        if pname not in AUTH:
            continue
        grp = next((k for k in p.get("ks", []) if k.get("c") == "群团组织"), None)
        if not grp:
            continue
        m = next((x for x in grp["ks"] if x["n"] == "省总工会"), None)
        if m:
            if m.get("u") != AUTH[pname]:
                if m.get("u"):
                    print(f"  修正 {pname}: {m['u']} -> {AUTH[pname]}")
                    fixed += 1
                else:
                    added += 1
                m["u"] = AUTH[pname]
            mkey = f"{pname}·省总工会"
            if mkey in rules:
                rules[mkey]["portal"] = AUTH[pname]
                rules[mkey]["sources"] = [AUTH[pname]]
                rules[mkey]["method"] = "独立门户（全总官网省级工会栏目权威来源）"
        # 群团组规则 depts 同步
        gkey = f"{pname}·{grp['n']}"
        if gkey in rules:
            for d in rules[gkey]["depts"]:
                if d["n"] == "省总工会":
                    d["u"] = AUTH[pname]

    # 2) 工会系统模块省级节点
    tiao = next((g for g in tree["ks"] if g["n"] == "条（垂直管理系统）"), None)
    if tiao:
        union = next((g for g in tiao["ks"] if g["n"].startswith("工会系统")), None)
        if union:
            acftu = next((g for g in union["ks"] if g["n"] == "中华全国总工会"), None)
            pgrp = next((g for g in acftu["ks"] if g["n"].startswith("省级工会")), None)
            for node in pgrp["ks"]:
                pname = node["n"].replace("总工会", "")
                if pname in AUTH:
                    node["u"] = AUTH[pname]
                    rkey = f"工会系统·{node['n']}"
                    if rkey in rules:
                        rules[rkey]["portal"] = AUTH[pname]
                        rules[rkey]["sources"] = [AUTH[pname]]
            # 更新省级工会组数量不变；组规则 depts 同步
            rkey = pgrp["n"]
            if rkey in rules:
                for d in rules[rkey]["depts"]:
                    pname = d["n"].replace("总工会", "")
                    if pname in AUTH:
                        d["u"] = AUTH[pname]

    json.dump(tree, open("tree.json", "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    json.dump(rules, open("extraction_rules.json", "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    print(f"p48 完成：修正 {fixed} 处错误 URL，补缺 {added} 处；"
          f"省级工会全量 {len(AUTH)}/32 权威化")


if __name__ == "__main__":
    main()
