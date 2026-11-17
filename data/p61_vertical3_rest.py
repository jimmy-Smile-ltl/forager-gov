# -*- coding: utf-8 -*-
"""P61: 补建三个垂管系统模块（证监会/移民管理/自然资源督察）。

证监会系统：中国证监会 csrc.gov.cn + 上海/深圳专员办（p60 渲染真实链接）
  + 36 派出机构证监局（官网为 JS 菜单加载，未提取到 → 列名，待专项渲染）
移民管理系统：国家移民管理局 nia.gov.cn + 31 出入境边防检查总站（列名，
  总站多数无独立公开门户）
自然资源督察系统：自然资源部 mnr.gov.cn + 9 督察局（列名，督察局无独立公开门户）
"""
import json

CSRC_PROVS = ["北京", "天津", "河北", "山西", "内蒙古", "辽宁", "吉林", "黑龙江",
              "上海", "江苏", "浙江", "安徽", "福建", "江西", "山东", "河南",
              "湖北", "湖南", "广东", "广西", "海南", "重庆", "四川", "贵州",
              "云南", "西藏", "陕西", "甘肃", "青海", "宁夏", "新疆",
              "大连", "宁波", "厦门", "青岛", "深圳"]
BJ_ZONGZHAN = ["北京", "天津", "河北", "山西", "内蒙古", "辽宁", "吉林", "黑龙江",
               "上海", "江苏", "浙江", "安徽", "福建", "江西", "山东", "河南",
               "湖北", "湖南", "广东", "广西", "海南", "重庆", "四川", "贵州",
               "云南", "西藏", "陕西", "甘肃", "青海", "宁夏", "新疆"]
DUCHA = ["北京", "沈阳", "上海", "南京", "济南", "广州", "武汉", "成都", "西安"]


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

    for pre in ("证监会系统", "移民管理系统", "自然资源督察系统"):
        for k in [x for x in rules if x.startswith(pre)]:
            del rules[k]

    # 证监会系统
    csrc_root = leaf("中国证券监督管理委员会", "证监会系统",
                     "http://www.csrc.gov.cn/", "中央")
    csrc_pq = [leaf(f"{p}证监局", "证监会系统", "", "省") for p in CSRC_PROVS]
    csrc_zy = [leaf("上海专员办", "证监会系统",
                    "https://www.csrc.gov.cn/shzyb/index.shtml", "中央"),
               leaf("深圳专员办", "证监会系统",
                    "https://www.csrc.gov.cn/szzyb/index.shtml", "中央")]
    csrc_sys = grp("证监会系统（39）", "证监会系统",
                   [csrc_root, grp(f"派出机构（{len(csrc_pq)}）", "证监会系统", csrc_pq),
                    grp(f"专员办（{len(csrc_zy)}）", "证监会系统", csrc_zy)])

    # 移民管理系统
    nia_root = leaf("国家移民管理局", "移民管理系统",
                    "https://www.nia.gov.cn/", "中央")
    nia_bj = [leaf(f"{p}出入境边防检查总站", "移民管理系统", "", "省")
              for p in BJ_ZONGZHAN]
    nia_sys = grp("移民管理系统（32）", "移民管理系统",
                  [nia_root, grp(f"出入境边防检查总站（{len(nia_bj)}）",
                                 "移民管理系统", nia_bj)])

    # 自然资源督察系统
    mnr_root = leaf("自然资源部", "自然资源督察系统",
                    "https://www.mnr.gov.cn/", "中央")
    dc = [leaf(f"国家自然资源督察{p}局", "自然资源督察系统", "", "省")
          for p in DUCHA]
    mnr_sys = grp("自然资源督察系统（10）", "自然资源督察系统",
                  [mnr_root, grp(f"督察局（{len(dc)}）", "自然资源督察系统", dc)])

    tiao["ks"] = [g for g in tiao["ks"]
                  if not g["n"].startswith(("证监会系统", "移民管理系统",
                                            "自然资源督察系统"))]
    tiao["ks"].extend([csrc_sys, nia_sys, mnr_sys])

    def add(key, portal, method, depts):
        rules[key] = {
            "portal": portal, "method": method, "sources": [portal],
            "code": f'# -*- coding: utf-8 -*-\n"""{key} 提取规则。\n'
                    f'方法：{method}\n来源：{portal}\n"""\n',
            "depts": depts, "cities": [],
        }

    for sys_g, portal, method in [
            (csrc_sys, "http://www.csrc.gov.cn/",
             "证监会官网派出机构（JS 菜单）+ 专员办栏目；证监局官网待专项渲染提取，"
             "未验证者列名（不猜域名）"),
            (nia_sys, "https://www.nia.gov.cn/",
             "移民局官网组织机构；边检总站多数无独立公开门户 → 列名"),
            (mnr_sys, "https://www.mnr.gov.cn/",
             "自然资源部官网派出机构；9 督察局无独立公开门户 → 列名")]:
        all_m = [m for g in sys_g["ks"] for m in g.get("ks", [])] + [sys_g["ks"][0]]
        add(sys_g["n"], portal, method,
            [{"n": m["n"], "u": m["u"], "o": i} for i, m in enumerate(all_m)])

    json.dump(tree, open("tree.json", "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    json.dump(rules, open("extraction_rules.json", "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    print("p61 完成：证监会39 / 移民管理32 / 自然资源督察10；"
          f"rules 总数 {len(rules)}")


if __name__ == "__main__":
    main()
