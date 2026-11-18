#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""p235 上级同系统官网「基层/县区」栏目 → 县级五系统补采（2026-11-17）。

S1 只抓了市级同系统官网**首页 + 3 个栏目页**，且 `/channel/1234.html`、
`/col/colNNN/index.html`、`index.php?...a=lists` 这类**频道页**被判成新闻路径
而丢弃——实测这正是县级人大/政协/监委最集中的官方入口形态：

    绍兴市人大 sxrd.sx.gov.cn/col/col1229604467/index.html  ← 新昌县人大
    宜昌市人大 → 宜都市人大常委会 http://www.yidu.gov.cn/rd/
    南充市人大 → 高坪区人大 http://www.gprd.gov.cn/
    雅安市纪委 → 各县区纪委 xxgk_news_quxian.php?quxian=…

本脚本按用户四档策略的①「上级部门单位官网找」+③「同级同系统单位碰运气」，
对每个市的**市人大/市政协/市监委/中院/市检察院**官网做 2 层栏目遍历：
  首页 → 「县区/基层/下辖/组织机构/友情链接…」栏目页 → 县级机构链接，
命中即按 p223 同一套 title 严格校验落库（L1 上级官网名录口径）。

用法：
  cd data && uv run python p235_upper_org_links.py --dry
  cd data && uv run python p235_upper_org_links.py
  P235_LIMIT=20 P235_WORKERS=6 P235_BROWSER=40
"""
import datetime
import hashlib
import json
import os
import re
import shutil
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
import urllib.parse
from urllib.parse import urlparse

DATA = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(DATA)
sys.path.insert(0, DATA)
sys.path.insert(0, os.path.join(ROOT, "util"))
import p223_county_5sys_fill as P  # noqa: E402

TREE_F = os.path.join(DATA, "tree.json")
REG_F = os.path.join(DATA, "site_registry.json")
STATE_F = os.path.join(DATA, "p235_state.json")
CACHE = "/tmp/p235_cache"
TODAY = datetime.date.today().isoformat()
DRY = "--dry" in sys.argv
FORCE = "--force" in sys.argv
LIMIT = int(os.environ.get("P235_LIMIT", "0")) or None
WORKERS = int(os.environ.get("P235_WORKERS", "6"))
NAV_N = int(os.environ.get("P235_NAV", "0")) or None   # 覆盖 crawl 的 max_nav
BROWSER_MAX = int(os.environ.get("P235_BROWSER", "40"))
P.DRY = DRY  # 统一 DRY 开关（apply_fill 读的是 p223 模块变量）

# 县级五系统 ← 上级同系统节点名（含省级兜底）
UPPER = {
    "县人大": ("市人大", "省人大"),
    "县政协": ("市政协", "省政协"),
    "县监委": ("市监委", "省监委", "市纪委", "省纪委"),
    "县人民法院": ("市中级人民法院", "省高级人民法院"),
    "县人民检察院": ("市人民检察院", "省人民检察院"),
}

# 频道页形态（**不是文章页**）：S1 因 NEWS_PATH 把它们全丢了
CHAN_EXTRA = (r"/(col|column)/col?\d+(/index\.html?)?$"
              r"|/channel/\d+\.html?$"
              r"|/channels?/[a-z0-9_-]+/?$"
              r"|/list[-_]?\d*\.html?$"
              r"|a=lists"
              r"|/category/[a-z0-9_-]+/?$"
              r"|/lm/\d+/?$"
              r"|/(rd|zx|jjjc|jw)/?$")
CHAN = re.compile(CHAN_EXTRA, re.I)
# 县级机构在上级站内的频道锚文本特征（「县区人大/基层人大/各区县…」）
NAV2 = re.compile(r"(县区|区县|市县|县市|基层|下辖|辖区|各地|直属|单位|导航|"
                  r"友情链接|网站群|子站|分站|机构|人大|政协|纪委|监委|法院|检察)")

_bcount = [0]
_block = threading.Lock()


def get(u):
    """抓页面：curl_cffi 优先，WAF/空响应才降级 smart_fetch（限次防浏览器风暴）。"""
    if not u:
        return ""
    os.makedirs(CACHE, exist_ok=True)
    k = hashlib.sha1(u.encode()).hexdigest()
    f = os.path.join(CACHE, k + ".html")
    if not FORCE and os.path.exists(f):
        try:
            h = open(f, encoding="utf-8", errors="ignore").read()
            if h:
                return h
        except OSError:
            pass
    h = P.fetch(u) or ""
    if len(h) < 400:
        with _block:
            allow = _bcount[0] < BROWSER_MAX
            if allow:
                _bcount[0] += 1
        if allow:
            try:
                from smart_fetch import smart_fetch
                h2, method = smart_fetch(u)
                if h2 and len(h2) > len(h or ""):
                    h = h2
                    print(f"    [smart_fetch/{method}] {u[:60]}", flush=True)
            except Exception as e:  # noqa: BLE001
                print(f"    [smart_fetch-err] {type(e).__name__} {u[:50]}", flush=True)
    if h:
        with open(f, "w", encoding="utf-8") as fh:
            fh.write(h)
    return h


def fetch_cached(u, timeout=15):
    """覆盖 p223 的内存缓存：标题/正文与 crawl 共用一份磁盘缓存。"""
    return get(u)


def same_host(a, b):
    return urlparse(a).netloc.lower() == urlparse(b).netloc.lower()


def crawl(u, max_nav=None):
    max_nav = max_nav or NAV_N or 10
    """首页 + 栏目页（2 层）。返回 [(page_url, html)]。"""
    pages = []
    h = get(u)
    if len(h) < 300:
        return pages
    pages.append((u, h))
    navs, seen = [], {u}
    for txt, link in P.extract_links(h, u):
        if link in seen:
            continue
        if not same_host(link, u):
            continue
        is_chan = bool(CHAN.search(link))
        if (P.NEWS_PATH.search(link) or P.NEWS_QUERY.search(link)) and not is_chan:
            continue
        if P.NAV_KW.search(txt) or P.NAV_KW.search(link) or NAV2.search(txt) or is_chan:
            seen.add(link)
            navs.append(link)
    # 先取「文字像县区/基层/机构」的，再取纯频道页
    navs.sort(key=lambda x: 0 if (P.NAV_KW.search(x) or NAV2.search(x)) else 1)
    nav_pages = []
    for nu in navs[:max_nav]:
        nh = get(nu)
        if nh and len(nh) > 300:
            pages.append((nu, nh))
            nav_pages.append((nu, nh))
    # 深爬：栏目页里再找「县区/基层/下辖」二级栏目跟一层（P235_DEEP=1）
    if os.environ.get("P235_DEEP") == "1":
        seen2 = {u for u, _ in pages}
        sub = []
        for nu, nh in nav_pages:
            for txt, link in P.extract_links(nh, nu):
                if link in seen2 or not same_host(link, u):
                    continue
                is_chan = bool(CHAN.search(link))
                if (P.NEWS_PATH.search(link) or P.NEWS_QUERY.search(link)) and not is_chan:
                    continue
                if NAV2.search(txt) or is_chan:
                    seen2.add(link)
                    sub.append(link)
        for nu in sub[:max_nav * 2]:
            nh = get(nu)
            if nh and len(nh) > 300:
                pages.append((nu, nh))
    return pages


_A_RE = re.compile(r"<a\b[^>]*href=[\"']([^\"'#]+)[\"'][^>]*>(.*?)</a>", re.I | re.S)
_OPT_RE = re.compile(r"<option\b[^>]*value=[\"']([^\"']+)[\"'][^>]*>(.*?)</option>", re.I | re.S)
_ONCLICK_RE = re.compile(
    r"<([a-zA-Z0-9]+)([^>]*\bonclick=[\"'][^\"']*"
    r"(?:window\.open|location\.href)[^\"']*[\"'][^>]*)>(.*?)</\1>", re.I | re.S)
_TAG_RE = re.compile(r"<[^>]+>")


def _txt(x):
    return re.sub(r"\s+", "", _TAG_RE.sub("", x or ""))


def links_ctx(html, base_url):
    """带栏目上下文的链接抽取（覆盖 <a>/<option>/onclick 三种形态）。

    实测宜昌市人大把县市区挂在 <option> 里（extract_links 支持），绍兴挂在
    县名下拉 `<a>` 里且前文没有栏目标题——上下文只是加分项，不能当必要条件。
    """
    out = []
    for m in _A_RE.finditer(html):
        href = (m.group(1) or "").strip()
        if not href or href.startswith(("javascript:", "mailto:", "tel:")):
            continue
        head = html[max(0, m.start() - 400):m.start()]
        ctx = _txt(head)[-90:]
        out.append((_txt(m.group(2)), P.clean_url(href, base_url) or href, ctx))
    for rx in (_OPT_RE, _ONCLICK_RE):
        for m in rx.finditer(html):
            raw = m.group(1) if rx is _OPT_RE else m.group(2)
            if rx is _ONCLICK_RE:
                um = re.search(r"(?:window\.open|location\.href)\s*[=(]\s*[\'\"]?([^\'\")\s]+)", raw)
                if not um:
                    continue
                raw = um.group(1)
            raw = (raw or "").strip()
            if not raw or raw.startswith(("javascript:", "mailto:", "tel:")):
                continue
            out.append((_txt(m.group(2) if rx is _OPT_RE else m.group(3)),
                        P.clean_url(raw, base_url) or raw, ""))
    return out


# 文章页形态（日期段 / 长数字 id / content-<id>-<id>）
ARTICLE2 = re.compile(
    r"(/content-\d+-\d+|/\d{4}[-/]?\d{2}[-/]?\d{2}/|/t\d{8}_|/art\d+"
    r"|/info/\d+|/\d{6,}\.s?html?|/show-\d+|/detail[-_]?\d+)", re.I)


def valid_channel(task, link, txt, ctx, upper_host):
    """上级站内**频道页**校验：纯地名锚 + 同站频道形态 + 页题只含该县名。

    判据：上级站本身就是该机构的官网（市人大节点的 u 即本 URL 所属站点），
    其站内 `/col/colNNN/`、`/channel/12.html` 这类频道页标题只写县名，
    就是该县人大/政协/纪委的官方频道页——不再依赖首页栏目标题（实测绍兴
    首页县名下拉里没有「县区人大」字样，靠上下文会全丢）。
    外站一律走 title 全验（独立站点必须自报机构名）。
    """
    if urlparse(link).netloc.lower() != upper_host:
        return False, "外站"
    if link.rstrip("/") == (task.get("_upper_u") or "").rstrip("/"):
        return False, "与上级站同址"
    # 频道页：上级官网 HTML 提取（来源权威），允许非 gov 的官方站，
    # 但媒体/聚合域一律拒（实测 hynews.zjol.com.cn 黄岩政协专栏）
    if not P.host_ok(link, strict=False):
        return False, "媒体/聚合域名"
    if not CHAN.search(link):
        return False, "非频道页形态"
    if P.LEADER_PATH.search(link):
        return False, "领导之窗页"
    art = ARTICLE2.search(link)
    if art:
        return False, f"文章页形态({art.group(1)[:14]})"
    tt = P.page_title(link) or ""
    if not tt:
        return False, "频道页 title 空"
    nm = task["county"].get("n", "")
    b = P.geo_base(nm)
    # 县名基底 == 本市基底（南昌县↔南昌市）：只出现市名不能算
    if b == P.geo_base(task["parent"].get("n", "")) and not P.has_name(tt, nm):
        return False, f"仅市名无县全名({b})"
    kb = P.KIND_BAD.search(tt)
    if kb:
        return False, f"领导/建议类栏目({kb.group(1)})"
    # 频道页必须出现**县全名**——只出现基底会把「衡阳_湖南人大网」（衡阳市
    # 频道）当成衡阳县人大
    if not P.has_name(tt, nm):
        return False, "频道页 title 无县全名"
    if len(tt) > len(nm) + 8:
        return False, f"频道页标题过长({tt[:16]})"
    if P.TITLE_BAD.search(tt.replace("政治协商会议", "")):
        return False, "业务栏目页"
    for other, kws in (("政府", ("政府",)), ("政协", ("政协",)),
                        ("法院", ("法院",)), ("检察", ("检察院", "检察")),
                        ("纪委", ("纪委", "监委"))):
        if task["org_name"] in ("县人大",) and other in ("政协", "法院", "检察", "纪委") and any(k in tt for k in kws):
            return False, f"他机构频道({other})"
        if task["org_name"] in ("县政协",) and other in ("政府", "法院", "检察", "纪委") and any(k in tt for k in kws):
            return False, f"他机构频道({other})"
        if task["org_name"] == "县监委" and other in ("政府", "政协", "法院", "检察") and any(k in tt for k in kws):
            return False, f"他机构频道({other})"
        if task["org_name"] == "县人民法院" and other in ("政府", "政协", "检察", "纪委") and any(k in tt for k in kws):
            return False, f"他机构频道({other})"
        if task["org_name"] == "县人民检察院" and other in ("政府", "政协", "法院", "纪委") and any(k in tt for k in kws):
            return False, f"他机构频道({other})"
    if P.BAD_COLUMN.search(link):
        return False, "财政/任免栏"
    return True, f"同站频道页 title={tt[:16]}"


def fill_from_pages(pages, tasks, reg, dup_names, upper_name):
    n = 0
    upper_host = urlparse(pages[0][0]).netloc.lower() if pages else ""
    for page_u, page_h in pages:
        if not any(not t["filled"] for t in tasks):
            break
        links = links_ctx(page_h, page_u)
        for t in tasks:
            if t["filled"]:
                continue
            nm = t["county"].get("n", "")
            b = P.geo_base(nm)
            for txt, link, ctx in links:
                pure = txt in (nm, b) or (b and txt == b)
                if pure:
                    ok, note = valid_channel(t, link, txt, ctx, upper_host)
                elif P.match_link(txt, link, t, allow_pure=True):
                    art = ARTICLE2.search(link)
                    if art:
                        continue
                    ok, note = P.valid_candidate(t, link, txt, strict=False)
                else:
                    continue
                if not ok:
                    continue
                # 站点不可达（抓取失败）不入库——空 title 的 JS 壳站仍有 HTML，
                # 而抓取失败是空串（实测 rd.10.gov.cn / rd.kq.gov.cn 已挂）
                if len(P.fetch_cached(link) or "") < 400:
                    continue
                src = (f"来源:{upper_name}官网({page_u}) 县区栏目 "
                       f"HTML 提取+title验证({note})·p235")
                if P.apply_fill(reg, t, link, src, "L1", dup_names):
                    n += 1
                    print(f"  FILL {t['prov']}/{t['parent'].get('n')}/{t['county'].get('n')} "
                          f"{t['org_name']} -> {link[:72]}", flush=True)
                break
    return n


def upper_url(task, prov_map):
    """上级同系统官网（市优先、省兜底）。"""
    nodes = [task["parent"]]
    pv = prov_map.get(task["prov"])
    if pv is not None and pv is not task["parent"]:
        nodes.append(pv)
    for node in nodes:
        for g in node.get("ks") or []:
            if g.get("c") != "并列机关":
                continue
            for cand in UPPER[task["org_name"]]:
                o = next((x for x in g.get("ks") or [] if x.get("n") == cand), None)
                if o and (o.get("u") or "").strip():
                    return o["u"].strip(), cand
    return "", ""


def main():
    tree = json.load(open(TREE_F, encoding="utf-8"))
    reg = json.load(open(REG_F, encoding="utf-8"))
    st = json.load(open(STATE_F, encoding="utf-8")) if os.path.exists(STATE_F) else {}
    done = st.setdefault("done", {})
    # 让 valid_candidate 接受频道页形态
    P.CHANNEL_OK = re.compile(P.CHANNEL_OK.pattern + "|" + CHAN_EXTRA, re.I)
    P.fetch_cached = fetch_cached

    blk, tasks = P.collect(tree)
    prov_map = {p["n"]: p for p in blk["ks"]}
    P.ALL_PROV_BASES.update(P.prov_base(x) for x in prov_map if P.prov_base(x))
    name_prov = {}
    for t in tasks:
        name_prov.setdefault(t["county"].get("n", ""), set()).add(t["prov"])
    dup_names = {n for n, ps in name_prov.items() if len(ps) > 1}
    city_bases = {}
    for t in tasks:
        p = t["parent"]
        if p.get("l") in ("市", "地级区"):
            city_bases.setdefault(t["prov"], set()).add(P.geo_base(p.get("n", "")))
    for t in tasks:
        p = t["parent"]
        cb = P.geo_base(p.get("n", ""))
        t["dup"] = t["county"].get("n") in dup_names
        t["siblings"] = sorted(x for x in city_bases.get(t["prov"], set())
                               if x and x != cb)

    # 分组：(上级站 URL, 机构类型) → 该市待补任务
    only = [x for x in (os.environ.get("P235_ORG") or "").split(",") if x]
    groups = {}
    for t in tasks:
        if t["filled"]:
            continue
        if only and t["org_name"] not in only:
            continue
        u, cand = upper_url(t, prov_map)
        if not u:
            continue
        t["_upper_u"] = u
        groups.setdefault((u, t["org_name"], cand), []).append(t)
    items = [(k, v) for k, v in groups.items()
             if FORCE or done.get(k[0] + "|" + k[1]) != "done"]
    if LIMIT:
        items = items[:LIMIT]
    print(f"p235 上级同系统站组 {len(groups)}，本轮爬 {len(items)}（{WORKERS} 并发，"
          f"待补任务 {sum(len(v) for _, v in items)}）")

    filled = [0]
    lock = threading.Lock()

    def work(item):
        (u, org_name, cand), ts = item
        try:
            pages = crawl(u)
            n = fill_from_pages(pages, ts, reg, dup_names, cand)
        except Exception as e:  # noqa: BLE001
            print(f"  ERR {u[:50]}: {type(e).__name__}", flush=True)
            return u, org_name, 0, "error"
        return u, org_name, n, ("done" if pages else "fail")

    with ThreadPoolExecutor(WORKERS) as ex:
        for u, org_name, n, status in ex.map(work, items):
            with lock:
                filled[0] += n
                done[u + "|" + org_name] = status
    print(f"p235 市级轮 filled: {filled[0]}")

    # ── 第二跳：省级同系统站（省人大/省政协/省纪委…）→ 市县频道 → 县级 ----
    # 市站没挂县区栏目时，省级站的「市县人大」频道常常挂着各市子站，
    # 子站底下才是县级频道（实测湖南人大网 /channel/<id>.html 一市一页）。
    prov_groups = {}
    for t in tasks:
        if t["filled"]:
            continue
        if only and t["org_name"] not in only:
            continue
        pv = prov_map.get(t["prov"])
        if pv is None:
            continue
        for g in pv.get("ks") or []:
            if g.get("c") != "并列机关":
                continue
            for cand in UPPER[t["org_name"]][1:]:
                o = next((x for x in g.get("ks") or [] if x.get("n") == cand), None)
                if o and (o.get("u") or "").strip():
                    t["_upper_u"] = o["u"].strip()
                    prov_groups.setdefault((o["u"].strip(), t["org_name"], cand), []).append(t)
                    break
            else:
                continue
            break
    pitems = [(k, v) for k, v in prov_groups.items()
              if FORCE or done.get(k[0] + "|" + k[1]) != "done"]
    if LIMIT:
        pitems = pitems[:LIMIT]
    print(f"p235 省级站组 {len(prov_groups)}，本轮爬 {len(pitems)}"
          f"（待补任务 {sum(len(v) for _, v in pitems)}）")

    def work2(item):
        (u, org_name, cand), ts = item
        try:
            pages = crawl(u, max_nav=25)
            n = fill_from_pages(pages, ts, reg, dup_names, cand)
        except Exception as e:  # noqa: BLE001
            print(f"  ERR {u[:50]}: {type(e).__name__}", flush=True)
            return u, org_name, 0, "error"
        return u, org_name, n, ("done" if pages else "fail")

    with ThreadPoolExecutor(WORKERS) as ex:
        for u, org_name, n, status in ex.map(work2, pitems):
            with lock:
                filled[0] += n
                done[u + "|" + org_name] = status
    print(f"p235 filled: {filled[0]}")
    if not DRY and filled[0]:
        d = os.path.join(ROOT, "backups", TODAY)
        os.makedirs(d, exist_ok=True)
        ts = datetime.datetime.now().strftime("%H%M%S")
        for f, tag in ((TREE_F, "tree"), (REG_F, "registry")):
            shutil.copy2(f, os.path.join(d, f"{tag}_before_p235_{ts}.json"))
        json.dump(tree, open(TREE_F, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        json.dump(reg, open(REG_F, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        json.dump(st, open(STATE_F, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("  已写 tree.json / site_registry.json / p235_state.json")
    elif not DRY:
        json.dump(st, open(STATE_F, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
