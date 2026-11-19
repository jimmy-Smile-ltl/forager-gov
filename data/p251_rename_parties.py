# -*- coding: utf-8 -*-
"""P251: 民主党派省级组织改名（数据质量修复）。

问题（2026-11-19 巡检）：8 个民主党派的省级组织节点是 p113/p115 按
「{省名}{党派}省委会」模板合成的，如「北京市民革省委会」「河北省民主同盟省委会」。
两个毛病：
  1. 语序反了——官方写法是「民革北京市委员会」（党派简称在前，地名居中）；
  2. 直辖市/自治区带「省」字——「北京市民革省委会」「新疆维吾尔自治区民革省委会」
     都不成立，省委会只对省。
统一改为「{党派简称}{省名}委员会」（如 民革北京市委员会 / 民盟河北省委员会 /
九三学社浙江省委员会），与各党派官网省级组织名录的写法一致。

只改 l=省 且前缀恰为省级行政区全名的叶子；九三学社下面挂的 4 个基层组织
（上海交通大学/上海宝山/重庆沙坪坝/重庆渝中九三学社委员会）是 市级，保持不动。

同步：tree.json 节点名、site_registry.json 主键与 n 字段。干跑加 --dry。
"""
import json
import sys

PROV = ["北京市", "天津市", "河北省", "山西省", "内蒙古自治区", "辽宁省",
        "吉林省", "黑龙江省", "上海市", "江苏省", "浙江省", "安徽省",
        "福建省", "江西省", "山东省", "河南省", "湖北省", "湖南省",
        "广东省", "广西壮族自治区", "海南省", "重庆市", "四川省",
        "贵州省", "云南省", "西藏自治区", "陕西省", "甘肃省", "青海省",
        "宁夏回族自治区", "新疆维吾尔自治区"]

# 旧名里的党派段（p113 用 party.replace("中国","") 生成）→ 官方简称
ABBR = {"民革": "民革", "民主同盟": "民盟", "民主建国会": "民建",
        "民主促进会": "民进", "农工民主党": "农工党", "致公党": "致公党",
        "台盟": "台盟", "九三学社": "九三学社"}


def new_name(old):
    """{省名}{党派}省委会 / {省名}九三学社委员会 → {简称}{省名}委员会。"""
    for pv in PROV:
        if not old.startswith(pv):
            continue
        rest = old[len(pv):]
        for old_seg, ab in ABBR.items():
            if rest == old_seg + "省委会" and ab != "九三学社":
                return ab + pv + "委员会"
            if old_seg == "九三学社" and rest == "九三学社委员会":
                return "九三学社" + pv + "委员会"
    return ""


def walk(n):
    yield n
    for k in n.get("ks", []) or []:
        yield from walk(k)


def main(dry=False):
    tree = json.load(open("tree.json", encoding="utf-8"))
    central = next(g for g in tree["ks"] if g["n"].startswith("中央"))
    dp = next(x for x in central["ks"] if "民主党派" in x["n"])
    rename, skipped = {}, []
    for party in dp["ks"]:
        for n in walk(party):
            nm = n.get("n", "")
            if n.get("ks") or n.get("l") != "省":
                continue
            nn = new_name(nm)
            if nn:
                rename[nm] = nn
                n["n"] = nn
            elif nm and ("九三学社" in nm or "省委" in nm):
                skipped.append(nm)
    # registry 同步（主键 = 类别|全名）。必须原位重建 dict：pop 再插会把改名
    # 条目甩到文件末尾，26k 条 registry 全文重排（12 万行 diff），无法 review
    reg = json.load(open("site_registry.json", encoding="utf-8"))
    newreg, hits = {}, 0
    for k, v in reg.items():
        cat, _, nm = k.partition("|")
        nn = rename.get(nm) if cat == "民主党派" else None
        if nn and "民主党派|" + nn not in reg:
            v = dict(v)
            v["n"] = nn
            newreg["民主党派|" + nn] = v
            hits += 1
        else:
            newreg[k] = v
    reg = newreg
    # extraction_rules.json：民主党派规则条的 depts 名与 tree 同源，规则面板直接展示
    rules = json.load(open("extraction_rules.json", encoding="utf-8"))
    rhits = 0
    for v in rules.values():
        for d in v.get("depts") or []:
            nn = rename.get(d.get("n", ""))
            if nn:
                d["n"] = nn
                rhits += 1
    # xxgk_remainder.json：信息公开专栏待人工复核清单，[名, 候选URL, 原因]
    try:
        rem = json.load(open("xxgk_remainder.json", encoding="utf-8"))
        for row in rem:
            if isinstance(row, list) and row and row[0] in rename:
                row[0] = rename[row[0]]
    except Exception:
        rem = None
    print(f"tree 改名 {len(rename)} 个 / registry 同步 {hits} 条 / rules depts {rhits} 条")
    print("样例:", list(rename.items())[:3])
    if skipped:
        print("未改（非省级前缀）:", skipped)
    if dry:
        print("--dry 干跑，未写盘")
        return
    with open("tree.json", "w", encoding="utf-8") as f:
        json.dump(tree, f, ensure_ascii=False, indent=1)
        f.write("\n")
    with open("site_registry.json", "w", encoding="utf-8") as f:
        json.dump(reg, f, ensure_ascii=False, indent=1)
        f.write("\n")
    with open("extraction_rules.json", "w", encoding="utf-8") as f:
        json.dump(rules, f, ensure_ascii=False, indent=1)
        f.write("\n")
    if rem is not None:
        with open("xxgk_remainder.json", "w", encoding="utf-8") as f:
            json.dump(rem, f, ensure_ascii=False, indent=1)
            f.write("\n")


if __name__ == "__main__":
    main(dry="--dry" in sys.argv)
