# -*- coding: utf-8 -*-
"""P69: 省级检察院 URL 权威化（最高检官网「全国检察院门户网站」区块）。

来源：https://www.spp.gov.cn/ 首页 link_con 区块（真实 HTML，用户提供）。
覆盖 32 省级单位；修正错误（广东 stjcy→gd、湖南 ldjcy→hn、吉林 jilin→jl）。
同步：块树并列机关、检察院系统模块省级节点、规则。
"""
import json

AUTH = {
    "北京市": "http://www.bjjc.gov.cn/bjoweb/",
    "天津市": "http://www.tj.jcy.gov.cn/",
    "河北省": "http://www.he.jcy.gov.cn/",
    "山西省": "http://www.sx.jcy.gov.cn/",
    "内蒙古自治区": "http://www.nm.jcy.gov.cn",
    "辽宁省": "http://www.ln.jcy.gov.cn/",
    "吉林省": "http://www.jl.jcy.gov.cn/",
    "黑龙江省": "https://www.hljjcy.gov.cn/",
    "上海市": "https://www.sh.jcy.gov.cn/",
    "江苏省": "http://www.jsjc.gov.cn/",
    "浙江省": "http://www.zjjcy.gov.cn/",
    "安徽省": "http://www.ah.jcy.gov.cn",
    "福建省": "http://www.fj.jcy.gov.cn/",
    "江西省": "http://www.jx.jcy.gov.cn/",
    "山东省": "http://www.sdjcy.gov.cn/",
    "河南省": "http://www.ha.jcy.gov.cn/",
    "湖北省": "http://www.hbjc.gov.cn/",
    "湖南省": "http://www.hn.jcy.gov.cn/",
    "广东省": "http://www.gd.jcy.gov.cn/",
    "广西壮族自治区": "http://www.gx.jcy.gov.cn",
    "海南省": "http://www.hi.jcy.gov.cn/",
    "重庆市": "http://www.cq.jcy.gov.cn/",
    "四川省": "http://www.sc.jcy.gov.cn/",
    "贵州省": "http://www.gz.jcy.gov.cn/",
    "云南省": "http://www.yn.jcy.gov.cn/",
    "西藏自治区": "http://www.xz.jcy.gov.cn/",
    "陕西省": "http://www.sn.jcy.gov.cn/",
    "甘肃省": "http://www.jcy.gansu.gov.cn/",
    "青海省": "http://www.qh.jcy.gov.cn/",
    "宁夏回族自治区": "http://www.nx.jcy.gov.cn/QJCY/index.html",
    "新疆维吾尔自治区": "http://www.xj.jcy.gov.cn/",
    "新疆生产建设兵团": "http://jcy.xjbt.gov.cn/",
}


def main():
    tree = json.load(open("tree.json", encoding="utf-8"))
    rules = json.load(open("extraction_rules.json", encoding="utf-8"))
    prov_g = next(g for g in tree["ks"] if g["n"].startswith("省级"))

    fixed = added = 0
    for p in prov_g["ks"]:
        pname = p["n"]
        if pname not in AUTH:
            continue
        par = next((k for k in p.get("ks", []) if k.get("c") == "并列机关"), None)
        if not par:
            continue
        m = next((x for x in par.get("ks", []) if "检察院" in x["n"]), None)
        if not m:
            continue
        if m.get("u") != AUTH[pname]:
            if m.get("u"):
                print(f"  修正 {pname}: {m['u']} -> {AUTH[pname]}")
                fixed += 1
            else:
                print(f"  补缺 {pname}: {AUTH[pname]}")
                added += 1
            m["u"] = AUTH[pname]
        mkey = f"{pname}·{m['n']}"
        if mkey in rules:
            rules[mkey]["portal"] = AUTH[pname]
            rules[mkey]["sources"] = [AUTH[pname]]
            rules[mkey]["method"] = "独立门户（最高检官网「全国检察院门户网站」区块真实 HTML 提取）"

    # 检察院系统模块省级节点同步
    tiao = next((g for g in tree["ks"] if g["n"] == "条（垂直管理系统）"), None)
    if tiao:
        jc_sys = next((g for g in tiao["ks"] if g["n"].startswith("检察院系统")), None)
        if jc_sys:
            gy = next((x for x in jc_sys["ks"] if x["n"].startswith("省级检察院")), None)
            if gy:
                for pn in gy["ks"]:
                    pname = pn["n"].replace("检察院", "")
                    if pname in AUTH:
                        pn["u"] = AUTH[pname]

    json.dump(tree, open("tree.json", "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    json.dump(rules, open("extraction_rules.json", "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    print(f"p69 完成：修正 {fixed}，补缺 {added}，省级检察院 {len(AUTH)}/32 权威化")


if __name__ == "__main__":
    main()
