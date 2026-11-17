# -*- coding: utf-8 -*-
"""P9b: 用 smart_fetch 补齐「无门户」的真实区县（链式重抓 + 拼音探测瑞数版）。

1. 省门户/市门户用 smart_fetch 重抓（WAF 现在可过），提取市/县链接
2. 剩余行拼音域名候选 → smart_fetch 验证标题
3. 再剩余 → Bing（沿用 p3c 逻辑）
"""
import json
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

_ROOT = "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开"
_UTIL = _ROOT + "/util"
sys.path.insert(0, _ROOT)
sys.path.insert(0, _UTIL)
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))

from common import norm_url  # noqa: E402
from p3_city_county import (  # noqa: E402
    collect_links, nav_pages_of, load_divisions, norm_prov_name, match_name, strip_suffix,
)
from p3b_fallback import SUFFIX_RE, short_name  # noqa: E402
from p7_browser_final import candidates_for, PSEUDO  # noqa: E402
from search_bing import search as bing_search  # noqa: E402

PSEUDO_RE = re.compile(PSEUDO.pattern) if hasattr(PSEUDO, "pattern") else re.compile(
    r"(市辖区|开发区|高新区|管理区|园区|工业区|示范区|合作区|保税区|实验区|管委会|循环化工园区|风景名胜区|新城)")


def sf(url):
    try:
        from util.smart_fetch import smart_fetch
        html, method = smart_fetch(url, timeout=25)
        return html
    except Exception:
        return None


def sf_verify(url, name):
    """smart_fetch 抓 url，标题含地名简称 → True。"""
    html = sf(url)
    if not html or len(html) < 800:
        return False
    m = re.search(r"<title>(.*?)</title>", html, re.S | re.I)
    if not m:
        return False
    title = re.sub(r"[\s|·\-—]", "", m.group(1))
    sn = short_name(name)
    return bool(sn and sn in title and "政务服" not in title)


def main():
    divs = load_divisions()
    cc = [json.loads(l) for l in open("city_county_final.jsonl", encoding="utf-8")]
    by_code = {r["code"]: r for r in cc}
    no_portal = [r for r in cc if not r.get("portal_url") and not PSEUDO_RE.search(r["name"])]
    print(f"p9b 目标 {len(no_portal)}", flush=True)

    prov_portals = {}
    for d in divs:
        if d["level"] in ("省", "特别行政区"):
            # 从 province.jsonl 拿省级门户
            pass
    for l in open("province.jsonl", encoding="utf-8"):
        r = json.loads(l)
        prov_portals[norm_prov_name(r["name"])] = r["portal_url"]

    found = {}

    # ---- 1) 省/市门户链式重抓（smart_fetch 版） ----
    # 按省聚合缺门户的市县
    by_prov = {}
    for r in no_portal:
        by_prov.setdefault(r["province"], []).append(r)

    for pname, targets in by_prov.items():
        pn = norm_prov_name(pname)
        portal = prov_portals.get(pn)
        if not portal:
            continue
        # 该省缺的是市还是县？
        need_cities = {r["name"] for r in targets if r["level"] == "市"}
        need_counties = {r["name"] for r in targets if r["level"] == "县"}

        # 省门户 → 市链接
        if need_cities:
            home = sf(portal)
            hits = collect_links(home, portal, need_cities, parent_names=(pn,))
            for np_ in nav_pages_of(home, portal)[:4]:
                nh = sf(np_)
                if nh:
                    for k, v in collect_links(nh, np_, need_cities, parent_names=(pn,)).items():
                        hits.setdefault(k, v)
            for name, (url, how) in hits.items():
                if sf_verify(url, name):
                    found[name] = (url, f"p9b链式({pn})")

        # 市门户 → 县链接（缺县的市的父级已解析门户）
        if need_counties:
            for r in targets:
                parent = r.get("parent") or ""
                prow = by_code.get(r["code"]) or r
                parent_portal = None
                # 父级门户（市）
                pd = next((d for d in divs if d["name"] == parent and d["level"] == "市"), None)
                if pd:
                    p_row = by_code.get(pd["code"])
                    parent_portal = p_row.get("portal_url") if p_row else None
                if parent_portal:
                    home = sf(parent_portal)
                    hits = collect_links(home, parent_portal, {r["name"]}, parent_names=(parent,))
                    if not hits:
                        for np_ in nav_pages_of(home, parent_portal)[:3]:
                            nh = sf(np_)
                            if nh:
                                for k, v in collect_links(nh, np_, {r["name"]}, parent_names=(parent,)).items():
                                    hits.setdefault(k, v)
                    if hits and hits.get(r["name"]) and sf_verify(hits[r["name"]][0], r["name"]):
                        found[r["name"]] = (hits[r["name"]][0], f"p9b链式({parent})")
        print(f"[p9b] {pn}: 链式已补 {sum(1 for r in targets if r['name'] in found)}/{len(targets)}", flush=True)

    # ---- 2) 拼音探测（smart_fetch 验证，WAF 可过） ----
    remaining = [r for r in no_portal if r["name"] not in found]
    print(f"[p9b] 拼音阶段 {len(remaining)}", flush=True)
    lock = threading.Lock()

    def pinyin_worker(r):
        for host in candidates_for(r["name"]):
            for scheme in ("https", "http"):
                if sf_verify(f"{scheme}://{host}/", r["name"]):
                    return r, f"{scheme}://{host}/"
        return r, None

    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = {ex.submit(pinyin_worker, r): r for r in remaining}
        for i, f in enumerate(as_completed(futs)):
            r, url = f.result()
            if url:
                found[r["name"]] = (url, "p9b拼音(smart_fetch)")
            if (i + 1) % 40 == 0:
                print(f"[p9b拼音] {i+1}/{len(remaining)} 累计{sum(1 for r in remaining if r['name'] in found)}", flush=True)

    # ---- 3) Bing 兜底（沿用 p3c 逻辑，验证也走 smart_fetch） ----
    remaining2 = [r for r in no_portal if r["name"] not in found]
    print(f"[p9b] Bing阶段 {len(remaining2)}", flush=True)

    def bing_worker(r):
        name, prov = r["name"], r["province"]
        sn = short_name(name)
        prov_sn = short_name(prov)
        for q in (f"{name}人民政府", f"{prov_sn}{name}人民政府官网"):
            try:
                results = bing_search(q, count=6, sleep=0.5)
            except Exception:
                continue
            for res in results:
                u = res["url"] or ""
                if not u.startswith(("http://", "https://")):
                    continue
                from urllib.parse import urlparse
                host = urlparse(u).netloc.lower()
                if not host.endswith(".gov.cn"):
                    continue
                blob = (res["title"] or "") + (res["cite"] or "")
                if sn not in blob and name not in blob:
                    continue
                root = f"https://{host}/"
                if sf_verify(root, name):
                    return r, root
        return r, None

    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = {ex.submit(bing_worker, r): r for r in remaining2}
        for i, f in enumerate(as_completed(futs)):
            r, url = f.result()
            if url:
                found[r["name"]] = (url, "p9b-bing")
            if (i + 1) % 30 == 0:
                print(f"[p9bBing] {i+1}/{len(remaining2)} 累计{sum(1 for r in remaining2 if r['name'] in found)}", flush=True)

    # ---- 回写 ----
    for r in no_portal:
        if r["name"] in found:
            r["portal_url"] = norm_url(found[r["name"]][0])
            r["how"] = found[r["name"]][1]
    with open("city_county_final.jsonl", "w", encoding="utf-8") as f:
        for r in sorted(by_code.values(), key=lambda x: x["code"]):
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    done = sum(1 for r in no_portal if r.get("portal_url"))
    print(f"p9b 完成: 补齐 {done}/{len(no_portal)}", flush=True)


if __name__ == "__main__":
    main()
