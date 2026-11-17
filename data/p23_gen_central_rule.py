# -*- coding: utf-8 -*-
"""P23 v2: 生成「中央」完整提取规则。

覆盖四个提取面：
1. 国务院部门机构（gov.cn 部门网站导航页 → 分类 → 官网专栏定位）
2. 中央并列机关（人大/政协/监委/最高法/最高检：固定门户 + 内设机构列名）
3. 海关总署直属海关 42 个（城市拼音 .customs.gov.cn 域名探测）
4. 瑞数 WAF 站点专栏 URL 的降级链（锚文本/路径特征 → 路径探测 → 百度SERP挖路径 → 浏览器）
"""
import json

CODE = '''# -*- coding: utf-8 -*-
"""中国政府信息公开名录 · 中央层面提取完整流程（国务院部门 + 并列机关 + 直属海关）。

来源页：
  https://www.gov.cn/home/2023-03/29/content_5748953.htm   # 国务院部门网站导航
  https://www.gov.cn/gwyzzjg/                                # 国务院组织机构
  https://www.gov.cn/home/2023-03/29/content_5748954.htm    # 地方政府网站导航
  https://www.gov.cn/zhengce/xxgk/                           # 国务院信息公开专栏

流程：导航页解析 → 机构归类 → 官网专栏定位 → 路径探测兜底
     （WAF 站点：百度 SERP 挖路径 / 浏览器渲染，见文末降级链）
依赖：pip install requests beautifulsoup4 lxml curl_cffi
"""
import re
import socket
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
NAV_PAGE = "https://www.gov.cn/home/2023-03/29/content_5748953.htm"


def fetch(url):
    resp = requests.get(url, headers={{"User-Agent": UA}}, timeout=15, verify=False)
    if resp.encoding and "gb" in resp.encoding.lower():
        return resp.content.decode("gb18030", errors="replace")
    return resp.content.decode("utf-8", errors="replace")


# ============ 一、国务院部门机构（导航页解析 + 归类） ============
CATEGORIES = {{
    "外交部": "国务院组成部门", "国家发展和改革委员会": "国务院组成部门",
    "教育部": "国务院组成部门", "商务部": "国务院组成部门",
    "中国人民银行": "国务院组成部门", "审计署": "国务院组成部门",
    "海关总署": "国务院直属机构", "国家税务总局": "国务院直属机构",
    "国务院国有资产监督管理委员会": "国务院直属特设机构",
    "国家能源局": "部委管理的国家局", "国家铁路局": "部委管理的国家局",
    "国家新闻出版署": "加挂牌子", "国家航天局": "加挂牌子",
    # ……完整 80 机构分类见 data/central.jsonl
}}

html = fetch(NAV_PAGE)
soup = BeautifulSoup(html, "lxml")
departments = []          # [(名称, URL, 页面顺序)]
for a in soup.find_all("a"):
    name = re.sub(r"\\s+", "", a.get_text(" ", strip=True))
    href = a.get("href") or ""
    if name in CATEGORIES and href.startswith(("http://", "https://")):
        departments.append((name, href))


# ============ 二、中央并列机关（固定门户） ============
PARALLEL = {{
    "全国人大": "https://www.npc.gov.cn/",
    "全国政协": "https://www.cppcc.gov.cn/",
    "国家监委（与中央纪委合署）": "https://www.ccdi.gov.cn/",
    "最高人民法院": "https://www.court.gov.cn/",
    "最高人民检察院": "https://www.spp.gov.cn/",
    # 中共中央：无独立公开门户，列名（中央直属机构 16 个 / 媒体事业单位 4 个）
}}


# ============ 三、海关总署直属海关 42 个（城市拼音域名探测） ============
CUSTOMS_CITIES = ["北京", "天津", "石家庄", "太原", "呼和浩特", "满洲里", "大连",
                  "沈阳", "长春", "哈尔滨", "上海", "南京", "杭州", "宁波", "合肥",
                  "福州", "厦门", "南昌", "青岛", "济南", "郑州", "武汉", "长沙",
                  "广州", "黄埔", "深圳", "拱北", "汕头", "江门", "湛江", "南宁",
                  "海口", "重庆", "成都", "贵阳", "昆明", "拉萨", "西安", "兰州",
                  "西宁", "银川", "乌鲁木齐"]
PY_EXCEPT = {{"哈尔滨": "harbin", "呼和浩特": "huhehaote", "乌鲁木齐": "urumqi",
             "拉萨": "lasa"}}     # 多音/异读城市拼音例外表

def dns_ok(host):
    try:
        socket.getaddrinfo(host, 443, socket.AF_INET)
        return True
    except Exception:
        return False

customs = []
for city in CUSTOMS_CITIES:
    py = PY_EXCEPT.get(city, None)
    if py is None:
        from pypinyin import lazy_pinyin      # pip install pypinyin
        py = "".join(lazy_pinyin(city))
    host = f"{{py}}.customs.gov.cn"
    if dns_ok(host):
        customs.append((f"{{city}}海关", f"http://{{host}}/"))
print("直属海关探测命中:", len(customs), "/", len(CUSTOMS_CITIES))


# ============ 四、信息公开专栏定位 + 降级链 ============
XXGK_PATH = re.compile(r"/(zfxxgkm?|xxgk|zwgk|govinfo)(/|.|$)")
def find_xxgk(portal_html, base):
    s = BeautifulSoup(portal_html, "lxml")
    best = None
    for a in s.find_all("a"):
        text = re.sub(r"\\s+", "", a.get_text(" ", strip=True))
        url = urljoin(base, a.get("href") or "")
        if not url.startswith(("http://", "https://")):
            continue
        score = 99
        if text == "政府信息公开" or text.startswith("政府信息公开专栏"):
            score = 1
        elif text == "政务公开":
            score = 2
        elif "信息公开" in text and len(text) <= 12:
            score = 3
        elif XXGK_PATH.search(url) and len(text) <= 20:
            score = 5
        if score < 99 and (best is None or score < best[0]):
            best = (score, url)
    return best[1] if best else None

PROBE = ["/zfxxgk/", "/zfxxgk/index.html", "/xxgk/", "/zwgk/", "/govinfo/"]
def resolve_xxgk(portal):
    html = fetch(portal)
    u = find_xxgk(html, portal)
    if u:
        return u, "导航链接"
    base = portal.rstrip("/")
    for p in PROBE:                          # 路径探测
        try:
            if requests.get(base + p, headers={{"User-Agent": UA}},
                            timeout=10, verify=False).status_code == 200:
                return base + p, "路径探测"
        except Exception:
            continue
    return None, "待核（WAF）"

results = []
for name, url in departments:
    xxgk, src = resolve_xxgk(url)
    results.append({{"name": name, "portal": url, "xxgk": xxgk, "src": src}})

print("\\n专栏URL命中:",
      sum(1 for r in results if r["xxgk"]), "/", len(results))

# 降级链（瑞数 WAF 站点，如 国防部/卫健委/海关总署等）：
#   1) 百度 SERP 原文挖真实专栏路径（如 customs.gov.cn/customs/302249/zfxxgk/）
#   2) CloakBrowser 独立 Chromium + DrissionPage 直连 CDP 渲染
#   3) smart_fetch 五级降级（curl_cffi → iv8 → nodenv → RsSpider/sdenv → Drission）
# 详见 采集代码归档/p16_browser_footer.py 与 util/smart_fetch.py
'''


def main():
    tree = json.load(open("tree.json", encoding="utf-8"))
    central_g = next(g for g in tree["ks"] if g["n"].startswith("中央"))
    # 提取结果 = 中央模块内全部带门户的实体（按目录顺序）
    depts = []
    def walk(n):
        if not n.get("ks") or n.get("k") != "分组":
            if n.get("u"):
                depts.append({"n": n["n"], "u": n["u"], "o": len(depts)})
        for k in n.get("ks", []):
            walk(k)
    walk(central_g)

    rules = json.load(open("extraction_rules.json", encoding="utf-8"))
    rules["中央"] = {
        "portal": "https://www.gov.cn/",
        "method": "四路提取：①国务院部门机构——gov.cn 部门网站导航页解析+机构归类+官网专栏定位；"
                  "②中央并列机关——全国人大/政协/监委/最高法/最高检固定门户，中共中央直属机构列名；"
                  "③海关总署直属海关 42 个——城市拼音 .customs.gov.cn 域名探测；"
                  "④瑞数 WAF 站点专栏——百度 SERP 挖路径/CloakBrowser 渲染降级链",
        "sources": ["https://www.gov.cn/home/2023-03/29/content_5748953.htm",
                    "https://www.gov.cn/gwyzzjg/",
                    "https://www.gov.cn/home/2023-03/29/content_5748954.htm",
                    "https://www.gov.cn/zhengce/xxgk/"],
        "code": CODE,
        "depts": depts,
        "cities": [],
    }
    json.dump(rules, open("extraction_rules.json", "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    print("中央规则 v2 已更新：提取结果", len(depts), "个实体")


if __name__ == "__main__":
    main()
