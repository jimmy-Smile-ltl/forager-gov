#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""p229 县级法院缺口：市中院官网「辖区法院」渠道补采（2026-11-17）。

p225 只在**省高院**页认领基层法院；山东/新疆/甘肃/广东等省高院页只列
部分法院，导致 674 个县级法院节点仍空。本轮换渠道：**本级中院官网**
（及其中「辖区法院 / 基层法院 / 法院导航」栏目页）提取同市中院下辖
基层法院链接——来源仍是官方页面真实 HTML（L1/L2），零猜测。

规则：
  - 只补空 u；已有 u 不覆盖
  - 匹配：链接文本/路径判定的县基底 × 本中院下辖县集合（防串市）
  - title 复验（县城名或机构名在标题内），失败退回锚文本严格校验
  - elink 链接解码（base64 / URL 编码两形态）
  - registry 写 `县级人民法院|<县名>`，来源留痕 s

用法：
  cd data && uv run python p229_court_mid_nav.py --dry
  cd data && uv run python p229_court_mid_nav.py
"""
import datetime
import json
import os
import shutil
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin, urlparse

DATA = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(DATA)
sys.path.insert(0, DATA)
from site_contract import base as _base, upsert_registry  # noqa: E402
from p223_county_5sys_fill import (page_title, unwrap, host_ok,  # noqa: E402
                                   NEWS_PATH, valid_candidate, prov_base)
import p223_county_5sys_fill as _p223  # noqa: E402
from p225_court_cleanup import court_links, b as court_base, nu  # noqa: E402

TREE_F = os.path.join(DATA, "tree.json")
REG_F = os.path.join(DATA, "site_registry.json")
TODAY = datetime.date.today().isoformat()
DRY = "--dry" in sys.argv
LIMIT = int(os.environ.get("P229_LIMIT", "0")) or None
_tl = threading.local()
NAV_KW = ("辖区法院", "基层法院", "下级法院", "法院导航", "法院地图",
          "机构设置", "本院概况", "网站地图", "友情链接", "基层院")


def _session():
    if not hasattr(_tl, "s"):
        from curl_cffi import requests as cr
        _tl.s = cr.Session(impersonate="chrome124")
    return _tl.s


PROXY = None


def init():
    global PROXY
    try:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(ROOT, ".env"))
        PROXY = os.getenv("TUNNEL_PROXY")
    except Exception:
        pass


def get(u, timeout=15):
    # 直连优先（隧道代理并发下会串响应），代理兜底
    for p in ([None, PROXY] if PROXY else [None]):
        try:
            kw = {"proxies": {"http": p, "https": p}} if p else {}
            r = _session().get(u, timeout=timeout, verify=False, **kw)
            if r.status_code == 200 and r.text and len(r.text) > 400:
                raw = r.content
                for enc in ("utf-8", "gb18030", "gbk"):
                    try:
                        return raw.decode(enc)
                    except Exception:
                        continue
        except Exception:
            continue
    return ""


def dec(u):
    return unwrap(u or "")


def county_set_of_city(city_node):
    out = {}
    for c in city_node.get("ks") or []:
        if c.get("k") == "人民政府" and (c.get("n") or "") != (city_node.get("n") or ""):
            out[court_base(c.get("n"))] = (c.get("n"), county_court_node(c))
    return {k: v for k, v in out.items() if k and v[1] is not None}


def county_court_node(county_node):
    """县节点下 并列机关 分组里的「县人民法院」叶子。"""
    for g in county_node.get("ks") or []:
        kids = g.get("ks") if "并列" in (g.get("n") or "") else [g]
        for d in kids or []:
            nm = d.get("n") or ""
            if "人民法院" in nm and "中级" not in nm and "高级" not in nm:
                return d
    return None


def find_court_node(city_node):
    for g in city_node.get("ks") or []:
        kids = (g.get("ks") or []) if "并列" in (g.get("n") or "") else [g]
        for d in kids:
            nm = d.get("n") or ""
            if "中级人民法院" in nm or (nm.endswith("中院") and "人民" not in nm):
                return d
    return None


def main():
    init()
    tree = json.load(open(TREE_F, encoding="utf-8"))
    reg = json.load(open(REG_F, encoding="utf-8"))
    blk = next(g for g in tree["ks"] if g["n"].startswith("省级"))
    _p223.ALL_PROV_BASES.update(prov_base(p.get("n") or "") for p in blk["ks"]
                                if prov_base(p.get("n") or ""))

    # 收集待办：(省, 市节点, 县基底, 县法院节点)
    jobs = []
    for prov in blk["ks"]:
        for city in prov.get("ks") or []:
            if city.get("k") != "人民政府" or city.get("l") not in ("市", "地级区"):
                continue
            mid = find_court_node(city)
            if not mid:
                continue
            counties = county_set_of_city(city)
            if not counties:
                continue
            miss = []
            for cb, (cname, node) in sorted(counties.items()):
                if node is not None and not (node.get("u") or "").strip():
                    miss.append((cb, cname, node))
            if not miss:
                continue
            if not (mid.get("u") or "").strip():
                continue
            jobs.append({"prov": prov.get("n"), "city": city, "mid": mid,
                         "miss": miss})
    # 重名县区（跨省）/ 同省他市名（防 title 串市）
    name_prov = {}
    for j in jobs:
        for cb, cname, _n in j["miss"]:
            name_prov.setdefault(cb, set()).add(j["prov"])
    city_by_prov = {}
    for j in jobs:
        city_by_prov.setdefault(j["prov"], set()).add(court_base(j["city"].get("n")))
    for j in jobs:
        j["siblings"] = sorted(x for x in city_by_prov.get(j["prov"], ())
                               if x and x != court_base(j["city"].get("n")))
        j["dup"] = any(len(name_prov.get(cb, ())) > 1 for cb, _c, _n in j["miss"])
    print(f"p229 待办中院: {len(jobs)}  待补县法院: {sum(len(j['miss']) for j in jobs)}")
    if LIMIT:
        jobs = jobs[:LIMIT]

    stat = {"mid": 0, "filled": 0, "cand": 0}
    lock = threading.Lock()

    def work(j):
        mid = j["mid"]
        base_url = mid["u"].strip()
        html = get(base_url)
        if not html:
            return j, []
        pages = [(base_url, html)]
        # 一层栏目页（辖区法院/机构设置）
        for m in __import__("re").finditer(
                r'<a[^>]+href=["\']([^"\'#]+)["\'][^>]*>(.*?)</a>', html, __import__("re").S):
            txt = __import__("re").sub(r"<[^>]+>", "", m.group(2))
            if any(k in txt for k in NAV_KW) and len(txt) < 20:
                nu_ = urljoin(base_url, m.group(1))
                if urlparse(nu_).netloc == urlparse(base_url).netloc:
                    pages.append((nu_, None))
        if len(pages) > 4:
            pages = pages[:4]
        links = []
        for pu, ph in pages:
            if ph is None:
                ph = get(pu)
                if not ph:
                    continue
            links.extend(court_links(pu, ph))
        out = []
        for cb, cname, node in j["miss"]:
            want = None
            city_b = court_base(j["city"].get("n"))
            for nm, u in links:
                u2 = dec(u)
                nb = court_base(nm)
                if not u2.startswith("http"):
                    continue
                if nb == cb or (nb.startswith(city_b) and nb[len(city_b):] == cb):
                    want = (nm, u2)
                    break
            if not want:
                continue
            ok, note = valid_candidate(
                {"county": {"n": cname}, "org_name": "县人民法院",
                 "prov": j["prov"], "parent": j["city"],
                 "dup": j.get("dup", False), "siblings": j.get("siblings") or []},
                want[1], want[0], strict=False)
            if not ok:
                continue
            out.append((node, want[1],
                        f"来源:{mid.get('n')}官网辖区法院导航·title验证({note})", cname))
        return j, out

    with ThreadPoolExecutor(6) as ex:
        for j, out in ex.map(work, jobs):
            if out:
                stat["mid"] += 1
            for node, u, src, cname in out:
                if DRY:
                    print(f"  [DRY] {j['prov']}/{j['city'].get('n')}/{cname} -> {u[:70]}")
                else:
                    node["u"] = u
                    node["s"] = src
                    key = f"县级人民法院|{court_base(cname)}"
                    upsert_registry(reg, key, u, name=cname,
                                    source_level="L2", source=src,
                                    verified_at=TODAY, locations=["块"])
                stat["filled"] += 1

    print("p229:", ", ".join(f"{k}={v}" for k, v in stat.items()),
          "（DRY 未写库）" if DRY else "")
    if not DRY and stat["filled"]:
        d = os.path.join(ROOT, "backups", TODAY)
        os.makedirs(d, exist_ok=True)
        ts = datetime.datetime.now().strftime("%H%M%S")
        shutil.copy2(TREE_F, os.path.join(d, f"tree_before_p229_{ts}.json"))
        shutil.copy2(REG_F, os.path.join(d, f"registry_before_p229_{ts}.json"))
        json.dump(tree, open(TREE_F, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        json.dump(reg, open(REG_F, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("  已写 tree.json / site_registry.json")


if __name__ == "__main__":
    main()
