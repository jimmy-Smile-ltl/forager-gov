#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""p241 错配 URL 清除后的「正确 URL」回填（2026-11-18 用户指令）。

背景：p240 全量核查清除了 300+ 个身份不符的 URL（国家部委顶替市级部门、
上级纪委顶替县级监委、跨地同名区县错配、文章页入口…）。用户指令：发现错误
URL 之后，更重要的是**拿到正确 URL**，实在不行允许调用百度搜索引擎。

渠道（与项目三档口径一致，SERP 为本轮用户明确授权）：
  ① 上级/同系统官网名录、本级政府门户导航（官方页面真实链接）
  ② 百度 SERP 兜底：只取 `mu` 真实 URL，标题必须通过身份判定
  ③ 条树叶：块树同机构回填后同步（只填空）

安全线：
  - **只填 u 为空的节点**，绝不覆盖现有 URL；
  - 每个候选都走 p240 的 judge（与全量核查同一套判定器）复核，
    复核不过立即回滚——哪怕是 p223 成熟渠道给的；
  - 不猜域名、不做拼音探测；SERP 结果必须 title 严格验证；
  - 拿不到/验证不过一律保持 u=""（列名），不降级、不凑数。

用法（单写者，先确认 p198 循环已停）：
  cd data && uv run python p241_wrong_url_backfill.py --dry   # 只探测不写库
  cd data && uv run python p241_wrong_url_backfill.py         # 落库（写前备份）
环境变量：
  P241_ONLY=five,generic,sync   # 只跑某几段
  P241_LIMIT=50                 # 每段上限（联调用）
  P241_WORKERS=4                # 通用段并发
"""
import datetime
import json
import os
import re
import shutil
import socket
import sys
import tempfile
import threading
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse, urlsplit, urlunsplit

DATA = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(DATA)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "util"))
sys.path.insert(0, DATA)

import p223_county_5sys_fill as F                      # noqa: E402
import p240_full_url_verify as V                       # noqa: E402
from site_contract import base as sc_base, upsert_registry  # noqa: E402

TREE_F = os.path.join(DATA, "tree.json")
REG_F = os.path.join(DATA, "site_registry.json")
STATE_F = os.path.join(DATA, "p241_state.json")
REPORT_F = os.path.join(DATA, "p241_report.json")
TODAY = datetime.date.today().isoformat()

DRY = "--dry" in sys.argv
ONLY = set((os.environ.get("P241_ONLY") or "five,generic,sync").split(","))
LIMIT = int(os.environ.get("P241_LIMIT", "0")) or None
WORKERS = int(os.environ.get("P241_WORKERS", "4"))
NAME_FILTER = os.environ.get("P241_FILTER") or ""   # 联调：按节点名过滤
TRACE_FILTER = os.environ.get("P241_TRACE") or ""   # 只跑某类清除痕迹（p240/p243）
F.DRY = DRY


def _atomic(obj, path):
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def checkpoint(tree, reg, state):
    """长跑中途落盘（单写者环境；写前备份已在 main 开头做过）。"""
    if DRY:
        return
    _atomic(tree, TREE_F)
    _atomic(reg, REG_F)
    _atomic(state, STATE_F)


def html_title(h):
    m = re.search(r"<title[^>]*>(.*?)</title>", h or "", re.S | re.I)
    if not m:
        return ""
    t = F.norm(m.group(1))
    try:
        import html as _h
        t = _h.unescape(t)
    except Exception:
        pass
    return t


# ── 目标收集 ────────────────────────────────────────────────
# 市级部门组里的「非本级机构」垃圾节点（门户导航误采国家平台/别省门户）：
# 不是本市部门，也没有对应官网，回填无从谈起——p241 --junk 直接删节点。
#   实测：武清区「2026年全国两会」、衡水市「中联办」、
#        保山市/普洱市「四川省人民政府网站」、淄博市「建设部」。
JUNK_DEPT = re.compile(r"(两会|中联办|人民政府网站?$|^建设部$)")


def is_junk(t):
    return t["k"] == "政府部门" and bool(JUNK_DEPT.search(t["name"]))


# ── URL 归属索引（防回填把已属别地区的站再挂一遍）──────────────
# p240 逐节点核查 + p243 串站裁决之后，树里每条 URL 都带着明确的地区身份。
# 回填候选若是别的地区机构的站（乐山「市中区检察院」回填到济南市中区、
# 大同市人大回填到大庆大同区、龙港市政协回填到葫芦岛龙港区），必须拦下。
URL_OWNERS = {}
URL_HOST_OWNERS = {}


def urln(u):
    return (u or "").strip().rstrip("/").lower()


def hostn(netloc):
    """主机归一：去掉 www.（实 cro 站 www./裸域两种写法都会出现，
    金川区纪委站被「http://jinchuanjcjjjc.gov.cn」绕过过一次主机归属检查）。"""
    h = (netloc or "").strip().lower()
    return h[4:] if h.startswith("www.") else h


FAM2 = (("法院", "法院"), ("检察", "检察"), ("人大", "人大"), ("政协", "政协"),
        ("纪委", "纪委"), ("监委", "纪委"))

# 五系统站点标题里必然出现的本系统词（标题一个都没有 → 不是这个系统的机关）
FIVE_WORD = {
    "人大": ("人大", "人民代表大会"),
    "政协": ("政协", "政治协商会议"),
    "法院": ("法院", "人民法院"),
    "检察": ("检察", "人民检察院"),
    "纪委": ("纪委", "监委", "纪检监察", "纪律检查", "监察委员会", "清廉"),
}


def fam2(name):
    """机构大类（「县人大」这种占位名和「大同市人大常委会」要归到同一类）。"""
    for k, v in FAM2:
        if k in (name or ""):
            return v
    return fam_of(name)


def place_form(full):
    """地名形态：pref（自治州/州/地区/盟）/ city（市）/ county / prov。

    裸「XX州」歧义（锦州=市简称，昌吉州=地级简称）按同基底是否有地级全名判。
    """
    if not full:
        return ""
    if V.is_real_prov(full):
        return "prov"
    if full.endswith(("自治州", "地区", "盟")):
        return "pref"
    if full.endswith("州"):
        prefs = {b for f, b in V.ALL_PLACES.items()
                 if f.endswith(("自治州", "地区", "盟"))}
        b = V.ALL_PLACES.get(full) or full[:-1]
        return "pref" if b in prefs else "city"
    if full.endswith("市"):
        return "city"
    return "county"


def _city_of(rec):
    for nm in reversed(list(rec.get("path") or []) + [rec.get("name") or ""]):
        p = V.place_of(nm)
        if p and V.is_city_level(p[0]):
            return p[0]
    return ""


def district_of(rec):
    """路径/名称里最后一个区县名。

    place_of 会把「城区」「矿区」这类通名当层级占位名拒掉（多市都有），
    但它们在路径里就是区划名——块树「城区 → 县人民法院」只能这样认出来，
    否则 deep 退化成「阳泉市」，和条树「阳泉城区法院」对不上。
    """
    nm = rec.get("name") or ""
    m = V.ROLE_TAIL.sub("", re.sub(r"[（(][^）)]*[）)]", "", nm)).strip("·、 ")
    if (m and V.ADMIN_SUFFIX.search(m)
            and (m[0] not in "省市县区" or m in V.PREFIX_PLACES)):
        return m
    for p in reversed(list(rec.get("path") or [])):
        q = re.sub(r"[（(][^）)]*[）)]", "", p).strip()
        if not q or "机关" in q or q.endswith("组"):
            continue
        if (V.ADMIN_SUFFIX.search(q)
                and (q[0] not in "省市县区" or q in V.PREFIX_PLACES)):
            return q
    return ""


def base_norm(rec):
    """地名基底归一：复合名剥上级市名。

    条树把区县名写成带市名的复合形态（「阳泉城区法院」「阳泉矿区法院」），
    块树是「城区/矿区 → 县人民法院」——直接比 rec_places 的基底会把同一个
    机构的站认成「别地区机构」。剥掉市名后统一到「城 / 矿」。
    """
    d = district_of(rec) or V.rec_places(rec)[2]
    city = _city_of(rec)
    if city and d.startswith(city) and len(d) > len(city):
        d = d[len(city):]                       # 荆州市沙市区 → 沙市区
    elif city and d.startswith(city[:-1]) and len(d) > len(city) - 1:
        cand = d[len(city) - 1:]                # 阳泉城区 → 城区
        if V.ADMIN_SUFFIX.search(cand):
            d = cand
    q = V.place_of(d)
    if q:
        return q[1]
    return V.ADMIN_SUFFIX.sub("", d).strip("·、 ") or d


def _ident_of(rec):
    rp = V.rec_places(rec)
    return ((rec.get("prov") or ""), base_norm(rec),
            fam2(rec.get("name", "")), place_form(rp[2]))


def build_url_owners(tree):
    """全树（块+条）已有 URL → 地区身份集合；另建主机索引（只拦根址复用）。"""
    URL_OWNERS.clear()
    URL_HOST_OWNERS.clear()

    def walk(n, path, lv, prov):
        name = (n.get("n") or "").strip()
        myprov = prov
        if n.get("l") == "省" and name:
            p = V.place_of(name)
            if p and V.is_real_prov(p[0]):
                myprov = p[0]
        u = (n.get("u") or "").strip()
        if u.startswith("http") and name and (n.get("k") or "") != "分组":
            rec = {"name": name, "k": n.get("k") or "", "c": n.get("c") or "",
                   "path": list(path), "lv": list(lv), "prov": myprov,
                   "tree": "blk"}
            ident = _ident_of(rec)
            URL_OWNERS.setdefault(urln(u), set()).add(ident)
            URL_HOST_OWNERS.setdefault(hostn(urlparse(u).netloc), set()).add(ident)
        for c in n.get("ks") or []:
            walk(c, path + [name], lv + [n.get("l") or ""], myprov)

    for g in tree["ks"]:
        walk(g, [], [], "")


def same_ident(a, b):
    if a[0] != b[0] or a[1] != b[1]:
        return False
    if a[2] and b[2] and a[2] != b[2]:
        return False
    # 同名「州/地区 ↔ 市」是上级机关与驻地市两个机构（阿勒泰地区院 vs 阿勒泰市院）
    return not ({a[3], b[3]} == {"pref", "city"})


def url_owner_conflict(t, u):
    """u 已被别地区/别系统机构占用时返回占用方，否则 ""。

    精确 URL 之外再看一层：候选是**站点根址**时，该主机若已被别机构占用
    （内乡县检察院 www.haneixiang.jcy.gov.cn/… 被 SERP 当楚雄市、临夏市候选），
    同样算串站。根址属于某个机构，主机级判重可靠；带路径的平台子站
    （12388 省站下的县页、法院网县级频道）只按精确 URL 判，不按主机判。
    """
    rp = V.rec_places(rec_of(t, ""))
    mine = ((t.get("prov") or ""), base_norm(rec_of(t, "")), fam2(t["name"]),
            place_form(rp[2]))

    def allowed(owners):
        for (au, ad) in V.ALLOW_OK:
            if urln(au) == urln(u) and ad == rp[2]:
                return True
        return any(same_ident(mine, o) for o in owners)

    owners = URL_OWNERS.get(urln(u))
    if owners and not allowed(owners):
        o = sorted(owners, key=lambda x: sum(len(y) for y in x), reverse=True)[0]
        return "/".join(x for x in o if x)
    p = urlparse(u)
    if (p.path or "") in ("", "/"):
        ho = URL_HOST_OWNERS.get(hostn(p.netloc))
        if ho and not allowed(ho):
            o = sorted(ho, key=lambda x: sum(len(y) for y in x), reverse=True)[0]
            return "/".join(x for x in o if x)
    return ""


def collect_targets(tree):
    """u 为空且带 p240/p243/p241b 清除痕迹的节点（分组容器、垃圾节点除外）。

    p240 = 单节点身份核查清除；p243 = 同一 URL 跨地区串站裁决清除；
    p241b = 回填结果独立复核清除（抓回来发现是栏目页/群团站/别级机构）。
    三类都留名待补，正确 URL 一律重走本脚本的官方渠道 + SERP 验证。
    """
    out = []

    def walk(n, path, lv, prov, kind, anc):
        name = (n.get("n") or "").strip()
        myprov = prov
        if n.get("l") == "省" and name:
            p = V.place_of(name)
            if p and V.is_real_prov(p[0]):
                myprov = p[0]
        trace = (n.get("s") or "")
        if (name and not (n.get("u") or "").strip()
                and ("p240" in trace or "p243" in trace or "p241b" in trace)
                and (n.get("k") or "") != "分组"):
            out.append({"node": n, "name": name, "k": n.get("k") or "",
                        "c": n.get("c") or "", "path": list(path),
                        "lv": list(lv), "prov": myprov, "tree": kind,
                        "anc": list(anc)})
        for c in n.get("ks") or []:
            walk(c, path + [name], lv + [n.get("l") or ""], myprov, kind,
                 anc + [n])

    for g in tree["ks"]:
        kind = "tiao" if (g.get("l") == "根"
                          or (g.get("n") or "").startswith("条")) else "blk"
        walk(g, [], [], "", kind, [])
    if NAME_FILTER:
        out = [t for t in out if NAME_FILTER in t["name"]]
    if TRACE_FILTER:
        out = [t for t in out
               if TRACE_FILTER in (t["node"].get("s") or "")]
    return [t for t in out if not is_junk(t)]


def tkey(t):
    return f"{t['tree']}|{'|'.join(t['path'] + [t['name']])}"


def index_nodes(tree):
    """id(node) → {path, lv, prov, tree, anc}（与 p240 collect_records 同口径）。"""
    idx = {}

    def walk(n, path, lv, prov, kind, anc):
        name = (n.get("n") or "").strip()
        myprov = prov
        if n.get("l") == "省" and name:
            p = V.place_of(name)
            if p and V.is_real_prov(p[0]):
                myprov = p[0]
        idx[id(n)] = {"path": list(path), "lv": list(lv), "prov": myprov,
                      "tree": kind, "anc": list(anc)}
        for c in n.get("ks") or []:
            walk(c, path + [name], lv + [n.get("l") or ""], myprov, kind,
                 anc + [n])

    for g in tree["ks"]:
        kind = "tiao" if (g.get("l") == "根"
                          or (g.get("n") or "").startswith("条")) else "blk"
        walk(g, [], [], "", kind, [])
    return idx


# ── 抓取 / 身份判定 ─────────────────────────────────────────
_DNS_CACHE = {}
_DNS_LOCK = threading.Lock()


def dns_ok(host):
    """域名是否解析（页面取不到时区分「死域」与「WAF/临时不通」）。"""
    if not host:
        return False
    with _DNS_LOCK:
        if host in _DNS_CACHE:
            return _DNS_CACHE[host]
    try:
        socket.getaddrinfo(host, None)
        ok = True
    except Exception:
        ok = False
    with _DNS_LOCK:
        _DNS_CACHE[host] = ok
    return ok


def snap(u):
    """取候选页面 → (res, 网络档, 说明)。页面取不到返回 None。"""
    h = F.fetch_cached(u)
    if not h or len(h) < 300:
        return None
    body = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", h,
                  flags=re.S | re.I)
    res = {"u": u, "code": 200, "via": "direct", "final": u,
           "title": html_title(h), "size": len(h), "err": "",
           "snippet": re.sub(r"<[^>]+>", " ", body)[:1500]}
    res["snippet"] = re.sub(r"[\s　\xa0]+", "", res["snippet"])
    st, why = V.base_status(res)
    return res, st, why


def rec_of(t, u):
    return {"u": u, "name": t["name"], "k": t["k"], "c": t["c"],
            "path": list(t["path"]), "lv": list(t["lv"]),
            "prov": t["prov"], "tree": t["tree"]}


# 专题/专栏路径：不是机构官网入口（实测：SERP 把「2026天津两会」专题页
# /sy/ztzl/ztlbone/… 当成机构入口）。机构真身可能挂在 /zt/ 子站，故只按
# 独立路径段判，且落库前仍要过 title 身份复核。
TOPIC_PATH = re.compile(r"/(ztzl|ztlbone|ztbd|zhuanti|special|topic|jjzt|rdzt)(/|$)",
                        re.I)
# 新闻动态/部门动态等门户栏目 + CMS 详情页（实测衡水统计局 ←
#   xxgk.hengshui.gov.cn/eportal/ui/?pageId=…&articleKey=…「职能介绍」；
#   贵港 ← www.gxgg.gov.cn/xwdt/bmdt2/t28337544.shtml 部门动态文章）
NEWS_EXTRA = re.compile(
    r"/(xwdt|xwzx|xinwen|bmdt|zwdt|gzdt|jryw|ttxw|ywdt|bmxx|xwfb|bmfb|"
    r"gzxx|bmxxgk|view|detail|article|show|ewm|tsjb|jbts|jubao|jbzx)(/|$)|"
    r"/(eportal|module|list|column|sgdt|gzdtx|gzyw)/|"
    r"(^|/)t\d{6,}\.(s?html?|jhtml?|jsp|aspx?)$|"
    r"(^|/)[A-F0-9]{16,}\.(s?html?|jhtml?)$|"
    r"(^|/)\d{4,}\.(s?html?|jhtml?)$|"
    r"ppjy|nmjb|jubao", re.I)
# 预决算/重点领域信息公开栏目（实测 利川市/来凤县监委 ← 门户
# /xxgk/zdlyxxg/czyjsx/…：政府预决算栏目，不是纪委监委站点）
BUDGET_PATH = re.compile(
    r"/(zdlyxxg|czyjsx|czyjs|czjs|czys|czjg|ysjs|ysgk|czxxgk|czyjsxx)(/|$)", re.I)
ARTICLE_QUERY_EXTRA = re.compile(
    r"[?&](articlekey|pageid|articleid|contentid|channelid|infoid|newsid|docid)=.",
    re.I)
# 门户信息公开/机构设置/政策文件栏目——不是部门独立官网（本项目口径：
# 门户栏目页不算官网）。实测贵港市统计局 ← /zfxxgk/fdzdgknr/jgsz/srmzfgzbm/…、
# 百色 ← /zwgk/zcwj/bmwj/tjj/、安顺 ← /zwgk/ysqgk/szfgzbm/stjj/、
# 固原 ← /zwgk/bmxxgkml/4190/…、天水 ← /zwgk/fdzdgknr/tjxx/…
PORTAL_PATH = re.compile(
    r"/(zwgk|zfxxgk|xxgk|fdzdgknr|bmxxgkml|bmxxgk|gknr|jgsz|szfgzbm|"
    r"zcwj|bmwj|ysqgk|tjxx|zfxxgkml|bmxx)(/|$)", re.I)
# 门户栏目/频道路径——不是任何机构的官网入口（不限节点类别）：领导之窗/
# 领导活动、机构概况、信访频道、政务公开栏目。实测 赤峰市政协 ← 市政府门户
# /cfszf_dwgk/swld/swldwsc/ldhd_wsc/index_1.html（市委领导活动）、塔城地区
# 信访局 ← /Petition/Notice（「信访须知_专员信箱_塔城地区行政公署」）
PORTAL_COLUMN = re.compile(
    r"/(swld|ldhd|ldzc|zfld|jgsz|jggk|dwgk|gknr|bmxxgk|petition|wsxf|xfxx|"
    r"zfgb|tjxx|zcwj|bmwj|ysqgk|zwgk|zfxxgk|xxgk)(/|$)|_dwgk|_swld", re.I)
# 群团子站顶替机构节点：实测 松江区人大 ← gqt.songjiang.gov.cn「松江共青团」
# （role 互斥不认群团，标题含区名即放行）
FAMILY_TITLE = re.compile(
    r"(共青团|团区委|团市委|团县委|总工会|工会|妇联|妇女联合会|统战部|工商联|"
    r"残联|科协|文联|记协|侨联|台联)")
# 五系统节点（条/块两种树的叶子）与政府品牌标题
FIVE_KINDS = ("并列机关", "人大系统", "政协系统", "法院系统", "基层法院",
              "检察院系统", "纪委系统")
GOV_TITLE = re.compile(r"(人民政府|行政公署|行署|政务服务网|人民政府门户)")
# 门户品牌标题（部门节点填成门户页面）
PORTAL_TITLE = re.compile(r"(人民政府|门户网站|信息公开$|信息公开目录|职能介绍)")
# 政法/宣传专题站标题：人民政府节点会被这类站顶替（实测 铜陵市郊区 ←
# 「铜陵市郊区平安网」jqpaw.gov.cn——标题含「郊区」，地区判定与
# 「本级名在标题」两条都能过，但它是区政法委的平安网，不是区政府门户）
GOV_NEG_TITLE = re.compile(r"(平安网|长安网|文明网|党建网|法治网|廉政网|纪检监察|政法网|新闻网)")
# 中央部委域名：地方机构节点指到中央部委站一律不是本级官网
# （实测黑龙江省林业和草原局 ← www.forestry.gov.cn 的「全省林业和草原
#  工作会议召开」文章页——标题含省名，p240 地区判定放行）
CENTRAL_HOSTS = (
    "ndrc.gov.cn", "moe.gov.cn", "most.gov.cn", "miit.gov.cn", "mps.gov.cn",
    "mca.gov.cn", "moj.gov.cn", "mof.gov.cn", "mofcom.gov.cn", "mohrss.gov.cn",
    "mnr.gov.cn", "mee.gov.cn", "mohurd.gov.cn", "mot.gov.cn", "mwr.gov.cn",
    "moa.gov.cn", "mct.gov.cn", "nhc.gov.cn", "mva.gov.cn", "mod.gov.cn",
    "stats.gov.cn", "nra.gov.cn", "ncha.gov.cn", "saac.gov.cn", "nea.gov.cn",
    "mem.gov.cn", "ggj.gov.cn", "spb.gov.cn", "cea.gov.cn", "ncac.gov.cn",
    "cnipa.gov.cn", "cnsa.gov.cn", "forestry.gov.cn", "nmpa.gov.cn",
    "cac.gov.cn", "samr.gov.cn", "sasac.gov.cn", "pbc.gov.cn",
    "customs.gov.cn", "chinatax.gov.cn", "mfa.gov.cn", "cbirc.gov.cn",
    "csrc.gov.cn", "sara.gov.cn", "chinacourt.org", "spp.gov.cn",
    "ccdi.gov.cn", "npc.gov.cn", "cppcc.gov.cn",
)


def is_central_host(u):
    h = urlparse(u).netloc.lower()
    if h in ("www.gov.cn", "gov.cn"):
        return True
    return any(h == d or h.endswith("." + d) for d in CENTRAL_HOSTS)


# 移动版详情页（12388 举报平台 /m/laws.html、/m/law-d1.html 是法规页）
MOBILE_ARTICLE = re.compile(
    r"/(m|mobile)/(laws?|law-d\d+|[a-z]+-d\d+|[a-z]+/laws?)\.s?html?$", re.I)
MOBILE_ROOT = re.compile(r"^(.*)/(m|mobile|wap)/?$", re.I)


def normalize_mobile(u):
    """移动版归一到机构子站根：/x/m、/x/wap → /x/；
    移动版详情页 /x/m/laws.html → /x/（12388 举报平台的法规页不是入口）。"""
    p = urlsplit(u)
    path = p.path or ""
    m = MOBILE_ARTICLE.search(path)
    if m:
        path = path[:m.start()]
    else:
        m = MOBILE_ROOT.match(path)
        if not m:
            return u
        path = m.group(1)
    if not path.endswith("/"):
        path += "/"
    return urlunsplit((p.scheme, p.netloc, path or "/", "", ""))


def path_guards(u):
    """URL 形态红线：文章/栏目/登录/预决算等一律不是机构入口。"""
    if u.count("?") > 1:
        # 拼接/伪装的查询串（实测 利川市监委 ?jcldgdnhfbcvxbmp?tkuo）
        return "查询串畸形"
    if TOPIC_PATH.search(urlparse(u).path or ""):
        return "专题/专栏路径"
    if PORTAL_COLUMN.search(urlparse(u).path or ""):
        return "门户栏目/频道页"
    if BUDGET_PATH.search(urlparse(u).path or ""):
        return "预决算/重点领域栏目"
    if NEWS_EXTRA.search(urlparse(u).path or ""):
        return "新闻/动态栏目"
    if ARTICLE_QUERY_EXTRA.search(u):
        return "CMS 详情页查询串"
    if (F.NEWS_PATH.search(u) or F.NEWS_QUERY.search(u)) \
            and not F.CHANNEL_OK.search(u):
        return "新闻/文章路径"
    if F.LOGIN_PATH.search(u):
        return "登录/后台页"
    if F.BAD_COLUMN.search(u):
        return "预决算/人事栏目"
    if F.LEADER_PATH.search(u):
        return "领导之窗页"
    if any(b in urlparse(u).netloc.lower() for b in F.BAD_HOST):
        return "媒体/聚合站"
    if urlparse(u).netloc.lower().endswith((".edu.cn", ".ac.cn")):
        return "高校/科研域名"
    return ""


def root_of(u):
    p = urlparse(u)
    return f"{p.scheme}://{p.netloc}/" if p.netloc else u


# ── 机构词识别（部门/群团节点的 title 身份）────────────────────
# p240 judge 只判「地区 + 机构类型互斥角色」，部门节点指到本级政府门户
# 也能过（标题含地名）。回填空缺时门槛要更高：标题必须真的写这个机构，
# 否则「XX市统计局」会被填成 XX 市政府门户、XX 市数据平台。
ORG_SUFFIX = re.compile(r"(局|委员会|委|办公室|办|厅|部|中心|站|所|署|院|处|科|队|馆|会|团)$")
# 简称 ↔ 全称（群团机构标题多写全称）
ORG_ALIAS = {
    "台联": ("台联", "台湾同胞联谊会"),
    "侨联": ("侨联", "归国华侨联合会", "华侨联合会"),
    "妇联": ("妇联", "妇女联合会"),
    "总工会": ("总工会", "工会"),
    "工会": ("总工会", "工会"),
    "科协": ("科协", "科学技术协会"),
    "共青团": ("共青团", "团委"),
    "团省委": ("共青团", "团省委", "团委"),
    "团市委": ("共青团", "团市委", "团委"),
    "残联": ("残联", "残疾人联合会"),
    "计生协": ("计生协", "计划生育协会"),
    "计划生育协会": ("计划生育协会", "计生协"),
    "文联": ("文联", "文学艺术界联合会"),
    "作协": ("作协", "作家协会"),
    "工商联": ("工商联", "工商业联合会"),
    "青联": ("青联", "青年联合会"),
    "记协": ("记协", "新闻工作者协会"),
    "红十字会": ("红十字会",),
    "法学会": ("法学会",),
    "黄埔": ("黄埔军校同学会", "黄埔"),
}
DEPT_KINDS = ("政府部门", "部门")


def org_kw(name):
    x = org_base(name)
    y = ORG_SUFFIX.sub("", x)
    return y if len(y) >= 2 else x


def org_hit(title, name):
    """title 里是否写了这个机构（简称/全称变体都认）。"""
    if not title:
        return False
    ob = org_base(name)
    cands = [ob] + list(ORG_ALIAS.get(ob, ()))
    k = org_kw(name)
    if len(k) >= 2:
        cands.append(k)
    return any(c and c in title for c in cands)


def child_place_hit(title, deep_full):
    """标题里出现本级的下辖区县 → 下级机构顶替本级（实测衡水市统计局 ←
    桃城区统计局，标题「桃城区人民政府办公室衡水市桃城区统计局」）。
    只在 deep 是地级市时判（省级部门标题偶尔会带市名，不作证据）。
    """
    if not title or not deep_full or deep_full in V.PROV_FULLS:
        return ""
    for c, city in V.CITY_OF_COUNTY.items():
        if city == deep_full and c != deep_full and c in title:
            return c
    return ""


# 跨市同名区县（江北区/鼓楼区/铁西区…）：p240 清理的错配主要形态，
# 回填时必须带父市或省名才能确认是哪一个（实测重庆江北区总工会 ←
#   nbgh.gov.cn 宁波江北区总工会，标题只有「江北区」）。
DUP_COUNTY = set()


def build_dup_counties():
    DUP_COUNTY.clear()
    for c, cities in V.CITY_OF_COUNTY.items():
        if len(cities) > 1:
            DUP_COUNTY.add(c)


def nearest_parent_place(t, deep_full):
    for nm in reversed(t["path"]):
        p = V.place_of(nm)
        if p and p[0] != deep_full:
            return p[0]
    return ""


INST_ALWAYS = ("群团组织", "民主党派")
# 常见部门业务词：标题里写了「别的部门」= 不是本机构入口
# （实测贵港市统计局 ← czj.gxgg.gov.cn/ggsbjyjsgkpt/ggbmys/2022/ggstjj/
#  「贵港市统计局-广西贵港市财政局网」是财政局站上的统计局部门预算页）
ORG_TYPES = ("财政", "统计", "教育", "公安", "民政", "司法", "人力资源",
             "自然资源", "生态环境", "住房", "交通", "水利", "农业农村",
             "商务", "文化", "卫生健康", "应急", "审计", "市场监督", "林业",
             "体育", "医疗保障", "税务", "发展改革", "工业和信息化", "科技",
             "退役军人", "气象", "地震", "档案", "粮食", "烟草", "海关",
             "新闻出版", "广播电视", "机关事务", "国有资产", "金融", "信访",
             "民族宗教", "外事")


def other_org_hit(title, name):
    """标题里出现、但节点名里没有的部门业务词。"""
    own = {x for x in ORG_TYPES if x in (name or "")}
    hit = {x for x in ORG_TYPES if x in (title or "")}
    extra = sorted(hit - own)
    return extra[0] if extra else ""


def verify(t, u, anchor="", official=False, allow_orgcn=False, nav=False):
    """候选 URL 身份复核。返回 (ok, note, 实际核验的 URL)。

    人民政府节点会把候选归一到门户根（栏目/专题页不是政府入口），
    所以必须把归一后的 URL 返回给调用方落库。

    nav=True 表示候选来自**官方页面真实链接**（上级官网/门户导航提取）。
    这类链接在页面取不到时，只要域名解析正常就按「封锁默认正确」收——
    与 p240 全量核查口径一致；SERP 线索不享受这条（没有官方页面背书）。
    """
    u = F.clean_fill_url((u or "").strip())
    if not u.startswith("http"):
        return False, "非http", u
    u = normalize_mobile(u)
    # 政府门户节点：入口就是门户根，栏目/专题页一律归一到根
    if t["k"] == "人民政府":
        u = root_of(u)
    # 部门/群团不得填成上级门户根（实测松原市统计局 ← www.jlsy.gov.cn、
    # 百色市统计局 ← www.baise.gov.cn：门户标题含地名，p240 judge 放行）
    if t["k"] != "人民政府":
        for a in t.get("anc") or []:
            au = (a.get("u") or "").strip()
            if au.startswith("http") and root_of(au) == u:
                return False, "候选=上级门户根(非本级机构)", u
    # 部门/群团不得填成上级门户域名下的栏目（实测益阳市信访局 ←
    # www.yiyang.gov.cn/xfj/「益阳市信访局」——门户子目录不是部门独立官网）
    if t["k"] in DEPT_KINDS + INST_ALWAYS and urlparse(u).path not in ("", "/"):
        uh = urlparse(u).netloc.lower().removeprefix("www.")
        for a in t.get("anc") or []:
            au = (a.get("u") or "").strip()
            if au.startswith("http") and \
                    urlparse(au).netloc.lower().removeprefix("www.") == uh:
                return False, "上级门户域名下的栏目页", u
    g = path_guards(u)
    if g:
        return False, g, u
    oc = url_owner_conflict(t, u)
    if oc:
        return False, f"同URL已属别地区机构({oc})", u
    # 部门/群团不得填成门户的信息公开/机构设置等栏目页
    if t["k"] in DEPT_KINDS + INST_ALWAYS and PORTAL_PATH.search(
            urlparse(u).path or ""):
        return False, "门户栏目页(非部门官网)", u
    host = urlparse(u).netloc.lower()
    if "zwfw." in host or host.startswith("zwfw"):
        return False, "政务服务网(非机构官网)", u
    if t["prov"] and is_central_host(u):
        return False, "中央部委域名(非地方机构)", u
    if official:
        if not F.host_ok(u, strict=False):
            return False, "非官方域名", u
    else:
        strict_ok = F.host_ok(u, strict=True)
        if not strict_ok and allow_orgcn and host.endswith((".org.cn", ".org")):
            strict_ok = True
        if not strict_ok:
            return False, "非 gov 域名(SERP 口径)", u
    s = snap(u)
    if s is None:
        host = urlparse(u).netloc.lower()
        if not dns_ok(host):
            return False, "DNS 解析失败(死域)", u
        # 页面取不到（WAF/超时/IP 封锁）：官方页面真实链接 + 锚文本严格
        # 通过才收；部门节点不走锚文本口子（实测天水市统计局被省统计局
        # tjj.gansu.gov.cn 顶替——锚文本只写「统计局」、URL 却是省级站）
        if (official and anchor and t["k"] not in DEPT_KINDS
                and anchor_strict(anchor, t,
                                  V.rec_places(rec_of(t, ""))[2])):
            return True, f"页面不可取(锚文本严格校验: {anchor[:24]})", u
        if official and nav and t["k"] not in DEPT_KINDS:
            return True, "页面不可取(官方页面链接+DNS可解析)", u
        return False, "页面不可取", u
    res, st, why = s
    if st == "dead":
        return False, f"死链({why})", u
    if st == "waf":
        if (official and anchor and t["k"] not in DEPT_KINDS
                and anchor_strict(anchor, t,
                                  V.rec_places(rec_of(t, ""))[2])):
            return True, f"WAF/封锁(锚文本严格校验: {anchor[:24]})", u
        if official and nav and t["k"] not in DEPT_KINDS:
            return True, f"WAF/封锁({why};官方页面链接)", u
        return False, f"WAF/封锁({why})", u
    rec = rec_of(t, u)
    v, why2 = V.judge(rec, res)
    if v == "ok_neutral" and "省级平台子站" in (why2 or ""):
        # 省级平台子站豁免只适用于五系统（省级官网的市级频道）；
        # 市级部门/门户/群团被省站顶替一律驳回（本轮清理的错配主要形态）。
        # 县级机构再加一条：上级平台子站的标题只会带上级地名（实测楚雄市
        # 检察院被填成州院站内频道 chuxiong.jcy.gov.cn/wzkx/，标题是州院名），
        # 不能当县级机构官网。
        if V.role_of(rec) not in ("法院", "检察", "人大", "政协", "监委", "纪委"):
            return False, f"省级平台顶替({why2})", u
        deep_full = V.rec_places(rec_of(t, ""))[2]
        if ((t.get("node") or {}).get("l") or "") == "县" and \
                deep_full not in (res["title"] or ""):
            return False, f"上级平台子站顶替县级机构({why2})", u
        # 省站根址也不是市级机构的官网（实测 塔城地区纪委监委 ← xjjw.gov.cn/web/，
        # 标题是自治区纪委监委、路径没有任何地区频道痕迹）
        lv2 = (t.get("node") or {}).get("l") or ""
        short_place = V.ADMIN_SUFFIX.sub("", deep_full)
        if lv2 and lv2 != "省" and short_place \
                and short_place not in (res["title"] or "") \
                and short_place not in u:
            return False, f"省站根址顶替({why2})", u
    if v in ("ok", "ok_neutral"):
        title = res["title"] or ""
        deep_full = V.rec_places(rec_of(t, ""))[2]
        # 跨市同名区县：标题必须带父市/省名（否则分不清是哪个市的同名区）。
        # 官方页面导航来的链接例外——来源页本身就在本市体系内
        # （南通市人大官网列出的「通州区人大」，标题只有「通州区人大常委会」）。
        # 政府门户没有这条例外：向阳区/郊区/城区这类通用区名，来源页在市内
        # 也挡不住「市政府门户/别区站点」，必须有标题证据。
        if deep_full in DUP_COUNTY and (not nav or t["k"] == "人民政府"):
            hints = [h for h in (nearest_parent_place(t, deep_full),
                                 t["prov"]) if h]
            body = res.get("snippet") or ""
            if hints and not any(h in title for h in hints) \
                    and not any(h in body for h in hints):
                return False, f"重名区县缺上级地名({deep_full}|{title[:24]})", u
        # 政府门户：标题必须写本级名（「城区」「郊区」这类通用区名，
        # 只靠上级地名判会放过市政府门户——实测汕尾市城区被填成汕尾市政府）
        if t["k"] == "人民政府" and t["name"] not in title:
            return False, f"标题不含本级名({title[:26]})", u
        if (t["k"] == "人民政府" and GOV_NEG_TITLE.search(title)
                and "人民政府" not in title):
            return False, f"非政府门户(政法/宣传站|{title[:22]})", u
        # 五系统节点被政府门户/行署顶替（实测 塔城地区纪委监委 ←
        # www.xjtc.gov.cn「塔城地区行政公署」：「行署」不在 p240 的角色词表里，
        # 角色冲突判不出，这里按标题里的政府品牌词补一刀）
        if t["k"] in FIVE_KINDS and GOV_TITLE.search(title) \
                and V.role_of(rec_of(t, "")) != "政府":
            return False, f"标题为政府站({title[:22]})", u
        # 五系统节点的标题必须写本系统词：标题里连「政协/人大/法院/检察/纪委」
        # 都没有的站不是这个系统的机关（实测 赤峰市政协 ← 赤峰市文化和旅游局
        # wlj.chifeng.gov.cn，p240 角色互斥判不出「文旅局」这种部门站）
        if t["k"] in FIVE_KINDS:
            fam = fam2(t["name"])
            words = FIVE_WORD.get(fam)
            if words and not any(w in title for w in words):
                return False, f"标题不含本系统词({fam}|{title[:24]})", u
        # 群团子站顶替机构节点（共青团/工会/妇联/统战…）；节点自己就是该群团时放过
        fam_term = family_conflict(title, t["name"])
        if fam_term:
            return False, f"标题为群团站({fam_term}|{title[:22]})", u
        # 五系统/门户标题是机构名，长句必是文章页（实测 金口河区人大 ←
        # 省人大站 /view/A745D6C5DD9EE075.html「金口河区人大常委会调研组开展工作调研」）
        if t["k"] not in DEPT_KINDS + INST_ALWAYS and len(title) > 34:
            return False, f"标题过长(疑文章页|{title[:24]})", u
        # 部门/群团：标题必须写这个机构（p240 judge 对部门只判地区与
        # 角色互斥，本级政府门户/数据平台都能过，回填口径更严）
        if t["k"] in DEPT_KINDS + INST_ALWAYS:
            if len(title) > 40:
                # 文章/会议报道标题（「黑龙江省林业和草原局|守正创新…召开」）
                return False, f"标题过长(疑文章页|{title[:24]})", u
            if not org_hit(title, t["name"]):
                return False, f"标题不含机构词({title[:26]})", u
            if PORTAL_TITLE.search(title):
                return False, f"门户品牌标题({title[:26]})", u
            child = child_place_hit(title, deep_full)
            if child:
                return False, f"标题为下级机构({child})", u
            if t["k"] in DEPT_KINDS:
                other = other_org_hit(title, t["name"])
                if other:
                    return False, f"标题为别的部门({other})", u
        return True, f"{v}|{why2 or 'title=' + title[:36]}", u
    return False, f"{v}|{why2}", u


# ── 锚文本匹配（官方导航渠道）────────────────────────────────
_LEAD_PLACE = re.compile(
    r"^(.{2,16}?(?:特别行政区|自治区|自治州|自治县|地区|新区|省|市|县|区|旗|盟))")


def org_base(name):
    """节点名去掉开头的层级占位字：「县人民法院」→「人民法院」。"""
    x = name or ""
    while True:
        m = re.match(r"^(省|市|县|区|州|盟|旗|地区|自治区)", x)
        if not m or len(x) - m.end() < 2:
            return x
        x = x[m.end():]


def name_terms(name):
    """节点名 + 去层级前缀后的机构词 + 该机构词的群团别名（妇联≈妇女联合会）。"""
    base = org_base(name)
    out = {name or "", base}
    for k, aliases in ORG_ALIAS.items():
        if k in (name or "") or k in base:
            out.update(aliases)
    return out


def family_conflict(title, name):
    """标题是别的群团站时返回命中的群团词，否则返回空串。"""
    if not title:
        return ""
    m = FAMILY_TITLE.search(title)
    if not m:
        return ""
    term = m.group(1)
    terms = name_terms(name)
    if term in terms or any(term in x for x in terms if len(x) >= 2):
        return ""
    # 节点名里另有别的群团词（「工商联」节点）与标题命中的词不同才算冲突
    return term


def anchor_ok(text, t, deep_full):
    tx = F.norm(text)
    if not tx or len(tx) > 30:
        return False
    if re.search(r"(国家|中国|中央|中华人民共和国|全国)", tx):
        return False
    # 门户首页新闻列表里的标题也常含机构名（「市统计局召开…会议」），
    # 靠机构词匹配会采到文章页——文章动词出现即不是导航项
    if F.ARTICLE_TITLE.search(tx):
        return False
    ob = org_base(t["name"])
    if len(ob) < 2 or ob not in tx:
        return False
    m = _LEAD_PLACE.match(tx)
    if m and m.group(1) != tx:
        place = m.group(1)
        if not (deep_full and (deep_full in place or place.endswith(deep_full))):
            return False
    return True


def anchor_strict(text, t, deep_full):
    """页面取不到时的锚文本严格校验：锚文本≈机构名本身，不是文章标题。

    （实测：阳泉城区被填成「阳泉『开局起步十五五』系列主题新闻发布会」
    的新闻锚文本——长标题 + 引号 + 文章动词一律不是机构入口。
    另外必须带本级地名：只有「统计局」三个字不足以定位到某个市的统计局。）
    """
    tx = F.norm(text)
    if not tx or len(tx) > 24:
        return False
    if re.search(r"[“”‘’《》]", tx):
        return False
    if F.ARTICLE_TITLE.search(tx):
        return False
    # 地名限定：锚文本要写本级地名（deep_full）或省名
    if not (deep_full and deep_full in tx) and not (t["prov"] and t["prov"] in tx):
        return False
    ob = org_base(t["name"])
    cands = {t["name"], ob}
    if deep_full:
        cands |= {deep_full + t["name"], deep_full + ob}
    if t["prov"]:
        cands |= {t["prov"] + t["name"], t["prov"] + ob}
    if tx in cands:
        return True
    # 「XX市统计局」这类带地名前缀的写法
    return tx.endswith(t["name"]) and len(tx) <= len(t["name"]) + 8


# ── 渠道 A：官方页面导航 ────────────────────────────────────
FAM_KW = ("中级人民法院", "人民法院", "人民检察院", "人大常委会",
          "人民代表大会", "政协", "纪委监委", "监委", "纪委", "总工会",
          "归国华侨联合会", "侨联", "台湾同胞联谊会", "台联",
          "计划生育协会", "法学会", "妇女联合会", "科学技术协会", "共青团")


def fam_of(name):
    for kw in FAM_KW:
        if kw in (name or ""):
            return kw
    return ""


def clear_name(name):
    """群团节点名 → 检索/匹配核心词（省侨联→侨联，区总工会→总工会）。"""
    return org_base(name)


def build_fam_index(tree):
    """(省, 族核心词) → [URL]，用于找上级同族组织官网（省总工会→区总工会）。"""
    idx = defaultdict(list)

    def walk(n, prov):
        name = (n.get("n") or "").strip()
        myprov = prov
        if n.get("l") == "省" and name:
            p = V.place_of(name)
            if p and V.is_real_prov(p[0]):
                myprov = p[0]
        u = (n.get("u") or "").strip()
        if u.startswith("http") and name:
            fam = fam_of(name)
            if fam and myprov:
                idx[(myprov, fam)].append(u)
        for c in n.get("ks") or []:
            walk(c, myprov)

    for g in tree["ks"]:
        walk(g, "")
    return idx


NAV_HINT = re.compile(
    r"(机构设置|机构概况|组织机构|部门|网站地图|站点导航|导航|直属单位|"
    r"下属单位|县区|市县|区县|地方|单位|友情链接)")


def refs_for(t, fam_index):
    """权威参考页（按优先级）：同级门户 → 省级门户 → 上级同系统/同族官网。"""
    refs = []

    def add(u, kind):
        u = (u or "").strip()
        if u.startswith("http") and u not in [x[0] for x in refs]:
            refs.append((u, kind))

    # 1) 同级政府门户（最近祖先 k=人民政府）
    for a in reversed(t["anc"]):
        if a.get("k") == "人民政府" and (a.get("u") or "").strip():
            add(a["u"], "gov_portal")
            break
    # 2) 省级门户
    for a in reversed(t["anc"]):
        if a.get("l") == "省" and a.get("k") == "人民政府":
            add(a.get("u"), "prov_portal")
            break
    # 3) 条树叶：最近有 URL 的上级同系统官网
    if t["tree"] == "tiao":
        for a in reversed(t["anc"]):
            u = (a.get("u") or "").strip()
            if u.startswith("http"):
                add(u, "upper_sys")
                break
    # 4) 同省同族上级组织官网
    fam = fam_of(t["name"])
    if fam and t["prov"]:
        for u in fam_index.get((t["prov"], fam), [])[:2]:
            add(u, "upper_fam")
    return refs[:4]


def page_links(ref_u, ref_kind):
    """参考页及其导航子页上的全部链接 [(text, url, page_url)]。"""
    h = F.fetch_cached(ref_u)
    if not h:
        return []
    pages = [(ref_u, h)]
    navs = []
    host = urlparse(ref_u).netloc
    for txt, link in F.extract_links(h, ref_u):
        if urlparse(link).netloc != host or link == ref_u:
            continue
        if F.NEWS_PATH.search(link) or F.NEWS_QUERY.search(link):
            continue
        if NAV_HINT.search(txt) or NAV_HINT.search(link):
            if link not in navs:
                navs.append(link)
        if len(navs) >= 3:
            break
    for nu in navs:
        nh = F.fetch_cached(nu)
        if nh and len(nh) > 300:
            pages.append((nu, nh))
    out = []
    for pu, ph in pages:
        for txt, link in F.extract_links(ph, pu):
            out.append((txt, link, pu))
    return out


# ── 渠道 B：百度 SERP ──────────────────────────────────────
SERP_BAD = F.BAD_HOST + ("chinacourt.org", "npc.gov.cn", "cppcc.gov.cn",
                         "ccdi.gov.cn", "spp.gov.cn", "court.gov.cn",
                         "12309.gov.cn", "12388.gov.cn")


def serp_cands(q):
    h = F.serp(q)
    if not h:
        return None
    urls = []
    for u in re.findall(r'mu="(https?://[^"]+)"', h):
        u = u.replace("&amp;", "&")
        dom = urlparse(u).netloc.lower()
        if any(b in dom for b in SERP_BAD):
            continue
        if u not in urls:
            urls.append(u)
        if len(urls) >= 8:
            break
    return urls


def probe_generic(t, fam_index):
    """单目标探测：官方导航 → SERP。返回 (url, level, note) 或 (None, '', why)。"""
    deep_full, deep_base = V.rec_places(rec_of(t, ""))[2:4]
    fam = fam_of(t["name"])
    # A. 官方页面真实链接
    for ref_u, kind in refs_for(t, fam_index):
        for txt, link, page_u in page_links(ref_u, kind):
            if not anchor_ok(txt, t, deep_full):
                continue
            ok, note, fu = verify(t, link, anchor=F.norm(txt), official=True,
                                  nav=True)
            if not ok:
                continue
            level = "L1" if kind in ("upper_sys", "upper_fam") else "L2"
            return (fu, level,
                    f"来源:官方页面导航[{kind}]({page_u})+复核({note})")
    # B. SERP 兜底
    ob = org_base(t["name"])
    nm = t["name"]

    def prefixed(x):
        # 节点名已含本级地名（「铁西区」「松原市统计局」）就不再拼前缀，
        # 否则会出「铁西区铁西区」这种查询
        if deep_full and deep_full not in x and (deep_base or "") not in x:
            return f"{deep_full}{x}"
        return x

    # org_base 已剥掉「省/市/县」层级占位前缀（省侨联→侨联），只用它拼查询，
    # 再拼一次原名会出「山西省省侨联」
    qs = []
    for q in (prefixed(ob), f"{prefixed(ob)} 官网"):
        if q and q not in qs:
            qs.append(q)
    serp_fail = True
    for q in qs:
        cands = serp_cands(q)
        if cands is None:
            continue
        serp_fail = False
        for u in cands:
            tries = [u] if root_of(u) == u else [root_of(u), u]
            for cu in tries:
                ok, note, fu = verify(t, cu, official=False,
                                      allow_orgcn=bool(fam))
                if ok:
                    more = "" if fu == u else "(根址优先)"
                    return (fu, "L3",
                            f"来源:SERP线索+title严格验证(查询「{q}」| {note}{more})")
    if serp_fail:
        return (None, "", "SERP 不可用")
    return (None, "", "渠道穷尽未命中")


# ── Phase A：五系统（复用 p223 四档机器）──────────────────────
def run_five(tree, reg, targets, state):
    five_t = [t for t in targets
              if t["tree"] == "blk" and t["k"] == "并列机关"]
    if not five_t:
        return 0
    blk, tasks = F.collect(tree)
    ids = {id(t["node"]) for t in five_t}
    tasks = [x for x in tasks if id(x["org"]) in ids]
    if LIMIT:
        tasks = tasks[:LIMIT]
    print(f"\n══ Phase A 五系统（p223 渠道）: {len(tasks)} 任务 ══")
    prov_map = {p["n"]: p for p in blk["ks"]}
    F.ALL_PROV_BASES.update(F.prov_base(x) for x in prov_map if F.prov_base(x))
    name_prov = defaultdict(set)
    for x in tasks:
        name_prov[x["county"].get("n", "")].add(x["prov"])
    dup_names = {n for n, ps in name_prov.items() if len(ps) > 1}
    all_city_bases = set()
    city_bases = defaultdict(set)
    for x in tasks:
        p = x["parent"]
        if p.get("l") in ("市", "地级区", "省"):
            all_city_bases.add(F.geo_base(p.get("n", "")))
        if p.get("l") in ("市", "地级区"):
            city_bases[x["prov"]].add(F.geo_base(p.get("n", "")))
    for x in tasks:
        cb = F.geo_base(x["parent"].get("n", ""))
        x["dup"] = x["county"].get("n", "") in dup_names
        x["siblings"] = sorted(b for b in city_bases.get(x["prov"], set())
                               if b and b != cb)
    old_s = {id(x["org"]): (x["org"].get("s") or "") for x in tasks}
    # 回滚快照：p223 渠道填的 URL 事后还要过 p240 复核，
    # 不过的连 registry 一起还原（之前多为 p240 置的 cleared 档）
    pre_reg = {}
    for x in tasks:
        key = F.county_key(x["prov"], x["county"], x["org_name"], dup_names)
        pre_reg[id(x["org"])] = (key, json.loads(json.dumps(reg.get(key))))
    captured = {}
    orig_apply = F.apply_fill

    def _rec_apply(reg_, task, u, src, level, dup_names_):
        got = orig_apply(reg_, task, u, src, level, dup_names_)
        if got:
            captured[id(task["org"])] = (u, src or "")
        return got

    st5 = state.setdefault("five", {})
    n0 = sum(1 for x in tasks if x["filled"])
    F.apply_fill = _rec_apply
    try:
        F.run_s1(tasks, reg, dup_names, st5, prov_map)
        checkpoint(tree, reg, state)
        F.run_s2(tasks, reg, dup_names, st5, all_city_bases)
        checkpoint(tree, reg, state)
        F.run_s4(tasks, reg, dup_names, st5)
    finally:
        F.apply_fill = orig_apply
    # ── 统一 p240 复核：p223 渠道给的 URL 也必须过身份判定 ──
    idx = index_nodes(tree)
    keep, rolled = 0, []
    for x in tasks:
        if not x["filled"]:
            continue
        o = x["org"]
        cu, csrc = captured.get(id(o), ("", ""))
        u = (o.get("u") or "").strip() or cu
        meta = idx.get(id(o)) or {}
        tgt = {"node": o, "name": (o.get("n") or x["org_name"]),
               "k": o.get("k") or "并列机关", "c": o.get("c") or "",
               "path": meta.get("path") or [], "lv": meta.get("lv") or [],
               "prov": meta.get("prov") or x["prov"], "tree": "blk",
               "anc": meta.get("anc") or []}
        # SERP 来源没有官方页面背书：页面取不到就不收
        ok, note, fu = verify(tgt, u, official=True, allow_orgcn=True,
                              nav=("SERP" not in csrc))
        if ok:
            if not DRY:
                o["u"] = fu
                o["s"] = (old_s[id(o)] + " | p241 五系统回填: "
                          + (o.get("s") or "")).strip(" |")
            else:
                print(f"  ✓ {tgt['name']} @ {'/'.join(tgt['path'][-2:])} "
                      f"-> {fu[:70]}")
            keep += 1
            continue
        rolled.append((tgt, u, note))
        x["filled"] = False
        if not DRY:
            o["u"] = ""
            o["s"] = old_s[id(o)]
            key, prev = pre_reg.get(id(o), (None, None))
            if key:
                if prev is None:
                    reg.pop(key, None)
                else:
                    reg[key] = prev
    for tgt, u, note in rolled:
        print(f"  ✗ 复核不过 {tgt['name']} @ {'/'.join(tgt['path'][-2:])} "
              f"-> {u[:64]}  ({note[:40]})")
    print(f"Phase A 复核: 保留 {keep} / 回滚 {len(rolled)} / {len(tasks)}")
    return keep - n0


# ── Phase B：通用（门户/上级导航 + SERP）────────────────────
def run_generic(tree, reg, targets, state):
    # 块树并列机关默认交给 Phase A（p223 四档）；P241_GENERIC_FIVE=1 时
    # 也让通用段跑一遍——p223 的 county task 只覆盖县级节点，市级/省级
    # 并列机关清空后需要通用段（上级导航 + SERP）兜底
    skip_five = not os.environ.get("P241_GENERIC_FIVE")
    todo = [t for t in targets
            if not (skip_five and t["tree"] == "blk" and t["k"] == "并列机关")]
    if LIMIT:
        todo = todo[:LIMIT]
    print(f"\n══ Phase B 通用: {len(todo)} 目标 ══")
    fam_index = build_fam_index(tree)
    st = state.setdefault("generic", {})

    def work(t):
        k = tkey(t)
        prev = st.get(k) or {}
        if prev.get("res") == "miss":
            return t, None, "", "上轮已穷尽(miss)"
        try:
            return (t,) + probe_generic(t, fam_index)
        except Exception as e:
            return t, None, "", f"异常:{type(e).__name__}"

    filled = 0
    done = 0
    with ThreadPoolExecutor(WORKERS) as ex:
        for t, u, level, note in ex.map(work, todo):
            done += 1
            k = tkey(t)
            if u and not DRY:
                t["node"]["u"] = F.clean_fill_url(u)
                t["node"]["s"] = ((t["node"].get("s") or "")
                                  + f" | p241 回填({level}): {note}").strip(" |")
                write_registry(reg, t, t["node"]["u"], level, note)
                filled += 1
                st[k] = {"res": "hit", "u": u, "note": note}
                print(f"  ✓ {t['name']} @ {'/'.join(t['path'][-2:])} -> {u[:70]}")
            elif u and DRY:
                filled += 1
                print(f"  [DRY] {t['name']} @ {'/'.join(t['path'][-2:])} "
                      f"-> {u[:70]}  ({note[:60]})")
            else:
                st[k] = {"res": "miss", "why": note}
                if DRY:
                    print(f"  [DRY-] {t['name']} @ {'/'.join(t['path'][-2:])} ({note[:40]})")
            if done % 25 == 0:
                checkpoint(tree, reg, state)
                print(f"  … 进度 {done}/{len(todo)}，已落盘", flush=True)
    print(f"Phase B 填充: {filled} / {len(todo)}")
    return filled


# ── Phase C：条/块互为镜像同步（只填空，双向）────────────────
def run_sync(tree, reg, targets, state):
    index = {"blk": defaultdict(set), "tiao": defaultdict(set)}

    def deep_of(rec):
        p = V.rec_places(rec)
        return p[2], p[3]

    def walk(n, path, lv, kind):
        name = (n.get("n") or "").strip()
        u = (n.get("u") or "").strip()
        if u.startswith("http") and name:
            rec = {"name": name, "k": n.get("k") or "", "c": n.get("c") or "",
                   "path": path, "lv": lv, "prov": "", "tree": kind}
            df, db = deep_of(rec)
            fam = fam_of(name)
            if df and fam:
                index[kind][(df, fam)].add(u)
        for c in n.get("ks") or []:
            walk(c, path + [name], lv + [n.get("l") or ""], kind)

    for g in tree["ks"]:
        kind = ("tiao" if (g.get("l") == "根"
                           or (g.get("n") or "").startswith("条")) else "blk")
        walk(g, [], [], kind)
    todo = [t for t in targets if not (t["node"].get("u") or "").strip()]
    print(f"\n══ Phase C 条块同步: {len(todo)} 目标 ══")
    filled = 0
    for t in todo:
        df = V.rec_places(rec_of(t, ""))[2]
        fam = fam_of(t["name"])
        other = "blk" if t["tree"] == "tiao" else "tiao"
        us = index[other].get((df, fam)) or set()
        if len(us) != 1:
            continue
        u = next(iter(us))
        ok, note, fu = verify(t, u, official=True, nav=True)
        if not ok:
            continue
        u = fu
        if not DRY:
            t["node"]["u"] = u
            t["node"]["s"] = ((t["node"].get("s") or "")
                              + f" | p241 条块同步({other}树同机构)+复核({note})"
                              ).strip(" |")
            write_registry(reg, t, u, "L2", f"条块同步 {note}")
        filled += 1
        print(f"  ✓ 同步 {t['name']} ({t['tree']}←{other}) -> {u[:70]}")
    print(f"Phase C 同步: {filled}")
    return filled


# ── registry 写入（五系统以外的类别）────────────────────────
def write_registry(reg, t, u, level, note):
    if DRY:
        return
    nm = t["name"]
    c = t["c"] or t["k"] or "其他"
    pb = sc_base(t["prov"]) if t["prov"] else ""
    full = nm
    if pb and pb not in nm and t["prov"] not in nm:
        full = f"{t['prov']}{nm}"
    key = f"{c}|{full}"
    # 复用历史 cleared 键（避免同一机构多键）：先按全名，再按节点裸名
    for name_try in (full, nm):
        cand = [k for k, v in reg.items()
                if (v.get("n") or k.split("|")[-1]) == name_try
                and not (v.get("u") or "").strip()]
        if cand:
            key = sorted(cand, key=len)[0]
            break
    upsert_registry(reg, key, u, name=full, source_level=level,
                    source=f"p241 {note}", verified_at=TODAY,
                    status="ok", locations=["块" if t["tree"] == "blk" else "条"])


# ── 主流程 ─────────────────────────────────────────────────
def main():
    tree = json.load(open(TREE_F, encoding="utf-8"))
    reg = json.load(open(REG_F, encoding="utf-8"))
    state = {}
    if os.path.exists(STATE_F):
        try:
            state = json.load(open(STATE_F, encoding="utf-8"))
        except Exception:
            state = {}

    V.collect_all_places(tree)
    build_dup_counties()
    build_url_owners(tree)
    recs = V.collect_records(tree)
    V.build_prov_hosts(recs)
    V.build_city_hosts(recs)

    targets = collect_targets(tree)
    print(f"p241 目标（u 为空 + p240 清除痕迹）: {len(targets)}")
    by = defaultdict(int)
    for t in targets:
        by[(t["k"] or "?", t["tree"])] += 1
    for k, n in sorted(by.items(), key=lambda x: -x[1]):
        print(f"   {k[0]:<10} {k[1]:<5} {n}")

    filled = 0
    # 写前备份（拷贝的是尚未落盘的旧 tree/registry）
    if not DRY:
        d = os.path.join(ROOT, "backups", TODAY)
        os.makedirs(d, exist_ok=True)
        ts = datetime.datetime.now().strftime("%H%M%S")
        shutil.copy2(TREE_F, os.path.join(d, f"tree_before_p241_{ts}.json"))
        shutil.copy2(REG_F, os.path.join(d, f"registry_before_p241_{ts}.json"))
    # 顺序：通用段先跑（补出的县级门户供五系统 S2 当参考页），
    # 再五系统（p223 四档），最后条树同步
    if "generic" in ONLY:
        filled += run_generic(tree, reg, targets, state)
    if "five" in ONLY:
        filled += run_five(tree, reg, targets, state)
    if "sync" in ONLY:
        filled += run_sync(tree, reg, targets, state)

    if not DRY:
        _atomic(tree, TREE_F)
        _atomic(reg, REG_F)
        _atomic(state, STATE_F)
        report = {"generated": datetime.datetime.now().isoformat(timespec="seconds"),
                  "filled": filled,
                  "targets": [{"key": tkey(t), "name": t["name"], "k": t["k"],
                               "path": t["path"], "tree": t["tree"],
                               "u": (t["node"].get("u") or ""),
                               "s": (t["node"].get("s") or "")[-160:]}
                              for t in targets]}
        _atomic(report, REPORT_F)
    print(f"\np241 完成: 填充 {filled}{'（DRY 未写库）' if DRY else ''}")


if __name__ == "__main__":
    main()
