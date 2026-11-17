# -*- coding: utf-8 -*-
"""P30: 市县并列机关组规则 + 县直部门（省政务服务网 deptSwitch）规则生成。

键约定（与模板 ruleKeyOf 一致）：
  市级并列机关组：{市名}·并列机关（6）
  县级并列机关组：{县名}·并列机关（6）
  县直部门组：{县名}·县直部门
（市县两级组节点 c=并列机关，父级为市/县 → ruleKeyOf 需扩展；模板同步补丁）
"""
import json
import re

from p26_gen_gat_rules import CODE_TMPL as CODE_GAT  # 复用港澳台模板结构（含列名+门户）

CODE_PAR = '''# -*- coding: utf-8 -*-
"""{title} 并列机关提取。

方法：{method}
来源页：{sources}

流程：政府门户首页请求（WAF 站点走 smart_fetch 降级链）→ 人大/政协/监委/
     法院/检察院 名称匹配 + .gov.cn 域名过滤 → 域名归属判定 → 门户登记
     → 缺失者列名（市委/县委等党委机关多数无独立公开门户）
依赖：pip install requests beautifulsoup4 lxml
"""
import re
from urllib.parse import urlparse

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


CAT_RE = re.compile(r"(人大|政协|监委|监察委|纪委|法院|检察院|检察)")
EXCLUDE = re.compile(r"(最高|全国|新闻|报告|会议|要闻|工作)")
html = fetch(PORTAL)
soup = BeautifulSoup(html, "lxml")
for a in soup.find_all("a"):
    text = re.sub(r"\\s+", "", (a.get("title") or a.get_text(" ", strip=True)).strip())
    href = a.get("href") or ""
    if (not text or not href.startswith(("http://", "https://"))
            or not CAT_RE.search(text) or EXCLUDE.search(text)):
        continue
    if not urlparse(href).netloc.lower().endswith(".gov.cn"):
        continue
    cat = ("人大" if "人大" in text else "政协" if "政协" in text else
           "监委" if ("监察委" in text or "纪委" in text) else
           "法院" if "法院" in text else "检察院")
    print(f"  {{cat}}: {{text}} -> {{href}}")
print("# 党委机关（市/县委）多数无独立公开门户 → 列名")
'''

CODE_DEPT = '''# -*- coding: utf-8 -*-
"""{title} 县直部门提取。

方法：{method}
说明：县级政府工作部门已基本不再自建官网，部门信息集中挂省政务服务网
     「部门列表」页（deptSwitch 通道，按行政区划代码 areaCode 定位）。
来源页：{sources}
"""
import re
from urllib.parse import urlencode

import requests

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
AREA_CODE = "{area_code}"          # 12 位：6 位行政区划代码 + 000000
DEPT_URL = "{dept_url}"


def fetch(url):
    resp = requests.get(url, headers={{"User-Agent": UA}}, timeout=15, verify=False)
    if resp.encoding and "gb" in resp.encoding.lower():
        return resp.content.decode("gb18030", errors="replace")
    return resp.content.decode("utf-8", errors="replace")


html = fetch(DEPT_URL)
# 部门列表页解析：名称 + 政务网频道链接（部门已无独立官网）
names = re.findall(r'aria-label="([^"]{{2,20}})"|title="([^"]{{2,20}})"', html)
print("部门列表页已获取，长度:", len(html))
'''


def main():
    tree = json.load(open("tree.json", encoding="utf-8"))
    prov_g = next(g for g in tree["ks"] if g["n"].startswith("省级"))
    rules = json.load(open("extraction_rules.json", encoding="utf-8"))
    cc_par = {}
    if __import__("os").path.exists("cc_parallel.jsonl"):
        for l in open("cc_parallel.jsonl", encoding="utf-8"):
            r = json.loads(l)
            cc_par.setdefault(r["code"], []).append(r)

    added = 0

    def handle_city(city):
        nonlocal added
        # ---- 市级并列机关组 ----
        cgrp = next((k for k in city.get("ks", []) if k.get("c") == "并列机关"), None)
        if cgrp:
            key = f"{city['n']}·{cgrp['n']}"
            members = [k for k in cgrp.get("ks", []) if k.get("k") != "分组"]
            par_rows = cc_par.get(city.get("cd", ""), [])
            portal_map = {r["org_cat"]: r["org_url"] for r in par_rows}
            for m in members:
                for cat in ("人大", "政协", "监委", "法院", "检察"):
                    if cat in m["n"] and cat in portal_map:
                        m["u"] = portal_map[cat]
            rules[key] = {
                "portal": city.get("u", ""),
                "method": "市政府门户首页链接采集（WAF 走 smart_fetch 降级链）→ 并列机关"
                          "名称匹配 + 域名过滤 → 门户登记；市委列名",
                "sources": [city.get("u", "")] if city.get("u") else [],
                "code": CODE_PAR.format(title=f"{city['n']} 并列机关",
                                        method="市政府门户首页链接采集",
                                        sources=city.get("u", ""),
                                        portal=city.get("u", "")),
                "depts": [{"n": m["n"], "u": m.get("u", ""), "o": i}
                          for i, m in enumerate(members)],
                "cities": [],
            }
            added += 1
    def handle_county(county, prov):
        nonlocal added
        xgrp = next((k for k in county.get("ks", []) if k.get("c") == "并列机关"), None)
        members = [k for k in xgrp.get("ks", []) if k.get("k") != "分组"] if xgrp else []
        par_rows = cc_par.get(county.get("cd", ""), [])
        portal_map = {r["org_cat"]: r["org_url"] for r in par_rows}
        if xgrp:
            for m in members:
                for cat in ("人大", "政协", "监委", "法院", "检察"):
                    if cat in m["n"] and cat in portal_map:
                        m["u"] = portal_map[cat]
            key = f"{county['n']}·{xgrp['n']}"
            rules[key] = {
                "portal": county.get("u", ""),
                "method": "县政府门户首页链接采集 → 并列机关名称匹配 + 域名过滤 → "
                          "门户登记（县法院/县检察院多数有独立门户；县委列名）",
                "sources": [county.get("u", "")] if county.get("u") else [],
                "code": CODE_PAR.format(title=f"{county['n']} 并列机关",
                                        method="县政府门户首页链接采集",
                                        sources=county.get("u", ""),
                                        portal=county.get("u", "")),
                "depts": [{"n": m["n"], "u": m.get("u", ""), "o": i}
                          for i, m in enumerate(members)],
                "cities": [],
            }
            added += 1
        # ---- 县节点自身规则（键=区划代码）：门户 + 并列机关 + 县直部门 ----
        if county.get("cd"):
            area = county["cd"] + "000000"
            zw = zwfw_dept_url(prov, area)
            dept_rows = [{"n": m["n"], "u": m.get("u", ""), "o": i}
                         for i, m in enumerate(members)]
            if zw:
                dept_rows.append({"n": "县直部门列表（省政务服务网）", "u": zw,
                                  "o": len(dept_rows)})
            rules[county["cd"]] = {
                "portal": county.get("u", ""),
                "method": "县政府门户首页采集（WAF 走 smart_fetch 降级链）→ 并列机关链接"
                          "（县法院/县检察院独立门户）；县直部门无独立官网，集中挂省政务服务网"
                          "「部门列表」页（areaCode=12位区划代码）",
                "sources": ([county.get("u", "")] if county.get("u") else []) +
                           ([zw] if zw else []),
                "code": CODE_DEPT.format(title=f"{county['n']} 县级提取（门户+并列机关+县直部门）",
                                         method="县门户采集 + 省政务服务网 deptSwitch 部门列表页",
                                         sources=zw or county.get("u", ""),
                                         area_code=area, dept_url=zw or ""),
                "depts": dept_rows,
                "cities": [],
            }
            added += 1

    for prov in prov_g["ks"]:
        def walk_prov(n):
            nonlocal added
            if n.get("l") == "市" and n.get("k") == "人民政府":
                handle_city(n)
            elif n.get("l") in ("县", "地级区") and n.get("k") == "人民政府":
                handle_county(n, prov["n"])
            for k in n.get("ks", []):
                walk_prov(k)
        for top in prov.get("ks", []):
            walk_prov(top)
    json.dump(rules, open("extraction_rules.json", "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    print(f"p30 完成：新增 {added} 条，rules 总数 {len(rules)}")


ZW_PATTERNS = {
    "四川省": "https://www.sczwfw.gov.cn/jiq/front/channel/deptSwitch?areaCode={area}",
    "北京市": "https://banshi.beijing.gov.cn/pubtask/frhot.html",
    "天津市": "https://zwfw.tj.gov.cn/#/home",
    "上海市": "https://zwdt.sh.gov.cn/govPortals/column_list/custom?id={area}",
    "重庆市": "https://zwykb.cq.gov.cn/",
    "河北省": "https://www.hbzwfw.gov.cn/hbzw/foursxcx/itemList/index.do?areaCode={area}",
    "山西省": "https://www.sxzwfw.gov.cn/icity/icity/departmental",
    "内蒙古自治区": "https://zwfw.nmg.gov.cn/handle_affairs?regionCode={area}",
    "辽宁省": "https://www.lnzwfw.gov.cn/",
    "吉林省": "https://zwfw.jl.gov.cn/jlszwfw/grbs/",
    "黑龙江省": "https://www.zwfw.hlj.gov.cn/",
    "江苏省": "https://www.jszwfw.gov.cn/",
    "浙江省": "https://www.zjzwfw.gov.cn/zjservice-fe/#/departmental",
    "安徽省": "https://www.ahzwfw.gov.cn/",
    "福建省": "https://zwfw.fujian.gov.cn/",
    "江西省": "https://www.jxzwfww.gov.cn/",
    "山东省": "https://www.shandong.gov.cn/zwfw/",
    "河南省": "https://www.hnzwfw.gov.cn/portal/legal/themePage",
    "湖北省": "https://zwfw.hubei.gov.cn/webview/fw/frfw.html",
    "湖南省": "https://zwfw-new.hunan.gov.cn/onething/service/index.jsp?areacode={area}",
    "广东省": "https://www.gdzwfw.gov.cn/",
    "广西壮族自治区": "https://zwfw.gxzf.gov.cn/",
    "海南省": "https://wssp.hainan.gov.cn/",
    "贵州省": "https://zwfw.guizhou.gov.cn/",
    "云南省": "https://zwfw.yn.gov.cn/portal/",
    "西藏自治区": "https://www.xzzwfw.gov.cn/",
    "陕西省": "https://zwfw.shaanxi.gov.cn/",
    "甘肃省": "https://zwfw.gansu.gov.cn/",
    "青海省": "https://www.qhzwfw.gov.cn/",
    "宁夏回族自治区": "https://zwfw.nx.gov.cn/",
    "新疆维吾尔自治区": "https://zwfw.xinjiang.gov.cn/",
}


def zwfw_dept_url(prov_name, area):
    pat = ZW_PATTERNS.get(prov_name, "")
    if "{area}" in pat:
        return pat.replace("{area}", area)
    return pat or ""


if __name__ == "__main__":
    main()
