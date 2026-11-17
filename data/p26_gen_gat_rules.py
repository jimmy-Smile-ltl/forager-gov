# -*- coding: utf-8 -*-
"""P26: 生成港澳台板块的提取规则（组 / 香港 / 澳门 / 台湾）。"""
import json

CODE_TMPL = '''# -*- coding: utf-8 -*-
"""{title} 提取规则。

方法：{method}
来源页：{sources}

说明：港澳台实行与内地不同的公开制度（香港《公开资料守则》、澳门公开制度；
台湾地区县市政府门户为公开域名列名）。内地网络一般无法访问，未做连通性验证。
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


# 1) 门户请求（内地网络不可达时此处将失败，域名按公开口径登记）
for url in SOURCES:
    try:
        html = fetch(url)
        soup = BeautifulSoup(html, "lxml")
        print("页面:", url, "| 标题:", soup.title.get_text(strip=True) if soup.title else "?")
    except Exception as e:
        print("不可达（预期）:", url, "-", type(e).__name__)

# 2) 下级区划 / 县市政府 列名登记（公开口径）
MEMBERS = {members!r}
for name in MEMBERS:
    print("  ", name)
'''


def main():
    tree = json.load(open("tree.json", encoding="utf-8"))
    gat_g = next(g for g in tree["ks"] if g["n"].startswith("港澳台"))
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

    SPECS = [
        ("港澳台（特别行政区与台湾）",
         "特别行政区与台湾为独立体系：香港/澳门实行各自的公开资料制度（非内地《政府信息公开条例》）；"
         "台湾地区 22 县市政府门户按公开域名列名，内地网络一般不可达",
         ["https://www.gov.hk/", "https://www.gov.mo/"]),
        ("香港", "香港特区政府门户 gov.hk（公开资料守则体系）→ 18 个区议会分区列名",
         ["https://www.gov.hk/"]),
        ("澳门", "澳门特区政府门户 gov.mo（公开制度）→ 8 个堂区列名",
         ["https://www.gov.mo/"]),
        ("台湾", "台湾地区 22 县市政府官网（公开域名：台北市 gov.taipei 为城市顶级域名，"
                 "其余为 gov.tw 系）——内地网络不可达，未做连通性验证，列名参考",
         ["https://www.gov.taipei/", "https://www.ntpc.gov.tw/"]),
    ]
    for key, method, srcs in SPECS:
        node = gat_g if key == "港澳台（特别行政区与台湾）" else \
            next(n for n in gat_g["ks"] if n["n"].startswith(key))
        members = [k["n"] for k in node.get("ks", [])] if node.get("ks") else []
        rules[key] = {
            "portal": srcs[0],
            "method": method,
            "sources": srcs,
            "code": CODE_TMPL.format(title=node["n"], method=method,
                                     sources="、".join(srcs),
                                     members=members[:40]),
            "depts": subtree_entities(node),
            "cities": [],
        }
        print(f"  + {key}: {len(rules[key]['depts'])} 个提取结果")

    json.dump(rules, open("extraction_rules.json", "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    print("rules 总数:", len(rules))


if __name__ == "__main__":
    main()
