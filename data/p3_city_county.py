# -*- coding: utf-8 -*-
"""P3: 市/县门户 URL 链式解析。

省门户首页 → 地级市网站链接 → 市门户首页 → 区县网站链接。
匹配：锚文本/option 文本 ↔ 区划名称（清洗+消歧）。
输出: city_portals.jsonl / county_portals.jsonl（含未匹配项，供 P3b 搜索兜底）
"""
import json
import re
import sys
from urllib.parse import urljoin, urlparse

sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
from common import fetch, norm_url, domain_of

# 导航页关键词
NAV_PAGE_KEYS = ["政府网站导航", "网站导航", "市州网站", "地市网站", "州政府网站", "地方政府网站",
                 "区县网站", "县市区网站", "区县政府", "各县区", "县区门户", "市政府网站", "区县链接"]
NAV_TITLE_KEYS = ["网站导航", "政府网站", "市州", "地市", "区县", "县区"]

GOV_LINK_RE = re.compile(r"\.gov\.cn", re.I)


def clean_text(t):
    t = re.sub(r"[\s·◆●▶■▲★　]", "", t)
    t = t.strip("|-—→>")
    return t


def strip_suffix(t):
    """去掉 政府/门户/网站 等后缀词。"""
    return re.sub(r"(人民政府|政府|门户网站|门户|网站|政务服务网|政务服务|官网|政务网|人民政府网)$", "", t)


def load_divisions():
    return json.load(open("divisions.json", encoding="utf-8"))


def norm_prov_name(p):
    """'四川省'→'四川'、'广西壮族自治区'→'广西'、'北京市'→'北京'。"""
    p = re.sub(r"(省|市|特别行政区)$", "", p)
    p = re.sub(r"(壮族|回族|维吾尔)?自治区$", "", p)
    return p


def collect_links(html, base_url, name_set, parent_names=(), min_text_len=2):
    """从页面收集匹配 name_set 中名称的链接 [(name, url, how)]。

    name_set: 目标区划名集合；parent_names: 需排除的上级名称（防 长沙市/长沙县 混淆）。
    """
    from bs4 import BeautifulSoup

    if not html:
        return {}
    soup = BeautifulSoup(html, "lxml")
    found = {}
    # <a> 链接
    for a in soup.find_all("a"):
        t = clean_text(a.get_text(" ", strip=True))
        h = a.get("href") or ""
        if not t or len(t) < min_text_len or h.startswith(("javascript", "#")):
            continue
        abs_url = urljoin(base_url, h)
        if not GOV_LINK_RE.search(abs_url):
            continue
        name = match_name(t, name_set, parent_names)
        if name and name not in found:
            found[name] = (abs_url, "a链接")
    # <select><option> 下拉（旧站常见）
    for sel in soup.find_all("select"):
        for opt in sel.find_all("option"):
            t = clean_text(opt.get_text(" ", strip=True))
            v = opt.get("value") or ""
            if not t:
                continue
            name = match_name(t, name_set, parent_names)
            if not name or name in found:
                continue
            if v and v.startswith(("http://", "https://")):
                found[name] = (v, "select下拉")
            elif v and GOV_LINK_RE.search(v):
                found[name] = (urljoin(base_url, v), "select下拉")
    return found


def match_name(t, name_set, parent_names=()):
    """t 中匹配区划名。优先精确，其次包含（防上级名称干扰）。"""
    s = strip_suffix(t)
    if not s:
        return None
    if s in name_set:
        return s
    for n in name_set:
        if len(s) <= len(n) + 6 and (s.endswith(n) or s.startswith(n)):
            if n in parent_names and s != n:
                continue
            return n
    return None


def nav_pages_of(html, base_url):
    """从首页找 政府网站导航 类页面。"""
    from bs4 import BeautifulSoup

    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")
    urls = []
    for a in soup.find_all("a"):
        t = clean_text(a.get_text(" ", strip=True))
        h = a.get("href") or ""
        if h.startswith(("javascript", "#")) or not t:
            continue
        if len(t) <= 12 and any(k in t for k in NAV_PAGE_KEYS):
            urls.append(urljoin(base_url, h))
    return urls[:8]


def resolve_children(prov_name, portal_url, child_divs):
    """抓 省级门户 → 匹配子级区划。返回 {name: (url, how)}"""
    found = {}
    name_set = {d["name"] for d in child_divs}
    home = fetch(portal_url)
    found.update(collect_links(home, portal_url, name_set, parent_names=(prov_name,)))
    if len(found) >= max(3, len(child_divs) * 0.6):
        return found
    # 导航页兜底
    for np_ in nav_pages_of(home, portal_url):
        nh = fetch(np_)
        if not nh:
            continue
        more = collect_links(nh, np_, name_set, parent_names=(prov_name,))
        for k, v in more.items():
            found.setdefault(k, v)
        if len(found) >= max(3, len(child_divs) * 0.8):
            break
    return found


def main():
    divs = load_divisions()
    provs = [json.loads(l) for l in open("province.jsonl", encoding="utf-8")]
    # 名称规范化对齐：divisions 用全称（四川省），province.jsonl 用简称（四川）
    prov_portal = {}
    for p in provs:
        if p["name"] == "新疆生产建设兵团":
            continue
        prov_portal[norm_prov_name(p["name"])] = p["portal_url"]

    cities = [d for d in divs if d["level"] == "市"]
    counties = [d for d in divs if d["level"] == "县"]

    # ---------- 阶段1: 省 → 市 ----------
    city_found = {}
    for pname, portal in prov_portal.items():
        kids = [d for d in cities if norm_prov_name(d["province"]) == pname]
        if not kids:
            print(f"{pname}: 无地级市（直辖市/直管）", flush=True)
            continue
        found = resolve_children(pname, portal, kids)
        city_found.update(found)
        miss = len(kids) - len(found)
        print(f"{pname}: 市 {len(found)}/{len(kids)}" + (f" 缺{miss}" if miss else ""), flush=True)

    # ---------- 阶段2: 市 → 县（含直辖市/省直辖：省 → 县） ----------
    county_found = {}
    for pname, portal in prov_portal.items():
        # 直辖市 / 省直辖县：从省门户直接找
        direct_kids = [d for d in counties if norm_prov_name(d["province"]) == pname and d["parent"] == d["province"]]
        if direct_kids:
            found = resolve_children(pname, portal, direct_kids)
            county_found.update(found)
            print(f"{pname}: 直辖县 {len(found)}/{len(direct_kids)}", flush=True)

    city_portal_map = {}  # 市名 -> URL
    for d in cities:
        v = city_found.get(d["name"])
        if v:
            city_portal_map[d["name"]] = v[0]

    for d in cities:
        kids = [x for x in counties if x["parent"] == d["name"]]
        if not kids:
            continue
        cname = d["name"]
        cp = city_portal_map.get(cname)
        if not cp:
            continue
        found = resolve_children(cname, cp, kids)
        county_found.update(found)
        miss = len(kids) - len(found)
        if miss or len(found) < 3:
            print(f"  {cname}: 县 {len(found)}/{len(kids)}" + (f" 缺{miss}" if miss else ""), flush=True)

    # ---------- 输出 ----------
    def dump(path, divs, found):
        rows = []
        for d in divs:
            v = found.get(d["name"])
            rows.append({
                "code": d["code"], "name": d["name"], "level": d["level"],
                "province": d["province"], "parent": d["parent"],
                "portal_url": norm_url(v[0]) if v else "",
                "how": v[1] if v else "未匹配",
            })
        with open(path, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        hit = sum(1 for r in rows if r["portal_url"])
        print(f"{path}: {hit}/{len(rows)}")

    dump("city_portals.jsonl", cities, city_found)
    dump("county_portals.jsonl", counties, county_found)


if __name__ == "__main__":
    main()
