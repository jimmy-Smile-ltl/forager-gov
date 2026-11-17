# -*- coding: utf-8 -*-
"""P33: 省级群团组织板块（省总工会/团省委/省妇联…）。

口径：中央编办群众团体机关的省级组织，与省政府部门并列于省人民政府之下
（党委领导的群团体系「条条」）。

流程：smart_fetch 抓 31 省门户首页 → 群团关键词链接提取
      → 归入 17 个规范成员槽 → 未命中者列名（无独立官网/未链接）。
键约定：组 = {省名}·群团组织（N）；成员 = {省名}·{成员名}（如 四川省·省总工会）。
"""
import json
import re
import sys
import os
from urllib.parse import urlparse

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
sys.path.insert(0, _ROOT + "/util")

# (成员名, 匹配关键词)
MEMBERS = [
    ("省总工会", "总工会|工会"),
    ("团省委", "共青团|团委"),
    ("省妇联", "妇联|妇女联合会"),
    ("省科协", "科协|科学技术协会"),
    ("省文联", "文联|文学艺术界"),
    ("省作协", "作协|作家协会"),
    ("省工商联", "工商联"),
    ("省侨联", "侨联"),
    ("省台联", "台联"),
    ("省残联", "残联"),
    ("省贸促会", "贸促|国际贸易促进"),
    ("省红十字会", "红十字"),
    ("省法学会", "法学会"),
    ("省记协", "记协|新闻工作者协会"),
    ("省人民对外友好协会", "对外友好协会|友协"),
    ("省计划生育协会", "计划生育协会"),
    ("省欧美同学会", "欧美同学会"),
]
CAT_RE = re.compile("|".join(k for _, k in MEMBERS))
EXCLUDE = re.compile(r"(国家|全国|中国|中央|中华|工委|妇联新闻|共青团新闻|要闻|动态)")


def sf(url):
    try:
        from util.smart_fetch import smart_fetch
        html, _ = smart_fetch(url, timeout=20)
        return html
    except Exception:
        return None


def extract(html, base):
    from bs4 import BeautifulSoup
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")
    host = urlparse(base).netloc.lower().replace("www.", "")
    out, seen = [], set()
    for a in soup.find_all("a"):
        text = re.sub(r"\s+", "", (a.get("title") or a.get_text(" ", strip=True)).strip())
        href = a.get("href") or ""
        if not text or not href.startswith(("http://", "https://")):
            continue
        if not CAT_RE.search(text) or EXCLUDE.search(text) or len(text) > 24:
            continue
        h = urlparse(href).netloc.lower().replace("www.", "")
        if not (h.endswith((".gov.cn", ".org.cn", ".org", ".net")) or h == host):
            continue
        if (text, href) in seen:
            continue
        seen.add((text, href))
        for name, pat in MEMBERS:
            if re.search(pat, text):
                out.append((name, text, href))
                break
    return out


def main(html_override=None):
    """html_override: {省名: 渲染后HTML}，供 p34 浏览器渲染补采复用。"""
    tree = json.load(open("tree.json", encoding="utf-8"))
    prov_g = next(g for g in tree["ks"] if g["n"].startswith("省级"))
    rules = json.load(open("extraction_rules.json", encoding="utf-8"))

    CODE_GQ = '''# -*- coding: utf-8 -*-
"""{prov} 群团组织提取（省总工会/团省委/省妇联…）。

方法：省门户首页链接采集（WAF 走 smart_fetch 降级链）→ 群团关键词匹配
      + 域名过滤（.gov.cn/.org.cn/.org）→ 归入规范成员槽；
      未命中者列名（多数省级群团无独立公开门户或未在门户链接）。
来源页：{sources}
依赖：pip install requests beautifulsoup4 lxml
"""
import re
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

PORTAL = "{portal}"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
KEYWORDS = {keywords!r}


def fetch(url):
    resp = requests.get(url, headers={{"User-Agent": UA}}, timeout=15, verify=False)
    if resp.encoding and "gb" in resp.encoding.lower():
        return resp.content.decode("gb18030", errors="replace")
    return resp.content.decode("utf-8", errors="replace")


html = fetch(PORTAL)
soup = BeautifulSoup(html, "lxml")
for a in soup.find_all("a"):
    text = re.sub(r"\\s+", "", (a.get("title") or a.get_text(" ", strip=True)).strip())
    href = a.get("href") or ""
    if not text or not href.startswith(("http://", "https://")):
        continue
    if not any(re.search(k, text) for k in KEYWORDS) or len(text) > 24:
        continue
    host = urlparse(href).netloc.lower()
    if not host.endswith((".gov.cn", ".org.cn", ".org", ".net")):
        continue
    print("  ", text, "->", href)
'''

    added_g = added_m = 0
    for prov in prov_g["ks"]:
        pname = prov["n"]
        # 防重：省内已有同名实体（如厅局组里已有省总工会）则跳过该成员；
        # 排除既有群团组自身（保证幂等：重复运行不吞成员）
        existing = set()
        def collect(n):
            if n.get("c") == "群团组织":
                return
            if not n.get("ks") or n.get("k") != "分组":
                existing.add(n["n"])
            for k in n.get("ks", []):
                collect(k)
        collect(prov)

        html = (html_override or {}).get(pname) or sf(prov.get("u", ""))
        hits = extract(html, prov.get("u", ""))
        slots = []
        for name, _ in MEMBERS:
            cand = [h for h in hits if h[0] == name]
            u = cand[0][2] if cand else ""
            slots.append({"n": name, "u": u})
        # 门户本站命中优先独立域名
        portal_host = urlparse(prov.get("u", "")).netloc.lower().replace("www.", "")
        for s in slots:
            cand = [h for h in hits if h[0] == s["n"]]
            ext = [h for h in cand
                   if urlparse(h[2]).netloc.lower().replace("www.", "") != portal_host]
            if ext:
                s["u"] = ext[0][2]

        members = [s for s in slots if s["n"] not in existing]
        gname = f"群团组织（{len(members)}）"
        grp = {"n": gname, "l": "省", "k": "分组", "c": "群团组织", "u": "",
               "x": "", "s": "", "m": "",
               "ks": [{"n": s["n"], "l": "省", "k": "群团组织", "c": "群团组织",
                       "u": s["u"], "x": "", "s": "", "m": ""} for s in members]}
        # 插到并列机关/厅局组之后、市之前；先移除既有群团组（幂等）
        kids = [k for k in prov["ks"] if k.get("c") != "群团组织"]
        prov["ks"] = kids
        idx = max([i for i, k in enumerate(kids) if k.get("c") in ("并列机关", "厅局")],
                  default=-1) + 1
        kids.insert(idx, grp)
        # 清理本轮未再生成的成员规则 + 旧组规则（防孤儿键）
        keep = {f"{pname}·{s['n']}" for s in members}
        for name, _ in MEMBERS:
            k = f"{pname}·{name}"
            if k in rules and k not in keep:
                del rules[k]
        stale_grp = [k for k in rules
                     if k.startswith(pname + "·群团组织（") and k != gkey]
        for k in stale_grp:
            del rules[k]

        # ---- 规则 ----
        gkey = f"{pname}·{gname}"
        rules[gkey] = {
            "portal": prov.get("u", ""),
            "method": "省门户首页链接采集（WAF 走 smart_fetch 降级链）→ 群团关键词匹配"
                      " + 域名过滤 → 归入规范成员槽；未命中者列名",
            "sources": [prov.get("u", "")],
            "code": CODE_GQ.format(prov=pname, sources=prov.get("u", ""),
                                   portal=prov.get("u", ""),
                                   keywords=[k for _, k in MEMBERS]),
            "depts": [{"n": s["n"], "u": s["u"], "o": i}
                      for i, s in enumerate(members)],
            "cities": [],
        }
        added_g += 1
        for s in members:
            mkey = f"{pname}·{s['n']}"
            rules[mkey] = {
                "portal": s["u"],
                "method": "省门户群团链接提取 + 域名归属判定；" +
                          ("独立门户（群团组织官网）"
                           if s["u"] else "无独立公开门户/未在门户链接 → 列名参考"),
                "sources": [s["u"]] if s["u"] else [prov.get("u", "")],
                "code": (f'# -*- coding: utf-8 -*-\n"""\n{pname} {s["n"]} 提取规则。\n'
                         f'门户：{s["u"]}\n'
                         '方法：省门户首页链接采集 → 群团关键词匹配 + 域名过滤。\n'
                         '"""\nimport re\nimport requests\n\n'
                         f'PORTAL = "{s["u"]}"\n'
                         'UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X '
                         '10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) '
                         'Chrome/125.0.0.0 Safari/537.36"}\n\n'
                         'html = requests.get(PORTAL, headers=UA, timeout=15, '
                         'verify=False).content.decode("utf-8", errors="replace")\n'
                         'print("页面长度:", len(html))\n')
                         if s["u"] else
                         (f'# -*- coding: utf-8 -*-\n"""{pname} {s["n"]}: '
                          '无独立公开门户（列名）。"""\n'),
                "depts": [{"n": s["n"], "u": s["u"], "o": 0}],
                "cities": [],
            }
            added_m += 1
        hit_n = sum(1 for s in members if s["u"])
        print(f"  {pname}: 群团组 {len(members)} 成员，命中门户 {hit_n}")

    json.dump(tree, open("tree.json", "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    json.dump(rules, open("extraction_rules.json", "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    print(f"p33 完成：新增 {added_g} 组规则 + {added_m} 成员规则，"
          f"rules 总数 {len(rules)}")


if __name__ == "__main__":
    main()
