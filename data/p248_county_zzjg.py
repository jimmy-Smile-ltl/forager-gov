#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""p248 县级人民政府「组织机构 / 部门信息」栏目采集（2026-11-18 用户指令扩展）。

背景：p246 只覆盖省/市两级门户。用户指出**县级形态完全不同**——多数县没有独立的
部门导航页，机构/部门信息通常藏在：
  ① 政务公开模块 →「部门信息公开 / 部门乡镇信息公开 / 机构设置」
     （云南禄丰 https://www.ynlf.gov.cn/zfxxgk/fdzdgknr/bmxzxxgk.htm，57 个部门）；
  ② 首页「政府机构」点击后才展开的政务公开目录
     （景洪 https://www.jh.gov.cn/jh/xhtml/zwgkml.html，31 个部门）；
  ③ **省级统一平台**：四川省各县直接走
     https://www.sczwfw.gov.cn/jiq/front/channel/deptSwitch?areaCode={6位区划代码}000000
     （「直通部门-四川政务服务网」，按区划代码出全县部门列表，实测高县 28 / 翠屏区 29）。

渠道顺序（全部官方页面，**不拼域名、不猜路径、不走 SERP**）：
  static  —— 门户首页静态 HTML 锚文本分类 + 回抓验证（复用 p246）
  deep    —— 政务公开/信息公开索引下钻（复用 p246）
  sc      —— 四川省统一平台（仅 p1=四川省，areaCode=树内 cd；页面自证「直通部门」+
             部门链接 areaCode 必须等于本县区划代码）
  xxgk    —— registry 里已登记的县级信息公开专栏（zc 错配的链接会被验证器挡掉）
  click   —— 渲染后点击「政府机构/机构设置」兜底（复用 p246，最慢，最后跑）

产物：data/zzjg_county.json
  key = `县|{省}|{市}|{名称}`（同名县跨省不冲突）
  value = u/title/src/method/score/verified_at/cd + links[]
状态：data/p248_state.json（断点，不入库）

用法（在 data/ 目录；单写者，不得与 p246/p247 同时运行）：
  PROXY_MODE=dps RS_DISABLE=1 P246_RENDER_PROXY=1 BROWSER_TIERS=off \
    uv run python p248_county_zzjg.py --phase static --workers 4
  ... --phase deep --workers 3 --limit 200
  ... --phase sc --workers 4
  ... --phase xxgk --workers 3
  ... --phase click --workers 2 --only "高县 禄丰市"
"""
import argparse
import datetime
import json
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin, urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import p246_zzjg_pages as P  # 复用 分类/评分/验证/合并 的单一判定标准

TODAY = datetime.date.today().isoformat()
OUT_F = os.path.join(HERE, "zzjg_county.json")
STATE_F = os.path.join(HERE, "p248_state.json")
REG_F = os.path.join(HERE, "site_registry.json")

SC_PLATFORM = ("https://www.sczwfw.gov.cn/jiq/front/channel/deptSwitch"
               "?areaCode={code}000000")
SC_ANCHOR = re.compile(
    r'<a[^>]+href="([^"]*bmft_index[^"]*)"[^>]*>\s*([^<]{2,20})\s*</a>', re.I)
DEPT_NAME = re.compile(r"[一-龥]{2,14}(?:局|委员会|办公室|中心|院|所|站|馆)")

# 四川省统一平台对 2016–2021 年区划调整的 6 个县区仍按**调整前代码**建页：
# 用现码取到的是空模板（0 个部门链接）。下列旧码已逐个实测：页面正文含**现名**
# （郫都/新津/罗江/隆昌/叙州/会理）且部门 ≥30 条——是平台自身的信息，不是拼接猜测。
SC_LEGACY = {
    "510117": ("510124", "郫都区"),   # 原郫县
    "510118": ("510132", "新津区"),   # 原新津县
    "510604": ("510626", "罗江区"),   # 原罗江县
    "511083": ("511028", "隆昌市"),   # 原隆昌县
    "511504": ("511521", "叙州区"),   # 原宜宾县
    "513402": ("513425", "会理市"),   # 原会理县
}

# ── 归属校验（2026-11-18 用户指令：绝不能采成上级单位的部门机构） ──────────
_ADMIN_SUFFIX = re.compile(
    r"(特别行政区|自治区|自治州|自治县|自治旗|新区|矿区|林区|县|市|区|旗|盟|州|省)$")
_ETHNIC = re.compile(r"[一-龥]{1,3}族")


def base_name(n):
    """行政区名 → 基底名：去括号、去行政后缀、循环剥民族修饰。
    「恩施土家族苗族自治州」→「恩施」；「高县」→「高」（单字，调用方须用全名）。"""
    s = re.sub(r"[（(][^）)]*[）)]", "", n or "").strip()
    s = _ADMIN_SUFFIX.sub("", s)
    while True:
        t = _ETHNIC.sub("", s)
        if t == s:
            break
        s = t
    return s or (n or "").strip()


def name_aliases(n, prov=""):
    """本县在页面里的可接受叫法：全名 + 基底名 + 去省名前缀（功能区名常见）。

    例：「河北沧州经济开发区」（河北省）→ 也接受「沧州经济开发区」——
    功能区页面的标题通常只写「区直部门_沧州经济开发区」。
    """
    full = re.sub(r"[（(][^）)]*[）)]", "", n or "").strip()
    b = base_name(n)
    out = {full}
    if len(b) >= 2:
        out.add(b)
    pb = base_name(prov)
    if pb and len(pb) >= 2 and full.startswith(pb) and len(full) - len(pb) >= 3:
        out.add(full[len(pb):])
    return {x for x in out if x}


def _page_text(html):
    t = re.sub(r"(?is)<(script|style).*?</\1>", " ", html or "")
    t = re.sub(r"<[^>]+>", " ", t)
    return re.sub(r"\s+", "", t)


# 单一部门页（「某县某局机构职能」）不是本县的部门清单——用户要的是全量部门/机构，
# 实采里出现过 12 条（如「涿鹿县退役军人事务局机构职能」），在复验时剔除。
_SINGLE_DEPT = re.compile(r"(局|委员会|办公室|中心|医院|学校|学院|支队|大队|所)"
                          r"(主要职责|机构职能|机构设置|机构职责|职责|简介)")
_DEPT_TAIL = re.compile(r"(局|委员会|办公室|中心|支队|大队|院|所)$")


def _dept_like(html):
    """页面里像「部门名」的锚文本数（判断是不是部门清单页）。"""
    n = 0
    for mm in re.finditer(r"(?is)<a\b[^>]*>(.*?)</a>", html or ""):
        tx = P.norm_text(mm.group(1))
        if 3 <= len(tx) <= 14 and _DEPT_TAIL.search(tx):
            n += 1
    return n


def sc_codes(t):
    """本县在四川统一平台上可接受的 areaCode 集合：现码 + 已实测的调整前旧码。"""
    cd = (t.get("cd") or "").strip()
    if not cd:
        return set()
    out = {cd}
    if cd in SC_LEGACY:
        out.add(SC_LEGACY[cd][0])
    return out


def county_guard(t, rec, html):
    """归属校验：这条记录是不是**本县自己**的机构/部门页。

    三条硬规则（任一不过即拒）：
      ① URL 归属：链接与县级门户同一主域；四川统一平台例外——host 必须是
         sczwfw.gov.cn 且 URL 里的 areaCode 必须属于本县（现码或已实测的旧码）。
      ② 本县自证：<title>/h1-h3 出现本县名，或正文 ≥2 次出现本县名。
      ③ 上级排除：标题出现上级市/省基底名 + 政府/机构/部门，而本县名缺席
         → 判为上级单位页面（这正是「采成上级」的典型形态）。
    """
    if not html:
        return False, "no-html"
    u = rec.get("u") or ""
    host = (urlparse(u).hostname or "").lower()
    if host.endswith("sczwfw.gov.cn"):
        # 四川统一平台是**区划代码驱动**：页面本身只列部门名、不含县名，
        # 归属证据 = URL 的 areaCode 属于本县 + 页面确有该码的部门链接。
        codes = sc_codes(t)
        hit = [c for c in codes if f"areaCode={c}" in u]
        if not hit:
            return False, "sc-code-mismatch"
        cd = hit[0]
        if cd[-2:] == "00":
            return False, "sc-city-code"      # 市级码（末两位 00）= 采到了上级
        n = sum(1 for href, _ in SC_ANCHOR.findall(re.sub(r"\s+", "", html))
                if f"areaCode={cd}" in href)
        if n < 10:
            return False, f"sc-dept{n}"
        return True, f"sc-areaCode({cd},{n}部门)"
    if not P.same_site(u, t["url"]):
        return False, f"off-site({host})"
    own_host = (urlparse(t["url"]).hostname or "").lower()
    self_host = bool(own_host) and host == own_host

    m = re.search(r"(?is)<title[^>]*>(.*?)</title>", html)
    ttl = P.norm_text(m.group(1)) if m else ""
    heads = [P.norm_text(x) for x in
             re.findall(r"(?is)<h[1-3][^>]*>(.*?)</h[1-3]>", html)][:4]
    zone = ttl + "|" + "|".join(heads)
    body = _page_text(html)[:30000]
    alias = name_aliases(t["name"], t.get("prov") or "")
    full = re.sub(r"[（(][^）)]*[）)]", "", t["name"]).strip()

    def has_name(s):
        return any(a in s for a in alias if len(a) >= 2) or full in s

    city_b = base_name(t.get("city") or "")
    prov_b = base_name(t.get("prov") or "")
    parent = city_b if len(city_b) >= 2 and city_b in ttl else (
        prov_b if len(prov_b) >= 2 and prov_b in ttl else "")
    # 本县门户主机上的页面＝本县自己的页面：县级站点的部门页常常只写「机构简介」
    # 「政府机构」「县政府工作部门」，正文里一次县名都不出现（永嘉/洞头/泰顺/诸暨
    # 实锤）。主机自证优先于「正文必须出现县名」，否则会把好数据当漏采剔掉。
    if parent and not has_name(ttl) and not self_host:
        return False, f"parent-unit({parent})"
    if _SINGLE_DEPT.search(ttl) and _dept_like(html) < 6:
        return False, "single-dept"
    if self_host:
        return True, f"host-self({host})"
    if has_name(zone):
        return True, f"title-name({ttl[:20]})"
    cnt = sum(body.count(a) for a in alias if len(a) >= 2) or body.count(full)
    if cnt >= 2:
        return True, f"body-name x{cnt}"
    return False, "no-county-name"


_PARENT_TAIL = re.compile(r"(政府|委员会|局|办公室|中心|厅|院|部|公署)$")
# 非清单页：公告/招聘/预决算/单条公文——用户要的是「部门/机构栏目」，这些不是
_NON_LIST = re.compile(r"招聘|招录|录用|选调|遴选|公示|公告|通知|决算|预算|征求|批复|"
                       r"解读|访谈|视频|图片|活动|名单|实施细则|管理办法|责任追究|法人证书")
# 全省统办的业务入口（公积金/社保等）：省局就是本县的合法入口，不算「上级单位」
_SERVICE_KIND = re.compile(r"公积金|社保|社会保险|医保")


def _is_parent_unit(t, title, link_u="", own_u=""):
    """title 写的是上级市/省的机构名（本县名缺席）→ True。

    实采反例：「海南省住房公积金管理局」挂到白沙黎族自治县、「政府工作机构_昌都市
    人民政府」挂到芒康县——URL 都落在上级域（*.hainan.gov.cn / *.changdu.gov.cn），
    same_site 按父域比较放过了。title 规则不用抓页就能拦住。

    反例的反例（不能误杀）：汝南 `runan.gov.cn`、门源 `menyuan.gov.cn`、栖霞
    `njqxq.gov.cn` 都是本县自己的站，只是页面模板把市名印进了 title。用「链接主机
    == 本县门户主机」放行；上级站是 `xx.changdu.gov.cn` 这类不同主机，不会被放过。
    """
    ttl = re.sub(r"\s+", "", title or "")
    if not ttl:
        return False
    full = re.sub(r"[（(][^）)]*[）)]", "", t["name"]).strip()
    if full and full in ttl:
        return False
    if any(a in ttl for a in name_aliases(t["name"], t.get("prov") or "")
           if len(a) >= 2):
        return False
    lh = (urlparse(link_u).hostname or "").lower()
    oh = (urlparse(own_u).hostname or "").lower()
    if lh and oh and lh == oh:
        return False
    nb = base_name(t["name"])
    for pn in (t.get("city"), t.get("prov")):
        b = base_name(pn or "")
        if len(b) < 2 or b in nb:
            continue      # 功能区名自带市名（「张家口经济开发区」含「张家口」），不算上级
        if b in ttl and _PARENT_TAIL.search(ttl):
            return True
    return False


def _link_bad(t, l):
    """单条链接不合格：上级单位机构栏 / 非清单页（公告、预决算等）。"""
    ti = l.get("title") or ""
    if _NON_LIST.search(ti):
        return True
    if _SERVICE_KIND.search(l.get("kind") or ""):
        return False
    return _is_parent_unit(t, ti, l.get("u") or "", t.get("url") or "")


def quick_guard(t, rec):
    """不抓页的快速归属校验（写库前必过）：URL 归属 + 上级单位标题。

    上级单位的链接只丢该条；全丢则整条拒绝（防「整条采成上级」）。
    """
    links = []
    for l in rec.get("links") or []:
        u = (l.get("u") or "").strip()
        if not u:
            continue
        host = (urlparse(u).hostname or "").lower()
        if host.endswith("sczwfw.gov.cn"):
            if not any(f"areaCode={c}" in u for c in sc_codes(t)):
                return False, "sc-code-mismatch"
        elif not P.same_site(u, t["url"]):
            return False, f"off-site({host})"
        if _link_bad(t, l):
            continue
        links.append(l)
    if (rec.get("links") or []) and not links:
        return False, "parent-unit-only"
    if links != (rec.get("links") or []):
        rec["links"] = links
        if rec.get("u") and all(l.get("u") != rec["u"] for l in links):
            rec["u"] = links[0]["u"]
            rec["title"] = links[0].get("title") or rec.get("title", "")
    return True, ""

_lock = threading.Lock()


def log(*a):
    print(*a, flush=True)


# ── 目标 ────────────────────────────────────────────────────────────────
def load_county_targets():
    """树内 k=人民政府、l=县 且有门户 URL 的县级节点。"""
    tree = json.load(open(os.path.join(HERE, "tree.json"), encoding="utf-8"))
    out, seen = [], set()

    def walk(n, path):
        for ch in n.get("ks") or []:
            p = path + [ch.get("n")]
            if (ch.get("k") == "人民政府" and ch.get("l") == "县"
                    and (ch.get("u") or "").strip()):
                prov = ch.get("p1") or (p[-3] if len(p) >= 3 else "")
                city = ch.get("p2") or (p[-2] if len(p) >= 2 else "")
                key = f"县|{prov}|{city}|{ch.get('n')}"
                if key in seen:
                    continue
                seen.add(key)
                out.append(dict(key=key, level="县", name=ch.get("n"),
                                prov=prov, city=city, cd=ch.get("cd") or "",
                                url=ch["u"].strip()))
            walk(ch, p)

    walk(tree, [])
    return out


def load_state():
    if os.path.exists(STATE_F):
        try:
            return json.load(open(STATE_F, encoding="utf-8"))
        except Exception:
            pass
    return {"done": {}, "fail": {}}


def save_state(st):
    json.dump(st, open(STATE_F, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)


def merge_out(key, rec):
    data = {}
    if os.path.exists(OUT_F):
        data = json.load(open(OUT_F, encoding="utf-8"))
    data[key] = rec
    json.dump(data, open(OUT_F, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)


# ── 阶段：四川统一平台 ───────────────────────────────────────────────────
def try_portal_sc(t):
    """四川省县级：省政务服务网「直通部门」页（areaCode = 树内 6 位区划代码）。

    页面自证三条：① 标题/正文含「直通部门」；② 部门链接 ≥10 条；
    ③ 每条部门链接的 areaCode 参数 == 本县区划代码（防止拿到别人的部门）。
    """
    if t.get("prov") != "四川省" or not t.get("cd"):
        return None, "not-sichuan"
    code = t["cd"]

    def scan(cd):
        url = SC_PLATFORM.format(code=cd)
        h, m = P.fetch(url, timeout=20)
        if not h or len(h) < 2000:
            return url, h, m, [], 0
        if "直通部门" not in h:
            return url, h, m, [], -1
        depts, wrong = [], 0
        for href, name in SC_ANCHOR.findall(h):
            if f"areaCode={cd}" not in href:
                wrong += 1
                continue
            nm = P.norm_text(name)
            if nm and nm not in depts:
                depts.append(nm)
        return url, h, m, depts, wrong

    url, h, m, depts, wrong = scan(code)
    used = code
    if len(depts) < 10 and code in SC_LEGACY:      # 区划调整：平台仍按旧码建页
        old, want = SC_LEGACY[code]
        url2, h2, m2, d2, w2 = scan(old)
        # 旧码页面必须自证现名（防止把别的县的部门挂过来）
        if len(d2) >= 10 and want in _page_text(h2)[:30000]:
            url, h, m, depts, wrong = url2, h2, m2, d2, w2
            used = old
    if not h or len(h) < 2000:
        return None, f"sc-{m}-short"
    if "直通部门" not in h:
        return None, f"sc-not-dept-page ({m})"
    if len(depts) < 10:
        return None, f"sc-dept{len(depts)} (错码{wrong})"
    code_note = (f"areaCode={used}000000"
                 + (f"（区划调整后平台仍用旧码；正文自证「{t['name']}」）"
                    if used != code else ""))
    rec = dict(
        u=url, title=f"{t['name']}·直通部门（四川政务服务网）",
        src=(f"四川省统一平台（官方）：直通部门-四川政务服务网，"
             f"{code_note}，部门 {len(depts)} 个"),
        method=f"sc/{m}", score=8, verified_at=TODAY, cd=code,
        links=[dict(kind="机构设置", u=url,
                    title=f"{t['name']}·直通部门（四川政务服务网）",
                    src=(f"四川省统一平台：{code_note}，"
                         f"部门 {len(depts)} 个（{m}）"),
                    method=m, score=8)])
    return rec, ""


# ── 阶段：registry 信息公开专栏入口 ─────────────────────────────────────
def _registry_xxgk():
    reg = {}
    if os.path.exists(REG_F):
        try:
            reg = json.load(open(REG_F, encoding="utf-8"))
        except Exception:
            reg = {}
    out = {}
    for k, v in reg.items():
        if not k.startswith("县级人民政府|"):
            continue
        name = k.split("|", 1)[1]
        u = (v.get("xxgk") or "").strip()
        if u:
            out.setdefault(name, []).append(u)
    return out


def try_portal_xxgk(t):
    """registry 里已登记的信息公开专栏 → 部门/机构栏目（入口可能错配，验证器把关）。"""
    deadline = time.time() + P.BUDGET
    cands = _REGISTRY_XXGK.get(t["name"]) or []
    if not cands:
        return None, "no-xxgk"
    for entry in cands[:2]:
        if time.time() > deadline:
            break
        h, m = P.fetch_or_render(entry, timeout=20)
        if not h or len(h) < 2000:
            continue
        own = P.self_candidate(entry, h, m)
        if own and own["kind"] in P.CORE_KINDS and P.same_site(own["u"], t["url"]):
            own["src"] = f"信息公开专栏「{entry}」即目标 → " + own["src"]
            return P.make_rec([own], method=f"xxgk/{m}"), ""
        sub = []
        for mm in re.finditer(P.ANCHOR_RE, h):
            hr = re.search(r"href\s*=\s*[\"']([^\"']+)[\"']", mm.group(1), re.I)
            if not hr:
                continue
            text = P.norm_text(mm.group(2))
            if not text or len(text) > 20 or not P.SUB_KW.search(text):
                continue
            u = urljoin(entry, hr.group(1).strip())
            if u.startswith("http") and P.same_site(u, t["url"]) and u not in sub:
                sub.append(u)
        for su in sub[:3]:
            if time.time() > deadline:
                break
            h2, m2 = P.fetch_or_render(su, timeout=15)
            own2 = P.self_candidate(su, h2, m2)
            if own2 and own2["kind"] in P.CORE_KINDS:
                own2["src"] = f"信息公开专栏「{entry}」→「{su}」→ " + own2["src"]
                return P.make_rec([own2], method=f"xxgk/{m}+{m2}"), ""
            l2 = P.collect_links(su, h2, t["url"], deadline)
            if l2:
                for x in l2:
                    x["src"] = f"信息公开专栏「{entry}」→「{su}」→ " + x["src"]
                return P.make_rec(l2, method=f"xxgk/{m}+{m2}"), ""
    return None, f"xxgk-no-verified (入口{len(cands)})"


PHASES = {
    "static": P.try_portal_static,
    "deep": P.try_portal_deep,
    "sc": try_portal_sc,
    "xxgk": try_portal_xxgk,
    "click": P.try_portal_click,
}
_REGISTRY_XXGK = {}


def main():
    global _REGISTRY_XXGK
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", default="static", choices=list(PHASES) + ["all"])
    ap.add_argument("--only", default="", help="按县名过滤（空格分隔，子串匹配）")
    ap.add_argument("--prov", default="", help="按省名过滤（子串匹配）")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--budget", type=float, default=None)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--retry-fail", action="store_true")
    ap.add_argument("--retry-fail-re", default="",
                    help="与 --retry-fail 连用：只重试上次失败原因匹配该正则的目标"
                         "（如 'blocked|short|timeout|exc'，配合 PROXY_MODE=dps 省代理）")
    ap.add_argument("--audit", action="store_true", help="复核已采结果（回抓验证归属）")
    ap.add_argument("--audit-render", action="store_true", help="复核时允许渲染兜底")
    ap.add_argument("--sync-registry", action="store_true", help="把 zzjg 写入 site_registry.json")
    ap.add_argument("--drop", default="",
                    help="剔除错采记录（县级 key 全文，空格分隔）并清断点，供下轮重采")
    ap.add_argument("--tidy", action="store_true",
                    help="离线清理：按 title 剔除上级单位/非清单页链接")
    args = ap.parse_args()
    if args.budget:
        P.BUDGET = args.budget
    if args.tidy:
        tidy_counties()
        return
    if args.drop:
        drop_counties(args.drop.split("\n") if "\n" in args.drop else args.drop.split())
        return

    targets = load_county_targets()
    only = args.only.split()
    if only:
        targets = [t for t in targets if any(o in t["name"] for o in only)]
    if args.prov:
        targets = [t for t in targets if args.prov in t["prov"]]
    _REGISTRY_XXGK = _registry_xxgk()

    st = load_state()
    out = json.load(open(OUT_F, encoding="utf-8")) if os.path.exists(OUT_F) else {}
    log(f"== 目标县级 {len(targets)}，已收 {len(out)}")

    if args.audit:
        audit_counties(targets, workers=args.workers, render=args.audit_render)
        return
    if args.sync_registry:
        sync_registry()
        return

    phases = list(PHASES) if args.phase == "all" else [args.phase]
    for phase in phases:
        fn = PHASES[phase]
        todo = []
        rx = re.compile(args.retry_fail_re, re.I) if args.retry_fail_re else None
        for t in targets:
            rec = out.get(t["key"])
            if rec and any(l.get("kind") in P.CORE_KINDS
                           for l in rec.get("links") or []):
                continue
            if not args.retry_fail and st["done"].get(t["key"]):
                continue
            if rx:      # 只重试「上次失败原因」匹配的（如只重试被封/超时的，省代理）
                msg = st["fail"].get(f"{phase}:{t['key']}") or ""
                if not msg or not rx.search(msg):
                    continue
            todo.append(t)
        if args.limit:
            todo = todo[:args.limit]
        log(f"== 阶段 {phase}: 待处理 {len(todo)} / 总 {len(targets)}")
        done_n = hit_n = 0
        t0 = time.time()
        with ThreadPoolExecutor(max_workers=max(1, args.workers)) as ex:
            futs = {ex.submit(fn, t): t for t in todo}
            for fut in as_completed(futs):
                t = futs[fut]
                try:
                    rec, err = fut.result()
                except Exception as e:
                    rec, err = None, f"exc:{str(e)[:60]}"
                done_n += 1
                with _lock:
                    if rec:
                        ok, why = quick_guard(t, rec)
                        if not ok:          # URL 归属不过 → 直接丢弃，绝不入库
                            st["fail"][f"{phase}:{t['key']}"] = f"guard:{why}"
                            log(f"[{phase}][XX] {t['key']} 归属校验拒绝 {why} "
                                f"{rec.get('u')}")
                            continue
                        hit_n += 1
                        base = dict(out.get(t["key"]) or {})
                        base.update(rec)
                        base["cd"] = t.get("cd", "")
                        merge_out(t["key"], base)
                        out[t["key"]] = base
                        st["done"][t["key"]] = phase
                        st["fail"].pop(f"{phase}:{t['key']}", None)
                        log(f"[{phase}][OK] {t['key']} -> {rec['u']}  ({rec['title'][:26]})")
                    else:
                        st["fail"][f"{phase}:{t['key']}"] = err
                        log(f"[{phase}][--] {t['key']} {err}")
                    if done_n % 20 == 0:
                        save_state(st)
        save_state(st)
        log(f"== 阶段 {phase} 完成: 处理 {done_n}，命中 {hit_n}，"
            f"耗时 {time.time() - t0:.0f}s")

    log(f"== 累计县级命中 {len(out)} / 目标 {len(targets)}")


# ── 复核（2026-11-18 用户指令：误采/错采/漏采都要查） ──────────────────
REJ_F = os.path.join(HERE, "zzjg_county_rejected.json")
MISS_F = os.path.join(HERE, "zzjg_county_missing.json")


def drop_counties(keys):
    """剔除指定县级记录并清断点，让下轮重新采集（门户 URL 订正后用）。"""
    out = json.load(open(OUT_F, encoding="utf-8")) if os.path.exists(OUT_F) else {}
    st = load_state()
    rej = {}
    if os.path.exists(REJ_F):
        try:
            rej = json.load(open(REJ_F, encoding="utf-8"))
        except Exception:
            rej = {}
    hit = [k for k in out if k in set(keys)]
    for k in hit:
        rej[k] = dict(url=out[k].get("u"), why=["manual:门户URL订正后重采"],
                      title=out[k].get("title"))
        out.pop(k, None)
        st["done"].pop(k, None)
        for ph in PHASES:
            st["fail"].pop(f"{ph}:{k}", None)
    json.dump(out, open(OUT_F, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(rej, open(REJ_F, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    save_state(st)
    log(f"== 剔除 {len(hit)} 条：{hit}")
    miss = [k for k in keys if k not in hit]
    if miss:
        log(f"   （未命中，跳过：{miss}）")


def tidy_counties():
    """离线清理（不抓页）：按 title 规则剔除上级单位 / 非清单页链接。

    只依据已采到的 title 字段，替代 audit 的第一步；audit 仍会回抓复核。
    """
    out = json.load(open(OUT_F, encoding="utf-8")) if os.path.exists(OUT_F) else {}
    st = load_state()
    tg = {t["key"]: t for t in load_county_targets()}
    rej = {}
    if os.path.exists(REJ_F):
        try:
            rej = json.load(open(REJ_F, encoding="utf-8"))
        except Exception:
            rej = {}
    n_link = n_rec = 0
    for k in list(out):
        t, rec = tg.get(k), out[k]
        if not t or not rec.get("links"):
            continue
        keep = []
        for l in rec["links"]:
            if _link_bad(t, l):
                n_link += 1
                continue
            keep.append(l)
        if not keep:
            n_rec += 1
            rej[k] = dict(url=rec.get("u"), why=["tidy:上级单位/非清单页"],
                          title=rec.get("title"))
            out.pop(k, None)
            st["done"].pop(k, None)
            for ph in PHASES:
                st["fail"].pop(f"{ph}:{k}", None)
            continue
        if len(keep) != len(rec["links"]):
            rec["links"] = keep
            if rec.get("u") and all(l.get("u") != rec["u"] for l in keep):
                rec["u"] = keep[0]["u"]
                rec["title"] = keep[0].get("title") or rec.get("title", "")
    json.dump(out, open(OUT_F, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(rej, open(REJ_F, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    save_state(st)
    log(f"== 离线清理：删链接 {n_link}，整条剔除 {n_rec}，剩余 {len(out)} 县")


def audit_counties(targets, workers=6, render=False, sync=False):
    """逐条回抓复核已采结果：归属（非上级单位）+ 本县自证；不合格整条剔除并清断点。

    输出：zzjg_county_rejected.json（剔除明细）、zzjg_county_missing.json（漏采清单）。
    """
    tmap = {t["key"]: t for t in targets}
    out = json.load(open(OUT_F, encoding="utf-8")) if os.path.exists(OUT_F) else {}
    st = load_state()
    rej = {}
    if os.path.exists(REJ_F):
        try:
            rej = json.load(open(REJ_F, encoding="utf-8"))
        except Exception:
            rej = {}
    keys = [k for k in out if k in tmap]
    log(f"== 复核 {len(keys)} 条县级记录（workers={workers} render={render}）")
    verdicts, lock = {}, threading.Lock()
    n_ok = n_bad = 0

    def one(k):
        t, rec = tmap[k], out[k]
        good, why_list = [], []
        n_core = 0
        for l in rec.get("links") or []:
            u = (l.get("u") or "").strip()
            if not u:
                continue
            kind = l.get("kind") or "机构设置"
            # 非核心类（公积金/高校等）常是合法外链：只查同站，不抓页
            if kind not in P.CORE_KINDS:
                if _link_bad(t, l):
                    why_list.append(f"aux-bad {u}")
                elif P.same_site(u, t["url"]):
                    good.append(l)
                else:
                    why_list.append(f"aux-off-site {u}")
                continue
            n_core += 1
            h, m = P.fetch(u, timeout=20)
            if (not h or len(h) < 800) and render:
                h = P.render_page(u, wait_ms=1500, use_proxy=True)
            # ① 页面类型复核：公文/决算/服务页一律不认（用当前判定器重跑一遍）。
            # 四川统一平台例外：标题含「政务服务」会被 service-page 规则误杀，
            # 它的归属证据是 areaCode + 部门链接（下面 county_guard 校验）。
            is_sc = (urlparse(u).hostname or "").lower().endswith("sczwfw.gov.cn")
            if not is_sc:
                ok_s, _s, _t, why_s = P.page_score(u, h, kind)
                if not ok_s:
                    why_list.append(f"page:{why_s} {u}")
                    continue
            # ② 归属复核：必须是本县自己的页面（防上级单位）
            ok, why = county_guard(t, {"u": u}, h)
            if (not ok and render and not is_sc
                    and why in ("no-county-name", "no-html")):
                h2 = P.render_page(u, wait_ms=1800, use_proxy=True)   # JS 壳兜底再验一次
                if h2 and len(h2) > len(h or ""):
                    h = h2
                    ok_s2, _s2, _t2, why_s2 = P.page_score(u, h, kind)
                    ok = ok_s2 and county_guard(t, {"u": u}, h)[0]
                    why = county_guard(t, {"u": u}, h)[1] if ok else f"render:{why_s2}"
            why_list.append(f"{why} {u}")
            if ok:
                good.append(l)
        if good and n_core:
            nrec = dict(rec)
            nrec["links"] = good
            nrec["u"] = good[0]["u"] if rec.get("u") not in [g["u"] for g in good] else rec["u"]
            return k, True, nrec, why_list
        return k, False, None, why_list

    with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        futs = [ex.submit(one, k) for k in keys]
        for i, fut in enumerate(as_completed(futs), 1):
            k, ok, nrec, why = fut.result()
            with lock:
                verdicts[k] = (ok, why)
                if ok:
                    n_ok += 1
                    if nrec != out[k]:
                        merge_out(k, nrec)
                        out[k] = nrec
                else:
                    n_bad += 1
                    rej[k] = dict(url=out[k].get("u"), why=why,
                                  title=out[k].get("title"))
                    log(f"[audit][XX] {k} 剔除：{why[0] if why else 'no-links'}")
                    out.pop(k, None)
                    st["done"].pop(k, None)
                if i % 50 == 0:
                    log(f"   ... 复核 {i}/{len(keys)} ok={n_ok} bad={n_bad}")
    json.dump(out, open(OUT_F, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(rej, open(REJ_F, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    save_state(st)

    missing = [t for t in targets if t["key"] not in out]
    json.dump(missing, open(MISS_F, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    by_prov = {}
    for t in missing:
        by_prov[t["prov"]] = by_prov.get(t["prov"], 0) + 1
    log(f"== 复核完成：通过 {n_ok}，剔除 {n_bad}；漏采 {len(missing)}"
        f"（{len(targets)} 目标）")
    for p, n in sorted(by_prov.items(), key=lambda x: -x[1])[:12]:
        log(f"   漏采 {p}: {n}")
    return out


# ── registry 同步（按门户 URL 对齐，避免同名县串号） ────────────────────
def sync_registry():
    """把县级 zzjg 写入 site_registry.json。

    registry 里县级 key 形态不统一（`县级人民政府|长安区` 与
    `县级人民政府|河北省长安区` 并存，同名区县靠加省名区分）——只按名字匹配会串号，
    所以先用**门户 URL** 对齐，名字仅作二次校验。
    """
    targets = {t["key"]: t for t in load_county_targets()}
    out = json.load(open(OUT_F, encoding="utf-8")) if os.path.exists(OUT_F) else {}
    reg_path = os.path.join(HERE, "site_registry.json")
    reg = json.load(open(reg_path, encoding="utf-8"))

    def norm(u):
        return (u or "").strip().rstrip("/").lower()

    by_url = {}
    for k, v in reg.items():
        if k.startswith("县级人民政府|") and v.get("u"):
            by_url.setdefault(norm(v["u"]), k)
    n_upd = n_new = 0
    for key, rec in out.items():
        t = targets.get(key)
        if not t:
            continue
        rk = by_url.get(norm(t["url"]))
        if not rk:                      # 老门户换了域名的，按名字 + 省份兜底
            for cand in (f"县级人民政府|{t['prov']}{t['name']}",
                         f"县级人民政府|{t['name']}"):
                if cand in reg and norm(reg[cand].get("u")) == norm(t["url"]):
                    rk = cand
                    break
        if not rk:
            rk = f"县级人民政府|{t['prov']}{t['name']}"
            reg[rk] = dict(u=t["url"], n=t["name"], locations=["块"],
                           source_level="L2", verified_at="", status="unknown")
            n_new += 1
        e = reg[rk]
        e["zzjg"] = rec["u"]
        e["zzjg_src"] = rec.get("src", "")
        e["zzjg_verified_at"] = rec.get("verified_at", TODAY)
        if rec.get("links"):
            e["zzjg_links"] = [{"kind": l.get("kind", ""), "u": l.get("u", "")}
                               for l in rec["links"] if l.get("u")]
        n_upd += 1
    os.system(f'cd "{HERE}" && uv run python backup_now.py >/dev/null 2>&1')
    json.dump(reg, open(reg_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    log(f"== registry 同步：更新 {n_upd}，新建 {n_new}")


if __name__ == "__main__":
    main()
