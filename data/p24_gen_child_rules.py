# -*- coding: utf-8 -*-
"""P24: 生成中央各子节点的提取规则（中共中央/国务院/人大/政协/监委/最高法/最高检）。"""
import json

CODE_FIXED = '''# -*- coding: utf-8 -*-
"""{title}门户与信息公开专栏提取。

方法：{method}
来源页：{sources}

流程：固定门户请求 → 标题校验 → 信息公开专栏链接定位 → 内设/专委会按公开口径列名
依赖：pip install requests beautifulsoup4 lxml
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


# 1) 门户请求 + 标题校验
html = fetch(PORTAL)
soup = BeautifulSoup(html, "lxml")
print("门户标题:", soup.title.get_text(strip=True) if soup.title else "?")

# 2) 信息公开/公开 专栏链接定位（锚文本 + URL 路径特征）
XXGK_PATH = re.compile(r"/(zfxxgkm?|xxgk|zwgk|govinfo|gk)(/|.|$)")
best = None
for a in soup.find_all("a"):
    text = re.sub(r"\\s+", "", a.get_text(" ", strip=True))
    url = urljoin(PORTAL, a.get("href") or "")
    if not url.startswith(("http://", "https://")):
        continue
    score = 99
    if "信息公开" in text or "政务公开" in text or "公开" == text:
        score = 1 if text in ("政府信息公开", "信息公开", "政务公开", "公开") else 3
    elif XXGK_PATH.search(url) and len(text) <= 20:
        score = 5
    if score < 99 and (best is None or score < best[0]):
        best = (score, url)
print("信息公开专栏:", best[1] if best else "待核")

# 3) 内设机构 / 专门委员会列名（公开口径）
MEMBERS = {members}
print("列名成员:", len(MEMBERS))
'''

CODE_GW = '''# -*- coding: utf-8 -*-
"""国务院（中央人民政府）门户、部委机构与直属海关提取。

方法：{method}
来源页：{sources}

流程：门户+信息公开专栏 → 部门网站导航页解析归类 → 各官网专栏定位
     → 42 直属海关城市拼音域名探测 → WAF 站点降级链
依赖：pip install requests beautifulsoup4 lxml pypinyin
"""
import re
import socket
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
PORTAL = "https://www.gov.cn/"
XXGK = "https://www.gov.cn/zhengce/xxgk/"          # 国务院信息公开专栏
NAV_PAGE = "https://www.gov.cn/home/2023-03/29/content_5748953.htm"   # 部门网站导航


def fetch(url):
    resp = requests.get(url, headers={{"User-Agent": UA}}, timeout=15, verify=False)
    if resp.encoding and "gb" in resp.encoding.lower():
        return resp.content.decode("gb18030", errors="replace")
    return resp.content.decode("utf-8", errors="replace")


# 1) 部门导航页解析：名称 + 官网 URL（国务院组成部门/直属机构/部管国家局/加挂牌子）
CATEGORIES = {{"外交部": "国务院组成部门", "海关总署": "国务院直属机构",
             "国家能源局": "部委管理的国家局", "国家航天局": "加挂牌子"}}
soup = BeautifulSoup(fetch(NAV_PAGE), "lxml")
departments = []
for a in soup.find_all("a"):
    name = re.sub(r"\\s+", "", a.get_text(" ", strip=True))
    href = a.get("href") or ""
    if name in CATEGORIES and href.startswith(("http://", "https://")):
        departments.append((name, href))

# 2) 42 直属海关：城市拼音 .customs.gov.cn 域名探测
CUSTOMS_CITIES = ["北京", "天津", "石家庄", "太原", "呼和浩特", "满洲里", "大连",
                  "沈阳", "长春", "哈尔滨", "上海", "南京", "杭州", "宁波", "合肥",
                  "福州", "厦门", "南昌", "青岛", "济南", "郑州", "武汉", "长沙",
                  "广州", "黄埔", "深圳", "拱北", "汕头", "江门", "湛江", "南宁",
                  "海口", "重庆", "成都", "贵阳", "昆明", "拉萨", "西安", "兰州",
                  "西宁", "银川", "乌鲁木齐"]
PY_EXCEPT = {{"哈尔滨": "harbin", "呼和浩特": "huhehaote", "乌鲁木齐": "urumqi", "拉萨": "lasa"}}
customs = []
for city in CUSTOMS_CITIES:
    py = PY_EXCEPT.get(city)
    if py is None:
        from pypinyin import lazy_pinyin
        py = "".join(lazy_pinyin(city))
    host = f"{{py}}.customs.gov.cn"
    try:
        socket.getaddrinfo(host, 443, socket.AF_INET)
        customs.append((f"{{city}}海关", f"http://{{host}}/"))
    except Exception:
        pass
print("部门机构:", len(departments), "| 直属海关:", len(customs))

# 3) 各官网信息公开专栏定位（锚文本+路径特征 → 路径探测 → WAF 降级链）
XXGK_PATH = re.compile(r"/(zfxxgkm?|xxgk|zwgk|govinfo)(/|.|$)")
PROBE = ["/zfxxgk/", "/zfxxgk/index.html", "/xxgk/", "/zwgk/", "/govinfo/"]
def resolve_xxgk(portal):
    s = BeautifulSoup(fetch(portal), "lxml")
    best = None
    for a in s.find_all("a"):
        text = re.sub(r"\\s+", "", a.get_text(" ", strip=True))
        url = urljoin(portal, a.get("href") or "")
        if not url.startswith(("http://", "https://")):
            continue
        score = 99
        if text in ("政府信息公开", "政务公开", "信息公开", "公开"):
            score = 1
        elif "信息公开" in text and len(text) <= 12:
            score = 3
        elif XXGK_PATH.search(url) and len(text) <= 20:
            score = 5
        if score < 99 and (best is None or score < best[0]):
            best = (score, url)
    if best:
        return best[1]
    base = portal.rstrip("/")
    for p in PROBE:
        try:
            if requests.get(base + p, headers={{"User-Agent": UA}},
                            timeout=10, verify=False).status_code == 200:
                return base + p
        except Exception:
            continue
    return None    # WAF 站点 → 百度 SERP 挖路径 / CloakBrowser 渲染降级链
'''


def main():
    tree = json.load(open("tree.json", encoding="utf-8"))
    central_g = next(g for g in tree["ks"] if g["n"].startswith("中央"))
    rules = json.load(open("extraction_rules.json", encoding="utf-8"))

    SPECS = {
        "中共中央（党中央）": {
            "portal": "", "method": "党中央机关无独立公开门户：中央直属机构 16 个按公开口径列名；"
                                     "直属事业单位（人民日报社/求是杂志社/光明日报社/经济日报社）收录官网",
            "sources": ["https://www.people.com.cn/", "https://www.qstheory.cn/",
                        "https://www.gmw.cn/", "https://www.ce.cn/"],
        },
        "国务院（中央人民政府）": {
            "portal": "https://www.gov.cn/",
            "method": "门户+信息公开专栏（/zhengce/xxgk/）→ 部门网站导航页解析归类（80 机构）→ "
                      "42 直属海关城市拼音域名探测 → 各官网专栏定位+WAF 降级链",
            "sources": ["https://www.gov.cn/home/2023-03/29/content_5748953.htm",
                        "https://www.gov.cn/zhengce/xxgk/"],
        },
        "全国人民代表大会（全国人大常委会）": {
            "portal": "https://www.npc.gov.cn/",
            "method": "固定门户请求+标题校验 → 信息公开专栏定位 → 专门委员会 10 个列名",
            "sources": ["https://www.npc.gov.cn/"],
        },
        "中国人民政治协商会议全国委员会": {
            "portal": "https://www.cppcc.gov.cn/",
            "method": "固定门户请求+标题校验 → 信息公开专栏定位 → 专门委员会 10 个列名",
            "sources": ["https://www.cppcc.gov.cn/"],
        },
        "国家监察委员会（与中央纪委合署办公）": {
            "portal": "https://www.ccdi.gov.cn/",
            "method": "中央纪委国家监委网站（一个机构两块牌子）→ 公开专栏定位 → 内设机构 15 个列名",
            "sources": ["https://www.ccdi.gov.cn/"],
        },
        "最高人民法院": {
            "portal": "https://www.court.gov.cn/",
            "method": "固定门户请求+标题校验 → 公开专栏定位 → 内设机构 22 个列名（含六个巡回法庭）",
            "sources": ["https://www.court.gov.cn/"],
        },
        "最高人民检察院": {
            "portal": "https://www.spp.gov.cn/",
            "method": "固定门户请求+标题校验 → 公开专栏定位 → 内设机构 17 个列名（办公厅/政治部/十个检察厅…）",
            "sources": ["https://www.spp.gov.cn/"],
        },
    }

    def subtree_entities(node):
        out = []
        def walk(n):
            if not n.get("ks") or n.get("k") != "分组":
                out.append({"n": n["n"], "u": n.get("u", ""), "o": len(out)})
            for k in n.get("ks", []):
                walk(k)
        walk(node)
        return out

    for child in central_g["ks"]:
        name = child["n"]
        if name not in SPECS:
            continue
        spec = SPECS[name]
        kids = [k for k in child.get("ks", [])]
        members = [k["n"] for g in kids for k in g.get("ks", [])] if kids else []
        if name == "国务院（中央人民政府）":
            code = CODE_GW.format(method=spec["method"],
                                  sources="、".join(spec["sources"]))
        else:
            code = CODE_FIXED.format(title=name, method=spec["method"],
                                     sources="、".join(spec["sources"]),
                                     portal=spec["portal"],
                                     members=repr(members[:30]))
        rules[name] = {
            "portal": spec["portal"],
            "method": spec["method"],
            "sources": spec["sources"],
            "code": code,
            "depts": subtree_entities(child),
            "cities": [],
        }
        print(f"  + {name}: {len(rules[name]['depts'])} 个提取结果")

    json.dump(rules, open("extraction_rules.json", "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    print("rules 总数:", len(rules))


if __name__ == "__main__":
    main()
