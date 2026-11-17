# -*- coding: utf-8 -*-
"""P56: 铁路系统模块重建 —— 政府侧 + 企业侧（全部真实 HTML 提取）。

政府侧（国家铁路局 nra.gov.cn/zzjg/ 真实链接）：
  局领导7（党组书记局长/4副局长/总工程师/安全总监）、内设机构8、地区监管局8、
  事业单位7；信息公开专栏 /xxgk/gkml/。
企业侧（nra.gov.cn 站内与国铁集团官网真实链接）：国铁集团、经规院、铁科院、
  中国铁建、12306、人民铁道网、广州局、南宁局、中国铁设、中铁投资、地方铁路协会
  = 11 个有官网；18 个铁路局集团公司中 16 个官网未在权威页面出现 → 列名
  （待国铁集团「所属企业」栏目提取，不猜域名）。
"""
import json

CODE = '''# -*- coding: utf-8 -*-
"""{title} 提取规则。

方法：国家铁路局官网 nra.gov.cn「组织机构 /zzjg/」页真实 HTML 提取
     （内设机构/地区监管局/事业单位链接列表）；
     企业侧取 nra 网站地图「铁路相关企业」与国铁集团官网链接。
来源页：https://www.nra.gov.cn/zzjg/
"""
import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

URL = "{url}"
html = requests.get(URL, timeout=15, verify=False,
                    headers={{"User-Agent": "Mozilla/5.0"}}).content \
    .decode("utf-8", errors="replace")
soup = BeautifulSoup(html, "lxml")
for a in soup.find_all("a"):
    t = re.sub(r"\\s+", "", (a.get("title") or a.get_text(" ", strip=True)).strip())
    h = a.get("href") or ""
    if ("监管局" in t or "司" in t or "中心" in t or "集团" in t) and len(t) <= 30:
        print("  ", t, "->", urljoin(URL, h))
'''

LEADERS = [
    ("党组书记、局长", "https://www.nra.gov.cn/zzjg/jld/"),
    ("党组成员、副局长（4）", "https://www.nra.gov.cn/zzjg/jld/"),
    ("总工程师", "https://www.nra.gov.cn/zzjg/zgcs/"),
    ("安全总监", "https://www.nra.gov.cn/zzjg/aqzj/"),
]
NSJG = [
    ("综合司(外事司)", "https://www.nra.gov.cn/zzjg/nsjg/zhs/"),
    ("科技与法制司", "https://www.nra.gov.cn/zzjg/nsjg/fzs/"),
    ("安全监察司", "https://www.nra.gov.cn/zzjg/nsjg/aqjc/"),
    ("运输监督管理司", "https://www.nra.gov.cn/zzjg/nsjg/yss/"),
    ("工程监督管理司", "https://www.nra.gov.cn/zzjg/nsjg/gcs/"),
    ("设备监督管理司", "https://www.nra.gov.cn/zzjg/nsjg/sbs/"),
    ("人事司", "https://www.nra.gov.cn/zzjg/nsjg/rss/"),
    ("直属机关党委", "https://www.nra.gov.cn/zzjg/nsjg/zsdw/"),
]
JGJ = [
    ("沈阳铁路监督管理局", "https://www.nra.gov.cn/zzjg/jgj/syjd/"),
    ("上海铁路监督管理局", "https://www.nra.gov.cn/zzjg/jgj/shj/"),
    ("广州铁路监督管理局", "https://www.nra.gov.cn/zzjg/jgj/gzgl/"),
    ("成都铁路监督管理局", "https://www.nra.gov.cn/zzjg/jgj/cdgl/"),
    ("武汉铁路监督管理局", "https://www.nra.gov.cn/zzjg/jgj/whgl/"),
    ("西安铁路监督管理局", "https://www.nra.gov.cn/zzjg/jgj/xagl/"),
    ("兰州铁路监督管理局", "https://www.nra.gov.cn/zzjg/jgj/lzgl/"),
    ("北京铁路督察室", "https://www.nra.gov.cn/zzjg/jgj/bjdc/"),
]
SYDW = [
    ("信息中心", "https://www.nra.gov.cn/zzjg/sydw/xxzx/"),
    ("安全技术中心", "https://www.nra.gov.cn/zzjg/sydw/aqjs/"),
    ("装备技术中心", "https://www.nra.gov.cn/zzjg/sydw/zbzx/"),
    ("工程质量监督中心", "https://www.nra.gov.cn/zzjg/sydw/gcjd/"),
    ("市场监测评价中心", "https://www.nra.gov.cn/zzjg/sydw/scpc/"),
    ("规划与标准研究院", "https://www.nra.gov.cn/zzjg/sydw/ghyj/"),
    ("机关服务中心", "https://www.nra.gov.cn/zzjg/sydw/jgfw/"),
]
# 企业（有官网，真实链接来源）
QY = [
    ("中国国家铁路集团有限公司", "http://www.china-railway.com.cn/"),
    ("中国铁路广州局集团有限公司", "http://www.gzrailway.com.cn/"),
    ("中国铁路南宁局集团有限公司", "http://www.nntlj.com/"),
    ("中国铁路经济规划研究院有限公司", "http://www.crecc.com.cn/"),
    ("中国铁道科学研究院集团有限公司", "https://www.rails.cn/"),
    ("中国铁建股份有限公司", "https://www.crcc.cn/"),
    ("中国铁路客户服务中心", "http://www.12306.cn/"),
    ("人民铁道网", "https://www.peoplerail.com/"),
    ("中国铁路设计集团有限公司", "http://www.tsdig.com/"),
    ("中国铁路投资有限公司", "http://www.cric-china.com.cn/"),
    ("中国地方铁路协会", "http://www.china-dftlxh.cn/"),
]
# 18 局集团公司：仅广州/南宁有官网（已在 QY），其余列名
BUREAUS_18 = ["哈尔滨", "沈阳", "北京", "太原", "呼和浩特", "郑州", "武汉",
              "西安", "济南", "上海", "南昌", "广州", "南宁", "成都",
              "昆明", "兰州", "乌鲁木齐", "青藏"]
QY_URL = {n: u for n, u in QY}


def leaf(nm, u, lv="中央", x=""):
    return {"n": nm, "l": lv, "k": "铁路系统", "c": "铁路系统", "u": u,
            "x": x, "s": "", "m": ""}


def grp(nm, kids):
    return {"n": nm, "l": "条", "k": "分组", "c": "铁路系统", "u": "",
            "x": "", "s": "", "m": "", "ks": kids}


def main():
    tree = json.load(open("tree.json", encoding="utf-8"))
    rules = json.load(open("extraction_rules.json", encoding="utf-8"))

    # 清理旧铁路规则
    old = [k for k in rules if k.startswith("铁路系统")]
    for k in old:
        del rules[k]

    nra = leaf("国家铁路局", "https://www.nra.gov.cn/",
               x="https://www.nra.gov.cn/xxgk/gkml/")
    g_ld = grp(f"局领导（{len(LEADERS)}）", [leaf(n, u) for n, u in LEADERS])
    g_ns = grp(f"内设机构（{len(NSJG)}）", [leaf(n, u) for n, u in NSJG])
    g_jg = grp(f"地区监管局（{len(JGJ)}）", [leaf(n, u, "省") for n, u in JGJ])
    g_sy = grp(f"事业单位（{len(SYDW)}）", [leaf(n, u) for n, u in SYDW])
    qy_kids = [leaf(n, u) for n, u in QY] + [
        leaf(f"中国铁路{n}局集团有限公司", "", "省")
        for n in BUREAUS_18
        if f"中国铁路{n}局集团有限公司" not in QY_URL]
    g_qy = grp(f"铁路企业（{len(qy_kids)}）", qy_kids)

    new_grp = grp("铁路系统（6）", [nra, g_ld, g_ns, g_jg, g_sy, g_qy])
    tiao = next(g for g in tree["ks"] if g["n"] == "条（垂直管理系统）")
    tiao["ks"] = [g if not g["n"].startswith("铁路系统") else new_grp
                  for g in tiao["ks"]]
    if not any(g["n"].startswith("铁路系统") for g in tiao["ks"]):
        tiao["ks"].append(new_grp)

    # 块树：国家铁路局补信息公开专栏
    central = next(g for g in tree["ks"] if g["n"].startswith("中央"))
    gw = next(g for g in central["ks"] if g["n"].startswith("国务院"))
    gjj = next(g for g in gw["ks"] if g["n"].startswith("部委管理的国家局"))
    tl = next((n for n in gjj["ks"] if n["n"] == "国家铁路局"), None)
    if tl:
        tl["x"] = "https://www.nra.gov.cn/xxgk/gkml/"

    # ---- 规则 ----
    def add(key, portal, method, depts, url):
        rules[key] = {
            "portal": portal,
            "method": method,
            "sources": [portal],
            "code": CODE.format(title=key, url=url),
            "depts": depts,
            "cities": [],
        }

    all_m = [nra] + [m for g in (g_ld, g_ns, g_jg, g_sy, g_qy) for m in g["ks"]]
    add("铁路系统（6）", "https://www.nra.gov.cn/",
        "国家铁路局官网组织机构页 + 网站地图真实 HTML 提取（政府侧全部 + 企业有官网者）；"
        "16 个局集团公司官网未在权威页面出现 → 列名待提取",
        [{"n": m["n"], "u": m["u"], "o": i} for i, m in enumerate(all_m)],
        "https://www.nra.gov.cn/zzjg/")
    for g in (g_ld, g_ns, g_jg, g_sy, g_qy):
        sec = g["n"].split("（")[0]
        add(g["n"], "https://www.nra.gov.cn/",
            f"nra.gov.cn 组织机构页「{sec}」真实 HTML 提取",
            [{"n": m["n"], "u": m["u"], "o": i} for i, m in enumerate(g["ks"])],
            "https://www.nra.gov.cn/zzjg/")
        for m in g["ks"]:
            add(f"{g['n']}·{m['n']}", m["u"] or "https://www.nra.gov.cn/",
                f"nra.gov.cn 组织机构页「{sec}」真实 HTML 提取" +
                ("；官网未在权威页面出现 → 列名" if not m["u"] else ""),
                [{"n": m["n"], "u": m["u"], "o": 0}],
                "https://www.nra.gov.cn/zzjg/")

    json.dump(tree, open("tree.json", "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    json.dump(rules, open("extraction_rules.json", "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    print(f"p56 完成：铁路系统 6 组 {len(all_m)} 成员，rules 总数 {len(rules)}")


if __name__ == "__main__":
    main()
