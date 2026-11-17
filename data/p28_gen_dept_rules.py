# -*- coding: utf-8 -*-
"""P28: 省政府部门（厅局组）提取规则补齐 —— 每省 1 条，提取结果为该省全部厅局（官网原始顺序）。"""
import json

from p21_gen_rules import METHODS

CODE_DEPT = '''# -*- coding: utf-8 -*-
"""{prov} 省政府部门（厅局）提取。

方法：{method}
来源页：{sources}

流程：首页/组织机构页请求 → 定位「部门网站」导航容器（标签文本匹配 →
     向上找 >=8 链接的祖先）→ 部门名模式过滤 → 域名归属判定（防跨省链接）
     → 保留 DOM 原始顺序（官网顺序，发改委在前）
     → 各厅局门户信息公开专栏定位 + 路径探测兜底
依赖：pip install requests beautifulsoup4 lxml
"""
import re
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

PORTAL = "{portal}"
SOURCES = {sources!r}
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")


def fetch(url):
    resp = requests.get(url, headers={{"User-Agent": UA}}, timeout=15, verify=False)
    if resp.encoding and "gb" in resp.encoding.lower():
        return resp.content.decode("gb18030", errors="replace")
    return resp.content.decode("utf-8", errors="replace")


# 1) 定位「部门网站」导航容器（首页 footer 常为 JS 渲染：
#    需浏览器渲染时见 p16_browser_footer.py CloakBrowser CDP 方案）
CONTAINER_RE = re.compile(r"(部门网站|委办局|厅局网站|政府部门|组成部门|直属机构|政府机构)")
boxes = set()
for src in SOURCES:
    soup = BeautifulSoup(fetch(src), "lxml")
    for text_node in soup.find_all(string=CONTAINER_RE):
        node = text_node.parent
        for _ in range(4):
            if node is None:
                break
            if len(node.find_all("a")) >= 8:
                boxes.add(node)
                break
            node = node.parent

# 2) 容器内链接过滤：部门名模式 + 域名
DEPT_RE = re.compile(
    r"^(省|市|自治区)?[^，。|、（）]{{1,12}}?"
    r"(委员会|办公厅|办公室|厅|局|委|办|中心|管委会|执法队|总队)$")
JUNK_TAIL = re.compile(r"(区|县|市|州|盟|旗)$")
JUNK_PREFIX = re.compile(r"^(国家|国务院|中央|中国|全国)")

departments = []        # 保持 DOM 原始顺序（官网顺序）
for box in boxes:
    for idx, a in enumerate(box.find_all("a")):
        name = re.sub(r"\\s+", "", (a.get("title") or a.get_text(" ", strip=True)).strip())
        url = urljoin(PORTAL, a.get("href") or "")
        host = urlparse(url).netloc.lower().replace("www.", "")
        if not DEPT_RE.match(name) or JUNK_TAIL.search(name) or JUNK_PREFIX.match(name):
            continue
        if not host.endswith(".gov.cn"):
            continue
        departments.append((idx, name, url))
    if departments:
        break

# 3) 归属判定：域名全拼/省域子域（防跨省导航，如全国文旅系统链接）
def detect_province(url):
    host = urlparse(url).netloc.lower()
    for key in ("{prov!s}".replace("省", "").replace("市", ""),
                "{prov!s}".replace("省", "").replace("市", "")):
        if key and key in host:
            return "{prov}"
    return None

for idx, name, url in departments:
    owner = detect_province(url)
    flag = "" if owner in ("{prov}", None) else "  <- 归属" + str(owner) + "，剔除"
    print(f"{{idx:3d}}  {{name:16s}} {{url}} {{flag}}")
'''


def main():
    tree = json.load(open("tree.json", encoding="utf-8"))
    prov_g = next(g for g in tree["ks"] if g["n"].startswith("省级"))
    rules = json.load(open("extraction_rules.json", encoding="utf-8"))

    added = 0
    for prov in prov_g["ks"]:
        pname = prov["n"]
        dept_grp = next((k for k in prov.get("ks", []) if k.get("c") == "厅局"), None)
        if not dept_grp:
            continue
        short = pname.replace("省", "").replace("市", "").replace("壮族自治区", "") \
            .replace("回族自治区", "").replace("维吾尔自治区", "").replace("自治区", "")
        method, srcs = METHODS.get(short, ("首页底部导航容器", [prov.get("u", "")]))
        gkey = f"{pname}·{dept_grp['n']}"
        members = [k for k in dept_grp.get("ks", []) if k.get("k") != "分组"]
        rules[gkey] = {
            "portal": prov.get("u", ""),
            "method": method,
            "sources": srcs,
            "code": CODE_DEPT.format(prov=pname, method=method,
                                     sources="、".join(srcs),
                                     portal=prov.get("u", "")),
            "depts": [{"n": m["n"], "u": m.get("u", ""), "o": i}
                      for i, m in enumerate(members)],
            "cities": [],
        }
        added += 1
    json.dump(rules, open("extraction_rules.json", "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    print(f"新增 {added} 条（厅局组），rules 总数 {len(rules)}")


if __name__ == "__main__":
    main()
