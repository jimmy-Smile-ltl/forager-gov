# -*- coding: utf-8 -*-
"""P11b: 厅局修正第二弹 —— 清洗误采 + 针对 北京/广东/湖南/上海/天津/重庆 定向补采。"""
import json
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

_ROOT = "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开"
_UTIL = _ROOT + "/util"
sys.path.insert(0, _ROOT)
sys.path.insert(0, _UTIL)
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))

from common import find_xxgk_url, norm_url, probe_xxgk_paths  # noqa: E402
from p2_prov_depts import extract_dept_links  # noqa: E402
from search_bing import search as bing_search  # noqa: E402

CENTRAL_PREFIX = re.compile(r"^(国家|国务院|中央|中国|全国)")


def sf(url):
    try:
        from util.smart_fetch import smart_fetch
        html, method = smart_fetch(url, timeout=25)
        return html
    except Exception:
        return None


def is_junk(r):
    """误采行：中央前缀无省名 / 门户为省门户本站 / 政务服务网 / 公开目录内容页。"""
    name, prov = r["name"], r["province"]
    u = r.get("portal_url", "")
    host = urlparse(u).netloc.lower()
    if not u:
        return name.startswith(("国家", "国务院", "中央"))
    if CENTRAL_PREFIX.match(name):
        prov_short = re.sub(r"(省|市|自治区|特别行政区)$", "", prov)
        prov_short = re.sub(r"(壮族|回族|维吾尔)?自治区$", "", prov_short)
        if not (prov_short and prov_short in name):
            return True
    if "zwfw" in host or "icity" in host or "onething" in u:
        return True
    if "gkmlpt/content" in u or re.search(r"/content/\d+", u):
        return True
    # 门户 = 省门户本站（如 gansu.gov.cn 挂中央链接）
    prov_hosts = {
        "北京": "www.beijing.gov.cn", "天津": "www.tj.gov.cn", "上海": "www.shanghai.gov.cn",
        "重庆": "www.cq.gov.cn", "广东": "www.gd.gov.cn", "湖南": "www.hunan.gov.cn",
        "甘肃": "www.gansu.gov.cn", "河北": "www.hebei.gov.cn", "山西": "www.shanxi.gov.cn",
        "内蒙古": "www.nmg.gov.cn", "辽宁": "www.ln.gov.cn", "吉林": "www.jl.gov.cn",
        "黑龙江": "www.hlj.gov.cn", "江苏": "www.jiangsu.gov.cn", "浙江": "www.zj.gov.cn",
        "安徽": "www.ah.gov.cn", "福建": "www.fujian.gov.cn", "江西": "www.jiangxi.gov.cn",
        "山东": "www.shandong.gov.cn", "河南": "www.henan.gov.cn", "湖北": "www.hubei.gov.cn",
        "广西": "www.gxzf.gov.cn", "海南": "www.hainan.gov.cn", "四川": "www.sc.gov.cn",
        "贵州": "www.guizhou.gov.cn", "云南": "www.yn.gov.cn", "西藏": "www.xizang.gov.cn",
        "陕西": "www.shaanxi.gov.cn", "青海": "www.qinghai.gov.cn", "宁夏": "www.nx.gov.cn",
        "新疆": "www.xinjiang.gov.cn",
    }
    if prov_hosts.get(prov) and host == prov_hosts[prov]:
        return True
    return False


def resolve_xxgk(r):
    html = sf(r["portal_url"])
    if html:
        u = find_xxgk_url(html, r["portal_url"])
        if u:
            r["xxgk_url"] = norm_url(u)
            r["xxgk_src"] = "smart_fetch导航"
            return
    u = probe_xxgk_paths(r["portal_url"])
    if u:
        r["xxgk_url"] = norm_url(u)
        r["xxgk_src"] = "路径探测"


def find_list_pages(pname, portal):
    """候选部门列表页 URL：已知模式探测 + Bing。"""
    cands = []
    base = portal.rstrip("/")
    patterns = {
        "北京": ["/zhengfu/", "/zhengfu/zfjg/", "/zhengce/zwgk/zfjg/", "/gjzfx/"],
        "广东": ["/zfjg/", "/zwgk/zfjg/", "/zfxxgk/zfjg/", "/zjxw/zfjg/"],
        "湖南": ["/hnszf/zfjg/", "/zfjg/", "/zwgk/zfjg/"],
        "上海": ["/nw48056/index.html", "/zfjg/"],
        "天津": ["/zfjg/", "/zfxxgk/zfjg/"],
        "重庆": ["/zfjg/", "/zwgk/zfjg/"],
    }
    for p in patterns.get(pname, []):
        cands.append(base + p)
    try:
        for q in (f"{pname}人民政府 组织机构", f"{pname}政府 部门网站"):
            for r in bing_search(q, count=6, sleep=0.5):
                u = r["url"] or ""
                if u.startswith("http") and urlparse(u).netloc.endswith(".gov.cn"):
                    cands.append(u)
    except Exception:
        pass
    return cands


def collect_province(pname, portal, existing_hosts):
    """返回该省新增部门列表。"""
    new_recs = []
    seen_hosts = set(existing_hosts)
    for lp in find_list_pages(pname, portal):
        html = sf(lp)
        if not html:
            continue
        for t, u in extract_dept_links(html, lp):
            host = urlparse(u).netloc.lower().replace("www.", "")
            if host in seen_hosts or host == "":
                continue
            if is_junk({"name": t, "province": pname, "portal_url": u}):
                continue
            seen_hosts.add(host)
            rec = {"name": t, "province": pname, "category": "省政府组成部门/直属机构",
                   "portal_url": norm_url(u)}
            resolve_xxgk(rec)
            new_recs.append(rec)
        if len(new_recs) >= 15:
            break
    return new_recs


def main():
    depts = [json.loads(l) for l in open("prov_depts.jsonl", encoding="utf-8")]
    before = len(depts)
    kept, dropped = [], []
    for r in depts:
        (dropped if is_junk(r) else kept).append(r)
    print(f"清洗误采: {len(dropped)} 行", flush=True)
    for r in dropped:
        print("  ✗", r["province"], r["name"], "|", r.get("portal_url", "")[:50], flush=True)
    depts = kept

    targets = {
        "北京": "https://www.beijing.gov.cn/", "广东": "https://www.gd.gov.cn/",
        "湖南": "https://www.hunan.gov.cn/", "上海": "https://www.shanghai.gov.cn/",
        "天津": "https://www.tj.gov.cn/", "重庆": "https://www.cq.gov.cn/",
    }
    for pname, portal in targets.items():
        existing_hosts = {urlparse(r["portal_url"]).netloc.lower().replace("www.", "")
                          for r in depts if r["province"] == pname and r.get("portal_url")}
        new_recs = collect_province(pname, portal, existing_hosts)
        depts += new_recs
        print(f"{pname}: +{len(new_recs)} → 共 {sum(1 for r in depts if r['province']==pname)}", flush=True)

    # 去重
    by_host = {}
    for r in depts:
        h = urlparse(r["portal_url"]).netloc.lower().replace("www.", "") if r.get("portal_url") else ""
        if h and h not in by_host:
            by_host[h] = r
    final = list(by_host.values()) + [r for r in depts if not r.get("portal_url")]
    with open("prov_depts.jsonl", "w", encoding="utf-8") as f:
        for r in sorted(final, key=lambda x: (x["province"], x["name"])):
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"厅局 {before} → {len(final)}", flush=True)


if __name__ == "__main__":
    main()
