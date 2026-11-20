#!/usr/bin/env python3
"""p250 县级政府部门名录 — 从「政府信息公开 → 法定主动公开内容 → 组织机构」抽部门清单

用户口径（2026-11-19）：
  「政府信息公开 --》 法定主动公开内容 --》 组织机构 就是我需要的内容」
  「存在分页，采集完毕，然后 清洗，删去冗余内容，最后去重」
  「删去机构职能几个字就是我想要的内容了」

输入：zzjg_county.json（p248 已采到的县级「组织机构」栏目页 URL，2338 县）
输出：county_depts.json  {key: {u, method, pages, depts:[{n,u,c}], ...}}

两阶段：
  static — curl_cffi 直抓，抽同站部门锚点（实测约 75% 的县首屏静态可抽）
  render — 静态无产出的县走 9222 常驻浏览器渲染 + 逐页点击分页
           （云南统一平台 `/{县}rmzf/cXXXX/pc/list.html`：HTML 132KB 但列表靠
            POST /u/search/list/channel/... 加载，静态只有空壳；
            分页 DOM 是 `<a class="num" data-page="N">`，点它换页）

清洗规则：
  1. 剥尾部冗余词（机构职能/机构职责/职能机构/职能职责及分工/组织机构/机构设置/
     机构简介/主要职责/内设机构/职责分工/… 最长优先、循环剥）
  2. 只留同站链接 —— 实测区分本地部门与页面上的「上级/外站」链接的唯一可靠信号：
     松岭区页里的「省教育厅」指向 jyt.hlj.gov.cn、「发展和改革委员会」指向
     drc.hlj.gov.cn，都是省站；顺德区页里的「个人中心」指向 gdzwfw.gov.cn。
  3. 剔除导航噪声（网站地图/联系我们/无障碍/首页/登录…）
  4. 按清洗后名称去重（同一部门的 `XX局机构职责` / `XX局机构职能` 合并为一条）

用法：
  cd data && uv run python p250_county_depts.py --phase static --workers 8
  cd data && uv run python p250_county_depts.py --phase render --workers 2
  cd data && uv run python p250_county_depts.py --report
  --only 云龙县 / --prov 云南省 / --limit N / --force（重采已完成）
  --keys-file K.txt（只跑列出的 key，配合 p248 回炉低产县）
  --seeds（只跑 county_depts_seed.json 里人工核验的入口页）

2026-11-19 复盘：入口 URL 本身不是部门清单时（公开目录/单篇公文/企业信息公示），
渲染再多次也抽不出部门——`--phase render` 对这类县 100 个县零产出。正解是先让
p248 的 `xxgkpage` 阶段换到正确入口（政府信息公开→法定主动公开内容→组织机构），
再用 `--force --keys-file` 重抽本文件。
"""
import argparse
import json
import os
import re
import signal
import subprocess
import sys
import time
from datetime import date
from urllib.parse import urljoin, urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import p246_zzjg_pages as P  # noqa: E402  复用统一获取层/同站判定

IN_F = os.environ.get("P250_IN") or os.path.join(HERE, "zzjg_county.json")
OUT_F = os.environ.get("P250_OUT") or os.path.join(HERE, "county_depts.json")
# 人工核验过的入口页（用户逐站分析产物），优先级高于自动候选
SEED_F = os.path.join(HERE, "county_depts_seed.json")


def load_seeds():
    if not os.path.exists(SEED_F):
        return {}
    try:
        return json.load(open(SEED_F, encoding="utf-8")).get("seeds") or {}
    except Exception:
        return {}

TODAY = date.today().isoformat()

# ── 清洗词表（长词在前，循环剥离直到不再变化）─────────────────────────────
SUFFIXES = [
    "职能配置、内设机构和人员编制规定", "职能配置内设机构和人员编制规定",
    "职能配置、内设机构规定", "职能配置和内设机构规定",
    "职能配置内设机构规定", "职能配置、内设机构", "职能配置和内设机构",
    "职能配置内设机构", "职能配置",
    "主要职责内设机构和人员编制规定", "职能职责及分工", "职责分工及联系方式",
    "机构职能配置", "主要职责内设机构", "内设机构及职责",
    "机构职能", "机构职责", "职能机构", "组织机构", "机构设置", "机构简介",
    "机构概况", "机构介绍", "机构信息", "机构编制", "机关简介", "机关职能",
    "内设机构", "工作职责", "工作职能", "职责分工", "主要职责", "主要职能",
    "职能介绍", "职能职责", "单位职责", "单位职能", "部门职责", "部门职能",
    "联系方式", "职责", "职能", "机构", "简介", "概况", "设置", "分工",
]

# 长文章标题里截出部门名（六合区「机构」栏是《XX局职能配置和内设机构规定》
# 这类公文标题列表，不是部门入口）。截断前须满足：标记后跟的是公文语汇，
# 否则「五郭店乡内设机构-行政综合服务中心」会被错切成「五郭店乡」。
MARK = re.compile(r"(职能配置|主要职责|职能职责|机构职能|机构设置|职责配置|"
                  r"工作职责|内设机构和人员编制|内设机构|机构改革)")
DOC_TAIL = re.compile(r"规定|通知|办法|意见|方案|细则|编制|职责|分工|成员|班子|"
                      r"信息|简介|概况|说明|一览|^$|[、，,]")
# 「XX局职能配置…-叶城县人民政府」：破折号后是站点名，不是机构名的一部分
SITE_TAIL = re.compile(r"^(.{4,40}?)[-_](.{2,20}(?:人民政府|政府|门户网站|网站|政府网))$")

# 导航/装饰噪声（整条丢弃）
NOISE = re.compile(
    r"网站地图|联系我们|无障碍|登录|注册|首页|上一页|下一页|返回|更多|"
    r"中央部门网站|省级政府网站|市政府网站|县区政府网站|区政府网站|友情链接|"
    r"主办单位|承办单位|版权|ICP备|公网安备|网站声明|网站标识|帮助中心|"
    r"个人中心|政务服务网|智能问答|长者版|无障碍版|简繁|繁体|English|"
    r"微博|微信|手机版|APP下载|收藏|打印|分享|关闭|"
    # 栏目/平台类（不是机构）：实测「行政执法公示平台」「信息公开专栏」进过列表
    r"公示平台|公开平台|服务平台|平台|专栏|专题|栏目|网站|客户端|新媒体|矩阵|"
    r"下辖|各乡镇|各镇|各部门|各街道|各委办局|"
    r"法治政府|服务型政府|责任政府|阳光政府|"
    r"新闻中心|资讯中心|新闻发布厅|新闻发布|数说|"
    # 公文标题（「关于调整XX局领导分工的通知」）不是机构条目
    r"^关于|通知$|公告$|公示$|批复$"
)

# 只有行政区通名、没有机构名的残片（`乡人民政府` / `区政府` / `县政府`），
# 多为锚文本被截断或站点导航条
BARE_GOV = re.compile(r"^(省|市|州|县|区|旗|乡|镇|街道)?(人民)?政府$")

# 部门名合法尾巴（清洗后必须命中其一）
TAIL = re.compile(
    r"(局|委员会|办公室|管委会|指挥部|管理局|服务中心|中心|部|厅|院|所|站|队|署|"
    r"协会|联合会|总工会|团委|妇联|残联|工商联|红十字会|"
    r"集团|公司|学校|学院|医院|卫生院|馆|台|社|银行|政府|镇|乡|街道|"
    r"支队|大队|分局|派出所)$"
)

# 明显属于上级机关 / 非本级（同站判定漏网时的第二道闸）
UPPER = re.compile(r"^(省|自治区|国家|中央|国务院)")

PARTY = re.compile(
    r"^(党委|党工委|区委|县委|市委|党组|纪委|监委|纪检|组织部|宣传部|统战部|"
    r"政法委|政法委员会|机关工委|编办|机构编制委员会|老干部局|巡察)"
)

TOWN = re.compile(r"(人民政府|镇政府|乡政府|街道办事处|街道|镇|乡)$")

# 2026-11-19 网页展示巡检发现的三类脏数据（县级名录里真实出现过）：
#   1. 面包屑污染：海南 7 个县把**省厅**采成了本县部门，锚文本是
#      `&gt;海南省公安厅`（页面导航条「省级部门」混进部门列表）——先剥前缀，
#      再由 county_guard_depts 按省名前缀拒掉（用户红线：不能采成上级部门）；
#   2. HTML 属性残片：`陶河镇"tabindex="-1">陶河镇`（锚文本里带属性串）；
#   3. 栏目占位名：`默认主站`（导航 select 的默认项）、`信息公开查阅场所`。
BREAD_PREFIX = re.compile(r"^(?:&gt;|&lt;|&amp;gt;|&amp;lt;|>|»|›)+")
HTML_ATTR = re.compile(r'^[^"<>]{0,24}"[^<>]*>\s*')
PLACEHOLDER = re.compile(
    r"^(?:默认主站|主站|网站首页|首页|政府|人民政府|政务公开|政府信息公开|"
    r"信息公开|部门|机构|组织机构|部门平台链接|信息公开查阅场所|"
    r"信息公开阅读场所|信息公开受理/查阅场所|政务公开查阅场所)$")


def repair_name(n):
    """已落盘名称的修复（reclean 用）：只剥面包屑/属性残片/实体，不重跑词尾规则。

    2026-11-19：改用 html.unescape 统一解实体。此前只处理 &gt;/&amp;gt;，
    `&ensp;海南省商务厅` 因前缀不是「海南省」绕过了县级闸门，把 5 个省厅
    采成了文昌市部门（用户红线：不能采成上级单位）。
    """
    import html as _html
    n = _html.unescape(n or "")
    n = n.replace("​", "").replace("﻿", "")
    n = BREAD_PREFIX.sub("", n)
    n = HTML_ATTR.sub("", n)
    n = re.sub(r'"?[A-Za-z-]+="[^"]*"', "", n)
    return re.sub(r"[\s   ]+", "", n)


def finalize_depts(key, depts):
    """落盘前统一收口（抽取与 reclean 共用同一套口径）。

    - 占位名（默认主站/查阅场所）不是部门；
    - `XX县人民政府`/`XX县政府` 是该县本体，门户挂在县节点上，不算部门；
    - 括号被截断的补右括号（`江安县委办公室（县档案局` → 补 `）`）；
    - URL 内空格去掉（四川平台 `deptCode=…-9 &areaCode=`）；
    - 同 URL 语义重复（`扎兰屯市人民政府办公室` vs `政府办公室`）只留更完整的。
    """
    parts = key.split("|")
    county = parts[-1] if parts else ""
    self_names = {county + "人民政府", county + "政府"} if county else set()
    norm = []
    for d in depts:
        n = d.get("n") or ""
        if not n or PLACEHOLDER.match(n) or n in self_names:
            continue
        if n.count("（") > n.count("）"):
            n += "）"
        u = re.sub(r"\s+", "", d.get("u") or "")
        norm.append({**d, "n": n, "u": u})
    keep_by_url = {}
    out = []
    for d in norm:
        cmp_n = d["n"].replace("人民政府", "政府")
        prev = keep_by_url.get(d["u"])
        if prev is not None:
            pn = prev["n"].replace("人民政府", "政府")
            if cmp_n in pn:                     # 新条目是旧条目的残片 → 丢新的
                continue
            if pn in cmp_n:                     # 旧条目是残片 → 换成新的
                out.remove(prev)
        keep_by_url[d["u"]] = d
        out.append(d)
    seen, uniq = set(), []
    for d in out:
        if d["n"] in seen:
            continue
        seen.add(d["n"])
        uniq.append(d)
    return uniq


# ── 名称清洗 ─────────────────────────────────────────────────────────────
def clean_name(raw):
    n = re.sub(r"<[^>]+>", "", raw or "")
    n = repair_name(n)
    n = re.sub(r"&nbsp;|\s+", "", n)
    n = re.sub(r"^[·•\-—_>»\|\s、，,\.]+|[·•\-—_>«\|\s、，,\.]+$", "", n)
    sm = SITE_TAIL.match(n)
    if sm:
        n = sm.group(1)
    changed = True
    while changed:
        changed = False
        for s in SUFFIXES:
            if n.endswith(s) and len(n) > len(s):
                n = n[:-len(s)]
                changed = True
                break
    return n


def shorten_by_mark(name, locals_=()):
    """公文标题截出部门名——**仅当原名本身不成立、或标记后是公文语汇**时才截。

    「叶城县财政局职能配置、内设机构和人员编制规定」不是合法机构名（尾巴是
    「规定」）→ 截到「叶城县财政局」；而「五郭店乡内设机构-行政综合服务中心」
    标记后是实体名（不是公文语汇），截成「五郭店乡」反而错。
    """
    m = MARK.search(name)
    if not m or m.start() < 3:
        return name
    if name_ok(name, locals_) and not DOC_TAIL.search(name[m.end():]):
        return name
    alt = name[:m.start()]
    return alt if name_ok(alt, locals_) else name


def classify(name):
    if PARTY.search(name):
        return "party"
    if TOWN.search(name):
        return "town"
    return "gov"


def local_tokens(key):
    """`县|省|市|云龙县` → {'云龙县','云龙'}；用于放行「国家税务总局云龙县税务局」
    这类以「国家」开头、实为本级机构的条目，同时仍挡掉页面上的上级机关链接。"""
    name = key.split("|")[-1]
    toks = {name}
    base = base_of(name)
    if len(base) >= 2:
        toks.add(base)
    return toks


def base_of(name):
    """行政名 → 地名基底：迪庆藏族自治州→迪庆、巍山彝族回族自治县→巍山、云龙县→云龙。"""
    n = re.sub(r"(自治州|自治县|自治旗|自治区|林区|特区|矿区|新区|县|市|区|旗|盟)$",
               "", name or "")
    for _ in range(4):
        m = re.search(r"(?:[一-龥]{1,3}族)+$", n)
        if not m or m.start() < 1:
            break
        n = n[:m.start()]
    return n


def county_guard_depts(key, depts):
    """县级部门名录的「采成上级」闸门（用户红线：不能把上级单位的部门采成本县的）。

    实测 `县|吉林省|四平市|铁西区` 的组织机构页 `txq.siping.gov.cn/qzf/zfjg/`
    是本区站点，但页面上列的是**四平市**各部门（四平市发展改革委…）——同站判定
    挡不住，只能按名称前缀判：

      含本县名             → 收（`大理州生态环境局云龙分局` 是本地派出机构）
      以所属市/省名开头     → 拒（上级部门）
      其余（无地名前缀短名） → 收（`司法局` / `发展和改革局` 这类是本级简称）
    """
    parts = key.split("|")
    if len(parts) < 4:
        return depts
    prov, city, name = parts[1], parts[2], parts[3]
    toks = local_tokens(key)
    city_b = base_of(city)
    prov_b = base_of(prov)
    # 直辖市：省名=市名（重庆市|重庆市|巫溪县），只需一遍
    upper = {b for b in (city_b, prov_b) if len(b) >= 2}
    out = []
    for d in depts:
        n = d.get("n") or ""
        if any(t in n for t in toks):
            out.append(d)
            continue
        if any(n.startswith(b) for b in upper):
            continue
        out.append(d)
    return out


def _tail_ok(name):
    """合法尾巴判定。合署名「XX局（XX委员会）」以括号收尾，括号内或括号前
    命中部门后缀即算合法——finalize_depts 会自动补右括号，若不兼容会让
    reclean 第二次运行时把上轮已闭合的条目误删（2026-11-19 实测 11 条）。"""
    if TAIL.search(name):
        return True
    if name.endswith("）"):
        i = name.rfind("（")
        if i > 0 and (TAIL.search(name[i + 1:-1]) or TAIL.search(name[:i])):
            return True
    return False


def name_ok(name, locals_=()):
    """单条名称合规性（抽取与 reclean 共用同一套口径）。"""
    if not (3 <= len(name) <= 32):
        return False
    if NOISE.search(name) or BARE_GOV.match(name):
        return False
    if UPPER.match(name) and not any(t in name for t in locals_):
        return False
    return _tail_ok(name)


def extract_depts(html, base_url, locals_=()):
    """HTML → [{n,u,c}]；已按清洗名去重，保留首个 URL。"""
    seen = {}
    for m in re.finditer(r'<a\b[^>]*href="([^"]+)"[^>]*>([\s\S]{0,160}?)</a>', html, re.I):
        href, raw = m.group(1).strip(), m.group(2)
        if not href or href.startswith(("javascript:", "#", "mailto:", "tel:")):
            continue
        name = shorten_by_mark(clean_name(raw), locals_)
        if not name_ok(name, locals_):
            continue
        u = urljoin(base_url, href)
        if not P.same_site(u, base_url):
            continue
        if urlparse(u).scheme not in ("http", "https"):
            continue
        if name in seen:
            continue
        seen[name] = {"n": name, "u": u, "c": classify(name)}
    return list(seen.values())


# ── 输出 ─────────────────────────────────────────────────────────────────
def load_out():
    if os.path.exists(OUT_F):
        try:
            return json.load(open(OUT_F, encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_out(d):
    tmp = OUT_F + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    os.replace(tmp, OUT_F)


def _child_init():
    """子进程：给所有 socket 一个默认超时，彻底杜绝 SYN_SENT 无限挂起。"""
    import socket
    socket.setdefaulttimeout(25)


RESULT_MARK = "@@RESULT@@"


def run_one_subproc(key, task, timeout):
    """在独立子进程里跑一个县，硬超时 killpg。

    为什么不用进程池：`ProcessPoolExecutor.wait()` 第一步要给每个 future 的
    `_condition` 加锁，实测主线程会永久停在 `_PyMutex_LockTimed` 上——带
    timeout 的等待根本没机会生效，整批挂死（2026-11-19 连续复现 3 次）。
    `mp.Pool.terminate()` 之后 `join()` 同样会被卡在系统调用的子进程拖死。
    每县一个 `Popen` + `communicate(timeout)` 是最土但绝不会卡住的写法：
    阻塞发生在内核 poll 上，超时直接 SIGKILL 整个进程组。
    """
    cmd = [sys.executable, os.path.abspath(__file__), "--worker", key, "--task", task]
    try:
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             cwd=HERE, start_new_session=True)
    except Exception as e:
        return key, None, f"spawn失败:{type(e).__name__}"
    try:
        out_b, err_b = p.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(p.pid, signal.SIGKILL)
        except Exception:
            try:
                p.kill()
            except Exception:
                pass
        try:
            p.communicate(timeout=10)
        except Exception:
            pass
        return key, None, "timeout"
    txt = out_b.decode("utf-8", "replace")
    idx = txt.rfind(RESULT_MARK)
    if idx < 0:
        err = err_b.decode("utf-8", "replace").strip().splitlines()
        tail = err[-1][:100] if err else f"exit={p.returncode}"
        return key, None, "noout:" + tail
    try:
        obj = json.loads(txt[idx + len(RESULT_MARK):])
        return obj.get("key") or key, obj.get("rec"), "ok"
    except Exception as e:
        return key, None, f"badjson:{type(e).__name__}"


# ── 阶段 1：静态 ─────────────────────────────────────────────────────────
def do_static(item):
    """worker（子进程）用：返回 (key, rec|None)，不碰共享内存。"""
    key, rec = item
    u = rec.get("u") or ""
    if not u:
        return key, None
    html, method = P.fetch(u, timeout=20)
    if not html:
        return key, None
    depts = finalize_depts(key, county_guard_depts(
        key, extract_depts(html, u, local_tokens(key))))
    return key, {
        "u": u,
        "method": "static/" + (method or ""),
        "pages": 1,
        "pages_total": None,
        "depts": depts,
        "collected_at": TODAY,
    }


# ── 阶段 2：渲染 + 分页 ──────────────────────────────────────────────────
NEXT_TEXTS = ("下一页", "下页", "后一页")
MAX_PAGES = 15


def _click_page(page, no):
    for sel in (f'a.num[data-page="{no}"]',
                f'[data-page="{no}"]',
                f'a:text-is("{no}")'):
        try:
            el = page.query_selector(sel)
            if el and el.is_visible():
                el.click(timeout=4000)
                return True
        except Exception:
            pass
    return False


def _click_next(page):
    for sel in ('a.next', 'a:has-text("下一页")', 'a:has-text("下页")',
                'a:has-text("后一页")', 'a[title="下一页"]'):
        try:
            el = page.query_selector(sel)
            if el and el.is_visible():
                el.click(timeout=4000)
                return True
        except Exception:
            pass
    try:
        for t in NEXT_TEXTS:
            el = page.get_by_role("link", name=t).first
            if el and el.is_visible():
                el.click(timeout=4000)
                return True
    except Exception:
        pass
    return False


def do_render(item, deadline_s=90):
    from util.cdp_util import cdp_page

    key, rec = item
    u = rec.get("u") or ""
    if not u:
        return key, None
    deadline = time.time() + deadline_s
    got = {}
    pages = 0
    toks = local_tokens(key)
    try:
        with cdp_page() as (page, _ctx):
            page.goto(u, wait_until="domcontentloaded", timeout=45000)
            time.sleep(2.5)
            for no in range(1, MAX_PAGES + 1):
                if time.time() > deadline:
                    break
                pages = no
                base = page.url
                for d in extract_depts(page.content(), base, toks):
                    got.setdefault(d["n"], d)
                if no >= MAX_PAGES:
                    break
                moved = _click_page(page, no + 1) or _click_next(page)
                if not moved:
                    break
                time.sleep(2.2)
    except Exception as e:
        sys.stderr.write(f"   ⚠️ {key} render 异常: {type(e).__name__}: {str(e)[:80]}\n")
        if not got:
            return key, None
    return key, {
        "u": u,
        "method": "render/pager",
        "pages": pages,
        "pages_total": None,
        "depts": finalize_depts(key, county_guard_depts(key, list(got.values()))),
        "collected_at": TODAY,
    }


# ── 主流程 ───────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", default="all", choices=["static", "render", "all"])
    ap.add_argument("--workers", type=int, default=0)
    ap.add_argument("--only", default="")
    ap.add_argument("--keys-file", default="",
                    help="只处理文件里的 key（每行一个，与 zzjg_county.json 的 key 完全相等）")
    ap.add_argument("--prov", default="")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--min-depts", type=int, default=3)
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--reclean", action="store_true",
                    help="不联网，只对已有结果重跑县级闸门/去重（采成上级的条目剔除）")
    ap.add_argument("--seeds", action="store_true",
                    help="只采 county_depts_seed.json 里人工核验过的入口页")
    args = ap.parse_args()

    src = json.load(open(IN_F, encoding="utf-8"))
    out = load_out()

    if args.reclean:
        dropped = 0
        for k, v in out.items():
            before = len(v.get("depts") or [])
            toks = local_tokens(k)
            fixed = []
            for d in (v.get("depts") or []):
                n = repair_name(d.get("n") or "")
                # 归类随 TOWN/PARTY 规则变化（2026-11-19 补「XX镇/XX乡」形态），
                # reclean 时一并重算，前端据此显示「乡镇/街道」「党委机构」标注
                d = {**(d if n == d.get("n") else {**d, "n": n}), "c": classify(n)}
                if name_ok(n, toks):
                    fixed.append(d)
            kept = finalize_depts(k, county_guard_depts(k, fixed))
            v["depts"] = kept
            dropped += before - len(kept)
        save_out(out)
        print(f"reclean: 剔除 {dropped} 条（上级部门/栏目噪声/重复）")
        if args.phase in ("static", "render") or args.force:
            pass          # 显式要求继续采集
        else:
            return        # 纯离线收口，别顺带联网重采（2026-11-19 误触发）

    if args.report:
        tot = len(out)
        dist = {}
        for k, v in out.items():
            n = len(v.get("depts") or [])
            dist[n] = dist.get(n, 0) + 1
        ok = [v for v in out.values() if len(v.get("depts") or []) >= args.min_depts]
        all_depts = sum(len(v.get("depts") or []) for v in out.values())
        print(f"已产出县数: {tot} / 待采 {len(src)}")
        print(f"≥{args.min_depts} 部门的县: {len(ok)}")
        print(f"部门条目总数(去重前): {all_depts}")
        print("按产量分档:", dict(sorted(dist.items())[:8]), "...",
              dict(sorted(dist.items())[-5:]))
        return

    keys = sorted(src)
    if args.only:
        keys = [k for k in keys if args.only in k]
    if args.keys_file:
        want = {ln.strip() for ln in open(args.keys_file, encoding="utf-8")
                if ln.strip() and not ln.startswith("#")}
        keys = [k for k in keys if k in want]
    if args.prov:
        keys = [k for k in keys if k.startswith("县|" + args.prov)] or \
               [k for k in keys if args.prov in k]

    def need(k, floor, task="render"):
        if args.force or k not in out:
            return True
        if task == "static":
            # 静态已试过就别再试：重试不会让 JS 壳变出内容，交渲染阶段
            return False
        return len(out[k].get("depts") or []) < floor

    def run_phase(task, todo, w, per_item_timeout, label, tick=20):
        """每县一个子进程，父进程只等 `communicate(timeout)`。

        线程杀不掉：实测某县门户解析到 202.103.252.132 后 TCP 永远 SYN_SENT，
        线程池会整批挂死（2026-11-19 实况）；`ProcessPoolExecutor.wait()`
        进 `_AcquireFutures` 就卡死在 future 的条件锁上，timeout 形同虚设，
        连续复现 3 次。子进程 + killpg 是这套环境下唯一稳定收敛的调度。
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        t0 = time.time()
        done = timed = 0
        live = []
        with ThreadPoolExecutor(max_workers=w) as ex:
            futs = {ex.submit(run_one_subproc, k, task, per_item_timeout): k
                    for k in todo}
            for f in as_completed(futs):
                k = futs[f]
                done += 1
                try:
                    key, rec, status = f.result()
                except Exception as e:
                    key, rec, status = k, None, f"{type(e).__name__}"
                if rec:
                    out[key] = rec
                elif status == "timeout":
                    timed += 1
                    live.append(k)
                if done % tick == 0:
                    hit = sum(1 for v in out.values()
                              if len(v.get("depts") or []) >= args.min_depts)
                    print(f"   {done}/{len(todo)}  命中 {hit}  超时 {timed}  "
                          f"{time.time()-t0:.0f}s", flush=True)
                    save_out(out)
        save_out(out)
        if live:
            print(f"   {label} 超时 {timed} 个（{per_item_timeout}s/县），"
                  f"如 {', '.join(live[:3])}")
        return done

    if args.seeds:
        seeds = load_seeds()
        todo = [k for k in seeds
                if args.force or args.only or
                len((out.get(k) or {}).get("depts") or []) < args.min_depts]
        if args.only:
            todo = [k for k in todo if args.only in k]
        print(f"[seeds] {len(todo)}/{len(seeds)} 个人工核验入口", flush=True)
        task = "render" if args.phase == "render" else "static"
        run_phase(task, todo, args.workers or 4,
                  180 if task == "render" else 90, "seeds", tick=5)
        save_out(out)
        return

    if args.phase in ("static", "all"):
        todo = [k for k in keys if need(k, args.min_depts, "static")]
        if args.limit:
            todo = todo[:args.limit]
        w = args.workers or 10
        print(f"[static] {len(todo)} 县，{w} 并发", flush=True)
        run_phase("static", todo, w, 75, "static")
        save_out(out)

    if args.phase in ("render", "all"):
        todo = [k for k in keys if need(k, args.min_depts, "render")]
        if args.limit:
            todo = todo[:args.limit]
        w = args.workers or 2
        print(f"[render] {len(todo)} 县，{w} 并发（9222 常驻，不新起浏览器）",
              flush=True)
        run_phase("render", todo, w, 180, "render", tick=20)
        save_out(out)

    hit = sum(1 for v in out.values() if len(v.get("depts") or []) >= args.min_depts)
    print(f"完成。已产出 {len(out)} 县，其中 ≥{args.min_depts} 部门 {hit} 县")
    print(f"输出: {OUT_F}")


def worker_mode(key, task):
    """子进程入口：跑一个县，把结果以标记行打到 stdout。"""
    _child_init()
    seed = load_seeds().get(key)
    src = json.load(open(IN_F, encoding="utf-8"))
    rec = seed or src.get(key)
    if not rec:
        out_key, res = key, None
    elif task == "render":
        dl = float(os.environ.get("P250_RENDER_DEADLINE", "55"))
        out_key, res = do_render((key, rec), deadline_s=dl)
    else:
        out_key, res = do_static((key, rec))
    if seed and res:
        # 人工核验入口：方法名标 manual，来源备注带过去便于回溯
        res["method"] = "manual/" + str(res.get("method", "")).split("/")[-1]
        if seed.get("m"):
            res["seed_m"] = seed["m"]
    sys.stdout.write(RESULT_MARK + json.dumps({"key": out_key, "rec": res},
                                              ensure_ascii=False) + "\n")
    sys.stdout.flush()


if __name__ == "__main__":
    if "--worker" in sys.argv:
        i = sys.argv.index("--worker")
        wk = sys.argv[i + 1]
        wt = "render" if "--task" in sys.argv and \
            sys.argv[sys.argv.index("--task") + 1] == "render" else "static"
        worker_mode(wk, wt)
    else:
        main()
