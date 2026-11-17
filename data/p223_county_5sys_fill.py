#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""p223 五系统县级（含直辖市辖区/县）URL 补全 — 四档策略（2026-11-17 用户指令）。

需求：URL_STATS 中县级缺失严重（人大 98%、政协 98.5%、监委 93.7%、
法院 29%、检察院 55.7%），按用户给定顺序补全：

  S1 上级单位官网：市中级法院/市检察院/市人大/市政协/市监委（直辖市为
     省高院/省检察院/省人大/省政协/省监委）官网导航里的辖区/基层机构链接；
     市院无 URL 时回落省院官网。
  S2 本级其他官网导航：县/区政府门户（或门户的机构设置/网站地图栏目页）
     里的 人大/政协/法院/检察院/纪委监委 链接；门户自身频道页（/rd/ 等）
     经 title 验证后作为官方入口收录（p206 口径）。
  S3 同级同系统互链：同市/同省其他县区同系统官网的导航/友情链接区块。
  S4 百度 SERP 兜底：搜索结果严格 title 验证（地名+机构词双验）才落库。

写库契约（site_contract + p222）：
  - 树节点只写 u/s；registry 用县级标准键：
    `县级人大|县名`、`县级政协|县名`、`县级监委|县名`、
    `县级人民法院|县名`、`县级人民检察院|县名`
    （全国重名县区 → 键加省名前缀消歧）。
  - 来源分级：S1=L1，S2/S3=L2，S4=L3。
  - 拿不到/验证不过一律保持 u=""（列名），不猜域名。

用法（单写者，挂 p198_loop 顺序执行）：
  cd data && uv run python p223_county_5sys_fill.py
环境变量：
  P223_STRATEGY=S1,S2,S3,S4（默认全部）
  P223_DRY=1（只统计不写库）
  P223_S1_LIMIT / P223_S2_LIMIT / P223_S3_LIMIT / P223_S4_LIMIT（每组上限）
  P223_CONC=6（并发）
"""
import base64
import datetime
import json
import os
import re
import shutil
import sys
import tempfile
import threading
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import parse_qs, urljoin, urlparse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BASE_DIR)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "util"))
sys.path.insert(0, BASE_DIR)
from site_contract import base as geo_base, upsert_registry  # noqa: E402

TREE_F = os.path.join(BASE_DIR, "tree.json")
REG_F = os.path.join(BASE_DIR, "site_registry.json")
STATE_F = os.path.join(BASE_DIR, "p223_state.json")
TODAY = datetime.date.today().isoformat()

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(ROOT, ".env"))
except Exception:
    pass
TUNNEL = os.environ.get("TUNNEL_PROXY", "")
PROXY = {"http": TUNNEL, "https": TUNNEL} if TUNNEL else None
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36")

# ── 五系统定义 ───────────────────────────────────────────────
ORG5 = {
    "县人大": {"cat": "人大", "kws": ("人民代表大会", "人大常委会", "人大"),
              "feat": r"(rd|renda|spc)"},
    "县政协": {"cat": "政协", "kws": ("政协委员会", "政协"),
              "feat": r"(zx|zhengxie|cppcc)"},
    "县人民法院": {"cat": "县级人民法院", "kws": ("人民法院", "法院"),
                "feat": r"(court|fy|fayuan)"},
    "县人民检察院": {"cat": "县级人民检察院", "kws": ("人民检察院", "检察院"),
                 "feat": r"(jcy|jiancha|jc)"},
    "县监委": {"cat": "县级监委", "kws": ("纪委监委", "监察委员会", "监委", "纪委"),
              "feat": r"(jjjc|jjw|jiwei|jijian|12388|jw|jc|lz|qf|cdi|di)"},
}
ORG_ORDER = ["县人民法院", "县人民检察院", "县人大", "县政协", "县监委"]
# 门户频道路径特征（按机构区分，防「机构职能总表」被五系统共用）
ORG_PATH = {
    "县人大": re.compile(r"(^|/)(rd|renda)(/|$)", re.I),
    "县政协": re.compile(r"(^|/)(zx|zhengxie|cppcc)(/|$)", re.I),
    "县人民法院": re.compile(r"(^|/)(fy|fayuan|court)(/|$)", re.I),
    "县人民检察院": re.compile(r"(^|/)(jcy|jiancha)(/|$)", re.I),
    "县监委": re.compile(r"(^|/)(jw|jiwei|jjjc|jijian|jcj|jc)(/|$)", re.I),
}

# 上级（市/省）并列机关节点名候选
PARENT_ORG = {
    "县人大": ("市人大", "省人大"),
    "县政协": ("市政协", "省政协"),
    "县人民法院": ("市中级人民法院", "省高级人民法院"),
    "县人民检察院": ("市人民检察院", "省人民检察院"),
    "县监委": ("市监委", "省监委", "市纪委", "省纪委"),
}

COUNTY_C = {
    "县级人民政府", "市辖区（地级行政区划）", "直辖市辖区", "直辖市辖县",
    "直辖市辖县（县级行政区划）", "省直辖县级市/县/林区",
    "兵团直辖县级市（自治区直辖县级市）", "功能区", "县级单位",
}

# 新闻/文章/门户栏目路径（不是机构官网）
NEWS_PATH = re.compile(
    r"/(news|content|article|detail|info|tzgg|art|Show|doc|Item|columns|channel)(/|_|\.)|"
    r"/art\d+|/t\d{8}_|/\d{4}[-/]?\d{2}/|/c\d{6,}|/content_\d+|/\d{5,}\.s?html?"
    r"|/(19|20)\d{6}/|/\d{8}\.s?html?|/static/",
    re.I)
# 门户频道页形态（UUID 栏目：/columns/<uuid>/index.html）——不是文章页，
# 真实存在的人大/政协频道官方入口常是这一形态（p228 SERP 实测正定县）。
CHANNEL_OK = re.compile(r"/columns/[0-9a-f][0-9a-f-]{7,}(/index\.html?)?/?(\?.*)?$", re.I)
# 财政预决算 / 部门预算公示专栏（曾把「人大常委会办公室预算」页当区人大官网）
BAD_COLUMN = re.compile(
    r"/(ysjs|czyjs|czxx|czbg|cwbg|caiheng|qyjsgk|czjsgk|cwys|yjsgk|"
    r"czys|ysgk|jfzq|czgk)/", re.I)
BAD_HOST = (
    "baidu.com", "weixin.qq.com", "weibo.com", "people.com.cn", "xinhuanet.com",
    "news.cn", "cctv.com", "mzfzw.net", "qq.com", "163.com", "sohu.com",
    "zhihu.com", "douyin.com", "baike.baidu.com", "wikipedia.org", "google.com",
)
NAV_KW = re.compile(
    r"(基层|辖区|下辖|下级|县区|市县|区县|法院导航|检察院导航|基层院|派出院|"
    r"机构设置|机构概况|组织机构|院情|本院概况|网站地图|站点导航|友情链接|"
    r"直属单位|下属单位|审判机构|检察机构|领导之窗|政务公开|信息公开)")
# 文章页判据之二：查询串里带数字 id 的 CMS 视图（index.php?a=cms&id=3490）
NEWS_QUERY = re.compile(
    r"[?&](id|cid|aid|newsid|articleid|contentid|infoid|docid|pkid)=\d+", re.I)
DRY = os.environ.get("P223_DRY") == "1"
# 省级基底名（跨省同名陷阱用：河北区↔河北省、吉林市↔吉林省）
ALL_PROV_BASES = set()


def _atomic(obj, path):
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def norm(t):
    return re.sub(r"[\s　\xa0]+", "", re.sub(r"<[^>]+>", "", t or ""))


# ── 抓取 ───────────────────────────────────────────────────
_tl = threading.local()


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


def fetch(u, timeout=15, tries=2):
    """抓页面。**先直连、失败再走隧道代理**——隧道代理在并发下会把别家
    请求的响应串回来（实测三站 title 同时变成「潞州区提案」、江西站 title
    变成「甘肃省人民检察院」），直连稳定且更快；代理仅作反爬兜底。"""
    if not u or not u.startswith("http"):
        return None
    for _ in range(tries):
        for px in (None, PROXY):
            try:
                r = _session().get(u, timeout=timeout, verify=False, proxies=px,
                                    allow_redirects=True)
                if r.status_code == 200 and r.content and len(r.content) > 200:
                    return _decode(r)
                _tl.last_err = f"http{r.status_code}"
            except Exception as e:
                _tl.last_err = type(e).__name__
    return None


_html_cache = {}
_html_lock = threading.Lock()


def fetch_cached(u, timeout=15):
    """同一上级官网在多个系统/县区组间复用页面 HTML（限 400 页防内存爆）。"""
    with _html_lock:
        if u in _html_cache:
            return _html_cache[u]
    h = fetch(u, timeout=timeout)
    with _html_lock:
        if len(_html_cache) < 400:
            _html_cache[u] = h
    return h


_title_cache = {}
_title_lock = threading.Lock()


def page_title(u):
    with _title_lock:
        if u in _title_cache:
            return _title_cache[u]
    h = fetch_cached(u)
    t = ""
    if h:
        m = re.search(r"<title[^>]*>(.*?)</title>", h, re.S | re.I)
        if m:
            t = norm(m.group(1))
            try:
                import html as _h
                t = _h.unescape(t)
            except Exception:
                pass
    with _title_lock:
        _title_cache[u] = t
    return t


# ── 链接提取（a / option / onclick window.open）──────────────
def unwrap(u):
    u = (u or "").strip().strip("'\"")
    p = urlparse(u)
    if p.netloc.endswith("elink.chinacourt.cn") or ("/link?" in u and "elid=" in u):
        vals = parse_qs(p.query).get("elid") or []
        if vals:
            v = urllib.parse.unquote(vals[0])
            if not v.startswith("http"):
                try:
                    v = base64.b64decode(v + "=" * (-len(v) % 4)).decode("utf-8", "ignore")
                except Exception:
                    v = ""
            if v.startswith("http"):
                return v
    return u


def clean_url(u, base_url):
    try:
        import html as _h
        u = _h.unescape(u or "")
    except Exception:
        pass
    u = unwrap(u)
    if not u or u.startswith(("javascript:", "#", "mailto:", "tel:")):
        return ""
    u = u.strip()
    if u.startswith("//"):
        u = "https:" + u
    elif not u.startswith("http"):
        u = urljoin(base_url, u)
    u = u.split("#")[0]
    p = urlparse(u)
    if p.scheme not in ("http", "https") or not p.netloc:
        return ""
    return u


def extract_links(html, base_url):
    pairs = []
    for m in re.finditer(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html or "", re.S):
        pairs.append((norm(m.group(2)), m.group(1)))
    for m in re.finditer(r'<option[^>]+value=["\']([^"\']+)["\'][^>]*>(.*?)</option>',
                         html or "", re.S):
        pairs.append((norm(m.group(2)), m.group(1)))
    for m in re.finditer(
            r'<([a-zA-Z0-9]+)([^>]*\bonclick=["\'][^"\']*'
            r'(?:window\.open|location\.href)[^"\']*["\'][^>]*)>(.*?)</\1>',
            html or "", re.S):
        attrs, inner = m.group(2), m.group(3)
        um = re.search(r'(?:window\.open|location\.href)\s*[=(]\s*[\'"]?([^\'")\s]+)',
                       attrs)
        if um:
            pairs.append((norm(inner), um.group(1)))
    out, seen = [], set()
    for txt, u in pairs:
        cu = clean_url(u, base_url)
        if not cu or cu in seen:
            continue
        seen.add(cu)
        out.append((txt, cu))
    return out


def host_ok(u, allow_host=None, strict=True):
    """域名合规：strict=SERP 兜底（只认 .gov.cn）；非 strict=从官方页面
    真实链接提取（来源权威，允许 .org.cn/.com 等官方站，如政协/工会在
    非 gov 域的官网），仍排除媒体/聚合域名。"""
    h = urlparse(u).netloc.lower()
    if allow_host and h == allow_host:
        return True
    if any(b in h for b in BAD_HOST):
        return False
    if h == "gov.cn" or h.endswith(".gov.cn"):
        return True
    if strict:
        return False
    return bool(h) and "." in h and not any(
        b in h for b in ("zwfw.", "chinacourt.org", "beian.", "1688.com"))


# ── 任务构建 ────────────────────────────────────────────────
def collect(tree):
    blk = next(g for g in tree["ks"] if g["n"].startswith("省级"))
    tasks = []

    def walk(n, prov, ancestors):
        if n.get("k") == "人民政府" and n.get("c") in COUNTY_C and n.get("ks"):
            grp = next((g for g in n["ks"] if g.get("c") == "并列机关"), None)
            if grp:
                parent = None
                for a in reversed(ancestors):
                    if a.get("k") == "人民政府" and a.get("l") in ("省", "市", "地级区"):
                        parent = a
                        break
                if parent:
                    for on in ORG_ORDER:
                        o = next((x for x in grp.get("ks") or [] if x.get("n") == on), None)
                        if o is not None:
                            tasks.append({"prov": prov, "parent": parent, "county": n,
                                          "org": o, "org_name": on,
                                          "filled": bool((o.get("u") or "").strip())})
        for c in n.get("ks") or []:
            walk(c, prov, ancestors + [n])

    for p in blk["ks"]:
        walk(p, p["n"], [p])
    return blk, tasks


def parent_site(task, prov_map):
    """上级同系统官网 URL（市优先，无则省）。"""
    nodes = [task["parent"]]
    pv = prov_map.get(task["prov"])
    if pv is not None and pv is not task["parent"]:
        nodes.append(pv)
    for node in nodes:
        for g in node.get("ks") or []:
            if g.get("c") != "并列机关":
                continue
            for cand in PARENT_ORG[task["org_name"]]:
                o = next((x for x in g.get("ks") or [] if x.get("n") == cand), None)
                if o and (o.get("u") or "").strip():
                    return o["u"].strip()
    return ""


COUNTY_KEY = {
    # 与 site_registry 存量口径对齐（人大|X县人大 / 纪委|X县监委 / 县级人民法院|X）
    "县人大": ("人大", "人大"),
    "县政协": ("政协", "政协"),
    "县监委": ("纪委", "监委"),
    "县人民法院": ("县级人民法院", ""),
    "县人民检察院": ("县级人民检察院", ""),
}


def county_key(prov, county, org_name, dup_names):
    cat, suf = COUNTY_KEY[org_name]
    nm = county.get("n", "")
    if nm in dup_names:
        nm = f"{prov}{nm}"
    return f"{cat}|{nm}{suf}"


# ── 匹配与验证 ──────────────────────────────────────────────
def has_name(t, nm):
    """边界感知的县名包含判定（防「新绛县」被当成「绛县」的串名陷阱）。

    合法前缀只有地名层级（运城市绛县…）或分隔符（·-（）等）；像「新绛县」
    里「绛县」前是普通汉字 → 不算命中。
    """
    if not t or not nm:
        return False
    i = 0
    while True:
        j = t.find(nm, i)
        if j < 0:
            return False
        if j == 0 or t[j - 1] in "·-—－（(【[《|:：":
            return True
        if t[:j].endswith(("省", "市", "州", "地区", "盟", "旗", "县", "区")):
            return True
        i = j + 1


def prov_base(n):
    """省级名 → 基底（河北省→河北、内蒙古自治区→内蒙古）。"""
    x = geo_base(n)
    for suf in ("维吾尔自治区", "壮族自治区", "回族自治区", "自治区",
                "特别行政区", "省", "市"):
        if x.endswith(suf) and len(x) > len(suf):
            return x[:-len(suf)]
    return x


def text_has_county(t, county):
    nm = county.get("n", "")
    b = geo_base(nm)
    if not b:
        return False
    if has_name(t, nm):
        return True
    if b != nm and has_name(t, b):
        return len(t) <= max(len(nm) + 8, len(b) + 10)
    return False


def text_has_org(t, org_name):
    return any(k in t for k in ORG5[org_name]["kws"])


def match_link(text, url, task, allow_pure=False):
    t = norm(text)
    if not t or len(t) > 40:
        return False
    if NEWS_PATH.search(url) or NEWS_QUERY.search(url):
        return False
    has_c = text_has_county(t, task["county"])
    has_o = text_has_org(t, task["org_name"])
    if has_c and has_o:
        return True
    if allow_pure and has_c:
        nm = task["county"].get("n", "")
        b = geo_base(nm)
        if t == nm or t == b or (b and t.endswith(b) and len(t) <= len(b) + 8):
            return True
    return False


NEUTRAL_TITLE = re.compile(
    r"^(首页|网站首页|欢迎访问.*|.*网站首页|.*门户网站|.*人民政府网?站?|.*人民政府)$")

# 业务栏目页特征（title 层）：预决算/三公经费/任免/公示/招标… 都不是机构官网
TITLE_BAD = re.compile(
    r"(决算|预算|三公|经费|任免|招录|招考|招聘|中标|成交|招标|采购|"
    r"表彰|先进事迹|工作报告|述职|述廉|考核|公示|通知|公告|通告|会议|培训|"
    r"主题教育|专项整治|巡察|巡视|整改|民主生活会)")


def title_ok(title, task, anchor_exact):
    """严格 title 验证：县名 + 机构词；重名县区要求市/省上下文。"""
    county, city = task["county"], task["parent"]
    org_name = task["org_name"]
    nm = county.get("n", "")
    b = geo_base(nm)
    if not title:
        return (anchor_exact, "title空(JS壳)") if anchor_exact else (False, "title空")
    # 业务栏目页（预决算/三公经费/任免/公示…）——实测「凉州区人民政府法院、
    # 检察院财务决算和“三公”经费」曾被当成凉州区人民法院官网（/col/col29244/）
    badw = TITLE_BAD.search(title)
    if badw:
        return False, f"非官网栏目页({badw.group(1)})"
    # 上级法院/检察院站点（中院官网「临夏法院网-临夏州中级人民法院」曾被
    # 当成临夏市/临夏县法院）——县级机构标题里出现上级字眼即驳回
    if org_name in ("县人民法院", "县人民检察院"):
        up = re.search(r"(中级人民|高级人民|最高人民法院|州中级|地区中级|分院)", title)
        if up:
            return False, f"上级机构站点({up.group(1)})"
    if not (has_name(title, nm) or (b != nm and has_name(title, b))):
        return False, "无县名"
    if not text_has_org(title, org_name):
        if NEUTRAL_TITLE.match(title) and anchor_exact:
            return True, "中性标题+精确锚文本"
        return False, "无机构词"
    cb = geo_base(city.get("n", "")) if city else ""
    pb = prov_base(task["prov"]) if task["prov"] else ""
    # 跨省同名陷阱：县区基底=他省省名（天津河北区 ↔ 河北省）——须全名出现
    if b in ALL_PROV_BASES and b != pb and not has_name(title, nm):
        return False, f"基底与他省同名({b})"
    if task.get("dup") and cb and cb not in title and pb and pb not in title:
        return False, "重名县缺市/省上下文"
    if cb and cb not in title:
        for other in (task.get("siblings") or []):
            if other and other != cb and other in title:
                return False, f"疑似他市({other})"
    return True, "ok"


def valid_candidate(task, u, text, strict=True):
    """URL + title 双验。返回 (ok, note)。"""
    if not host_ok(u, strict=strict):
        return False, "非gov域名"
    if BAD_COLUMN.search(u):
        return False, "财政预决算/人事任免类栏目"
    if (NEWS_PATH.search(u) or NEWS_QUERY.search(u)) and not CHANNEL_OK.search(u):
        return False, "新闻/栏目路径"
    t = page_title(u)
    anchor_exact = text_has_county(norm(text), task["county"]) and \
        text_has_org(norm(text), task["org_name"])
    ok, note = title_ok(t, task, anchor_exact)
    if not t and anchor_exact:
        # JS 壳空标题：退化为锚文本严格校验（不可免检——曾把「河北省纪检
        # 监委网站」锚文本挂到天津河北区）
        ok2, note2 = title_ok(norm(text), task, True)
        if ok2:
            return True, "title空(JS壳)+锚文本严格校验"
        return False, f"title空+锚文本不过({note2})"
    if ok:
        return True, f"title={t[:40]}|{note}"
    return False, note


# ── 写库 ────────────────────────────────────────────────────
# WAF 会话参数服务器会下发（如 ?WebShieldDRSessionVerify=…），入库前剥掉
_WAF_Q = re.compile(r"[?&](WebShieldDRSessionVerify|jsessionid|PHPSESSID|"
                    r"sessionid|wafverify|verify)\b[^&]*", re.I)


_MOBILE_P = re.compile(r"/(phone|wap|m|mobile)/(m?index\.[a-z]+)$", re.I)


def clean_fill_url(u):
    u = (u or "").strip()
    if "?" in u:
        head, _, q = u.partition("?")
        # 注意：_WAF_Q 带 ?/& 前缀断言，故匹配时把 ? 补回去
        q2 = _WAF_Q.sub("", "?" + q).lstrip("?").lstrip("&")
        u = head + (("?" + q2) if q2 else "")
    # 移动版入口页 → 站点根（实测：陆河县检察院 /lhjcy/phone/mindex.shtml）
    p = urlparse(u)
    if _MOBILE_P.search(p.path or ""):
        u = f"{p.scheme}://{p.netloc}/"
    return u


def apply_fill(reg, task, u, src, level, dup_names):
    u = clean_fill_url(u)
    if task.get("filled"):
        return False
    if DRY:
        task["filled"] = True
        print(f"  [DRY] {task['prov']}/{task['parent'].get('n')}/{task['county'].get('n')} "
              f"{task['org_name']} -> {u}")
        return True
    task["org"]["u"] = u
    task["org"]["s"] = src
    county = task["county"]
    key = county_key(task["prov"], county, task["org_name"], dup_names)
    _cat, _suf = COUNTY_KEY[task["org_name"]]
    upsert_registry(reg, key, u, name=county.get("n", "") + _suf,
                    source_level=level,
                    source=src, verified_at=TODAY, locations=["块"])
    task["filled"] = True
    return True


# ── S1 上级官网 ────────────────────────────────────────────
def run_s1(tasks, reg, dup_names, st, prov_map, limit=None):
    groups = {}
    for t in tasks:
        if t["filled"]:
            continue
        u = parent_site(t, prov_map)
        if not u:
            continue
        groups.setdefault((u, t["org_name"]), []).append(t)
    print(f"S1 上级官网组: {len(groups)}")
    items = list(groups.items())
    if limit:
        items = items[:limit]
    filled = 0

    def work(item):
        (u, org_name), ts = item
        h = fetch_cached(u)
        if not h or len(h) < 300:
            return 0, f"fetch-fail:{getattr(_tl, 'last_err', '')}"
        pages = [(u, h)]
        navs = []
        for txt, link in extract_links(h, u):
            if urlparse(link).netloc != urlparse(u).netloc:
                continue
            if NEWS_PATH.search(link) or link in [x[0] for x in pages]:
                continue
            if NAV_KW.search(txt) or NAV_KW.search(link):
                navs.append(link)
            if len(navs) >= 3:
                break
        for nu in navs:
            nh = fetch_cached(nu)
            if nh and len(nh) > 300:
                pages.append((nu, nh))
        local = 0
        for page_u, page_h in pages:
            links = extract_links(page_h, page_u)
            for t in ts:
                if t["filled"]:
                    continue
                for txt, link in links:
                    if not match_link(txt, link, t, allow_pure=True):
                        continue
                    ok, note = valid_candidate(t, link, txt, strict=False)
                    if not ok:
                        continue
                    src = (f"来源:{t['parent'].get('n', '')}官网({page_u})"
                           f"辖区链接 HTML 提取+title验证({note})")
                    if apply_fill(reg, t, link, src, "L1", dup_names):
                        local += 1
                    break
        return local, "ok"

    with ThreadPoolExecutor(int(os.environ.get("P223_CONC", "6"))) as ex:
        for item, res in zip(items, ex.map(work, items)):
            filled += res[0]
            st.setdefault("s1", {})[f"{item[0][0]}|{item[0][1]}"] = res[1]
            if res[0]:
                print(f"  S1 {item[0][1]} {item[0][0][:60]} -> {res[0]}")
    print("S1 filled:", filled)
    return filled


# ── S2 本级政府门户 ────────────────────────────────────────
def run_s2(tasks, reg, dup_names, st, all_city_bases, limit=None):
    portals = {}
    for t in tasks:
        if t["filled"]:
            continue
        portal_u = (t["county"].get("u") or "").strip()
        if not portal_u:
            continue
        e = portals.setdefault(portal_u, {"county": t["county"], "prov": t["prov"],
                                          "parent": t["parent"], "tasks": []})
        e["tasks"].append(t)
    print(f"S2 县级门户组: {len(portals)}")
    items = list(portals.items())
    if limit:
        items = items[:limit]
    filled = 0

    def work(item):
        pu, info = item
        county, parent = info["county"], info["parent"]
        h = fetch(pu)
        if not h or len(h) < 300:
            return 0, "fetch-fail"
        pt = page_title(pu)
        cb = geo_base(parent.get("n", ""))
        if pt:
            if geo_base(county.get("n", "")) not in pt and county.get("n", "") not in pt:
                return 0, f"portal-title-mismatch:{pt[:30]}"
            if cb and cb not in pt:
                for other in all_city_bases:
                    if other and other != cb and other in pt:
                        return 0, f"portal-wrong-city:{other}:{pt[:24]}"
        pages = [(pu, h)]
        navs = []
        for txt, link in extract_links(h, pu):
            if urlparse(link).netloc != urlparse(pu).netloc:
                continue
            if NEWS_PATH.search(link) or link == pu:
                continue
            if NAV_KW.search(txt) or NAV_KW.search(link):
                navs.append(link)
            if len(navs) >= 3:
                break
        for nu in navs:
            nh = fetch(nu)
            if nh and len(nh) > 300:
                pages.append((nu, nh))
        host = urlparse(pu).netloc.lower()
        nm = county.get("n", "")
        used = {pu}
        local = 0
        for page_u, page_h in pages:
            links = extract_links(page_h, page_u)
            for t in info["tasks"]:
                if t["filled"]:
                    continue
                org_name = t["org_name"]
                for txt, link in links:
                    t2 = norm(txt)
                    if not t2 or len(t2) > 20:
                        continue
                    if NEWS_PATH.search(link) or NEWS_QUERY.search(link):
                        continue
                    # 同一 URL 不得同时充当本县多个机构（门户机构职能页陷阱）
                    if link in used:
                        continue
                    sys_anchor = text_has_org(t2, org_name)
                    sys_path = ORG_PATH[org_name].search(urlparse(link).path)
                    if not sys_anchor and not sys_path:
                        continue
                    same_host = urlparse(link).netloc.lower() == host
                    if not host_ok(link, allow_host=host, strict=False):
                        continue
                    title = page_title(link)
                    if not title or not text_has_county(title, county):
                        continue
                    if text_has_org(title, org_name):
                        ok, note = True, "title双验"
                    elif same_host and sys_path:
                        # 门户频道：标题首段须是本站机构（曾出现 /jw/ 路径的页面
                        # 标题实为「教委_XX区人民政府」——路径不可信，标题首段
                        # 必须带本机构词或县名才认）
                        head = re.split(r"[_|｜\-—·:：\s]", title, 1)[0]
                        if text_has_org(head, org_name) or text_has_county(head, county):
                            ok, note = True, "门户频道(title首段含县名/机构)"
                        else:
                            continue
                    else:
                        continue
                    src = (f"来源:{county.get('n', '')}政府门户({page_u})导航"
                           f" HTML 提取+title验证({note})")
                    if apply_fill(reg, t, link, src, "L2", dup_names):
                        local += 1
                        used.add(link)
                    break
        return local, "ok"

    with ThreadPoolExecutor(int(os.environ.get("P223_CONC", "6"))) as ex:
        for item, res in zip(items, ex.map(work, items)):
            filled += res[0]
            st.setdefault("s2", {})[item[0]] = res[1]
            if res[0]:
                print(f"  S2 {item[1]['county'].get('n')} -> {res[0]}")
    print("S2 filled:", filled)
    return filled


# ── S3 同级同系统互链 ──────────────────────────────────────
def run_s3(tasks, reg, dup_names, st, limit=None):
    groups = {}
    for t in tasks:
        if t["filled"]:
            continue
        groups.setdefault((t["parent"].get("n", ""), t["org_name"], t["prov"]), []).append(t)
    items = []
    for (parent_name, org_name, prov), ts in groups.items():
        srcs = [t["org"]["u"].strip() for t in tasks
                if t["org_name"] == org_name and t["filled"] and t["prov"] == prov
                and (t["org"].get("u") or "").strip()]
        # 同市优先
        same = [t["org"]["u"].strip() for t in tasks
                if t["org_name"] == org_name and t["filled"] and t["prov"] == prov
                and t["parent"].get("n") == parent_name and (t["org"].get("u") or "").strip()]
        srcs = list(dict.fromkeys(same + srcs))[:3]
        if srcs:
            items.append(((parent_name, org_name, prov), [t for t in ts if not t["filled"]], srcs))
    print(f"S3 互链组: {len(items)}")
    if limit:
        items = items[:limit]
    filled = 0

    def work(item):
        key, ts, srcs = item
        local = 0
        for su in srcs:
            h = fetch_cached(su)
            if not h:
                continue
            links = extract_links(h, su)
            for t in ts:
                if t["filled"]:
                    continue
                for txt, link in links:
                    if not match_link(txt, link, t, allow_pure=True):
                        continue
                    ok, note = valid_candidate(t, link, txt, strict=False)
                    if not ok:
                        continue
                    src = f"来源:同级同系统官网({su})互链 HTML 提取+title验证({note})"
                    if apply_fill(reg, t, link, src, "L2", dup_names):
                        local += 1
                    break
        return local

    with ThreadPoolExecutor(int(os.environ.get("P223_CONC", "6"))) as ex:
        for item, n in zip(items, ex.map(work, items)):
            filled += n
            st.setdefault("s3", {})["|".join(item[0])] = f"ok:{n}"
            if n:
                print(f"  S3 {item[0]} -> {n}")
    print("S3 filled:", filled)
    return filled


# ── S4 SERP 兜底 ──────────────────────────────────────────
_serp_lock = threading.Lock()


def serp(q):
    """SERP 抓取：每线程独立 Session（http_client 单例非线程安全——p213 教训）。
    先直连、失败退隧道代理——百度对隧道出口 IP 返回 227 字节验证页
    （p204 实测），故代理只作兜底。"""
    url = f"https://www.baidu.com/s?wd={urllib.parse.quote(q)}&rn=10"
    for proxy in (None, PROXY):
        try:
            kw = {"proxies": proxy} if proxy else {}
            r = _session().get(url, timeout=15, verify=False, **kw)
            if r.status_code == 200 and len(r.text) > 20000:
                return r.text
        except Exception:
            continue
    return None


def _s4_q(t):
    """SERP 检索词（与查询时构造保持一致，用于 state 去重推进）。"""
    pn = t["parent"].get("n", "")
    return f"{t['prov']}{'' if pn == t['prov'] else pn}{t['county'].get('n', '')}{t['org_name'][1:]}"


S4_BAD_DOM = ("baidu.com", "weixin", "weibo", "people.com.cn", "xinhuanet", "news.cn",
              "cctv.com", "mzfzw", "qq.com", "163.com", "sohu.com", "chinacourt.org",
              "npc.gov.cn", "cppcc.gov.cn", "ccdi.gov.cn", "spp.gov.cn", "court.gov.cn")


def _s4_probe(t):
    """网络+校验（线程内完成）；返回 (t, url, note) 或 None。写库留给主线程。"""
    county, org_name = t["county"], t["org_name"]
    h = serp(_s4_q(t))
    if not h:
        return (t, "__serpfail__", "")
    cands = []
    for u in re.findall(r'mu="(https?://[^"]+)"', h):
        dom = urlparse(u).netloc.lower()
        if any(b in dom for b in S4_BAD_DOM) or not host_ok(u):
            continue
        cands.append(u)
        if len(cands) >= 6:
            break
    county_host = urlparse(county.get("u") or "").netloc.lower().replace("www.", "")
    for u in cands:
        dom = urlparse(u).netloc.lower()
        same_portal = bool(county_host) and dom.replace("www.", "") == county_host
        # 本县政府门户上的机构频道页（/columns/<uuid>/）也算官方入口，
        # 但域名特征规则不适用——由 title 双验兜底（S2 同口径）。
        if not same_portal and not re.search(ORG5[org_name]["feat"], dom, re.I):
            continue
        ok, note = valid_candidate(t, u, "")
        if not ok:
            continue
        return (t, u, note)
    return (t, None, "")


def run_s4(tasks, reg, dup_names, st, limit=None):
    seen = st.setdefault("s4", {})
    retry = os.environ.get("P223_S4_RETRY") == "1"   # 默认跳过已查过的，保证多轮推进
    pending = [t for t in tasks if not t["filled"]]
    if not retry:
        # 已明确查过无果（miss）的跳过；serp-fail 下轮重试
        pending = [t for t in pending if seen.get(_s4_q(t)) != "miss"]
    pending.sort(key=lambda t: (0 if t["parent"].get("l") == "省" else 1,
                                ORG_ORDER.index(t["org_name"])))
    if limit:
        pending = pending[:limit]
    workers = int(os.environ.get("P223_S4_WORKERS", "4"))
    print(f"S4 SERP 待查: {len(pending)}（{workers} 并发）")
    filled = 0
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(workers) as ex:
        for t, u, note in ex.map(_s4_probe, pending):
            q = _s4_q(t)
            if u == "__serpfail__":
                seen[q] = "serp-fail"
                continue
            got = False
            if u and apply_fill(reg, t, u, f"来源:SERP线索+title严格验证({note})",
                                "L3", dup_names):
                filled += 1
                got = True
                print(f"  S4 {q} -> {u[:76]}")
            seen[q] = "hit" if got else "miss"
    print("S4 filled:", filled)
    return filled

    return filled


# ── 主流程 ─────────────────────────────────────────────────
def main():
    tree = json.load(open(TREE_F, encoding="utf-8"))
    reg = json.load(open(REG_F, encoding="utf-8"))
    st = {}
    if os.path.exists(STATE_F):
        try:
            st = json.load(open(STATE_F, encoding="utf-8"))
        except Exception:
            st = {}

    blk, tasks = collect(tree)
    missing = [t for t in tasks if not t["filled"]]
    print(f"县级五系统缺口任务: {len(missing)} / 全部 {len(tasks)}")
    prov_map = {p["n"]: p for p in blk["ks"]}
    ALL_PROV_BASES.update(prov_base(x) for x in prov_map if prov_base(x))
    # 重名县区（跨省）——title 校验需市/省上下文
    name_prov = {}
    for t in tasks:
        name_prov.setdefault(t["county"].get("n", ""), set()).add(t["prov"])
    dup_names = {n for n, ps in name_prov.items() if len(ps) > 1}
    # 全国市名基底（门户错配检测）
    all_city_bases = set()
    for t in tasks:
        p = t["parent"]
        if p.get("l") in ("市", "地级区", "省"):
            all_city_bases.add(geo_base(p.get("n", "")))
    # 同省其他市名（title 反串校验）
    city_bases = {}
    for t in tasks:
        p = t["parent"]
        if p.get("l") in ("市", "地级区"):
            city_bases.setdefault(t["prov"], set()).add(geo_base(p.get("n", "")))
    for t in tasks:
        p = t["parent"]
        cb = geo_base(p.get("n", ""))
        t["dup"] = t["county"].get("n") in dup_names
        t["siblings"] = sorted(x for x in city_bases.get(t["prov"], set())
                               if x and x != cb)

    strategies = (os.environ.get("P223_STRATEGY") or "S1,S2,S3,S4").split(",")
    filled = 0
    if "S1" in strategies:
        filled += run_s1(tasks, reg, dup_names, st, prov_map,
                         int(os.environ.get("P223_S1_LIMIT", "0")) or None)
    if "S2" in strategies:
        filled += run_s2(tasks, reg, dup_names, st, all_city_bases,
                         int(os.environ.get("P223_S2_LIMIT", "0")) or None)
    if "S3" in strategies:
        filled += run_s3(tasks, reg, dup_names, st,
                         int(os.environ.get("P223_S3_LIMIT", "0")) or None)
    if "S4" in strategies:
        filled += run_s4(tasks, reg, dup_names, st,
                         int(os.environ.get("P223_S4_LIMIT", "0")) or None)

    if not DRY:
        today_dir = os.path.join(ROOT, "backups", TODAY)
        os.makedirs(today_dir, exist_ok=True)
        ts = datetime.datetime.now().strftime("%H%M%S")
        shutil.copy2(TREE_F, os.path.join(today_dir, f"tree_before_p223_{ts}.json"))
        shutil.copy2(REG_F, os.path.join(today_dir, f"registry_before_p223_{ts}.json"))
        _atomic(tree, TREE_F)
        _atomic(reg, REG_F)
    if not DRY:
        _atomic(st, STATE_F)
    print(f"p223 完成: 填充 {filled}{'（DRY 未写库）' if DRY else ''}")


if __name__ == "__main__":
    main()
