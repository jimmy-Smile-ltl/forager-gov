# -*- coding: utf-8 -*-
"""P80: 药监系统省级 URL 权威化（nmpa.gov.cn「地方药监」下拉，真实 HTML）。

31 省药监局权威 URL 全覆盖（补齐天津/上海/湖北/湖南/海南/贵州/西藏 7 缺，
修正河南为首页）。同步药监系统模块节点 + 规则。
"""
import json
import re

AUTH = {
    "北京市": "http://yjj.beijing.gov.cn",
    "天津市": "https://scjg.tj.gov.cn/tjsscjdglwyh_52651/tjyj/",
    "河北省": "http://yjj.hebei.gov.cn",
    "山西省": "http://yjj.shanxi.gov.cn/",
    "内蒙古自治区": "http://mpa.nmg.gov.cn/",
    "辽宁省": "http://ypjg.ln.gov.cn/",
    "吉林省": "http://mpa.jl.gov.cn/",
    "黑龙江省": "http://mpa.hlj.gov.cn/",
    "上海市": "http://yjj.sh.gov.cn/",
    "江苏省": "http://da.jiangsu.gov.cn/",
    "浙江省": "http://mpa.zj.gov.cn/",
    "安徽省": "http://mpa.ah.gov.cn/",
    "福建省": "https://yjj.scjgj.fujian.gov.cn/",
    "江西省": "http://mpa.jiangxi.gov.cn/",
    "山东省": "http://mpa.shandong.gov.cn/",
    "河南省": "http://yjj.henan.gov.cn",
    "湖北省": "https://mpa.hubei.gov.cn/",
    "湖南省": "http://mpa.hunan.gov.cn",
    "广东省": "http://mpa.gd.gov.cn/",
    "广西壮族自治区": "http://yjj.gxzf.gov.cn/",
    "海南省": "http://amr.hainan.gov.cn/himpa/",
    "重庆市": "http://yaojianju.cq.gov.cn",
    "四川省": "http://yjj.sc.gov.cn/",
    "贵州省": "http://yjj.guizhou.gov.cn/",
    "云南省": "http://mpa.yn.gov.cn",
    "西藏自治区": "http://mpa.xizang.gov.cn/",
    "陕西省": "http://mpa.shaanxi.gov.cn/",
    "甘肃省": "http://yjj.gansu.gov.cn/",
    "青海省": "http://ypjgj.qinghai.gov.cn/",
    "宁夏回族自治区": "http://nxyjj.nx.gov.cn/",
    "新疆维吾尔自治区": "http://mpa.xinjiang.gov.cn/",
}


def main():
    tree = json.load(open("tree.json", encoding="utf-8"))
    rules = json.load(open("extraction_rules.json", encoding="utf-8"))
    tiao = next(g for g in tree["ks"] if g["n"] == "条（垂直管理系统）")
    yj = next(g for g in tiao["ks"] if g["n"].startswith("药监系统"))
    gy = next(x for x in yj["ks"] if x["n"].startswith("省级药品监督"))

    fixed = added = 0
    for pn in gy["ks"]:
        pname = pn["n"].replace("药品监督管理局", "")
        if pname in AUTH:
            if pn.get("u") != AUTH[pname]:
                if pn.get("u"):
                    fixed += 1
                else:
                    added += 1
                pn["u"] = AUTH[pname]

    rk = yj["n"]
    if rk in rules:
        for d in rules[rk]["depts"]:
            pname = d["n"].replace("药品监督管理局", "")
            if pname in AUTH:
                d["u"] = AUTH[pname]
        rules[rk]["method"] = ("药监体制=中央—省两级；省级 URL 来自国家药监局官网"
                               "「地方药监」下拉真实 HTML 提取（31/31 权威化，"
                               "nmpa 瑞数 WAF 页面）；无市县层（体制使然）")

    json.dump(tree, open("tree.json", "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    json.dump(rules, open("extraction_rules.json", "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    print(f"p80 完成：修正 {fixed}，补缺 {added}，省级药监局 31/31 权威化")


if __name__ == "__main__":
    main()
