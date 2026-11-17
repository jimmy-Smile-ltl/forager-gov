# -*- coding: utf-8 -*-
"""P5: 合并产出最终 CSV（全量名单 + 官网名单）。

输入: central.jsonl / province.jsonl / prov_depts.jsonl /
      city_portals.jsonl / county_portals.jsonl（已含 xxgk）/ divisions.json
输出: 政府信息公开全量名单.csv / 政府信息公开官网名单.csv
"""
import csv
import json
import re
import sys

sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
from common import curl_fetch_text

COLS = ["名称", "层级", "条块", "类别", "归属", "行政区划代码", "省份",
        "上级区划", "门户URL", "信息公开专栏URL", "专栏URL来源", "数据来源", "备注"]

XXGK_ROOT_RE = re.compile(r"^(https?://[^/]+)(/zfxxgkm?|/xxgk|/zwgk)(/.+)$")


def normalize_xxgk(u, src):
    """/xxgk/ 等根路径下的深链 → 若根可访问则收敛到根。"""
    m = XXGK_ROOT_RE.match(u or "")
    if not m:
        return u, src
    root = m.group(1) + m.group(2) + "/"
    try:
        html = curl_fetch_text(root, timeout=10)
        if html and len(html) > 500:
            return root, src
    except Exception:
        pass
    return u, src


def read_jsonl(fn):
    return [json.loads(l) for l in open(fn, encoding="utf-8")]


def row(name, level, tiao, cat, belong, code, prov, parent, portal, xxgk, src, dsrc, note=""):
    return [name, level, tiao, cat, belong, code, prov, parent, portal, xxgk, src, dsrc, note]


def main():
    central = read_jsonl("central.jsonl")
    provs = read_jsonl("province.jsonl")
    depts = read_jsonl("prov_depts.jsonl")
    cc = read_jsonl("city_county_final.jsonl")
    cities = [r for r in cc if r["level"] == "市"]
    counties = [r for r in cc if r["level"] == "县"]
    divs = json.load(open("divisions.json", encoding="utf-8"))

    div_by_code = {d["code"]: d for d in divs}
    rows = []

    # ---------- 中央 ----------
    rows.append(row("国务院（中央人民政府）", "中央", "人民政府", "国务院", "",
                    "100000", "中央", "", "https://www.gov.cn/",
                    "https://www.gov.cn/zhengce/xxgk/", "导航链接", "gov.cn中国政府网", ""))
    for r in central:
        name = r["name"]
        xxgk, src = normalize_xxgk(r.get("xxgk_url", ""), r.get("xxgk_src", ""))
        note = ""
        if not xxgk:
            if r.get("home_ok") is False:
                note = "专栏URL待核（站点反爬/WAF拦截）"
            else:
                note = "专栏URL待核（导航JS渲染）"
        if r.get("category") == "加挂牌子":
            note = (note + "；" if note else "") + f"加挂牌子，挂靠{r.get('parent','')}"
        if r["name"] == "国务院研究室":
            note = (note + "；" if note else "") + "无独立门户网站"
        rows.append(row(name, "中央", "部门", r["category"], r.get("parent") or "国务院",
                        "", "中央", "", r["portal_url"], xxgk, src,
                        r.get("source", "gov.cn国务院部门网站导航"), note))

    # ---------- 中央并列机关（党委领导下与国务院并列） ----------
    for nm, url, cat, note in [
        ("中共中央（党中央）", "", "党委领导机关", "无独立公开门户，列名参考"),
        ("全国人民代表大会（全国人大常委会）", "https://www.npc.gov.cn/", "全国人大", ""),
        ("中国人民政治协商会议全国委员会", "https://www.cppcc.gov.cn/", "全国政协", ""),
        ("国家监察委员会", "https://www.ccdi.gov.cn/", "国家监委", "与中央纪委合署办公"),
        ("最高人民法院", "https://www.court.gov.cn/", "最高人民法院", ""),
        ("最高人民检察院", "https://www.spp.gov.cn/", "最高人民检察院", ""),
    ]:
        rows.append(row(nm, "中央", "并列机关", cat, "", "", "中央", "", url, "", "", "gov.cn导航", note))

    # ---------- 海关总署直属海关（垂直管理） ----------
    import os as _os
    if _os.path.exists("customs_cities.json"):
        customs = json.load(open("customs_cities.json", encoding="utf-8"))
        for c in customs:
            rows.append(row(c["name"], "省", "海关", "直属海关（垂直管理）", "海关总署",
                            "", c["name"].replace("海关", ""), "", c["portal"], "", "",
                            "customs.gov.cn域名探测",
                            "海关总署垂直管理，与所在省人民政府并列"))

    # ---------- 省级（31+兵团） ----------
    prov_code_map = {d["name"]: d["code"] for d in divs if d["level"] in ("省", "特别行政区")}
    for r in provs:
        xxgk, src = normalize_xxgk(r.get("xxgk_url", ""), r.get("xxgk_src", ""))
        note = ""
        if not xxgk:
            note = "专栏URL待核（站点反爬/WAF拦截）"
        code = prov_code_map.get(r["name"], "")
        if r["name"] == "新疆生产建设兵团":
            code = "659000"
        rows.append(row(r["name"], "省", "人民政府", r["category"], "",
                        code, r["name"], "", r["portal_url"], xxgk, src,
                        r.get("source", "gov.cn地方政府网站导航"), note))

    # ---------- 省级并列机关（人大/政协/监委/法院/检察院） ----------
    if _os.path.exists("prov_parallel.jsonl"):
        for pr in read_jsonl("prov_parallel.jsonl"):
            nm = pr["name"]
            cat = pr["category"]
            if cat == "监委" and not ("监察委" in nm or "纪委" in nm):
                cat = "检察院"
            if cat == "检察院" and "监察" in nm:
                cat = "监委"
            rows.append(row(nm, "省", "并列机关", f"省{cat}", pr["province"], "",
                            pr["province"], "", pr.get("portal_url", ""), "", "",
                            "省门户footer采集", "与省人民政府并列，党委领导"))

    # ---------- 港澳台（手动，参考行） ----------
    rows.append(row("香港特别行政区政府", "特别行政区", "人民政府", "特别行政区政府", "",
                    "810000", "香港特别行政区", "", "https://www.gov.hk/", "", "",
                    "手动补充", "非内地政府信息公开体系，另行公开制度"))
    rows.append(row("澳门特别行政区政府", "特别行政区", "人民政府", "特别行政区政府", "",
                    "820000", "澳门特别行政区", "", "https://www.gov.mo/", "", "",
                    "手动补充", "非内地政府信息公开体系，另行公开制度"))
    rows.append(row("台湾省（待统一，无内地门户）", "省", "人民政府", "省级人民政府", "",
                    "710000", "台湾省", "", "", "", "",
                    "手动补充", "无内地政府门户；台湾地区县市政府门户仅列参考（内地网络不可达）"))
    if _os.path.exists("taiwan_counties.json"):
        for tc in json.load(open("taiwan_counties.json", encoding="utf-8")):
            rows.append(row(tc["name"], "港澳台", "人民政府", "台湾地区县市政府", "台湾省",
                            "", "台湾省", "台湾省", tc["portal"], "", "",
                            "公开域名列名", "台湾地区县市政府门户，内地网络一般无法访问，列名参考"))

    # ---------- 市/县 ----------
    for r in cities:
        d = div_by_code.get(r["code"], {})
        xxgk, src = normalize_xxgk(r.get("xxgk_url", ""), r.get("xxgk_src", ""))
        note = "" if r.get("portal_url") else f"门户URL未解析（{r.get('how','未匹配')}）"
        if r.get("zwfw_link"):
            note = (note + "；" if note else "") + "曾错配政务服务网链接，已移除"
        if r.get("portal_url") and not xxgk:
            note = (note + "；" if note else "") + "信息公开专栏URL待核"
        rows.append(row(r["name"], "市", "人民政府", "地级人民政府", "",
                        r["code"], r["province"], r["province"],
                        r.get("portal_url", ""), xxgk, src,
                        "省门户链式解析+pinyin/Bing兜底", note))
    for r in counties:
        d = div_by_code.get(r["code"], {})
        xxgk, src = normalize_xxgk(r.get("xxgk_url", ""), r.get("xxgk_src", ""))
        note = ""
        if not r.get("portal_url"):
            note = f"门户URL未解析（{r.get('how','未匹配')}）"
            if r.get("zwfw_link"):
                note += "；曾错配政务服务网链接，已移除"
        elif not xxgk:
            note = "信息公开专栏URL待核"
        if d.get("note") in ("省直辖", "直辖市辖区"):
            note = (note + "；" if note else "") + d["note"]
        rows.append(row(r["name"], "县", "人民政府", "县级人民政府", "",
                        r["code"], r["province"], r.get("parent", ""),
                        r.get("portal_url", ""), xxgk, src,
                        "市门户链式解析+pinyin/Bing兜底", note))

    # ---------- 省厅局 ----------
    for r in depts:
        xxgk, src = normalize_xxgk(r.get("xxgk_url", ""), r.get("xxgk_src", ""))
        note = ""
        if not r.get("portal_url"):
            note = "门户URL未解析（曾错配政务服务网）"
        elif not xxgk:
            note = "信息公开专栏URL待核"
        rows.append(row(r["name"], "省", "部门", r["category"], r["province"],
                        "", r["province"], "", r["portal_url"], xxgk, src,
                        "省政府门户组织机构页解析", note))

    # ---------- 输出 ----------
    dept_order = {(r["province"], r["name"]): r.get("order", 999) for r in depts}
    def sort_key(r):
        lvl = lvl_order.get(r[1], 9)
        prov = r[6] or ""
        if r[1] == "省" and r[2] == "部门":
            idx = f"{dept_order.get((r[6], r[0]), 999):04d}"
            return (lvl, prov, "0" + idx, r[0] or "")   # "0"前缀保证厅局排在同省人民政府/并列机关后
        return (lvl, prov, r[7] or "", r[0] or "")
    def write_csv(fn, data):
        with open(fn, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(COLS)
            w.writerows(data)

    # 排序：中央→省→市→县；同层级按归属/名称
    lvl_order = {"中央": 0, "特别行政区": 1, "省": 1, "市": 2, "县": 3}
    rows.sort(key=sort_key)

    write_csv("政府信息公开全量名单.csv", rows)
    hits = [r for r in rows if r[9]]
    write_csv("政府信息公开官网名单.csv", hits)

    n = len(rows)
    print(f"全量名单 {n} 行 | 官网名单（有专栏URL）{len(hits)} 行")
    for lv in ("中央", "省", "市", "县", "特别行政区"):
        lv_rows = [r for r in rows if r[1] == lv]
        lv_hit = sum(1 for r in lv_rows if r[9])
        print(f"  {lv}: {len(lv_rows)} 行, 专栏URL命中 {lv_hit}")


if __name__ == "__main__":
    main()
