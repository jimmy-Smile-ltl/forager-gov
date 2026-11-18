#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""p240 全量 URL 正确性核查（2026-11-18 用户指令）。

用户要求：检查全部 URL 的正确性——「主要是不要有错误的 url」。遇到防火墙 /
IP 封锁的默认正确，并尽量用代理请求核查。

做法：
  1. 收集 tree.json（块树 + 条树）全部有 URL 的节点，外加 site_registry.json
     中「不在树里」的 URL（registry-only 156 条）；
  2. 每个唯一 URL 抓一次（线程内独立 curl_cffi Session，impersonate=chrome124）：
     先直连；直连异常 / 403·412·429·5xx / 挑战页时再走代理（TUNNEL_PROXY）；
  3. 分档：
       ok               200 + 标题与机构身份一致
       ok_neutral       标题为空/中性（首页/网站首页）——无反向证据，默认正确
       waf              403/412/429/5xx、验证码/挑战页、超时、连接重置
                        ——按用户口径「防火墙 / IP 封锁默认正确」
       dead             DNS 解析失败 / 连接拒绝 / 404·410 两次确认 / 停用页
                        ——不清树（沿项目死链纪律，只记 registry status）
       mismatch         200 + 标题明确是**别的机构**（机构类型冲突）或
                        **别的地区**（标题只含另一个已知行政区全名）
                        ——这是「错误的 url」，进入清除队列
       suspect          弱信号（标题不含期望地名 / 文章详情页路径）
                        ——只报告，人工复核后再决定
  4. 输出 data/url_verify_report.json + data/p240_results.jsonl（断点续跑），
     控制台打印分档统计与 mismatch/suspect 样例。

用法：
  cd data && uv run python p240_full_url_verify.py --limit 200     # 抽样
  cd data && uv run python p240_full_url_verify.py                 # 全量（可断点续跑）
  cd data && uv run python p240_full_url_verify.py --report        # 只出报告
  cd data && uv run python p240_full_url_verify.py --apply         # 清除 mismatch（写前备份）
环境变量：
  P240_CONC=20        并发
  P240_TIMEOUT=12     单次超时秒
  P240_NO_PROXY=1     禁用代理
"""
import argparse
import datetime
import json
import os
import re
import shutil
import socket
import sys
import threading
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BASE_DIR)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "util"))

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(ROOT, ".env"))
except Exception:
    pass

TREE_F = os.path.join(BASE_DIR, "tree.json")
REG_F = os.path.join(BASE_DIR, "site_registry.json")
OUT_JSONL = os.path.join(BASE_DIR, "p240_results.jsonl")
REPORT_F = os.path.join(BASE_DIR, "url_verify_report.json")
TODAY = datetime.date.today().isoformat()

TUNNEL = os.environ.get("TUNNEL_PROXY", "").strip()
PROXIES = None if os.environ.get("P240_NO_PROXY") == "1" else (
    {"http": TUNNEL, "https": TUNNEL} if TUNNEL else None)
CONC = int(os.environ.get("P240_CONC", "20"))
TIMEOUT = int(os.environ.get("P240_TIMEOUT", "12"))

# ── 抓取 ─────────────────────────────────────────────────────
_tl = threading.local()
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36")


def _session():
    if not hasattr(_tl, "s"):
        from curl_cffi import requests as cr
        _tl.s = cr.Session(impersonate="chrome124")
    return _tl.s


def _decode(resp):
    raw = resp.content or b""
    enc = None
    try:
        enc = resp.encoding
    except Exception:
        pass
    head = raw[:4000].decode("ascii", "ignore")
    m = re.search(r'charset=["\']?([\w-]+)', head, re.I)
    if m:
        enc = m.group(1)
    for e in (enc, "utf-8", "gb18030"):
        if not e:
            continue
        try:
            return raw.decode(e)
        except Exception:
            continue
    return raw.decode("utf-8", "ignore")


def norm(t):
    return re.sub(r"[\s　\xa0]+", "", re.sub(r"<[^>]+>", "", t or ""))


def _title(html):
    for pat in (r"<title[^>]*>(.*?)</title>",
                r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)',
                r'<meta[^>]+name=["\'](?:ArticleTitle|title)["\'][^>]+content=["\']([^"\']+)'):
        m = re.search(pat, html or "", re.S | re.I)
        if m:
            t = norm(m.group(1))
            try:
                import html as _h
                t = _h.unescape(t)
            except Exception:
                pass
            if t:
                return t
    return ""


_host_locks = {}
_host_locks_guard = threading.Lock()


def _host_lock(host):
    with _host_locks_guard:
        lk = _host_locks.get(host)
        if lk is None:
            lk = _host_locks[host] = threading.Lock()
        return lk


_dns_cache = {}
_dns_guard = threading.Lock()


def dns_check(host, timeout=4.0):
    """带超时的 DNS 预检。

    getaddrinfo 卡住时 libcurl 的 timeout 管不住（它在独立的 resolver 线程里），
    死域名多了会把工作线程全耗光——上一轮 2.3 万 URL 抓到最后就是被这个拖停的。
    解析不出来的站点直接按「封锁默认正确」交回 waf，绝不拖住整个进程。
    """
    h = (host or "").split(":")[0].strip().lower()
    if not h:
        return False, "空 host"
    with _dns_guard:
        c = _dns_cache.get(h)
        if c is not None:
            return c
    out = {}

    def run():
        try:
            socket.getaddrinfo(h, None)
            out["ok"] = True
        except Exception as e:
            out["ok"] = False
            out["err"] = f"DNS 解析失败: {type(e).__name__}: {e}"[:120]

    t = threading.Thread(target=run, daemon=True)
    t.start()
    t.join(timeout)
    if t.is_alive():
        res = (False, "DNS 解析超时")
    else:
        res = (out.get("ok", False), out.get("err", ""))
    with _dns_guard:
        _dns_cache[h] = res
    return res


WAF_CODES = {401, 403, 405, 406, 412, 418, 429, 451, 500, 502, 503, 504,
             521, 522, 523, 525, 526}
DEAD_CODES = {404, 410, 400}


def fetch_one(u):
    """直连优先，失败/被封再走代理。返回结果 dict。"""
    res = {"u": u, "code": 0, "via": "", "final": "", "title": "",
           "size": 0, "err": "", "snippet": ""}
    host = urlparse(u).netloc.lower()
    ok, derr = dns_check(host)
    if not ok:
        res["err"] = derr or "DNS 解析失败"
        return res
    with _host_lock(host):
        attempts = [("direct", None)]
        if PROXIES:
            attempts.append(("proxy", PROXIES))
        for via, px in attempts:
            kw = {"proxies": px} if px else {}
            try:
                r = _session().get(u, timeout=TIMEOUT, verify=False,
                                   allow_redirects=True, **kw)
                body = r.content or b""
                res.update(code=r.status_code, via=via,
                           final=str(getattr(r, "url", "") or u), size=len(body),
                           err="")
                if r.status_code == 200 and len(body) > 200:
                    html = _decode(r)
                    res["title"] = _title(html)
                    txt = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html,
                                 flags=re.S | re.I)
                    res["snippet"] = norm(txt)[:1500]
                    return res
                # 拿到响应但不可用 → 判断是否值得换代理
                if via == "direct" and (r.status_code in WAF_CODES
                                        or (r.status_code in DEAD_CODES
                                            and len(body) < 3000)):
                    continue
                return res
            except Exception as e:
                msg = f"{type(e).__name__}: {str(e)[:120]}"
                res["err"] = msg
                res["via"] = ""
                continue
        return res


WAF_MARKERS = ("请输入验证码", "验证码", "请稍候", "正在验证", "安全验证",
               "Just a moment", "Attention Required", "Access denied",
               "拒绝访问", "访问受限", "访问被限制", "IP访问受限", "频繁访问",
               "安全狗", "云锁", "创宇盾", "网站防火墙", "瑞数", "环境异常",
               "challenge-platform", "cf-chl", "captcha", "滑动验证",
               "该页面需要验证", "403 Forbidden")
DEAD_MARKERS = ("404 Not Found", "页面不存在", "页面未找到", "您访问的页面不存在",
                "您访问的页面已删除", "网站已关闭", "站点已关闭", "网站已停用",
                "该域名已过期", "域名已过期", "无法找到该页", "Not Found",
                "该页面已被删除", "信息已删除")


def base_status(res):
    """网络层分档：ok/waf/dead/suspect。"""
    code, title, size = res["code"], res["title"], res["size"]
    if not res["via"]:
        err = (res.get("err") or "").lower()
        if ("resolve" in err or "nodename" in err or "name or service" in err
                or "could not resolve" in err):
            return "dead", "DNS 解析失败"
        if "refused" in err or "connection refused" in err:
            return "dead", "连接拒绝"
        return "waf", f"请求失败({res.get('err', '')[:60]})"
    if code in WAF_CODES or code >= 500:
        return "waf", f"HTTP {code}"
    if code in DEAD_CODES:
        return "dead", f"HTTP {code}"
    if code >= 400:
        # 代理出口异常码（441/446/455 等）与其它 4xx：按「封锁默认正确」处理
        return "waf", f"HTTP {code}"
    if size < 200:
        return "waf", "响应过短(挑战/空壳)"
    head = (title + res.get("snippet", "")[:800])
    if any(m in head for m in WAF_MARKERS):
        return "waf", "WAF/验证页特征"
    if any(m in (title + res.get("snippet", "")[:300]) for m in DEAD_MARKERS):
        return "dead", "停用/死链页特征"
    return "ok", ""


# ── 身份判定 ─────────────────────────────────────────────────
ADMIN_SUFFIX = re.compile(
    r"(特别行政区|自治区|自治州|自治县|自治旗|地区|林区|新区|区|县|市|省|盟|旗|堂区)$")
ADMIN_UNIT = re.compile(
    r"特别行政区|自治区|自治州|自治县|自治旗|地区|林区|新区|区|县|市|省|盟|旗|堂区")
# 名字本身以「市」开头的真行政区：青岛市的市南区/市北区，枣庄/内江/乐山/济南等的市中区。
# 其余「市XX局」「区XX委」「县人民法院」都是层级占位名，不作地名。
# （「城区」是真区名但也是通用词，不放入本表——条树「晋城城区法院」按 ALLOW_OK 处理。）
PREFIX_PLACES = {"市南区", "市北区", "市中区"}
# 条树叶子里常见的简称（「喀左县法院」）：按全称认，否则标题里的全称会被判成外地。
PLACE_ALIAS = {"喀左": "喀喇沁左翼蒙古族自治县"}
ETHNIC = ("维吾尔", "哈萨克", "柯尔克孜", "塔吉克", "乌孜别克", "塔塔尔", "俄罗斯",
          "鄂温克", "鄂伦春", "达斡尔", "锡伯", "朝鲜", "蒙古", "土家", "哈尼",
          "傈僳", "拉祜", "景颇", "布朗", "仡佬", "阿昌", "普米", "德昂", "独龙",
          "基诺", "门巴", "珞巴", "保安", "裕固", "撒拉", "东乡", "毛南", "仫佬",
          "布依", "纳西", "赫哲", "羌", "彝", "藏", "苗", "壮", "侗", "白", "傣",
          "佤", "回", "满", "黎", "瑶", "畲", "水", "怒", "京", "土", "高山")
ROLE_TAIL = re.compile(
    r"(高级人民法院|中级人民法院|人民法院|人民检察院|检察院|人民代表大会|"
    r"人大常委会|政协委员会|纪律检查委员会|监察委员会|纪委监委|纪委|监委|"
    r"管理委员会|管委会|人民政府|总工会|委员会|人大|政协|党委|政府|"
    r"法院)$")
ROLE_KW = {
    "人大": ("人民代表大会", "人大常委会", "人大"),
    "政协": ("政治协商会议", "政协"),
    "法院": ("人民法院", "法院"),
    "检察": ("人民检察院", "检察院"),
    "监委": ("纪律检查委员会", "纪委监委", "纪检监察", "监察委员会", "纪委", "监委"),
    "党委": ("党委", "中共"),
    "政府": ("人民政府", "政府"),
}
ROLE_CONFLICT = {
    frozenset(("人大", "政协")), frozenset(("人大", "法院")), frozenset(("人大", "检察")),
    frozenset(("人大", "监委")), frozenset(("政协", "法院")), frozenset(("政协", "检察")),
    frozenset(("政协", "监委")), frozenset(("法院", "检察")), frozenset(("法院", "监委")),
    frozenset(("检察", "监委")), frozenset(("政府", "人大")), frozenset(("政府", "政协")),
    frozenset(("政府", "法院")), frozenset(("政府", "检察")), frozenset(("政府", "监委")),
}
# 文章/详情页路径（强信号，不算频道页 /columns/<uuid>/index.html）
ART_HARD = re.compile(
    r"/art/\d{4}/\d{1,2}/\d{1,2}/|/t\d{8}_\d+|/(19|20)\d{6}/|/content_\d+|"
    r"/\d{8}\.s?html?|/doc/|/Item/|/Show/|/content-\d+|/contents/\d+/\d+|"
    r"/\d{5,}\.s?html?|/(19|20)\d{2}[-/]\d{1,2}[-/]\d{1,2}/", re.I)
ART_QUERY = re.compile(
    r"[?&](id|cid|aid|newsid|articleid|contentid|infoid|docid|pkid)=\d+", re.I)
# 中性标题（无身份信息）
NEUTRAL_TITLE = re.compile(
    r"^(首页|网站首页|主页|home|index|欢迎光临|欢迎访问|登录|网站已改版|"
    r"页面加载中|加载中|请稍候)[!！。.]?$", re.I)


GENERIC_PLACES = {"市辖区", "省辖区", "自治区", "特别行政区", "地区", "新区",
                  "城区", "郊区", "矿区", "开发区", "高新区", "示范区", "管理区",
                  "县级", "乡镇", "街道"}


MUNICIPALITIES = {"北京市", "天津市", "上海市", "重庆市"}
PLACE_PREFIX = re.compile(r"^(中国人民政治协商会议|政协|中共|中国共产党)")


def is_real_prov(name):
    return name in MUNICIPALITIES or name.endswith(("省", "自治区", "特别行政区"))


def place_of(name):
    """从节点名剥角色后缀后识别行政区：返回 (全名, 基底) 或 None。"""
    n = re.sub(r"[（(][^）)]*[）)]", "", name or "").strip()
    n = PLACE_PREFIX.sub("", n).strip()
    prev = None
    while prev != n:
        prev = n
        n = ROLE_TAIL.sub("", n).strip("·、 ")
    if not n or "/" in n or "、" in n or "," in n:
        return None
    # 简称还原（「喀左县」→ 喀喇沁左翼蒙古族自治县）：只有简称才在 ALL_PLACES 里查不到
    for short, fullname in PLACE_ALIAS.items():
        if n.startswith(short) and n[len(short):] in ("", "县", "市", "区", "旗",
                                                      "自治县", "自治州", "自治旗"):
            n = fullname
            break
    if not ADMIN_SUFFIX.search(n):
        # 无行政后缀但恰是已知地名基底（「沈阳检察院」→「沈阳」、「大连检察」）：
        # 条树里市级院常省略「市」，按同名地名认，否则会退化成「省院」误判上级顶替。
        if len(n) >= 2 and n not in GENERIC_PLACES and n in ALL_BASE_SET:
            return n, n
        return None
    # 层级占位名（「市城市管理委员会」「市级政府部门」「县人民法院」）不是地名：
    # 剥完角色后缀仍以行政后缀开头，说明首个后缀是「本市/本县」而非地名首字。
    # 例外是名字本身以「市」开头的真区名（青岛市南/市北、枣庄/内江/乐山/济南市中区）。
    if n[0] in "省市县区" and n not in PREFIX_PLACES:
        return None
    # 复合名（「徐州鼓楼区法院」剥完角色词 → 「徐州鼓楼区」）不是真地名：
    # 取最后一个行政成分（「鼓楼区」），否则会拼出不存在的地名而把本级判丢。
    units = [m.end() for m in ADMIN_UNIT.finditer(n)]
    if len(units) >= 2 and units[-2] < len(n) - 1 and n not in PREFIX_PLACES:
        n = n[units[-2]:]
    full = n
    if full in GENERIC_PLACES:
        return None
    base = ADMIN_SUFFIX.sub("", n)
    changed = True
    while changed:
        changed = False
        for e in ETHNIC:
            # 单字族名（黎/苗/白/彝…）只剥「X族」，否则会把「昌黎」剥成「昌」
            tails = (e + "族",) if len(e) == 1 else (e + "族", e)
            for tail in tails:
                if not base.endswith(tail) or len(base) <= len(tail) + 1:
                    continue
                rest = base[:-len(tail)]
                if len(rest) < 2:
                    continue     # 剥完只剩单字（内蒙古→内）：这个族名不是修饰语
                base = rest
                changed = True
                break
            if changed:
                break
    base = base.strip("·、 ")
    # 单字基底（赵县/涉县/吉县…）保留：匹配时用全名兜底
    if not base:
        return None
    # 只有一个行政后缀的复合名（「徐州鼓楼区」）：靠 base 是否已知来分辨——
    # base 未知（「徐州鼓楼」）说明前缀是外加的上级市名，取已知地名的尾巴；
    # base 已知（「沧源佤族自治县」→ 沧源、「冀州区」→ 冀州）是正名，不动。
    # 只在行政区全集建好后启用：建表过程中调用必须保持原样，否则「马鞍山市」
    # 会被后采到的「鞍山市」截走，污染整张地名表。
    if PLACES_READY and base not in ALL_BASE_SET and len(full) >= 4:
        for k in range(1, len(full) - 1):
            if full[k:] in ALL_PLACES and full[:k] in ALL_BASE_SET:
                return place_of(full[k:])
    return full, base


ALL_PLACES = {}      # 全名 -> 基底
PLACE_PROV = {}      # 全名 -> 省名
PROV_FULLS = set()   # 省级行政区全名（用于跨省同基底校对：河北区 vs 河北省）
CITY_OF_COUNTY = {}  # 县/区全名 -> 所属地级市全名（条树叶子只有县名，靠它认父）
ALL_BASE_SET = set()  # 全部基底（复合名尾段匹配用）
PLACES_READY = False  # 地名表建好后，place_of 才启用「已知地名最长后缀」回退


def collect_all_places(tree):
    """全树收集行政区全名（省/市/县/港澳台），用于「标题里出现了别的地区」。"""
    def walk(n, prov, city):
        name = (n.get("n") or "").strip()
        myprov, mycity = prov, city
        lv = n.get("l") or ""
        p = place_of(name)
        # 只登记「节点名本身就是这个行政区」的节点。条树叶子里剥角色词剥出来的
        # 复合名（「徐州鼓楼区法院」→「徐州鼓楼区」）不是行政区，它的基底
        # 「徐州鼓楼」会反过来把自己认证成「已知」，让复合名拆分失效。
        n0 = PLACE_PREFIX.sub("", re.sub(r"[（(][^）)]*[）)]", "", name)).strip()
        if p and p[0] == n0 and lv in ("省", "市", "县", "地级区", "港澳台", "特别行政区"):
            ALL_PLACES[p[0]] = p[1]
            ALL_BASE_SET.add(p[1])
            if myprov:
                PLACE_PROV.setdefault(p[0], myprov)
            if lv == "省" and is_real_prov(p[0]):
                myprov = p[0]
                mycity = ""
                PROV_FULLS.add(p[0])
            elif lv in ("市", "地级区"):
                if lv == "地级区":
                    # 直辖市的区：父级是省级（重庆市），仍要能反查所属市
                    CITY_OF_COUNTY.setdefault(p[0], set()).add(mycity or myprov)
                mycity = p[0]
            elif lv == "县" and (mycity or myprov):
                CITY_OF_COUNTY.setdefault(p[0], set()).add(mycity or myprov)
        for c in n.get("ks") or []:
            walk(c, myprov, mycity)
    for g in tree["ks"]:
        walk(g, "", "")
    global PLACES_READY
    PLACES_READY = True


def collect_records(tree):
    """返回 [{u, name, k, c, path, lv, prov, tree}]，path/lv 为祖先名与层级。"""
    recs = []

    def walk(n, path, lv, prov, tree_kind):
        name = (n.get("n") or "").strip()
        u = (n.get("u") or "").strip()
        myprov = prov
        if (n.get("l") == "省") and name:
            p = place_of(name)
            if p and is_real_prov(p[0]):
                myprov = p[0]
        if u.startswith("http"):
            recs.append({"u": u, "name": name, "k": n.get("k") or "",
                         "c": n.get("c") or "", "path": list(path),
                         "lv": list(lv), "prov": myprov, "tree": tree_kind})
        for c in n.get("ks") or []:
            walk(c, path + [name], lv + [n.get("l") or ""], myprov, tree_kind)

    for g in tree["ks"]:
        kind = "tiao" if (g.get("l") == "根" or (g.get("n") or "").startswith("条")) else "blk"
        walk(g, [], [], "", kind)
    return recs


def rec_places(rec):
    """返回 (期望全名, 期望基底, 最深层全名, 最深层基底, 最深层是否下级,
    备选全名, 备选基底)。

    最深层 = 路径里最后一个行政区（县/区 > 市 > 省）。用于防止「省级/市级站点
    冒充下级机构」——如重庆各区县财政局全指到 czj.cq.gov.cn（重庆市财政局），
    标题只含「重庆」不含区县名，旧规则会漏判。

    备选（alt）：区县节点下的「市级政府部门」组是市级部门的结构性重复
    （p199/p200 遗留），URL 是市级部门站，地区应按**市**判；但组内也可能挂着
    区县自己的站点（如东丽区 12388 举报站），因此把被降级的区县列为备选，
    标题命中它同样算对。
    """
    full, base, seq = set(), set(), []
    for nm in list(rec["path"]) + [rec["name"]]:
        p = place_of(nm)
        if p:
            full.add(p[0])
            base.add(p[1])
            seq.append(p)
    alt_full, alt_base = "", ""
    lvs = rec.get("lv") or []
    if (rec["path"] and rec["path"][-1] == "市级政府部门" and len(seq) >= 2
            and (lvs[-2] if len(lvs) >= 2 else "") in ("县", "地级区")):
        # 只降级「挂在区县节点下」的重复组（组的 l 是市/县，看它宿主 lv[-2]）；
        # 挂在市节点下的是该市真实市局，不能降级。
        alt_full, alt_base = seq[-1]
        seq = seq[:-1]
    deep_full, deep_base = (seq[-1] if seq else ("", ""))
    deep_is_sub = len(seq) >= 2 and not deep_full.endswith("省")
    return full, base, deep_full, deep_base, deep_is_sub, alt_full, alt_base


def role_of(rec):
    """机构类型。部门/群团不判（标题五花八门，强判会大量误杀）。"""
    name, c, k = rec["name"], rec["c"], rec["k"]
    for role, kws in ROLE_KW.items():
        if any(kw in name for kw in kws):
            return role
    if k == "人民政府":
        return "政府"
    if k == "部门" or "部门" in c or k == "群团组织" or "群团" in c:
        return ""
    for role, kws in ROLE_KW.items():
        if any(kw in c for kw in kws):
            return role
    return ""


# 标题里的「国家级平台」特征——地区节点却指到国家部委站，属错配
NATIONAL_KW = ("中华人民共和国", "中央人民政府", "中国政府网", "国家", "中国")

# 省级平台子站：省份级机构域名 -> 省份。市级节点用它的子域（wx.jsjc.gov.cn）是
# 合法官方入口（省级官网市级频道，项目教训 #7），不算错配。
PROV_HOSTS = defaultdict(set)


def reg_domain(host):
    host = (host or "").lower().split(":")[0]
    p = host.split(".")
    if len(p) >= 3 and p[-2] in ("gov", "edu", "org", "com", "net", "mil"):
        return ".".join(p[-3:])
    return ".".join(p[-2:])


def province_level(rec):
    seq = [q for nm in list(rec["path"]) + [rec["name"]]
           if (q := place_of(nm))]
    return len(seq) == 1 and seq[0][0] == rec["prov"]


def build_prov_hosts(recs):
    for r in recs:
        if r["prov"] and province_level(r):
            PROV_HOSTS[r["prov"]].add(reg_domain(urlparse(r["u"]).netloc))


# 地级市平台域名表：仅作诊断参考（区县节点挂市级平台无法与「上级顶替」区分，
# 不做豁免——宁缺毋滥，栏目页一律按项目口径判错配/存疑）。
CITY_HOSTS = defaultdict(set)
URL_FREQ = Counter()


def build_city_hosts(recs):
    for r in recs:
        URL_FREQ[r["u"]] += 1
        p = place_of(r["name"])
        if p and is_city_level(p[0]):
            CITY_HOSTS[p[0]].add(reg_domain(urlparse(r["u"]).netloc))


def is_prov_subsite(u, prov):
    host = urlparse(u).netloc.lower().split(":")[0]
    dom = reg_domain(host)
    return host != dom and dom in PROV_HOSTS.get(prov, ())


def is_city_level(full):
    return bool(full) and full not in PROV_FULLS and full.endswith(("市", "州", "地区", "盟"))


# 人工复核通过的例外：(URL, 本级区划全名) -> 说明。链接确为该机构真实入口，
# 只是标题因区划调整/业务平台参数而不含本级地名。
ALLOW_OK = {
    ("https://www.dljp.gov.cn/", "金州区"):
        "金普新区门户为金州区实际政府入口（区划调整）",
    ("https://hljxf.gov.cn/wtserver/index.html?rid=230500", "双鸭山市"):
        "全省网上信访平台按 rid=230500 路由到双鸭山",
    ("https://www.xihaian.gov.cn/", "黄岛区"):
        "青岛西海岸新区与黄岛区合署，新区门户即黄岛区政府入口",
    ("https://www.whkfq.gov.cn/", "汉南区"):
        "武汉经开区与汉南区合署，经开区门户即汉南区政府入口",
    ("http://xw.wxfy.gov.cn/index.shtml", "新吴区"):
        "新吴区与无锡高新区合署，法院以高新区法院名义建站",
    ("http://ftz.xm.gov.cn/", "福建自贸试验区厦门片区"):
        "厦门片区管委会官网，标题用全称「中国（福建）自由贸易试验区厦门片区」",
    ("http://gxq.cq.gov.cn", "西部科学城重庆高新区"):
        "西部科学城重庆高新区与重庆高新区合署，门户标题用「重庆高新技术产业开发区」",
    ("http://xn.caac.gov.cn", "四川省"):
        "民航西南地区管理局驻四川，官网标题为全称「中国民用航空西南地区管理局」",
    ("http://www.uetd.gov.cn/", "头屯河区"):
        "乌鲁木齐经济技术开发区与头屯河区区政合一，经开区门户即区政府入口",
    ("http://zmqfy.cqfygzfw.gov.cn", "重庆自贸区"):
        "重庆自贸区法院＝重庆自由贸易试验区人民法院，标题用全称",
    ("http://tfxqcdfy.scssfw.gov.cn", "四川自贸区"):
        "四川自贸区法院＝四川天府新区人民法院/四川自由贸易试验区人民法院，标题用全称",
    ("https://jccqfy.shanxify.gov.cn", "晋城城区"):
        "条树叶子「晋城城区法院」＝晋城市城区人民法院，标题为「山西省晋城市城区人民法院网」",
}


def title_roles(title):
    return {role for role, kws in ROLE_KW.items()
            if any(kw in title for kw in kws)}


def other_places(title, exp_full, exp_base):
    """标题里出现的、不属于期望地区的行政区全名。"""
    exp_names = {f for f in exp_full if f} | {b for b in exp_base if len(b) >= 2}

    def suffix_of_bigger(tok, i, j):
        """tok 是标题里某个更长地名的尾巴 → 同一地名的子串，不是另一个地区。

        「马鞍山市」里的「鞍山市」这类；「鄂托克前旗」不算（它是另一个旗，
        不是「鄂托克旗」的子串）。
        """
        for s in range(max(0, i - 3), i):
            big = title[s:j + 1]
            if len(big) > len(tok) and big in ALL_PLACES and any(e in big for e in exp_names):
                return True
        return False

    out, L = [], len(title)
    # 期望地名在标题里的出现区间：双字县名常是本地名的尾巴（连南县 / 镇宁县 /
    # 紫云县 / 市南区 里的「南县 / 宁县 / 云县 / 南区」都是别处的真县名），
    # 只要与期望地名在标题里挨着，就是同一个地方，不算「另一个地区」。
    exp_occ = []
    for e in exp_names:
        if len(e) < 2:
            continue
        st = 0
        while True:
            p = title.find(e, st)
            if p < 0:
                break
            exp_occ.append((p, p + len(e)))
            st = p + 1
    for i in range(L):
        # 双字县名（文县/温县/吉县/单县…）也要认：窗口从 2 字起，「文县人民检察院」
        # 出现在河南温县节点上就是错配。复合地名的尾巴由 suffix_of_bigger 兜住。
        for j in range(i + 1, min(i + 9, L)):
            tok = title[i:j + 1]
            if not ADMIN_SUFFIX.search(tok) or tok not in ALL_PLACES:
                continue
            if tok in exp_full or ALL_PLACES[tok] in exp_base:
                continue
            if len(tok) == 2 and any(p <= j and i < q for p, q in exp_occ):
                continue
            if suffix_of_bigger(tok, i, j):
                continue
            # 功能区（经开区/新区/示范区）不是「另一个地区」，标题提及不构成错配
            if any(k in tok for k in ZONE_KW):
                continue
            # 复合串（「长治市潞州区」⊃ 期望的「长治市」）不是另一个地区
            if any(f and f in tok for f in exp_full):
                continue
            # 期望地名的子串（「宝山区」⊂「元宝山区」、「河口区」⊂「沙河口区」）也不是
            if any(tok in f for f in exp_full):
                continue
            out.append(tok)
    return list(dict.fromkeys(out))


def drop_nonconflicting(others, exp_full, deep_full):
    """剔掉不构成错配证据的「其他地区」。

    1) 该地名是**本级**的下辖县区（本级是市、标题写的是市里的某个县区）——
       如清远市中级法院节点标题「连南瑶族自治县人民法院」、徐州中院节点标题
       「徐州市鼓楼区人民法院」；
    2) 路径里没有市一级时，标题带的父市（西湖区法院节点 → 杭州市西湖区人民法院）。
       路径里有市时**不能**放行别的市——否则「徐州鼓楼区 → 福州鼓楼区政府」
       这类真错配会被漏掉。
    同级县区（鄂托克旗 ↔ 鄂托克前旗）照常判错配。
    """
    exp_cities = {f for f in exp_full
                  if f and not f.endswith("省") and f.endswith(("市", "州", "地区", "盟"))}
    keep = []
    for o in others:
        if deep_full in (CITY_OF_COUNTY.get(o) or set()):
            continue                       # o 是本级的下辖县区
        if not exp_cities and o in (CITY_OF_COUNTY.get(deep_full) or set()):
            continue                       # 路径缺市一级，标题的父市不算错配
        keep.append(o)
    return keep


ZONE_KW = ("开发区", "新区", "园区", "工业区", "度假区", "管理区", "示范区",
           "高新区", "经济区", "合作区", "保税区", "经开区", "改革示范区",
           "新城", "片区", "试验区", "风景名胜", "景区")
ZONE_FILLER = ("经济技术", "高新技术", "国家级", "国家", "省级", "市级",
               "经济", "技术", "高新", "产业", "示范",
               "管理", "工业", "旅游", "开发", "新区", "园区", "经开", "综改")
ZONE_ALIAS = (("综改", "综合改革"), ("经开", "经济技术开发"))


def zone_core(s):
    """功能区名归一：剥离「经济/技术/高新/开发」等修饰，只留地名与行政区后缀。"""
    for a, b in ZONE_ALIAS:
        s = s.replace(a, b)
    for kw in ZONE_FILLER:
        s = s.replace(kw, "")
    return s.replace("市", "")


def zone_hit(title, deep_full):
    """功能区写法差异（张家口经济开发区 ↔ 张家口经济技术开发区 ↔ 河北沧州经济开发区）。"""
    if not any(k in deep_full for k in ZONE_KW):
        return False
    if not any(k in title for k in ZONE_KW):
        return False
    a, b = zone_core(deep_full), zone_core(title)
    return bool(a) and bool(b) and (a in b or b in a)


def place_hit(title, full, base):
    """标题是否含该行政区。全名可靠；基底仅当 ≥2 字时放宽（避免单字县「赵/吉」误命中）。"""
    if full and full in title:
        return True
    if base and len(base) >= 2 and base in title:
        return True
    # 复合基底（「哈尔滨双城」「鸡西梨树」= 市名+区名连写）：尾段本身是已知基底也算命中，
    # 标题常只写本级（「双城区人民法院网」「鸡西梨树法院网」）
    if len(base) >= 3:
        for i in range(1, len(base) - 1):
            cand = base[i:]
            if cand in ALL_BASE_SET and cand in title:
                return True
    return False


def judge(rec, res):
    """返回 (verdict, reason)。verdict ∈ ok/ok_neutral/waf/dead/mismatch/suspect。"""
    st, why = base_status(res)
    if st in ("waf", "dead"):
        return st, why
    if st == "suspect":
        return "suspect", why
    title = res["title"]
    if not title or len(title) <= 3 or NEUTRAL_TITLE.match(title):
        return "ok_neutral", "标题为空/中性"
    role = role_of(rec)
    hits = title_roles(title)
    if role and role not in hits:
        conflict = [r for r in hits if frozenset((role, r)) in ROLE_CONFLICT]
        if conflict:
            return "mismatch", f"机构类型冲突: 期望{role} 标题为{'/'.join(sorted(conflict))}"
    exp_full, exp_base, deep_full, deep_base, deep_is_sub, alt_full, alt_base = rec_places(rec)
    if not exp_full:                       # 中央/驻地机构：无行政区可判
        path = urlparse(res["u"]).path
        if ART_HARD.search(path) or ART_QUERY.search(res["u"]):
            return "suspect", "文章/详情页路径"
        return "ok", ""
    # 省级平台子站：市级节点指到本省平台子域（wx.jsjc.gov.cn「江苏检察网」），
    # 属省级官网的市级频道——合法官方入口（项目教训 #7），不算错配。
    # 仅限「本级是市」；县级节点指到省级平台一律照常判错配。
    if is_city_level(deep_full) and rec["prov"] and is_prov_subsite(res["u"], rec["prov"]):
        return "ok_neutral", "省级平台子站（市级频道）"
    # 跨省同基底：河北区（天津）节点挂到河北省人民政府，标题含「河北省」
    if rec["prov"]:
        cross = [p for p in PROV_FULLS if p != rec["prov"] and p in title]
        if cross:
            return "mismatch", f"地区不符: 标题为{cross[0]}，本节点属{rec['prov']}"

    # 复核过的例外：链接本身即该机构真实入口（区划调整 / 业务平台带地市参数）
    if (rec["u"], deep_full) in ALLOW_OK:
        return "ok", ALLOW_OK[(rec["u"], deep_full)]

    # 节点全名本身出现在标题里 = 同一机构（「湾里管理局」→「南昌市湾里管理局」）。
    # 层级占位名（市/县开头的「市人民检察院」）与全国性节点名不算，防误放行。
    nm = rec["name"]
    if (len(nm) >= 4 and nm[0] not in "省市县区"
            and not any(x in nm for x in ("全国", "中央", "中国", "代表大会"))
            and nm in title):
        return "ok", "标题含机构全名"

    hit_deep = place_hit(title, deep_full, deep_base)
    if not hit_deep and deep_full and "翼" in deep_full:
        # 旗名常见「翼」省略：察哈尔右翼前旗 ↔ 察哈尔右前旗
        hit_deep = deep_full.replace("翼", "") in title
    if not hit_deep and alt_full:
        hit_deep = place_hit(title, alt_full, alt_base)
    if not hit_deep and deep_full:
        hit_deep = zone_hit(title, deep_full)
    hit_any = (hit_deep
               or any(f in title for f in exp_full)
               or any(b in title for b in exp_base if len(b) >= 2))
    if not hit_any:
        others = other_places(title, exp_full, exp_base)
        others = drop_nonconflicting(others, exp_full, deep_full)
        if others:
            return "mismatch", f"地区不符: 期望{'/'.join(sorted(exp_base))} 标题含{'/'.join(others[:3])}"
        if any(kw in title for kw in NATIONAL_KW) and not any(
                kw in rec["name"] for kw in ("国家", "中国", "中央")):
            return "mismatch", f"地区不符: 期望{'/'.join(sorted(exp_base))} 标题为国家机构/平台"
        return "suspect", "标题不含期望地名"
    if not hit_deep:
        # 命中上级地名但没命中本级地名 → 上级站点冒充下级机构
        return "mismatch", f"地区不符: 期望{deep_base} 标题仅含上级地名"
    if deep_is_sub and not any(k in deep_full for k in ZONE_KW):
        # 本级命中，但标题里还挂着别的行政区（跨市/跨县错配）
        # 功能区（新区/开发区）节点的标题常带所在区县名，不构成错配证据
        others = other_places(title, exp_full, exp_base)
        if others:
            # 条树叶子/registry-only 记录只带县名（路径无市），标题里的父市是正常的
            others = drop_nonconflicting(others, exp_full, deep_full)
            # 长标题多为文章页标题（各地来稿/转载），地名不作错配证据
            if others and len(title) <= 32:
                return "mismatch", f"地区不符: 本级{deep_base}命中 标题另含{'/'.join(others[:3])}"
    path = urlparse(res["u"]).path
    if ART_HARD.search(path) or ART_QUERY.search(res["u"]):
        return "suspect", "文章/详情页路径"
    return "ok", ""


# ── 结果存取 ─────────────────────────────────────────────────
def load_done():
    done = {}
    if os.path.exists(OUT_JSONL):
        with open(OUT_JSONL, encoding="utf-8") as f:
            for line in f:
                try:
                    r = json.loads(line)
                    done[r["u"]] = r
                except Exception:
                    continue
    return done


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--prune", action="store_true")
    ap.add_argument("--fresh", action="store_true")
    args = ap.parse_args()

    tree = json.load(open(TREE_F, encoding="utf-8"))
    collect_all_places(tree)
    recs = collect_records(tree)
    build_prov_hosts(recs)          # 省级平台域名表（市级频道豁免用）
    build_city_hosts(recs)          # 市级平台域名表（区级频道豁免用）
    reg = json.load(open(REG_F, encoding="utf-8"))
    tree_urls = {r["u"] for r in recs}
    reg_only = []
    for k, v in reg.items():
        u = (v.get("u") or "").strip()
        if u.startswith("http") and u not in tree_urls:
            reg_only.append({"u": u, "name": (v.get("n") or k.split("|")[-1]).strip(),
                             "k": "", "c": k.split("|")[0], "path": [],
                             "prov": "", "tree": "reg"})
    recs_all = recs + reg_only
    urls = list(dict.fromkeys(r["u"] for r in recs_all))
    print(f"p240 树节点 URL {len(tree_urls)} 条记录 {len(recs)}；"
          f"registry-only {len(reg_only)}；唯一 URL {len(urls)}")

    if args.report or args.apply:
        done = load_done()
    else:
        if args.fresh and os.path.exists(OUT_JSONL):
            os.remove(OUT_JSONL)
        done = load_done()
        todo = [u for u in urls if u not in done]
        if args.limit:
            todo = todo[:args.limit]
        print(f"已完成 {len(done)}，本轮待抓 {len(todo)}（并发 {CONC}，代理"
              f"{'启用' if PROXIES else '禁用'}）", flush=True)
        t0 = time.time()
        lock = threading.Lock()
        fh = open(OUT_JSONL, "a", encoding="utf-8")
        n = 0

        def work(u):
            r = fetch_one(u)
            with lock:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
                fh.flush()
            return r

        with ThreadPoolExecutor(CONC) as ex:
            for r in ex.map(work, todo):
                n += 1
                done[r["u"]] = r
                if n % 200 == 0:
                    el = time.time() - t0
                    print(f"  {n}/{len(todo)}  {el:.0f}s  "
                          f"{(n / max(el, 1)) * 60:.0f} URL/min", flush=True)
        fh.close()
        print(f"抓取完成，用时 {time.time() - t0:.0f}s")

    # ── 分档报告 ──
    verdicts = Counter()
    rows = []
    for rec in recs_all:
        res = done.get(rec["u"])
        if not res:
            verdicts["unfetched"] += 1
            continue
        v, why = judge(rec, res)
        verdicts[v] += 1
        rows.append({"key": f"{rec['tree']}|{'|'.join(rec['path'] + [rec['name']])}",
                     "u": rec["u"], "name": rec["name"], "tree": rec["tree"],
                     "path": rec["path"], "prov": rec["prov"],
                     "verdict": v, "reason": why,
                     "code": res["code"], "via": res["via"],
                     "title": res["title"], "final": res["final"]})
    print("\n分档:", dict(verdicts))
    by_u = {}
    for r in rows:
        by_u.setdefault(r["u"], set()).add(r["verdict"])
    print("按唯一 URL:", dict(Counter(
        "mismatch" if "mismatch" in vs else
        ("suspect" if "suspect" in vs else
         ("dead" if vs == {"dead"} else
          ("waf" if vs == {"waf"} else "ok"))) for vs in by_u.values())))

    report = {
        "generated": datetime.datetime.now().isoformat(timespec="seconds"),
        "totals": dict(verdicts),
        "rows": rows,
    }
    json.dump(report, open(REPORT_F, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"报告写入 {REPORT_F}")

    for v in ("mismatch", "suspect", "dead"):
        sample = [r for r in rows if r["verdict"] == v]
        print(f"\n── {v}（{len(sample)} 条记录，样例 {min(15, len(sample))}）──")
        for r in sample[:15]:
            print(f"  {r['name']:<16} {r['u'][:76]}")
            print(f"      [{r['code']}/{r['via']}] {r['title'][:60]}  ← {r['reason']}")

    if args.prune:
        d = os.path.join(ROOT, "backups", TODAY)
        os.makedirs(d, exist_ok=True)
        ts = datetime.datetime.now().strftime("%H%M%S")
        shutil.copy2(TREE_F, os.path.join(d, f"tree_before_p240prune_{ts}.json"))
        prune_misplaced(tree)
        json.dump(tree, open(TREE_F, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        print(f"p240 结构清理已写 tree.json（备份 {d}）")

    if args.apply:
        apply_fixes(tree, rows)


def apply_fixes(tree, rows):
    """按**节点**清除 mismatch（同一 URL 在别的节点上可能是对的，不能全局清）。

    registry 只清「该 URL 在树里已无任何正确节点」的条目，避免误杀河北省厅局
    这类本来正确的注册；dead 只报告不动树（项目死链纪律）。
    """
    bad_nodes = defaultdict(list)
    for r in rows:
        if r["verdict"] == "mismatch":
            bad_nodes[(r["tree"], tuple(r["path"]))].append(r)
    if not bad_nodes:
        print("没有 mismatch，无需清理")
        return
    d = os.path.join(ROOT, "backups", TODAY)
    os.makedirs(d, exist_ok=True)
    ts = datetime.datetime.now().strftime("%H%M%S")
    for f in ("tree.json", "site_registry.json"):
        shutil.copy2(os.path.join(BASE_DIR, f),
                     os.path.join(d, f"{f.split('.')[0]}_before_p240_{ts}.json"))

    cleared = set()
    n_clear = 0

    def walk(n, path, kind):
        nonlocal n_clear
        u = (n.get("u") or "").strip()
        if u:
            for r in bad_nodes.get((kind, tuple(path)), []):
                # 同路径下同名同 URL 的节点 = 同一条错配记录
                if r["name"] == (n.get("n") or "").strip() and r["u"] == u:
                    n["u"] = ""
                    # 信息公开专栏若在与错配 URL 同域，是同一错站的派生链接，一并清
                    x = (n.get("x") or "").strip()
                    if x and reg_domain(urlparse(x).netloc) == reg_domain(urlparse(u).netloc):
                        n["x"] = ""
                    n["s"] = ((n.get("s") or "") + f" | p240 全量核查清除: {r['reason']}").strip(" |")
                    cleared.add(u)
                    n_clear += 1
                    break
        for c in n.get("ks") or []:
            walk(c, path + [(n.get("n") or "").strip()], kind)

    for g in tree["ks"]:
        kind = "tiao" if (g.get("l") == "根" or (g.get("n") or "").startswith("条")) else "blk"
        walk(g, [], kind)
    json.dump(tree, open(TREE_F, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    # 树里还剩哪些 URL（被清掉的 URL 若仍被别的节点正确使用，registry 不动）
    alive = set()

    def collect(n):
        u = (n.get("u") or "").strip()
        if u:
            alive.add(u)
        for c in n.get("ks") or []:
            collect(c)
    for g in tree["ks"]:
        collect(g)

    reg = json.load(open(REG_F, encoding="utf-8"))
    reg_only_bad = {r["u"] for r in rows
                    if r["verdict"] == "mismatch" and r["tree"] == "reg"}
    reg_hit = 0
    for k, v in reg.items():
        u = (v.get("u") or "").strip()
        if (u in cleared and u not in alive) or u in reg_only_bad:
            v["u"] = ""
            v["status"] = "cleared"
            v["verified_at"] = TODAY
            v["note"] = (v.get("note") or "") + " | p240 全量核查清除"
            reg_hit += 1
    json.dump(reg, open(REG_F, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"p240 清除: 树节点 {n_clear} 个（唯一 URL {len(cleared)}）；"
          f"registry {reg_hit} 条（仅完全失效的 URL）")
    print(f"备份: {d}")


def prune_misplaced(tree):
    """删除市级政府部门组里误采的省级部门节点。

    这类节点是「市政府门户侧栏的省级部门链接块」被当成市局采下来的（白城、江门、
    池州、大兴安岭、凉山、玉树、海西、益阳、天水、绵阳、红河、天津河北区…），
    名字以「省」开头却挂在市/区县的 市级政府部门 组下，URL 全是省厅官网。
    """
    removed = []

    def walk(n, lv, path):
        nlv = n.get("l") or ""
        if (n.get("n") or "").strip() == "市级政府部门" and nlv in ("市", "县", "地级区"):
            keep = []
            for c in n.get("ks") or []:
                cname = (c.get("n") or "").strip()
                if cname.startswith("省") and len(cname) >= 3 and any(
                        k in cname for k in ("厅", "局", "委", "办", "院", "会")):
                    removed.append((path[-1] if path else "", cname, c.get("u") or ""))
                else:
                    keep.append(c)
            if len(keep) != len(n.get("ks") or []):
                n["s"] = ((n.get("s") or "") +
                          f" | p240 结构清理: 删除误采省级部门节点 {len(n.get('ks') or []) - len(keep)} 个").strip(" |")
                n["ks"] = keep
        for c in n.get("ks") or []:
            walk(c, nlv, path + [(n.get("n") or "").strip()])

    for g in tree["ks"]:
        walk(g, "", [(g.get("n") or "").strip()])
    print(f"p240 结构清理: 删除误采省级部门节点 {len(removed)} 个")
    for city, nm, u in removed[:10]:
        print(f"  {city} >> {nm}  {u[:60]}")
    return removed


if __name__ == "__main__":
    main()
