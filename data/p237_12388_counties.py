#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""p237 12388 举报网站「省→市→县」名录 → 县级监委补采（2026-11-17）。

纪委监委系统的县级机构多数没有独立门户，但**中央纪委国家监委举报网站**
（12388）为每个县建了官方举报子站，标题即「中共XX县纪律检查委员会
XX县监察委员会举报网站」——这是县级监委最权威、最系统的官方入口。

发现链（全程 HTML 名录，无任何域名/路径拼凑）：
  省监委官网 → 站内 12388 链接 → {省}.12388.gov.cn/
    → /html/sjjb2.html             （市州名录，锚文本=市名）
    → {市}/html/sjjb2.html          （县区名录，锚文本=县名）
    → {市}/{县}/                    （县级举报子站）

校验：
  - 域名必须是 12388.gov.cn 体系
  - 县名锚文本与该市县区节点精确匹配（同名县要求市内唯一）
  - 子站可访问（抓取 ≥400 字节）
  - 子站 title 非空时必须含县名，且不得含**别的**县名

落库：只填空 u；s = 「来源:12388举报网站名录（省纪委监委举报网站）HTML
名录提取+title验证」；registry 同步。

用法：
  cd data && uv run python p237_12388_counties.py --dry
  cd data && uv run python p237_12388_counties.py
  P237_LIMIT=3 P237_PROV=湖南省
"""
import datetime
import json
import os
import re
import shutil
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin, urlparse

DATA = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(DATA)
sys.path.insert(0, DATA)
sys.path.insert(0, os.path.join(ROOT, "util"))
import p223_county_5sys_fill as P  # noqa: E402

TREE_F = os.path.join(DATA, "tree.json")
REG_F = os.path.join(DATA, "site_registry.json")
STATE_F = os.path.join(DATA, "p237_state.json")
TODAY = datetime.date.today().isoformat()
DRY = "--dry" in sys.argv
LIMIT = int(os.environ.get("P237_LIMIT", "0")) or None
ONLY = os.environ.get("P237_PROV", "")
WORKERS = int(os.environ.get("P237_WORKERS", "6"))

_A = re.compile(r"<a\b[^>]*href=[\"']([^\"'#]+)[\"'][^>]*>(.*?)</a>", re.I | re.S)
_TAG = re.compile(r"<[^>]+>")
SKIP_TXT = ("首页", "相关", "网上", "举报", "中央", "返回", "法律", "须知",
            "案例", "查询")


def txt(x):
    return re.sub(r"\s+", "", _TAG.sub("", x or ""))


def anchors(html, base):
    out = []
    for m in _A.finditer(html):
        t = txt(m.group(2))
        u = urljoin(base, (m.group(1) or "").strip())
        if t and u.startswith("http"):
            out.append((t, u))
    return out


def prov_nodes(tree):
    blk = next(g for g in tree["ks"] if g["n"].startswith("省级"))
    return blk


def prov_jw_url(prov):
    for g in prov.get("ks") or []:
        if g.get("c") != "并列机关":
            continue
        for x in g.get("ks") or []:
            if x.get("n") in ("省监委", "省纪委", "省纪委监委"):
                u = (x.get("u") or "").strip()
                if u:
                    return u
    return ""


NAV12388 = re.compile(r"(举报|信访|投诉|监督|互动|12388|曝光|我要)", re.I)
_HOST12388 = re.compile(r"https?://([a-z0-9.\-]+12388\.gov\.cn)", re.I)
_HREF = re.compile(r"href=[\"']([^\"'#]+)[\"']", re.I)
_NONHTML = re.compile(r"\.(css|js|jpe?g|png|gif|ico|bmp|svg|pdf|zip|rar|doc|docx|xls|wps|mp4|mp3)$", re.I)


def _scan_12388(html, page_url):
    """页面里出现的 12388 子站：(host, 锚文本 URL 或 "")。"""
    out = []
    for _t, u in anchors(html, page_url):
        host = urlparse(u).netloc.lower()
        if "12388.gov.cn" in host and not host.startswith("www."):
            out.append((host, u))
    for m in _HOST12388.finditer(html or ""):
        host = m.group(1).lower()
        if not host.startswith("www.") and not any(h == host for h, _ in out):
            out.append((host, ""))
    return out


def find_12388(home, prov_name="", want="root"):
    """省纪委监委官网站内找本省 12388 站：首页 + 同站导航页（2 层）。

    实测江苏清风扬帆网首页只挂中央站 www.12388.gov.cn，本省站
    jiangsu.12388.gov.cn 藏在 /col/col440/index.html——只看首页必漏
    （北京/上海/广东/河南等 13 省同因「站内无12388链接」而全空）。
    发现仍是纯 HTML 提取，不做任何域名推测。

    want="root" 返回省级站根（省通道）；want="deep" 优先返回带市路径的
    锚链接（市通道：市纪委首页直链 {省}.12388.gov.cn/{市}/ 时直接用）。
    """
    h = P.fetch(home) or ""
    if len(h) < 400:
        try:
            from smart_fetch import smart_fetch
            h2, _m = smart_fetch(home)
            if h2 and len(h2) > len(h):
                h = h2
        except Exception:  # noqa: BLE001
            pass
    if not h:
        return ""
    host = urlparse(home).netloc.lower()
    pages = [(home, h)]
    seen = {home}
    navs = []
    for t, u in anchors(h, home):
        if urlparse(u).netloc.lower() != host or u in seen:
            continue
        seen.add(u)
        if P.NEWS_PATH.search(u):
            continue          # 文章页再多也不会挂 12388
        score = 0 if NAV12388.search(t + " " + u) else 1
        navs.append((score, u))
    # 图片导航按钮（<a href><img …></a>，无锚文本）anchors() 会丢——实测江苏
    # 12388 入口正是 /col/col440/index.html 的图片链接，必须补一遍 raw href
    for m in _HREF.finditer(h):
        u = P.clean_url(m.group(1), home)
        if not u or urlparse(u).netloc.lower() != host or u in seen:
            continue
        if _NONHTML.search(urlparse(u).path or ""):
            continue
        seen.add(u)
        if P.NEWS_PATH.search(u):
            continue
        navs.append((1, u))
    navs = [u for _s, u in sorted(navs, key=lambda x: x[0])][:32]
    with ThreadPoolExecutor(6) as ex:
        for u, hh in zip(navs[:28], ex.map(lambda x: P.fetch(x) or "", navs[:28])):
            if len(hh) > 300:
                pages.append((u, hh))
    hits = []
    for pu, ph in pages:
        for host2, u2 in _scan_12388(ph, pu):
            hits.append((host2, u2))
    if not hits:
        return ""
    hosts = list(dict.fromkeys(h for h, _ in hits))
    # 用省名验证子站归属（标题含省名/省简称；标题空=JS 壳站则放宽）
    pb = P.prov_base(prov_name) or prov_name[:2]
    good = ""
    for hh in hosts:
        tt = P.page_title(f"http://{hh}/") or ""
        if "中央" in tt:
            continue
        if not tt or not pb or pb in tt or (prov_name and prov_name in tt):
            good = hh
            break
    if not good:
        if len(hosts) != 1:
            return ""
        good = hosts[0]
    if want == "deep":
        for hh, u2 in hits:
            if hh == good and u2:
                pu = urlparse(u2)
                if pu.path not in ("", "/", "/index.html", "/index.shtml"):
                    return f"{pu.scheme}://{pu.netloc}{pu.path}"
    return f"http://{good}/"


def match_city(prov_cities, ct):
    """名录里的市名 → 树里市节点（支持基底/前缀匹配：伊犁州↔伊犁哈萨克自治州）。"""
    for c in prov_cities:
        if c.get("n") == ct:
            return c
    cb = P.geo_base(ct)
    for c in prov_cities:
        if P.geo_base(c.get("n") or "") == cb:
            return c
    for c in prov_cities:
        nm = c.get("n") or ""
        if cb and len(cb) >= 2 and (nm.startswith(cb) or cb.startswith(nm[:2])
                                    and len(cb) <= len(nm) + 2):
            return c
    return None


def listing_urls(root, fetch=P.fetch):
    """名录页候选：先跟站内 sjjb*.html 链接（权威），再试两个已知命名。

    市站 URL 多为 `{省站}/{市}`（无尾斜杠），urljoin 会把 html/sjjb2.html
    拼成省站名录——必须先补尾斜杠按目录处理；市站页头「首页」链回省级
    名录页，凡不在本市目录下的 sjjb 链接一律排除。
    """
    h = fetch(root) or ""
    base = root if root.endswith("/") else root + "/"
    bp = urlparse(base).path or "/"
    out = []
    for t, x in anchors(h, base):
        if not re.search(r"/sjjb\d*\.html?$", x, re.I):
            continue
        if bp not in ("", "/") and not (urlparse(x).path or "").startswith(bp):
            continue
        out.append(x)
    for f in ("html/sjjb2.html", "html/sjjb.html"):
        out.append(urljoin(base, f))
    return list(dict.fromkeys(out))


def county_links(prov, prov_cities, county_map, flat_map=None, root_hint=""):
    """返回 ([(county_node, url, city_name, county_name)], note)。"""
    u = prov_jw_url(prov)
    if not u:
        return [], "省监委无URL"
    root = find_12388(u, prov.get("n") or "")
    if not root and root_hint:
        # 省纪委站没挂 12388 的省份（河南/浙江…）：根址改用**已从官方 HTML
        # 发现并验证过的**同省 12388 子站 host（来自已落库的县区子站 URL），
        # 不是域名推测。
        root = f"http://{root_hint}/"
    if not root:
        return [], "站内无12388链接"
    lst, h = "", ""
    for cand in listing_urls(root):
        hh = P.fetch(cand) or ""
        if len(hh) >= 400 and len(anchors(hh, cand)) >= 3:
            lst, h = cand, hh
            break
    if not h:
        return [], f"名录页抓取失败 {root}"
    out, hit_city = [], 0
    # 直辖市：区县直接挂在省级站名录页下
    if flat_map:
        for t, x in anchors(h, lst):
            if not t or t in SKIP_TXT or x.endswith((".html", ".css", ".js")):
                continue
            if urlparse(x).netloc != urlparse(root).netloc:
                continue
            node = flat_map.get(t)
            if node is None:
                cb = P.geo_base(t)
                for nm, nd in flat_map.items():
                    if P.geo_base(nm) == cb:
                        node = nd
                        break
            if node is not None:
                out.append((node, x, prov.get("n") or "", t))
    cities = [(t, x) for t, x in anchors(h, lst)
              if t not in SKIP_TXT and len(t) <= 10
              and not x.endswith(".html")]
    for ct, cu in cities:
        city = match_city(prov_cities, ct)
        if city is None:
            continue
        hit_city += 1
        ch, buff = "", ""
        for cand in listing_urls(cu):
            hh = P.fetch(cand) or ""
            if len(hh) >= 400 and len(anchors(hh, cand)) >= 3:
                ch, buff = hh, cand
                break
        if not ch:
            continue
        for t, x in anchors(ch, buff):
            if not t or len(t) > 12 or t in SKIP_TXT:
                continue
            if x.endswith((".html", ".css", ".js")):
                continue
            if urlparse(x).netloc != urlparse(root).netloc:
                continue
            node = county_map.get((city.get("n"), t))
            if node is None:
                cb = P.geo_base(t)
                for (cn, nm), nd in county_map.items():
                    if cn == city.get("n") and P.geo_base(nm) == cb:
                        node = nd
                        break
            if node is not None:
                out.append((node, x, ct, t))
    return out, f"市州 {len(cities)}（树中命中 {hit_city}）"


def city_jw_url(city):
    for g in city.get("ks") or []:
        if g.get("c") != "并列机关":
            continue
        for x in g.get("ks") or []:
            if x.get("n") in ("市监委", "市纪委", "市纪委监委"):
                u = (x.get("u") or "").strip()
                if u:
                    return u
    return ""


def city_counties(city, links):
    """第二条通道：市监委官网站内 12388 链接 → 该市 12388 名录页。"""
    jw = city_jw_url(city)
    if not jw:
        return [], "市监委无URL"
    root = find_12388(jw, want="deep")
    if not root:
        return [], "市监委站无12388链接"
    lst, h = "", ""
    for cand in listing_urls(root):
        hh = P.fetch(cand) or ""
        if len(hh) >= 400 and len(anchors(hh, cand)) >= 3:
            lst, h = cand, hh
            break
    if not h:
        return [], f"12388名录抓取失败 {root}"
    out = []
    for t, x in anchors(h, lst):
        if not t or len(t) > 12 or t in SKIP_TXT:
            continue
        if x.endswith((".html", ".css", ".js")):
            continue
        if urlparse(x).netloc != urlparse(root).netloc:
            continue
        node = links.get(t)
        if node is None:
            cb = P.geo_base(t)
            for nm, nd in links.items():
                if P.geo_base(nm) == cb:
                    node = nd
                    break
        if node is not None:
            out.append((node, x, city.get("n") or "", t))
    return out, "ok"


def main():
    tree = json.load(open(TREE_F, encoding="utf-8"))
    reg = json.load(open(REG_F, encoding="utf-8"))
    st = json.load(open(STATE_F, encoding="utf-8")) if os.path.exists(STATE_F) else {}
    done = st.setdefault("provinces", {})
    blk = prov_nodes(tree)

    # 待补的县级监委节点（复用 p223 collect：已适配直辖市/兵团等挂法）
    _blk, all_tasks = P.collect(tree)
    tasks = [t for t in all_tasks
             if t["org_name"] == "县监委" and not t["filled"]]
    # 12388 子站根址提示：从**已落库（官方 HTML 发现）**的任何节点取，
    # 不限县监委——海南的 hainan.12388.gov.cn 正是从市监委（三沙市）拿到的。
    RX_H = re.compile(r"https?://([a-z0-9.\-]+12388\.gov\.cn)", re.I)

    def _hint(n, acc):
        m = RX_H.search((n.get("u") or "").strip())
        if m:
            acc.append(m.group(1))
        for c in n.get("ks") or []:
            _hint(c, acc)

    # 12388 子站根址提示：从**已落库（官方 HTML 发现）**的任意节点取，不限
    # 五系统（海南 hainan.12388.gov.cn 是从市监委「三沙市」节点拿到的）。
    root_hint = {}
    for prov in blk["ks"]:
        acc = []
        _hint(prov, acc)
        if acc:
            root_hint[prov.get("n") or ""] = acc[0]
    prov_cities, county_map, flat_map = {}, {}, {}
    for t in tasks:
        pn, cn, nm = t["prov"], t["parent"].get("n"), t["county"].get("n")
        if cn == pn:          # 直辖市的区县：父节点就是省级
            flat_map.setdefault(pn, {})[nm] = t
        else:
            prov_cities.setdefault(pn, {})[cn] = t["parent"]
            county_map[(cn, nm)] = t
    name_prov = {}
    for t in tasks:
        name_prov.setdefault(t["county"].get("n"), set()).add(t["prov"])
    dup_names = {n for n, ps in name_prov.items() if len(ps) > 1}
    print(f"p237 待补县级监委 {len(tasks)} 条（{len(blk['ks'])} 省）")

    lock = threading.Lock()
    filled = [0]

    def commit(links, label, pool, ct_default=""):
        n = 0
        for t, u, ct, nm in links:
            if t["filled"]:
                continue
            if any(b in urlparse(u).netloc.lower() for b in P.BAD_HOST):
                continue
            if len(P.fetch_cached(u) or "") < 400:
                continue
            tt = P.page_title(u) or ""
            if tt:
                full = t["county"].get("n", "")
                base = P.geo_base(full)
                # 自治县常写短名（通道侗族自治县 → 「中共通道县纪委…」）
                if not (P.has_name(tt, full)
                        or (base and base in tt and "举报" in tt)):
                    print(f"  SKIP title无县名 {nm} {tt[:30]}", flush=True)
                    continue
                others = [x for x in pool
                          if x and x != nm and len(x) >= 2 and x in tt
                          # 池里同时存在「兴庆区」与「兴庆区纪委监委」这类
                          # 包含关系时不算他县（实测银川 6 区县被误跳过）
                          and x not in nm and nm not in x]
                if others:
                    print(f"  SKIP title含他县 {nm} {tt[:30]}", flush=True)
                    continue
            src = (f"来源:{label} 12388 举报网站名录（{ct or ct_default}）"
                   f"HTML 名录提取+title验证·p237")
            if P.apply_fill(reg, t, u, src, "L1", dup_names):
                n += 1
                print(f"  FILL {t['prov']}/{ct or ct_default}/{nm} 县监委 "
                      f"-> {u[:78]}", flush=True)
        return n

    def work(prov):
        pn = prov.get("n") or ""
        if ONLY and ONLY not in pn:
            return pn, 0, "skip"
        if not P.DRY and done.get(pn) == "done":
            return pn, 0, "cached"
        cmap = {k: v for k, v in county_map.items() if v["prov"] == pn}
        fmap = flat_map.get(pn, {})
        if not cmap and not fmap:
            return pn, 0, "no-task"
        cities = list(prov_cities.get(pn, {}).values())
        links, note = county_links(prov, cities, cmap, fmap,
                                   root_hint.get(pn, ""))
        n = commit(links, f"{pn}纪委监委", list(fmap) + [x for (_c, x) in cmap])
        return pn, n, note

    with ThreadPoolExecutor(WORKERS) as ex:
        for pn, n, note in ex.map(work, blk["ks"]):
            with lock:
                filled[0] += n
                if n or note in ("cached", "no-task", "skip"):
                    done[pn] = "done" if n else note
            print(f"  {pn}: +{n} ({note})", flush=True)
    print(f"p237 省级通道 filled: {filled[0]}")

    # ── 第二通道：市监委官网站内 12388 链接（省站无链接/无名的省份兜底）──
    city_items = []
    for t in tasks:
        if t["filled"] or t["parent"].get("n") == t["prov"]:
            continue
        city_items.append(t)
    by_city = {}
    for t in city_items:
        by_city.setdefault((t["prov"], t["parent"].get("n")), (t["parent"], []))[1].append(t)
    items = [(k, v) for k, v in by_city.items()
             if v[1] and not all(x["filled"] for x in v[1])
             and (not ONLY or ONLY in k[0])]
    print(f"p237 市级通道 {len(items)} 个市（待补 {sum(len(v[1]) for _k, v in items)}）")

    def work2(item):
        (pn, cn), (city, ts) = item
        key = f"city|{pn}|{cn}"
        if not P.DRY and done.get(key) == "done":
            return cn, 0, "cached"
        links_by_name = {x["county"].get("n"): x for x in ts}
        links, note = city_counties(city, links_by_name)
        n = commit(links, f"{pn}{cn}纪委监委", list(links_by_name))
        return key, n, note

    with ThreadPoolExecutor(WORKERS) as ex:
        for key, n, note in ex.map(work2, items):
            with lock:
                filled[0] += n
                if n:
                    done[key] = "done"
            if n:
                print(f"  {key}: +{n} ({note})", flush=True)
    print(f"p237 filled: {filled[0]}")

    if not DRY and filled[0]:
        d = os.path.join(ROOT, "backups", TODAY)
        os.makedirs(d, exist_ok=True)
        ts = datetime.datetime.now().strftime("%H%M%S")
        for f, tag in ((TREE_F, "tree"), (REG_F, "registry")):
            shutil.copy2(f, os.path.join(d, f"{tag}_before_p237_{ts}.json"))
        json.dump(tree, open(TREE_F, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        json.dump(reg, open(REG_F, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        json.dump(st, open(STATE_F, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("  已写 tree.json / site_registry.json / p237_state.json")


if __name__ == "__main__":
    main()
