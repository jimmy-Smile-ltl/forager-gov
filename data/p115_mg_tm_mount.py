# -*- coding: utf-8 -*-
"""P115: 民革省级挂载（24 有官网）+ 台盟省级全列名 + rules 同步。"""
import json
import re

MG = {
    "北京市": "http://bjmg.org.cn/",
    "天津市": "https://tjminge.gov.cn/",
    "河北省": "http://www.hebmg.gov.cn/",
    "上海市": "https://www.shmg.org.cn/",
    "江苏省": "https://jsmg.cn/",
    "浙江省": "http://www.zjmg.gov.cn/",
    "安徽省": "http://www.ahmg.gov.cn/",
    "福建省": "http://www.fjmg.gov.cn/",
    "江西省": "http://www.jxmg.gov.cn/",
    "山东省": "http://www.sdmg.gov.cn/",
    "河南省": "http://www.hnmg.gov.cn/",
    "湖北省": "http://www.hbmg.gov.cn/",
    "湖南省": "http://www.hnsmg.com/",
    "广东省": "http://www.gdmg.gov.cn/",
    "广西壮族自治区": "http://www.gxmg.gov.cn/",
    "海南省": "http://mg.hainan.gov.cn/",
    "重庆市": "http://www.cqmg.gov.cn/",
    "四川省": "http://scmg.org.cn/",
    "贵州省": "http://www.gzmg.gov.cn/",
    "云南省": "http://www.mgynsw.gov.cn/",
    "陕西省": "http://sxmgwyh.cn/",
    "甘肃省": "http://www.gansuminge.net/",
    "青海省": "http://www.qhminge.org/Qhmgpt/sjmg/indexSj.action",
    "新疆维吾尔自治区": "http://www.xjmg.org/",
}

PROV_FULL = ["北京市", "天津市", "河北省", "山西省", "内蒙古自治区", "辽宁省",
             "吉林省", "黑龙江省", "上海市", "江苏省", "浙江省", "安徽省",
             "福建省", "江西省", "山东省", "河南省", "湖北省", "湖南省",
             "广东省", "广西壮族自治区", "海南省", "重庆市", "四川省",
             "贵州省", "云南省", "西藏自治区", "陕西省", "甘肃省", "青海省",
             "宁夏回族自治区", "新疆维吾尔自治区"]

tree = json.load(open("tree.json", encoding="utf-8"))
central = next(g for g in tree["ks"] if g["n"].startswith("中央"))
dp_grp = next(x for x in central["ks"] if "民主党派" in x["n"])

def leaf(nm, lv, u):
    return {"n": nm, "l": lv, "k": "民主党派", "c": "民主党派",
            "u": u, "x": "", "s": "", "m": ""}

# 民革（节点名规范见 p251：党派简称在前，如「民革北京市委员会」）
mg = next(x for x in dp_grp["ks"] if x["n"].startswith("中国国民党革命委员会"))
mg["ks"] = [leaf(f"民革{pf}委员会", "省", MG.get(pf, "")) for pf in PROV_FULL]

# 台盟全列名
tm = next(x for x in dp_grp["ks"] if x["n"].startswith("台湾民主自治同盟"))
tm["ks"] = [leaf(f"台盟{pf}委员会", "省", "") for pf in PROV_FULL]

# rules 同步
rules = json.load(open("extraction_rules.json", encoding="utf-8"))
rk = next(k for k in rules if "民主党派" in k)
if rk not in rules:
    rk = None
all_m = []
def walk(n):
    if not n.get("ks"):
        all_m.append(n)
        return
    if all(x.get("l") != "中央" for x in n["ks"]):
        all_m.append(n)
    for k in n["ks"]:
        walk(k)
walk(dp_grp)
if rk:
    rules[rk]["depts"] = [{"n": m["n"], "u": m.get("u", ""), "o": i}
                          for i, m in enumerate(all_m)]
    rules[rk]["method"] = (
        "8 个民主党派中央官网首页「省级组织/地方组织」区块真实 HTML 提取："
        "民革 24/31（minge.gov.cn 地方组织区块）、民盟 27（mmzy）、民建 29"
        "（cndca）、民进 28（mj.org.cn，北京列名待查）、农工 28（ngd）、"
        "致公 20（zg.org.cn 致公党只在有组织的省份建站）、九三 30 省级 + "
        "151 市级（93.gov.cn cityName 区块全量）、台盟 0（官网无地方组织"
        "导航，全列名）。缺失省份=该党派无省级组织或无独立官网，列名。")

json.dump(tree, open("tree.json", "w", encoding="utf-8"),
          ensure_ascii=False, separators=(",", ":"))
json.dump(rules, open("extraction_rules.json", "w", encoding="utf-8"),
          ensure_ascii=False, separators=(",", ":"))
n_u = sum(1 for m in all_m if m.get("u"))
print(f"p115 完成：民主党派节点 {len(all_m)}（{n_u} 有 URL）")
