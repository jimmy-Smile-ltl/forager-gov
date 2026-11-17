# -*- coding: utf-8 -*-
"""P81: 应急管理部内设机构补全（mem.gov.cn/jg/ 真实 HTML）。

内设机构 19 + 部管国家局 3（消防救援局/矿山安监局/地震局）+ 直属事业单位
国家安全生产应急救援中心。挂块树应急管理部节点下。
"""
import json

NSJG = [
    ("应急指挥中心（国家消防救援局指挥中心）", "./nsjg/yjzhzx/"),
    ("人事司（党委组织部）", "./nsjg/rss/"),
    ("队伍建设局", "./nsjg/jyxls/"),
    ("综合减灾和改革协调司", "./nsjg/fxjchzhjzs/"),
    ("救援协调和预案管理局", "./nsjg/jyxdhyaglj/"),
    ("风险监测和火灾综合防治司", "./nsjg/hzfzgls/"),
    ("防汛抗旱司", "./nsjg/fxkhs/"),
    ("地震和地质灾害救援司", "./nsjg/dzhdzzhjys/"),
    ("危险化学品安全监督管理一司", "./nsjg/wxhxpaqjdgls/"),
    ("安全生产执法和工贸安全监督管理局", "./nsjg/aqsczfj/"),
    ("安全生产综合协调司", "./nsjg/aqsczhxds/"),
    ("救灾和物资保障司", "./nsjg/jzhwzbzs/"),
    ("政策法规司", "./nsjg/zcfgs/"),
    ("国际合作和救援司（港澳台办公室）", "./nsjg/gjhzhjys/"),
    ("规划财务司", "./nsjg/ghcws/"),
    ("调查评估和统计司", "./nsjg/dcpghtjs/"),
    ("新闻宣传司（党委宣传部）", "./nsjg/xwxcs/"),
    ("科技和信息化司", "./nsjg/kjhxxhs/"),
    ("离退休干部局", "./nsjg/ltxgbj/"),
]
BUJG = [
    ("国家消防救援局", "http://www.119.gov.cn/"),
    ("国家矿山安全监察局", "https://www.chinamine-safety.gov.cn/"),
    ("中国地震局", "http://www.cea.gov.cn/"),
    ("国家安全生产应急救援中心", "http://www.nwserc.cn/"),
]
BASE = "https://www.mem.gov.cn/jg/"


def leaf(nm, cat, u, lv):
    return {"n": nm, "l": lv, "k": cat, "c": cat, "u": u,
            "x": "", "s": "", "m": ""}


def grp(nm, cat, kids):
    return {"n": nm, "l": "中央", "k": "分组", "c": cat, "u": "",
            "x": "", "s": "", "m": "", "ks": kids}


def main():
    tree = json.load(open("tree.json", encoding="utf-8"))
    rules = json.load(open("extraction_rules.json", encoding="utf-8"))
    central = next(g for g in tree["ks"] if g["n"].startswith("中央"))
    gw = next(g for g in central["ks"] if g["n"].startswith("国务院"))
    zcb = next(g for g in gw["ks"] if g["n"].startswith("国务院组成部门"))
    yj = next(n for n in zcb["ks"] if n["n"] == "应急管理部")

    yj["ks"] = [
        grp(f"内设机构（{len(NSJG)}）", "应急管理部内设机构",
            [leaf(n, "应急管理部内设机构", BASE + p, "中央") for n, p in NSJG]),
        grp(f"部管国家局与直属事业单位（{len(BUJG)}）", "应急管理部属机构",
            [leaf(n, "应急管理部属机构", u, "中央") for n, u in BUJG]),
    ]

    # 规则：应急管理部节点规则 depts 更新
    rk = "应急管理部"
    if rk in rules:
        all_m = [m for g in yj["ks"] for m in g["ks"]]
        rules[rk]["depts"] = [{"n": m["n"], "u": m["u"], "o": i}
                              for i, m in enumerate(all_m)]

    json.dump(tree, open("tree.json", "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    json.dump(rules, open("extraction_rules.json", "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    print(f"p81 完成：应急管理部内设 {len(NSJG)} + 部属 {len(BUJG)}")


if __name__ == "__main__":
    main()
