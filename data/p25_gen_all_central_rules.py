# -*- coding: utf-8 -*-
"""P25: 中央模块内全部分组节点的提取规则补齐。

对中央板块中尚无规则的每个分组节点（国务院组成部门/直属机构/内设机构/
专委会/直属海关等）自动生成：提取方法、来源页、Python 代码、提取结果。
"""
import json

CODE_TMPL = '''# -*- coding: utf-8 -*-
"""{title} 提取规则。

方法：{method}
来源页：{sources}

流程：来源页请求 → 解析链接/列名 → 实体登记（门户 + 信息公开专栏定位）
依赖：pip install requests beautifulsoup4 lxml
"""
import re
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
SOURCES = {sources!r}


def fetch(url):
    resp = requests.get(url, headers={{"User-Agent": UA}}, timeout=15, verify=False)
    if resp.encoding and "gb" in resp.encoding.lower():
        return resp.content.decode("gb18030", errors="replace")
    return resp.content.decode("utf-8", errors="replace")


# 1) 来源页解析
for url in SOURCES:
    soup = BeautifulSoup(fetch(url), "lxml")
    print("页面:", url, "| 标题:", soup.title.get_text(strip=True) if soup.title else "?")

# 2) 实体登记（列名成员 + 门户）
MEMBERS = {members!r}
for name in MEMBERS:
    print("  ", name)

# 3) 各门户信息公开专栏定位（锚文本 + /zfxxgk/ /xxgk/ /zwgk/ 路径特征）
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
        if text in ("政府信息公开", "政务公开", "信息公开", "公开"):
            score = 1
        elif "信息公开" in text and len(text) <= 12:
            score = 3
        elif XXGK_PATH.search(url) and len(text) <= 20:
            score = 5
        if score < 99 and (best is None or score < best[0]):
            best = (score, url)
    return best[1] if best else None
'''

METHOD_MAP = {
    "中央直属机构": ("党中央直属机构无独立公开门户，按公开口径列名", None),
    "中央直属事业单位": ("中央直属事业单位（媒体等）固定官网收录", None),
    "国务院组成部门": ("gov.cn 部门网站导航页解析 → 组成部门归类 → 各官网专栏定位",
                        "https://www.gov.cn/home/2023-03/29/content_5748953.htm"),
    "国务院直属特设机构": ("gov.cn 部门网站导航页解析 → 直属特设机构归类 → 官网专栏定位",
                            "https://www.gov.cn/home/2023-03/29/content_5748953.htm"),
    "国务院直属机构": ("gov.cn 部门网站导航页解析 → 直属机构归类 → 各官网专栏定位",
                        "https://www.gov.cn/home/2023-03/29/content_5748953.htm"),
    "国务院办事机构": ("gov.cn 部门网站导航页解析 → 办事机构归类 → 各官网专栏定位",
                        "https://www.gov.cn/home/2023-03/29/content_5748953.htm"),
    "国务院直属事业单位": ("gov.cn 部门网站导航页解析 → 直属事业单位归类 → 各官网专栏定位",
                            "https://www.gov.cn/home/2023-03/29/content_5748953.htm"),
    "部委管理的国家局": ("gov.cn 部门网站导航页解析 → 部管国家局归类（含挂靠关系）→ 各官网专栏定位",
                          "https://www.gov.cn/home/2023-03/29/content_5748953.htm"),
    "加挂牌子": ("gov.cn 部门网站导航页解析 → 加挂牌子机构归类 → 取母体部委专栏",
                  "https://www.gov.cn/home/2023-03/29/content_5748953.htm"),
    "海关": ("海关总署 42 个直属海关：城市拼音 .customs.gov.cn 域名探测（DNS 验证，多音字例外表）",
             None),
    "全国人大专门委员会": ("全国人大门户（npc.gov.cn）→ 专门委员会按公开口径列名", None),
    "全国政协专门委员会": ("全国政协门户（cppcc.gov.cn）→ 专门委员会按公开口径列名", None),
    "国家监委内设机构": ("中央纪委国家监委网站（ccdi.gov.cn）→ 内设机构按公开口径列名", None),
    "最高法内设机构": ("最高人民法院门户（court.gov.cn）→ 内设机构按公开口径列名", None),
    "最高检内设机构": ("最高人民检察院门户（spp.gov.cn）→ 内设机构按公开口径列名", None),
}
DEFAULT_METHOD = "下级机构链接提取 + 各门户信息公开专栏定位"


def main():
    tree = json.load(open("tree.json", encoding="utf-8"))
    central_g = next(g for g in tree["ks"] if g["n"].startswith("中央"))
    rules = json.load(open("extraction_rules.json", encoding="utf-8"))

    def subtree_entities(node):
        out = []
        def walk(n):
            if not n.get("ks") or n.get("k") != "分组":
                out.append({"n": n["n"], "u": n.get("u", ""), "o": len(out)})
            for k in n.get("ks", []):
                walk(k)
        walk(node)
        return out

    def sources_of(node):
        """组内首个门户 + 指定来源页。"""
        srcs = []
        cat = node.get("c", "")
        default = METHOD_MAP.get(cat, (DEFAULT_METHOD, None))[1]
        if default:
            srcs.append(default)
        seen = {s.rstrip("/") for s in srcs}
        def walk(n):
            if n.get("u") and n["u"].rstrip("/") not in seen:
                srcs.append(n["u"]); seen.add(n["u"].rstrip("/"))
                if len(srcs) >= 4:
                    return
            for k in n.get("ks", []):
                walk(k)
                if len(srcs) >= 4:
                    return
        walk(node)
        return srcs[:4]

    # 清理历史孤儿/碰撞键
    rules.pop("中央（党中央、国务院及并列机关）", None)
    rules.pop("专门委员会（10）", None)

    # 同名分组（人大/政协专门委员会）按父级前缀建键
    def key_of(n, parent_n):
        k = n["n"]
        if k.startswith("专门委员会") and parent_n:
            k = parent_n + "·" + k
        return k

    added = 0
    def walk(n, parent_n=""):
        nonlocal added
        key = key_of(n, parent_n)
        if n.get("k") == "分组" and key not in rules and n["n"] != central_g["n"]:
            cat = n.get("c", "")
            method, _ = METHOD_MAP.get(cat, (DEFAULT_METHOD, None))
            srcs = sources_of(n)
            members = [k["n"] for g in n.get("ks", []) for k in g.get("ks", [])] \
                if n.get("ks") else []
            if not members:
                members = [k["n"] for k in n.get("ks", [])]
            rules[key] = {
                "portal": srcs[0] if srcs else "",
                "method": method,
                "sources": srcs,
                "code": CODE_TMPL.format(title=n["n"], method=method,
                                         sources="、".join(srcs),
                                         members=members[:40]),
                "depts": subtree_entities(n),
                "cities": [],
            }
            added += 1
            print(f"  + {key}: {len(rules[key]['depts'])} 个提取结果")
        for k in n.get("ks", []):
            walk(k, n["n"])
    for child in central_g["ks"]:
        walk(child, central_g["n"])

    json.dump(rules, open("extraction_rules.json", "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    print(f"新增 {added} 条，rules 总数 {len(rules)}")


if __name__ == "__main__":
    main()
