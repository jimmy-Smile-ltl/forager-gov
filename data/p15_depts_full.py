# -*- coding: utf-8 -*-
"""P15: 省级政府直属厅局全量重采 —— 从各省门户首页底部「部门网站」导航模块提取。

关键点（用户指正）：
- 北京 m_links_module3 隐藏 ul、四川 xgljuldiv 悬停弹出 —— 提取全部 <a>，不筛显示状态
- 宽松部门名模式：结尾 委/厅/局/办/室/中心/管委会/执法队/总队 且 2-16 字，
  或以 title 属性判定（title="市发展改革委"）
- 排除：中央机构（国家/国务院前缀）、外省域名（URL 判定）、区县/市州链接（结尾 区/市/县/州/盟/旗）
- 门户本站子路径（如市政府办公厅 beijing.gov.cn/gongkai/...）按 URL 收录
"""
import json
import re
import sys
from urllib.parse import urljoin, urlparse

sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开")
sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开/util")
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))

from p13_reattribute import detect_province  # noqa: E402

LOOSE_NAME = re.compile(r"^(省|市|自治区)?[^，。|、（）]{1,12}?(委员会|办公厅|办公室|厅|局|委|办|中心|管委会|执法队|总队)$")
BAD_TAIL = re.compile(r"(区|县|市|州|盟|旗|苏木)$")  # 区县/市州链接排除
CENTRAL_PREFIX = re.compile(r"^(国家|国务院|中央|中国|全国)")


def sf(url):
    try:
        from util.smart_fetch import smart_fetch
        html, method = smart_fetch(url, timeout=25)
        return html
    except Exception:
        return None


def is_dept_link(text, title, href):
    t = (text or "").strip()
    tt = (title or "").strip()
    if not t and not tt:
        return False
    cand = t if t else tt
    if CENTRAL_PREFIX.match(cand):
        return False
    if BAD_TAIL.search(cand):
        return False
    if LOOSE_NAME.match(cand):
        return True
    if LOOSE_NAME.match(tt or t):
        return True
    return False


def extract_footer_depts(html, portal, pname):
    """从首页提取部门链接 {(name, url)}，按域名去重；门户子路径按 URL 去重。"""
    from bs4 import BeautifulSoup
    if not html:
        return {}
    soup = BeautifulSoup(html, "lxml")
    portal_host = urlparse(portal).netloc.lower().replace("www.", "")
    out = {}
    for a in soup.find_all("a"):
        text = re.sub(r"\s+", "", a.get_text(" ", strip=True))
        title = a.get("title") or ""
        href = a.get("href") or ""
        if not href or href.startswith(("javascript", "#")):
            continue
        if not is_dept_link(text, title, href):
            continue
        abs_url = urljoin(portal, href)
        host = urlparse(abs_url).netloc.lower().replace("www.", "")
        if not host.endswith(".gov.cn"):
            continue
        # 外省域名排除（URL 判定）
        det = detect_province(abs_url)
        if det and det != pname:
            continue
        name = text or re.sub(r"\s+", "", title)
        if not name:
            continue
        if host != portal_host:
            key = host
        else:
            # 门户本站：仅收政务路径（gongkai/zfxxgk/nw 等）
            if not re.search(r"/(gongkai|zfxxgk|nw\d|zfjg|jgsz)", abs_url):
                continue
            key = abs_url.rstrip("/").rsplit("/", 1)[-1] or abs_url
            key = abs_url
        out.setdefault(key, (name, abs_url))
    return out


def main():
    provs = [json.loads(l) for l in open("province.jsonl", encoding="utf-8")]
    depts = [json.loads(l) for l in open("prov_depts.jsonl", encoding="utf-8")]
    existing_hosts = set()
    existing_urls = set()
    for r in depts:
        if r.get("portal_url"):
            existing_urls.add(r["portal_url"].rstrip("/"))
            existing_hosts.add(urlparse(r["portal_url"]).netloc.lower().replace("www.", ""))

    for p in provs:
        pname = p["name"]
        if pname == "新疆生产建设兵团":
            continue
        portal = p["portal_url"]
        html = sf(portal)
        if not html:
            print(f"{pname}: 首页获取失败", flush=True)
            continue
        found = extract_footer_depts(html, portal, pname)
        added = 0
        for key, (name, url) in found.items():
            u = url.rstrip("/")
            if u in existing_urls or urlparse(u).netloc.lower().replace("www.", "") in existing_hosts:
                continue
            depts.append({"name": name, "province": pname,
                          "category": "省政府组成部门/直属机构", "portal_url": u})
            existing_urls.add(u)
            existing_hosts.add(urlparse(u).netloc.lower().replace("www.", ""))
            added += 1
        total = sum(1 for r in depts if r["province"] == pname)
        print(f"{pname}: +{added} → 共 {total}", flush=True)

    with open("prov_depts.jsonl", "w", encoding="utf-8") as f:
        for r in sorted(depts, key=lambda x: (x["province"], x["name"])):
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"厅局总数: {len(depts)}", flush=True)


if __name__ == "__main__":
    main()
