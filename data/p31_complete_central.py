# -*- coding: utf-8 -*-
"""P31: 中央政权架构完整性补缺（对照中央编办口径审计结果）。

新增/修改（tree.json）：
 1. 中共中央直属机构（16）→（20）：+ 中央网信办 / 中央对外联络部 /
    中央港澳工作办公室 / 中央档案馆（国家档案局）
 2. 部委管理的国家局（16）→（18）：+ 国家中医药管理局 / 国家密码管理局
 3. 国务院直属事业单位（7）→（8）：+ 中央广播电视总台
 4. 新板块「群团组织（21）」：中央编办管理的群众团体机关，20 个有官网 + 1 列名
 5. 新板块「民主党派中央（8）」：8 个民主党派中央

URL 均经 2026-10-30 连通性实测（HTTP HEAD/GET，200 或 WAF 拦截但站点真实）。
"""
import json

GROUPS = [
    ("群团组织（21）", "群团组织", [
        ("中华全国总工会", "https://www.acftu.org/"),
        ("共青团中央", "https://www.gqt.org.cn/"),
        ("中华全国妇女联合会", "https://www.women.org.cn/"),
        ("中国科学技术协会", "https://www.cast.org.cn/"),
        ("中国文学艺术界联合会", "https://www.cflac.org.cn/"),
        ("中国作家协会", "http://www.chinawriter.com.cn/"),
        ("中华全国工商业联合会", "https://www.acfic.org.cn/"),
        ("中华全国归国华侨联合会", "http://www.chinaql.org/"),
        ("中华全国台湾同胞联谊会", "http://www.tailian.org.cn/"),
        ("中国残疾人联合会", "https://www.cdpf.org.cn/"),
        ("中国国际贸易促进委员会", "https://www.ccpit.org/"),
        ("中国红十字会总会", "https://www.redcross.org.cn/"),
        ("中华职业教育社", "http://www.zhzjs.org.cn/"),
        ("中国法学会", "https://www.chinalaw.org.cn/"),
        ("中国人民对外友好协会", "https://www.cpaffc.org.cn/"),
        ("中华全国新闻工作者协会", "http://www.zgjx.cn/"),
        ("中国宋庆龄基金会", "https://www.sclf.org.cn/"),
        ("中国计划生育协会", "https://www.chinafpa.org.cn/"),
        ("黄埔军校同学会", "http://www.hjsd.org/"),
        ("欧美同学会", "https://www.wrsa.net/"),
        ("中国思想政治工作研究会", ""),   # 无独立官网 → 列名
    ]),
    ("民主党派中央（8）", "民主党派", [
        ("中国国民党革命委员会中央委员会", "http://www.minge.gov.cn/"),
        ("中国民主同盟中央委员会", "https://www.mmzy.org.cn/"),
        ("中国民主建国会中央委员会", "https://www.cndca.org.cn/"),
        ("中国民主促进会中央委员会", "https://www.mj.org.cn/"),
        ("中国农工民主党中央委员会", "http://www.ngd.org.cn/"),
        ("中国致公党中央委员会", "https://www.zg.org.cn/"),
        ("九三学社中央委员会", "http://www.93.gov.cn/"),
        ("台湾民主自治同盟中央委员会", "http://www.taimeng.gov.cn/"),
    ]),
]

NEW_PARTY_ORGANS = [
    ("中央网络安全和信息化委员会办公室", "https://www.cac.gov.cn/"),
    ("中央对外联络部", "https://www.idcpc.gov.cn/"),
    ("中央港澳工作办公室", "https://www.hmo.gov.cn/"),
    ("中央档案馆（国家档案局）", "https://www.saac.gov.cn/"),
]
NEW_GW_BUREAUS = [
    ("国家中医药管理局", "http://www.natcm.gov.cn/"),
    ("国家密码管理局", "https://www.sca.gov.cn/"),
]
NEW_GW_INST = [("中央广播电视总台", "https://www.cctv.com/")]

RENAMES = {
    "中央直属机构（16）": "中央直属机构（20）",
    "部委管理的国家局（16）": "部委管理的国家局（18）",
    "国务院直属事业单位（7）": "国务院直属事业单位（8）",
}


def leaf(nm, cat, u):
    return {"n": nm, "l": "中央", "k": cat, "c": cat, "u": u,
            "x": "", "s": "", "m": ""}


def main():
    tree = json.load(open("tree.json", encoding="utf-8"))
    central = next(g for g in tree["ks"] if g["n"].startswith("中央"))
    zg = next(g for g in central["ks"] if g["n"].startswith("中共中央"))
    gw = next(g for g in central["ks"] if g["n"].startswith("国务院"))

    # ---- 1-3: 既有组补成员 + 改名 ----
    for grp in zg["ks"] + gw["ks"]:
        if grp["n"] in RENAMES:
            grp["n"] = RENAMES[grp["n"]]
    zj_grp = next(g for g in zg["ks"] if g["n"].startswith("中央直属机构"))
    for nm, u in NEW_PARTY_ORGANS:
        zj_grp["ks"].append(leaf(nm, "党委机构", u))
    zj_grp["ks"] = [k for k in zj_grp["ks"] if not k["n"].startswith("国家互联网信息办公室")]  # 防重（国信办=网信办牌子，保留国务院办事机构处即可）
    gjj_grp = next(g for g in gw["ks"] if g["n"].startswith("部委管理的国家局"))
    for nm, u in NEW_GW_BUREAUS:
        gjj_grp["ks"].append(leaf(nm, "部门", u))
    sy_grp = next(g for g in gw["ks"] if g["n"].startswith("国务院直属事业单位"))
    for nm, u in NEW_GW_INST:
        sy_grp["ks"].append(leaf(nm, "部门", u))

    # ---- 4-5: 群团 + 民主党派新板块（置于最高检之后）----
    for gname, cat, members in GROUPS:
        grp = {"n": gname, "l": "中央", "k": "分组", "c": cat, "u": "",
               "x": "", "s": "", "m": "",
               "ks": [leaf(nm, cat, u) for nm, u in members]}
        central["ks"].append(grp)

    json.dump(tree, open("tree.json", "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    print("p31 完成：中央板块补缺已写入 tree.json")
    print("  中央顶层:", "、".join(g["n"] for g in central["ks"]))
    for gname, cat, members in GROUPS:
        print(f"  {gname}: {len(members)} 成员")


if __name__ == "__main__":
    main()
