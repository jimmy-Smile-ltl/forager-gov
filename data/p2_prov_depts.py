# -*- coding: utf-8 -*-
"""P2: 省厅局（省政府组成部门/直属机构）名单 + 门户 + 信息公开专栏 URL。

输入: province.jsonl + 各省政府门户
输出: prov_depts.jsonl
"""
import json
import re
import sys
from urllib.parse import urljoin, urlparse

sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
from common import fetch, find_xxgk_url, probe_xxgk_paths, norm_url, domain_of

# 部门名称形态（含厅/局/委/办/室，或具体机构词）
DEPT_NAME_RE = re.compile(
    r"^(省|市|自治区|自治州|州|盟)?[^，。|]{0,10}?"
    r"(人民政府办公室|政府办公厅|人民政府办公厅|办公厅|发展和改革委员会|教育委员会|科学技术委员会|经济和信息化委员会|卫生健康委员会|民族宗教事务委员会|国有资产监督管理委员会|住房和城乡建设委员会|交通委员会|商务委员会|农业农村委员会|文化和旅游委员会|市场监管委员会|财政厅|教育厅|科技厅|工业和信息化厅|公安厅|民政厅|司法厅|自然资源厅|生态环境厅|住房和城乡建设厅|交通运输厅|水利厅|农业农村厅|商务厅|文化和旅游厅|卫生健康委|退役军人事务厅|应急管理厅|审计厅|外事办|外事办公室|市场监督管理局|广播电视局|体育局|统计局|医疗保障局|林业局|中医药管理局|药品监督管理局|政务服务管理局|大数据管理局|国防动员办公室|人民防空办公室|地方金融监督管理局|机关事务管理局|监狱管理局|粮食和物资储备局|文物局|地震局|气象局|税务局|通信管理局|地质矿产勘查开发局|供销合作社|科学院|社会科学院|发展研究中心|办公厅|研究室|信访局|口岸管理办公室|政务服务和数字化建设管理局|人民政府驻京办事处|人民政府驻沪办事处|港澳事务办公室|台办|台湾事务办公室|参事室|发展改革委|住建厅|文旅厅|民宗委|林草局|乡村振兴局|能源局|水利厅|工业和信息化委|经信委|商务厅|广电局|工信厅|民政厅|公安厅|司法厅|财政厅|人社厅|生态环境厅|农业农村厅|商务厅|卫健委|文旅厅|应急厅|市场监管厅|药监局|医保局|体育局|统计局|林草局|民族宗教委|民委|教委|农委|粮食局|能源局|国防动员办|人防办|金融监管局|金融办|数据局|数字办|营商办|政务办|机关局|机关服务中心|驻京办|驻沪办|驻穗办)$"
)

# 页面导航中指向部门列表的关键词
DEPT_LIST_NAV = ["组织机构", "政府部门", "部门网站", "厅局", "直属机构", "组成部门", "政府机构", "机构设置", "部门频道"]

# 排除的中央机构域名片段
CENTRAL_DOMAINS = ("gov.cn",)  # 省厅局域名基本都是 gov.cn，中央域名需按名称排除
CENTRAL_HOSTS = {"www.gov.cn", "english.www.gov.cn", "big5.www.gov.cn"}


def extract_dept_links(html, base_url):
    """从页面提取疑似部门链接 [(名称, URL)]。"""
    from bs4 import BeautifulSoup

    out = []
    if not html:
        return out
    soup = BeautifulSoup(html, "lxml")
    seen = set()
    for a in soup.find_all("a"):
        text = re.sub(r"\s+", "", a.get_text(" ", strip=True))
        href = a.get("href") or ""
        if not text or href.startswith(("javascript", "#")):
            continue
        if len(text) > 20 or len(text) < 3:
            continue
        abs_url = urljoin(base_url, href)
        host = urlparse(abs_url).netloc.lower()
        if not host.endswith(".gov.cn") and host != "gov.cn":
            continue
        # 排除新闻/内容链接
        if re.search(r"\.(htm|html|shtml|pdf)$", abs_url.split("?")[0]) and "/art" in abs_url:
            continue
        if not DEPT_NAME_RE.match(text):
            continue
        key = (text, host)
        if key in seen:
            continue
        seen.add(key)
        out.append((text, abs_url))
    return out


def get_dept_list_pages(html, base_url):
    """从省政府首页找部门列表/组织机构页 URL。"""
    from bs4 import BeautifulSoup

    urls = []
    if not html:
        return urls
    soup = BeautifulSoup(html, "lxml")
    for a in soup.find_all("a"):
        text = re.sub(r"\s+", "", a.get_text(" ", strip=True))
        href = a.get("href") or ""
        if href.startswith(("javascript", "#")):
            continue
        if any(k in text for k in DEPT_LIST_NAV) and len(text) <= 10:
            urls.append(urljoin(base_url, href))
    return urls[:6]


def classify_dept(text, prov):
    """判断部门归属类别。"""
    if "办公厅" in text:
        return "省政府办公厅"
    if any(k in text for k in ("发展和改革", "发展改革委", "发改委")):
        return "省政府组成部门"
    if re.search(r"(厅|委员会|委员会)$", text) and "办公" not in text:
        return "省政府组成部门"
    if "审计厅" in text:
        return "省政府组成部门"
    if "局" in text or "办" in text or "室" in text:
        return "省政府直属机构/部门管理机构"
    return "省政府组成部门"


def main():
    provs = [json.loads(l) for l in open("province.jsonl", encoding="utf-8")]
    # 兵团单独处理（机关部门结构不同），其余 31 省
    provs = [p for p in provs if p["name"] != "新疆生产建设兵团"]
    print(f"目标省份 {len(provs)}")

    all_depts = {}  # domain -> rec
    for pi, p in enumerate(provs):
        pname, portal = p["name"], p["portal_url"]
        home = fetch(portal)
        direct = extract_dept_links(home, portal) if home else []
        depts = {u: (t, u) for t, u in direct}
        if len(depts) < 12:
            # 首页部门链接不全 → 找组织机构页
            for lp in get_dept_list_pages(home, portal):
                lh = fetch(lp)
                if not lh:
                    continue
                more = extract_dept_links(lh, lp)
                for t, u in more:
                    depts.setdefault(u, (t, u))
                if len(depts) >= 12:
                    break
        print(f"[{pi+1}/{len(provs)}] {pname}: {len(depts)} 部门")
        for url, (t, _u) in depts.items():
            host = urlparse(url).netloc.lower()
            all_depts.setdefault(host, {
                "name": t, "province": pname, "category": classify_dept(t, pname),
                "portal_url": norm_url(url),
            })

    recs = list(all_depts.values())
    print(f"去重后省厅局 {len(recs)} 个")

    # 解析各厅局信息公开专栏
    def worker(r):
        html = fetch(r["portal_url"])
        if html:
            u = find_xxgk_url(html, r["portal_url"])
            if u:
                r["xxgk_url"] = norm_url(u)
                r["xxgk_src"] = "导航链接"
                return True
        u = probe_xxgk_paths(r["portal_url"])
        if u:
            r["xxgk_url"] = norm_url(u)
            r["xxgk_src"] = "路径探测"
            return True
        return False

    from common import map_parallel
    map_parallel(recs, worker, workers=20, batch_label="厅局xxgk")

    with open("prov_depts.jsonl", "w", encoding="utf-8") as f:
        for r in sorted(recs, key=lambda x: (x["province"], x["name"])):
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    hit = sum(1 for r in recs if r.get("xxgk_url"))
    print(f"厅局信息公开URL命中 {hit}/{len(recs)}")


if __name__ == "__main__":
    main()
