# -*- coding: utf-8 -*-
"""P99: 证监会系统补全（csrc.gov.cn 首页「派出机构/会管单位」区块真实 HTML）。

派出机构 36（31 省区 + 5 计划单列市）URL 填充；专员办 2 校验；
会管单位 23 新增分组（交易所 8 + 基础设施 5 + 协会 4 + 其他 6）。
"""
import json
import re

PAICHU = {
    "北京": "beijing", "天津": "tianjin", "河北": "hebei", "山西": "shanxi",
    "内蒙古": "neimenggu", "辽宁": "liaoning", "吉林": "jilin",
    "黑龙江": "heilongjiang", "上海": "shanghai", "江苏": "jiangsu",
    "浙江": "zhejiang", "安徽": "anhui", "福建": "fujian", "江西": "jiangxi",
    "山东": "shandong", "河南": "henan", "湖北": "hubei", "湖南": "hunan",
    "广东": "guangdong", "广西": "guangxi", "海南": "hainan",
    "重庆": "chongqing", "四川": "sichuan", "贵州": "guizhou",
    "云南": "yunnan", "西藏": "xizang", "陕西": "shaanxi", "甘肃": "gansu",
    "青海": "qinghai", "宁夏": "ningxia", "新疆": "xinjiang",
    "深圳": "shenzhen", "大连": "dalian", "宁波": "ningbo",
    "厦门": "xiamen", "青岛": "qingdao",
}
BASE = "https://www.csrc.gov.cn/"

HUIGUAN = [
    ("上海证券交易所", "http://www.sse.com.cn"),
    ("深圳证券交易所", "http://www.szse.cn"),
    ("北京证券交易所", "http://www.bse.cn/"),
    ("上海期货交易所", "http://www.shfe.com.cn"),
    ("郑州商品交易所", "http://www.czce.com.cn"),
    ("大连商品交易所", "http://www.dce.com.cn"),
    ("中国金融期货交易所", "http://www.cffex.com.cn"),
    ("广州期货交易所", "http://www.gfex.com.cn/"),
    ("中国证券登记结算有限责任公司", "http://www.chinaclear.cn"),
    ("中国证券投资者保护基金有限责任公司", "http://www.sipf.com.cn"),
    ("中国期货市场监控中心有限责任公司", "http://www.cfmmc.com"),
    ("中证数据有限责任公司", "https://www.csdata.cn/"),
    ("全国中小企业股份转让系统有限责任公司", "http://www.neeq.com.cn"),
    ("中国证券业协会", "http://www.sac.net.cn"),
    ("中国期货业协会", "http://www.cfachina.org"),
    ("中国上市公司协会", "http://www.capco.org.cn/"),
    ("中国证券投资基金业协会", "http://www.amac.org.cn"),
    ("中证信息技术服务有限责任公司", "http://www.csits.org.cn/"),
    ("中证中小投资者服务中心有限责任公司", "http://www.isc.com.cn/"),
    ("中证商品指数有限责任公司", "http://www.ccidx.com"),
    ("中证金融研究院", "http://www.cifcm.cn"),
    ("资本市场学院", "http://www.ccmi.cn/"),
    ("中国资本市场学会", "https://www.ccms.org.cn"),
]

def leaf(nm, cat, u, lv):
    return {"n": nm, "l": lv, "k": cat, "c": cat, "u": u,
            "x": "", "s": "", "m": ""}

def main():
    tree = json.load(open("tree.json", encoding="utf-8"))
    rules = json.load(open("extraction_rules.json", encoding="utf-8"))
    tiao = next(g for g in tree["ks"] if g["n"] == "条（垂直管理系统）")
    zj = next(g for g in tiao["ks"] if g["n"].startswith("证监会系统"))

    # 派出机构
    pc = next(g for g in zj["ks"] if g["n"].startswith("派出机构"))
    filled = 0
    for k in pc["ks"]:
        core = re.sub(r"证监局$", "", k["n"])
        if core in PAICHU and not k.get("u"):
            k["u"] = BASE + PAICHU[core] + "/index.shtml"
            filled += 1
    # 专员办校验
    zb = next(g for g in zj["ks"] if g["n"].startswith("专员办"))
    for k in zb["ks"]:
        if "上海" in k["n"] and k.get("u") != BASE + "shzyb/index.shtml":
            k["u"] = BASE + "shzyb/index.shtml"
        if "深圳" in k["n"] and k.get("u") != BASE + "szzyb/index.shtml":
            k["u"] = BASE + "szzyb/index.shtml"

    # 会管单位分组
    grp = {"n": f"会管单位（{len(HUIGUAN)}）", "l": "条", "k": "分组",
           "c": "证监会系统", "u": "", "x": "", "s": "", "m": "",
           "ks": [leaf(nm, "证监会系统", u, "条") for nm, u in HUIGUAN]}
    zj["ks"] = [g for g in zj["ks"] if not g["n"].startswith("会管单位")]
    zj["ks"].append(grp)

    # rules
    rk = next(k for k in rules if k.startswith("证监会系统"))
    all_m = []
    def walk(n):
        if not n.get("ks"):
            all_m.append(n)
            return
        if all(x.get("l") != "省" for x in n["ks"]):
            all_m.append(n)
        for k in n["ks"]:
            walk(k)
    walk(zj)
    rules[rk]["depts"] = [{"n": m["n"], "u": m.get("u", ""), "o": i}
                          for i, m in enumerate(all_m)]
    rules[rk]["method"] = (
        "证监会体制=中央垂管：会机关 → 36 派出机构（31 省区证监局 + 深圳/大连/"
        "宁波/厦门/青岛 5 计划单列市证监局）+ 2 专员办 + 23 会管单位（交易所/"
        "结算登记/协会/研究院）。全部 URL 来自 csrc.gov.cn 首页「派出机构/会管"
        "单位」区块真实 HTML 提取（相对路径 /xx/index.shtml 基于根）。")
    json.dump(tree, open("tree.json", "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    json.dump(rules, open("extraction_rules.json", "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    n_u = sum(1 for m in all_m if m.get("u"))
    print(f"p99 完成：派出机构填充 {filled}，会管单位 {len(HUIGUAN)}，"
          f"系统节点 {len(all_m)}（{n_u} 有 URL）")

if __name__ == "__main__":
    main()
