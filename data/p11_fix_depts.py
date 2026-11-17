# -*- coding: utf-8 -*-
"""P11: 厅局修正 —— 清中央残留 + smart_fetch 补采缺厅局的省。

缺厅局的省：北京 0 / 甘肃 0 / 广东 1 / 湖南 1 / 天津 10 / 上海 15 / 重庆 17
"""
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
from p2_prov_depts import extract_dept_links, get_dept_list_pages, DEPT_NAME_RE  # noqa: E402

CENTRAL_PREFIX = re.compile(r"^(国家|国务院|中央|中国|全国)")


def sf(url):
    try:
        from util.smart_fetch import smart_fetch
        html, method = smart_fetch(url, timeout=25)
        return html
    except Exception:
        return None


def is_central_leftover(r):
    """中央机构误采行：名称带中央前缀且不含省名（垂管驻省机构保留）。"""
    if not CENTRAL_PREFIX.match(r["name"]):
        return False
    prov_short = re.sub(r"(省|市|自治区|特别行政区)$", "", r["province"])
    prov_short = re.sub(r"(壮族|回族|维吾尔)?自治区$", "", prov_short)
    if prov_short and prov_short in r["name"]:
        return False  # 如 国家税务总局江西省税务局
    return True


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


def main():
    depts = [json.loads(l) for l in open("prov_depts.jsonl", encoding="utf-8")]

    # ---- 1) 清中央残留 ----
    keep, drop = [], []
    for r in depts:
        (drop if is_central_leftover(r) else keep).append(r)
    print("清残留:", [(r['province'], r['name']) for r in drop])
    depts = keep

    # ---- 2) 补采缺厅局的省 ----
    TARGETS = {
        "北京": "https://www.beijing.gov.cn/", "天津": "https://www.tj.gov.cn/",
        "上海": "https://www.shanghai.gov.cn/", "重庆": "https://www.cq.gov.cn/",
        "广东": "https://www.gd.gov.cn/", "湖南": "https://www.hunan.gov.cn/",
        "甘肃": "https://www.gansu.gov.cn/",
    }
    existing = {(r["province"], urlparse(r["portal_url"]).netloc.lower().replace("www.", "")): r
                for r in depts if r.get("portal_url")}

    for pname, portal in TARGETS.items():
        print(f"== 补采 {pname}", flush=True)
        home = sf(portal)
        found = {}
        if home:
            found.update({urlparse(u).netloc: (t, u) for t, u in extract_dept_links(home, portal)})
        if len(found) < 15:
            for lp in get_dept_list_pages(home, portal)[:5]:
                lh = sf(lp)
                if not lh:
                    continue
                for t, u in extract_dept_links(lh, lp):
                    found.setdefault(urlparse(u).netloc, (t, u))
                if len(found) >= 15:
                    break
        print(f"   提取 {len(found)} 个候选", flush=True)
        new_cnt = 0
        for host, (t, u) in found.items():
            host_n = host.replace("www.", "")
            if (pname, host_n) in existing:
                continue
            rec = {"name": t, "province": pname, "category": "省政府组成部门/直属机构",
                   "portal_url": norm_url(u)}
            resolve_xxgk(rec)
            depts.append(rec)
            existing[(pname, host_n)] = rec
            new_cnt += 1
        print(f"   新增 {new_cnt}", flush=True)

    # 去重（域名）
    by_host = {}
    for r in depts:
        h = urlparse(r["portal_url"]).netloc.lower().replace("www.", "") if r.get("portal_url") else ""
        if h and h not in by_host:
            by_host[h] = r
    final = list(by_host.values()) + [r for r in depts if not r.get("portal_url")]
    with open("prov_depts.jsonl", "w", encoding="utf-8") as f:
        for r in sorted(final, key=lambda x: (x["province"], x["name"])):
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"厅局总数: {len(final)}", flush=True)


if __name__ == "__main__":
    main()
