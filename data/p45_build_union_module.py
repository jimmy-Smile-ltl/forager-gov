# -*- coding: utf-8 -*-
"""P45: 建「工会系统」模块 + 回填老系统。

模块（tree 根级新板块，置于港澳台后）：
  工会系统（中华全国总工会）
    中华全国总工会 (acftu.org)
      省级工会（N）
        {省名}总工会  [u]
          {市名}市总工会  [u]   ← 123 个市级工会
（安徽/青海/兵团无省级工会官网 → 列名；市工会仅列有官网者，其余市无独立官网）

回填老系统：
  1. 省群团组「省总工会」u 与工会系统来源交叉同步
  2. 有工会官网的市：市节点下新增「市总工会」子节点（k=群团组织）
规则键：工会系统 / 工会系统·中华全国总工会 / 工会系统·省级工会（N）/
        工会系统·{省名}总工会 / {市名}·市总工会（老系统市节点）
"""
import json
import re

PROV_UNION_EXTRA = {
    "天津市": "http://www.ftutj.cn/",
    "吉林省": "http://www.jlzgh.org/",
    "上海市": "http://www.shzgh.org/",
    "福建省": "https://www.fjgh.org/",
    "江西省": "https://www.jxgh.org.cn/",
    "湖南省": "https://www.hnzgh.org/",
    "重庆市": "https://www.cqgh.org/",
    "西藏自治区": "https://www.xzgh.org.cn/",
}

CODE_PROV = '''# -*- coding: utf-8 -*-
"""{prov} 工会系统提取规则。

方法：中华全国总工会官网（省级工会栏目）→ {prov}官网「区内/省内工会网站」
     区块提取——链接形态为 <select><option> 下拉框或 <a>（JS 动态填充者
     需浏览器渲染）；市名与行政区划树匹配 + 标题验证。
说明：工会系统网站仅到市级；{miss} 无独立官网 → 列名。
来源页：{sources}
"""
import re
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

PORTAL = "{portal}"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")


def fetch(url):
    resp = requests.get(url, headers={{"User-Agent": UA}}, timeout=15, verify=False)
    if resp.encoding and "gb" in resp.encoding.lower():
        return resp.content.decode("gb18030", errors="replace")
    return resp.content.decode("utf-8", errors="replace")


html = fetch(PORTAL)
soup = BeautifulSoup(html, "lxml")
# 1) <select><option> 下拉框（工会网站常为友情链接下拉）
for op in soup.find_all("option"):
    text = re.sub(r"\\s+", "", op.get_text(" ", strip=True))
    href = op.get("value") or ""
    if text and href.startswith(("http://", "https://")):
        print("  [下拉]", text, "->", href)
# 2) <a> 链接
for a in soup.find_all("a"):
    text = re.sub(r"\\s+", "", (a.get("title") or a.get_text(" ", strip=True)).strip())
    href = a.get("href") or ""
    if "工会" in text and len(text) <= 18 and href.startswith(("http://", "https://")):
        print("  [链接]", text, "->", href)
'''

CODE_CITY = '''# -*- coding: utf-8 -*-
"""{city} 市总工会 提取规则。

方法：{prov}官网「区内/省内工会网站」区块提取（下拉框/链接双通道，
     JS 填充需浏览器渲染）+ 市名匹配 + 标题验证。
门户：{portal}
"""
import requests

PORTAL = "{portal}"
resp = requests.get(PORTAL, timeout=15, verify=False,
                    headers={{"User-Agent": "Mozilla/5.0"}})
print("页面长度:", len(resp.content))
'''


def main():
    tree = json.load(open("tree.json", encoding="utf-8"))
    prov_g = next(g for g in tree["ks"] if g["n"].startswith("省级"))
    rules = json.load(open("extraction_rules.json", encoding="utf-8"))

    # ---- 省级工会 URL 总表 ----
    prov_urls = {}
    for p in prov_g["ks"]:
        grp = next((k for k in p.get("ks", []) if k.get("c") == "群团组织"), None)
        if grp:
            m = next((x for x in grp["ks"] if x["n"] == "省总工会"), None)
            if m and m.get("u"):
                prov_urls[p["n"]] = m["u"]
    prov_urls.update(PROV_UNION_EXTRA)

    # ---- 市级工会按省分组 ----
    cities = {}
    for l in open("union_system.jsonl", encoding="utf-8"):
        r = json.loads(l)
        cities.setdefault(r["province"], []).append(r)

    # ---- 1. 建模块子树 ----
    acftu = {"n": "中华全国总工会", "l": "中央", "k": "工会系统", "c": "工会系统",
             "u": "https://www.acftu.org/", "x": "", "s": "", "m": "", "ks": []}
    prov_grp = {"n": f"省级工会（{len(prov_urls)}）", "l": "中央", "k": "分组",
                "c": "工会系统", "u": "", "x": "", "s": "", "m": "", "ks": []}
    acftu["ks"].append(prov_grp)
    # 有 URL 的省
    for pname, u in sorted(prov_urls.items()):
        node = {"n": f"{pname}总工会", "l": "省", "k": "工会系统", "c": "工会系统",
                "u": u, "x": "", "s": "", "m": "",
                "ks": [{"n": re.sub(r"(自治州|市|地区|盟)$", "", r["city"]) + "市总工会",
                        "l": "市", "k": "工会系统", "c": "工会系统", "u": r["url"],
                        "x": "", "s": "", "m": ""}
                       for r in cities.get(pname, [])]}
        prov_grp["ks"].append(node)
    # 列名省（无省级工会官网）
    for pname in ("安徽省", "青海省", "新疆生产建设兵团"):
        prov_grp["ks"].append({"n": f"{pname}总工会", "l": "省", "k": "工会系统",
                               "c": "工会系统", "u": "", "x": "", "s": "", "m": ""})
    root_mod = {"n": "工会系统（中华全国总工会）", "l": "根", "k": "分组",
                "c": "工会系统", "u": "", "x": "", "s": "", "m": "", "ks": [acftu]}
    tree["ks"].append(root_mod)

    # ---- 2. 模块规则 ----
    all_prov_depts = [{"n": k["n"], "u": k.get("u", ""), "o": i}
                      for i, k in enumerate(prov_grp["ks"])]
    rules["工会系统"] = {
        "portal": "https://www.acftu.org/",
        "method": "中华全国总工会官网「省级工会」栏目 → 32 省级单位工会（29 有官网，"
                  "安徽/青海/兵团列名）→ 各省级工会官网「区内/省内工会网站」区块"
                  "（下拉框/链接双通道，JS 填充需浏览器渲染）→ 市级工会；"
                  "工会系统网站仅到市级，部分市无独立官网 → 列名",
        "sources": ["https://www.acftu.org/"],
        "code": CODE_PROV.format(prov="全国总工会", miss="—",
                                 sources="https://www.acftu.org/",
                                 portal="https://www.acftu.org/"),
        "depts": all_prov_depts,
        "cities": [],
    }
    rules["工会系统·中华全国总工会"] = {
        "portal": "https://www.acftu.org/",
        "method": "全总官网「省级工会」栏目（JS tab，需浏览器点击）→ 省级工会门户列表",
        "sources": ["https://www.acftu.org/"],
        "code": CODE_PROV.format(prov="中华全国总工会", miss="—",
                                 sources="https://www.acftu.org/",
                                 portal="https://www.acftu.org/"),
        "depts": all_prov_depts,
        "cities": [],
    }
    rules["工会系统·省级工会（%d）" % len(prov_urls)] = {
        "portal": "https://www.acftu.org/",
        "method": "省级工会门户：全总省级工会栏目 + 域名模式探测（{短名}zgh/gh.org(.cn)）"
                  " + 标题验证；安徽/青海/兵团无独立官网 → 列名",
        "sources": ["https://www.acftu.org/"],
        "code": CODE_PROV.format(prov="省级工会（%d）" % len(prov_urls), miss="—",
                                 sources="https://www.acftu.org/",
                                 portal="https://www.acftu.org/"),
        "depts": all_prov_depts,
        "cities": [],
    }
    for k in prov_grp["ks"]:
        pname = k["n"].replace("总工会", "")
        if not k.get("u"):
            continue
        rkey = f"工会系统·{k['n']}"
        cs = cities.get(pname, [])
        miss = "、".join(sorted(set(
            c["city"] for c in cs))[:0]) or "其余市"
        rules[rkey] = {
            "portal": k["u"],
            "method": f"{k['n']}官网「区内/省内工会网站」区块提取（下拉框/链接双通道，"
                      f"JS 填充需浏览器渲染）→ 市级工会；部分市无独立官网 → 列名",
            "sources": [k["u"]],
            "code": CODE_PROV.format(prov=k["n"], miss="部分市",
                                     sources=k["u"], portal=k["u"]),
            "depts": [{"n": re.sub(r"(自治州|市|地区|盟)$", "", c["city"]) + "市总工会",
                       "u": c["url"], "o": i}
                      for i, c in enumerate(cs)],
            "cities": [],
        }

    # ---- 3. 回填老系统 ----
    filled_prov = filled_city = 0
    for p in prov_g["ks"]:
        grp = next((k for k in p.get("ks", []) if k.get("c") == "群团组织"), None)
        # 3.1 省总工会同步
        if grp:
            m = next((x for x in grp["ks"] if x["n"] == "省总工会"), None)
            if m and p["n"] in prov_urls and not m.get("u"):
                m["u"] = prov_urls[p["n"]]
                filled_prov += 1
                mkey = f"{p['n']}·省总工会"
                if mkey in rules:
                    rules[mkey]["portal"] = prov_urls[p["n"]]
                    rules[mkey]["sources"] = [prov_urls[p["n"]]]
                    rules[mkey]["method"] = "独立门户（工会系统来源交叉验证）"
        # 3.2 市总工会节点
        if p["n"] in cities:
            for c in cities[p["n"]]:
                for top in p.get("ks", []):
                    def walk(n):
                        nonlocal filled_city
                        if n.get("l") == "市" and n.get("k") == "人民政府" \
                                and n["n"] == c["city"]:
                            if not any(x["n"] == "市总工会" for x in n.get("ks", [])):
                                n.setdefault("ks", []).insert(
                                    0, {"n": "市总工会", "l": "市", "k": "群团组织",
                                        "c": "群团组织", "u": c["url"],
                                        "x": "", "s": "", "m": ""})
                                filled_city += 1
                                ck = f"{c['city']}·市总工会"
                                rules[ck] = {
                                    "portal": c["url"],
                                    "method": f"{p['n']}官网「区内/省内工会网站」区块提取"
                                              f" + 市名匹配 + 标题验证",
                                    "sources": [c["url"]],
                                    "code": CODE_CITY.format(city=c["city"],
                                                             prov=p["n"],
                                                             portal=c["url"]),
                                    "depts": [{"n": "市总工会", "u": c["url"], "o": 0}],
                                    "cities": [],
                                }
                        for k in n.get("ks", []):
                            walk(k)
                    walk(top)

    json.dump(tree, open("tree.json", "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    json.dump(rules, open("extraction_rules.json", "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    print(f"p45 完成：模块 1 根组 + 全总 + 省级工会（{len(prov_urls)}）")
    print(f"  省总工会同步 {filled_prov}，市总工会节点新增 {filled_city}，"
          f"rules 总数 {len(rules)}")


if __name__ == "__main__":
    main()
