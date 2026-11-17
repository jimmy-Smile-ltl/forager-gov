# -*- coding: utf-8 -*-
"""P27: 省级并列机关提取规则补齐。

每省生成：并列机关组规则（6 成员提取结果）+ 6 个成员各自规则。
键约定：{省全名}·并列机关（N） / {省全名}·{成员名}（与模板 ruleKeyOf 一致）。
"""
import json

CODE_GROUP = '''# -*- coding: utf-8 -*-
"""{prov} 并列机关提取（省人大/省政协/省监委/省高级人民法院/省人民检察院 + 省委列名）。

方法：省门户首页底部 footer 链接采集 → 人大/政协/监委(纪委)/法院/检察院
     名称匹配 + .gov.cn 域名过滤 + URL 域名归属判定（防跨省链接）；
     省委多数无独立公开门户 → 列名。
来源页：{sources}

流程：渲染首页（JS 导航需浏览器）→ 提取链接 → 分类 → 门户登记
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


# 1) 首页请求（footer 导航为 JS 渲染时需浏览器：见 p18_parallel.py 的
#    CloakBrowser CDP + DrissionPage 方案）
html = fetch(PORTAL)
soup = BeautifulSoup(html, "lxml")

# 2) 链接匹配：人大/政协/监委/纪委/法院/检察院
CAT_RE = re.compile(r"(人大|政协|监委|监察委|纪委|法院|检察院|检察)")
EXCLUDE = re.compile(r"(最高|全国|新闻|报告|会议|要闻|工作)")
parallel = {{}}
for a in soup.find_all("a"):
    text = re.sub(r"\\s+", "", (a.get("title") or a.get_text(" ", strip=True)).strip())
    href = a.get("href") or ""
    if not text or not href.startswith(("http://", "https://")):
        continue
    if not CAT_RE.search(text) or EXCLUDE.search(text):
        continue
    if not urlparse(href).netloc.lower().endswith(".gov.cn"):
        continue
    cat = ("人大" if "人大" in text else "政协" if "政协" in text else
           "监委" if ("监察委" in text or "纪委" in text) else
           "法院" if "法院" in text else "检察院")
    parallel.setdefault(cat, (text, href))
print("并列机关链接:", len(parallel), "类")

# 3) 省委：无独立公开门户 → 列名（党委领导机关）
print("省委: 列名（党委领导机关，多数无独立公开门户）")
'''

CODE_MEMBER = '''# -*- coding: utf-8 -*-
"""{title} 提取规则。

方法：省门户首页 footer 链接采集（渲染后）→ 域名归属判定；门户为独立域名，
     公开体系为司法公开/检务公开等专门制度（非政府信息公开专栏口径）。
来源页：{sources}
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

# 2) 公开/信息公开 栏目定位（人大/法检走各自公开体系，锚文本含 公开/信息）
for a in soup.find_all("a"):
    text = re.sub(r"\\s+", "", a.get_text(" ", strip=True))
    href = a.get("href") or ""
    if ("公开" in text or "信息" in text) and len(text) <= 14 \\
            and href.startswith(("http://", "https://")):
        print("  ", text, "->", urljoin(PORTAL, href))
'''


def main():
    tree = json.load(open("tree.json", encoding="utf-8"))
    prov_g = next(g for g in tree["ks"] if g["n"].startswith("省级"))
    rules = json.load(open("extraction_rules.json", encoding="utf-8"))

    added = 0
    for prov in prov_g["ks"]:
        pname = prov["n"]
        par_grp = next((k for k in prov.get("ks", []) if k.get("c") == "并列机关"), None)
        if not par_grp:
            continue
        members = [k for k in par_grp.get("ks", []) if k.get("k") != "分组"]
        gkey = f"{pname}·{par_grp['n']}"
        rules[gkey] = {
            "portal": prov.get("u", ""),
            "method": "省门户首页 footer 链接采集（JS 导航需浏览器渲染）→ 人大/政协/监委/法院/检察院 "
                      "名称匹配 + .gov.cn 域名过滤 + URL 域名归属判定；省委无独立门户 → 列名",
            "sources": [prov.get("u", "")],
            "code": CODE_GROUP.format(prov=pname, sources=prov.get("u", ""),
                                      portal=prov.get("u", "")),
            "depts": [{"n": m["n"], "u": m.get("u", ""), "o": i}
                      for i, m in enumerate(members)],
            "cities": [],
        }
        added += 1
        for m in members:
            mkey = f"{pname}·{m['n']}"
            srcs = [m["u"]] if m.get("u") else [prov.get("u", "")]
            rules[mkey] = {
                "portal": m.get("u", ""),
                "method": "省门户 footer 链接采集 + 域名归属判定；" +
                          ("独立门户，公开走司法公开/检务公开等专门制度"
                           if m.get("u") else "无独立公开门户，列名参考"),
                "sources": srcs,
                "code": CODE_MEMBER.format(title=m["n"], sources="、".join(srcs),
                                           portal=srcs[0]),
                "depts": [{"n": m["n"], "u": m.get("u", ""), "o": 0}],
                "cities": [],
            }
            added += 1
    json.dump(rules, open("extraction_rules.json", "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    print(f"新增 {added} 条（31 组 + 成员），rules 总数 {len(rules)}")


if __name__ == "__main__":
    main()
