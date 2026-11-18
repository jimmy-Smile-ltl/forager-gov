# -*- coding: utf-8 -*-
"""p246 省/市人民政府「组织机构类」栏目页 URL 采集（2026-11-18）。

目标：为 33 个省级 + 333 个地级市 **人民政府门户**（树中 k=人民政府、l∈{省,市}）
找到门户内的「机构/单位/企业/高校」类栏目页 URL。用户 2026-11-18 指令扩围：
**内部组织、内设部门、机构、直属企业、事业单位、公积金、高校 等等都算，尽可能全面**。

类别（KIND_RULES，按优先级）：机构设置 > 内设机构 > 直属单位 > 事业单位 >
直属企业 > 公积金 > 高校。同一门户可命中多类，全部记入 `links`，其中优先级
最高的作为主 URL（`u`）。

口径（与项目红线一致）：
- **只从门户自己的真实 HTML/渲染 DOM 里取链接**（首页导航、底部导航、JS 渲染后的
  导航、点击展开的菜单），不拼路径、不猜 URL、不走 SERP；
- 候选页必须**回抓验证**：机构类看标题/正文「机构职能/机构设置/内设机构/直属单位」
  特征 + 部门名计数；企事业/公积金/高校类看类别关键词 + 实体名计数；办事服务页
  （提取公积金/登记管理/招生考试…）一律拒收；
- 来源（锚文本、方式）逐条留痕。

阶段：
  1. static   —— smart_fetch(门户首页) 取真实 HTML，锚文本分类 + 逐候验证；
  2. render   —— 静态失败的走 CDP 9222 渲染首页（滚动触发懒加载）再提取；
  3. deep     —— 首页 → 政府信息公开/政务公开索引 → 机构栏目（上海/广州形态）；
  4. candrender —— 强锚点但落地页是 JS 列表：渲染候选页再验证；
  5. click    —— 渲染后仍无锚点的，按关键词点击导航元素，捕获跳转页再验证；
  6. extras   —— `--refresh-extras`：对已命中门户重扫首页，补扩围类别（增量并入）。

每站默认 75 秒预算（`--budget` 可调），超时即跳过——用户指令「不要在一个网站
耽误太多时间，遇到一直无法解决的，暂时跳过」。

产物：
  data/zzjg_pages.json   事实源（key = `<level>|<名称>`，
                         value = u/title/src/method/score/verified_at + links[]）
  data/p246_state.json   断点（已处理 key、失败原因），不入库
可选 `--sync-registry`：把结果写进 site_registry.json 的
`zzjg` / `zzjg_src` / `zzjg_verified_at` / `zzjg_links`。

用法：
  cd data
  uv run python p246_zzjg_pages.py --phase static --workers 6
  uv run python p246_zzjg_pages.py --phase render --workers 2
  uv run python p246_zzjg_pages.py --phase deep --retry-fail --workers 4
  uv run python p246_zzjg_pages.py --phase click  --workers 1
  uv run python p246_zzjg_pages.py --refresh-extras --workers 6   # 扩围补采
  uv run python p246_zzjg_pages.py --reaudit --workers 8          # 全量复验
  uv run python p246_zzjg_pages.py --sync-registry
"""
import argparse
import datetime
import html as html_lib
import json
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from urllib.parse import urljoin, urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "util"))
sys.path.insert(0, HERE)

TODAY = datetime.date.today().isoformat()
STATE_F = os.path.join(HERE, "p246_state.json")
OUT_F = os.path.join(HERE, "zzjg_pages.json")

# ── 栏目类别（2026-11-18 用户指令扩围：内部组织/内设部门/机构/直属企业/
#    事业单位/公积金/高校 都算，尽可能全面）────────────────────────────
# 顺序 = 优先级：同一门户有多个栏目时，第一个（机构设置）当主 URL。
KIND_RULES = [
    ("机构设置", re.compile(r"组织机构|机构设置|机构职能|政府机构|机构概况|"
                            r"组织架构|机构介绍|机构名录|工作机构|政府组成部门|"
                            r"部门机构|机构职责|机构编制|机构信息|党政机构|"
                            r"组织体系|机构列表|机关简介|机构简介|机关职能|"
                            r"政府组成机构|政府工作部门")),
    ("内设机构", re.compile(r"内设机构|内设部门|处室设置|部门设置|科室设置|内设科室")),
    ("直属单位", re.compile(r"直属单位|直属机构|直属事业单位|下属单位|下属机构|"
                            r"部门管理机构|直属特设机构")),
    ("事业单位", re.compile(r"事业单位|公共企事业单位|公共事业单位|事业机构")),
    ("直属企业", re.compile(r"直属企业|市属企业|省属企业|国有企业|出资企业|"
                            r"直属公司|国资国企|国企")),
    ("公积金", re.compile(r"住房公积金|公积金")),
    ("高校", re.compile(r"高等院校|高等学校|市属高校|高校|院校")),
]
KIND_ORDER = [k for k, _ in KIND_RULES]
KIND_BASE = {"机构设置": 10, "内设机构": 9, "直属单位": 8, "事业单位": 8,
             "直属企业": 8, "公积金": 7, "高校": 7}
# 通用兜底锚文本（无类别关键词时的弱线索）
TEXT_RULES = [
    ("机构", 5), ("部门", 4), ("组织", 3),
]
# 路径特征（含这些片段的 URL 加分）
PATH_RULES = [
    ("zzjg", 6), ("jgzn", 6), ("jgsz", 6), ("jgjs", 5), ("jigou", 5),
    ("szfjg", 5), ("zfjg", 4), ("bmjs", 4), ("org", 3), ("jgs", 3),
    ("sydw", 5), ("qy", 2), ("gjj", 6), ("gx", 2),
]
# 闭合标签带空格的写法「</a >」（青海/甘肃门户常见）会让 <a…>(.*?)</a> 贪婪吞掉
# 后面整段导航，锚文本变成超长串被跳过 —— 候选于是「凭空消失」（青海 机构职能 链接）。
ANCHOR_RE = re.compile(r"<a\b([^>]*)>(.*?)</a\s*>", re.S | re.I)

NEG_TEXT = re.compile(r"新闻|专题|解读|问答|意见|举报|信访|留言|招聘|采购|招标|"
                      r"领导活动|领导之窗|部门领导|领导简介|领导简历|领导分工|"
                      r"人事任免|公示|公告|政策|文件|下载|地图|无障碍|登录|"
                      r"预算|决算|三公经费|绩效|统计公报|年度报告|工作报告|"
                      r"报送|上报")
NEG_PATH = re.compile(r"/art/|/content_|/doc/|content\.|Item/|/\d{6}/|/detail|"
                      r"/ldzc/|/lddt/|/bmdt/|/xwzx/|/zwlb/|/xwdt/|/ldjs/|/news|/xw/|/zixun/|"
                      r"\.(pdf|docx?|xlsx?|zip|rar)(\?|$)", re.I)
NEG_TITLE = re.compile(r"领导|动态|要闻|新闻|会议|活动|简历|之窗")
VERIFY_TITLE = re.compile(r"机构职能|机构设置|组织机构|政府机构|机构概况|组织架构|"
                          r"内设机构|机构介绍|政府组成部门|工作机构|机构名录|部门机构|"
                          r"机构职责|机构编制|机构信息|机关简介|机构简介|机关职能|"
                          r"政府组成机构|政府工作部门")
# 正文大标题证据：大量门户栏目页 <title> 沿用站点模版（「XX市人民政府-中国长春」），
# 真正的栏目名在 h1/h2 里（长春政府机构页 h2=「政府组成机构」）
HEAD_RE = re.compile(r"<h[1-3][^>]*>(.*?)</h[1-3]>", re.S | re.I)
# 便民服务/专题页类别词：主标题命中即判定「这是服务名录，不是机构设置页」
SERVICE_TOKEN = re.compile(r"医疗机构|医疗卫生|医院|卫生院|诊所|学校|幼儿园|公交|地铁|"
                           r"供水|供电|燃气|供暖|景区|旅游|场馆|图书馆|博物馆|体育馆|"
                           r"公园|便民服务|办事指南|价格|收费|招生|考试|招聘|招标|采购|"
                           r"公积金提取|社保|医保查询|个人服务|法人服务|公共服务|"
                           r"主题服务|部门服务|办事服务|政务服务|部门办事|办事大厅|"
                           r"网上办事|服务大厅")
# 「部门领导 / 领导之窗」类页面的正文自证：p247 网站地图渠道曾把呼和浩特
# `/2022_zwgk/bumenlingdao/`（部门领导页，30+ 部门名）误判成机构目录页
LEADER_TOKEN = re.compile(r"部门领导|领导之窗|领导班子|领导简介|领导简历|领导分工|"
                          r"领导介绍|领导信息|负责人名单|领导之窗")
# 公文/决算/统计类页面：标题带这些词的一定不是机构目录页。2026-11-18 实锤——
# 桓仁满族自治县静态阶段把「XX县委组织部2025年度部门决算」当机构页收下
# （正文里部门名够多、评分够线）。这类单实体公文页一律按 doc-page 拒收。
DOC_TOKEN = re.compile(r"预决算|预算|决算|三公经费|绩效评价|绩效目标|年度报告|"
                       r"工作报告|中标|成交公告|采购公告|招标公告|采购结果|"
                       r"信息公开年度|依申请公开|统计公报|普查公报|审计结果")
DEPT_RE = re.compile(r"[一-龥]{2,12}(?:厅|局|委员会|办公室|委|办)")
# 企事业单位名录页的实体特征（中心/公司/集团/院校/医院…）
ENTITY_RE = re.compile(r"[一-龥]{2,16}(?:中心|公司|集团|研究院|设计院|学校|"
                       r"学院|大学|医院|馆|所|站|社|台)")
# 各类别的服务页/办事页特征：这些锚文本/标题不是「机构/单位名录」，一律不收
KIND_NEG = {
    "公积金": re.compile(r"提取|贷款|还款|缴存|办理|指南|查询|计算器|下载|小程序|网点|"
                         r"政策|法规|条例|办法|通知|公告|解读|决定|新闻"),
    "高校": re.compile(r"招生|考试|录取|成绩|报名"),
    "事业单位": re.compile(r"登记管理|年检|注销|设立登记"),
    "直属企业": re.compile(r"招聘|采购|招标"),
    "直属单位": re.compile(r"招聘|采购|招标"),
}
KIND_NEG_TITLE = {
    "公积金": re.compile(r"提取|申请|贷款|还款|缴存|查询|办理|指南|下载|计算|"
                         r"政策|法规|条例|办法|通知|公告|解读|决定|新闻|问答|服务"),
    "事业单位": re.compile(r"登记管理|年检|注销|设立"),
    "高校": re.compile(r"招生|考试|录取|成绩|报名"),
    "直属企业": re.compile(r"招聘|采购|招标"),
    "直属单位": re.compile(r"招聘|采购|招标"),
}
LIST_RE = re.compile(r"名录|目录|一览|列表|清单|名单|单位列表|机构列表")
ORG_PATH = re.compile(r"zzjg|jgzn|jgsz|jgjs|jigou|zfjg|szfjg|bmjs|jgm|"
                      r"jgbz|zfgzjg|jgxx|jgjj|jgms|jgs", re.I)


def log(*a):
    print(*a, flush=True)


# ── 目标清单（树内 省/市 人民政府） ─────────────────────────────────────
def load_targets():
    tree = json.load(open(os.path.join(HERE, "tree.json"), encoding="utf-8"))
    out = []

    def walk(n, path):
        for ch in n.get("ks") or []:
            p = path + [ch.get("n")]
            if ch.get("k") == "人民政府" and ch.get("l") in ("省", "市") and ch.get("u"):
                out.append(dict(
                    key=f"{ch.get('l')}|{ch.get('n')}",
                    level=ch.get("l"), name=ch.get("n"),
                    prov=(p[-2] if len(p) >= 2 else ""),
                    url=ch.get("u").strip(),
                ))
            walk(ch, p)

    walk(tree, [tree.get("n")])
    return out


def base_domain(host):
    """注册域近似：gov.cn 二级域算边界（www.sjz.gov.cn → sjz.gov.cn）。"""
    h = (host or "").lower().split(":")[0]
    parts = h.split(".")
    if len(parts) >= 3 and parts[-2] in ("gov", "com", "org", "edu", "net"):
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def same_site(a, b):
    return base_domain(urlparse(a).hostname or "") == base_domain(urlparse(b).hostname or "")


def norm_text(s):
    s = re.sub(r"<[^>]+>", "", s or "")
    s = re.sub(r"&nbsp;|\s+", "", s)
    return s


def classify_label(text):
    """锚文本 → (类别, 基础分)；不命中返回 ("", 0)。"""
    for kind, rx in KIND_RULES:
        if rx.search(text):
            return kind, KIND_BASE[kind]
    for kw, pts in TEXT_RULES:
        if kw in text:
            return "机构设置", pts
    return "", 0


def link_candidates(html, base_url):
    """从 HTML 里抽候选 (score, text, url, kind)，按分数降序。"""
    cands = {}
    for m in re.finditer(ANCHOR_RE, html or ""):
        attrs, inner = m.group(1), m.group(2)
        href = re.search(r"href\s*=\s*[\"']([^\"']+)[\"']", attrs, re.I)
        if not href:
            continue
        href = html_lib.unescape(href.group(1).strip())   # &amp; → & (营口目录页)
        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue
        url = urljoin(base_url, href)
        if not url.startswith(("http://", "https://")):
            continue
        if not same_site(url, base_url):
            continue
        if NEG_PATH.search(url):
            continue
        text = norm_text(inner)
        title_attr = re.search(r"title\s*=\s*[\"']([^\"']+)[\"']", attrs, re.I)
        alt = re.search(r"alt\s*=\s*[\"']([^\"']+)[\"']", attrs, re.I)
        labels = [x for x in (text, norm_text(title_attr.group(1)) if title_attr else "",
                              norm_text(alt.group(1)) if alt else "") if x]
        if not labels:
            continue
        score = 0
        kind = ""
        for lab in labels:
            if len(lab) > 30:
                continue
            if NEG_TEXT.search(lab):
                continue
            k, pts = classify_label(lab)
            if pts > score:
                neg = KIND_NEG.get(k)
                if neg and neg.search(lab):
                    continue
                score, kind = pts, k
        if score == 0:
            continue
        path = url.lower()
        for kw, pts in PATH_RULES:
            if kw in path:
                score += pts
                break
        # 门户自身不算
        if url.rstrip("/") == base_url.rstrip("/"):
            continue
        if score > cands.get(url, (0,))[0]:
            cands[url] = (score, text or (title_attr.group(1) if title_attr else ""), kind)
    return sorted(((s, t, u, k) for u, (s, t, k) in cands.items()), reverse=True)


def page_score(url, html, kind="机构设置"):
    """候选页验证：返回 (ok, score, title, reason)。

    机构设置类沿用原口径（标题/正文特征 + 部门名计数 + 强标题+机构路径兜底）；
    直属单位/事业单位/企业/公积金/高校类改用**类别关键词 + 实体名计数**判定。
    """
    if not html or len(html) < 2000:
        return False, 0, "", "empty/short"
    tm = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
    title = norm_text(tm.group(1)) if tm else ""
    if kind == "高校" and re.search(r"高等学校|高等院校|高校|院校", title):
        kind = "高校"  # 标题自证
    # 「首都之窗」这类门户品牌词含「之窗」：机构页标题同时命中 VERIFY_TITLE 时放行
    if NEG_TITLE.search(title) and not VERIFY_TITLE.search(title):
        return False, 0, title, "neg-title"
    # 公文/预决算/统计公报类单页：部门名再多也不是机构目录（桓仁实锤）
    if DOC_TOKEN.search(title[:80]):
        return False, 0, title, "doc-page"
    if kind not in KIND_BASE:
        kind = "机构设置"
    kind_re = dict(KIND_RULES)[kind]
    body = re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>", " ", html, flags=re.I)
    title_hit = bool(kind_re.search(title))
    body_hit = bool(kind_re.search(body))

    if kind != "机构设置":
        # 企事业/公积金/高校栏目：必须有类别证据，否则一律不认
        if not (title_hit or body_hit):
            return False, 0, title, f"kind-miss({kind})"
        neg = KIND_NEG_TITLE.get(kind)
        if neg and neg.search(title):
            return False, 0, title, f"kind-service-page({kind})"
        if kind == "公积金":
            host = (urlparse(url).hostname or "").lower()
            agency = re.search(r"公积金(管理)?中心|公积金管理局|住房公积金网站|公积金网站", title)
            if not agency and not re.match(r"(gjj|zfgjj|gjjzx|zfgjjzx)[.-]", host):
                return False, 0, title, "not-agency(公积金)"
        if kind == "高校":
            title_list = (LIST_RE.search(title) or
                          re.search(r"(高校|院校|高等学校)(名单|名录|一览|信息|概况|设置)", title))
            unis = set(re.findall(r"[一-龥]{2,16}(?:大学|学院|职业技术学院|高等专科学校)", body))
            if not (title_list or len(unis) >= 8):
                return False, 0, title, f"not-list(高校,uni{len(unis)})"
        score = 2
        reasons = [f"kind:{kind}"]
        if title_hit:
            score += 3
            reasons.append("title")
        if body_hit:
            score += 1
        if LIST_RE.search(title) or LIST_RE.search(body[:20000]):
            score += 1
            reasons.append("list")
        ents = len(set(ENTITY_RE.findall(body)))
        if ents >= 6:
            score += 3
            reasons.append(f"ent{ents}")
        elif ents >= 3:
            score += 1
            reasons.append(f"ent{ents}")
        # 公积金/高校栏目本身极窄，标题自证即可（页面常为单条中心/院校介绍）
        if kind in ("公积金", "高校") and title_hit and len(html) > 2500:
            score += 2
        return score >= 5, score, title, ",".join(reasons)

    score = 0
    reasons = []
    # 栏目名常只在 h1/h2 里（<title> 是站点模版名）：长春「政府组成机构」页
    # 的 title 是「长春市人民政府-中国长春」，旧口径只能给到 3 分被误杀
    heads = []
    for x in HEAD_RE.findall(html[:80000]):
        t = norm_text(re.sub(r"<[^>]+>", "", x))
        if t and 1 < len(t) <= 30:
            heads.append(t)
    head_hit = any(VERIFY_TITLE.search(x) for x in heads[:12])
    strong_title = bool(VERIFY_TITLE.search(title) or head_hit)
    # 便民服务/专题页冒充机构页（朔州「医疗机构」名录页，正文 35 个「委/局」
    # 全来自页脚「政府工作部门」导航）——页面主标题自证是服务类别的一律不认
    if not strong_title and (SERVICE_TOKEN.search(title[:40]) or
                             (heads and SERVICE_TOKEN.search(heads[0][:40]))):
        return False, score, title, "service-page"
    # 部门领导/领导之窗页：`<title>` 常是中性模板名（呼和浩特「法定主动公开内容」），
    # 正文又排着 30+ 个部门名，单靠 dept 计数会误判成机构目录页 → 用大标题自证挡掉
    if (LEADER_TOKEN.search(title[:40])
            or any(LEADER_TOKEN.search(h) for h in heads[:3])):
        return False, score, title, "leader-page"
    if strong_title:
        score += 3
        reasons.append("title" if VERIFY_TITLE.search(title) else "head")
    elif "机构" in title:
        score += 1
        reasons.append("title-weak")
    if re.search(r"内设机构|内设部门", body):
        score += 2
        reasons.append("内设机构")
    if re.search(r"直属单位|直属机构|直属事业单位|直属特设机构|部门管理机构", body):
        score += 2
        reasons.append("直属单位")
    if re.search(r"主要职责|机构职能", body):
        score += 1
        reasons.append("职责")
    depts = set(DEPT_RE.findall(body))
    if len(depts) >= 30:
        # ≥30 个不同部门名 = 目录级页面。三门峡「政府机构」页 dept123、儋州
        # 「市各部门政府信息公开」dept93 —— 标题都是站模板名，只有 dept 一项证据
        # 也足以确认（伊春「部门信息报送情况」dept34 这类服务页已被 NEG_TEXT
        # 的「报送/上报」挡在候选之外）
        score += 5
        reasons.append(f"dept{len(depts)}")
    elif len(depts) >= 10:
        score += 3
        reasons.append(f"dept{len(depts)}")
    elif len(depts) >= 5:
        score += 2
        reasons.append(f"dept{len(depts)}")
    elif len(depts) >= 3:
        score += 1
        reasons.append(f"dept{len(depts)}")
    # 正文小标题证据（无 h 标签的版块标题）：「省政府组织机构」这类版块标题只出现
    # 在可见正文里。必须在**去标签后的文本**上判，且关键词后面紧跟部门名列表——
    # 否则导航栏/属性里的「机构设置」会把便民服务页（朔州 /bjfw/ylws/yljg/
    # 医疗机构名录，35 个「委/局」字样）误判成机构页。
    if not strong_title and len(depts) >= 10:
        vis = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body))
        for mm in re.finditer(r"组织机构|机构设置|政府组成部门|机关简介|机构简介|"
                              r"政府组成机构|政府工作部门", vis):
            if len(set(DEPT_RE.findall(vis[mm.end():mm.end() + 300]))) >= 3:
                score += 2
                reasons.append("bodyhint")
                break
    # 强标题 + 机构路径：落地页可能是 iframe/JS 列表，正文特征取不到也算通过
    if strong_title and ORG_PATH.search(url):
        score += 2
        reasons.append("title+path")
    # 机构路径 + 大量部门名：标题是站模板名（鞍山「政府信息公开-鞍山市人民政府」
    # /asszf/zfxxgkml/fdzdgknr/jgjj/ 页 dept35）——两项证据叠加足以确认，
    # 不依赖标题自证。2026-11-18 鞍山实锤（旧口径 score3 误杀真机构页）
    elif not strong_title and len(depts) >= 10 and ORG_PATH.search(url):
        score += 2
        reasons.append("dept+path")
    # 中性标题 + 中性路径 = 低置信（仍保留，供人工/复审挑拣）
    if not strong_title and not ORG_PATH.search(url):
        reasons.append("low-conf")
    return score >= 5, score, title, ",".join(reasons)


def fetch(url, timeout=20):
    from smart_fetch import smart_fetch
    try:
        html, method = smart_fetch(url, timeout=timeout)
        return html or "", method
    except Exception as e:
        return "", f"exc:{str(e)[:40]}"


def iframe_home(html, base_url):
    """门户根址只是 **iframe 外壳**（海南 www.hainan.gov.cn 返回 1150 字节，
    正文只有 `<iframe src="/hainan/">`，真首页在 iframe 里）→ 返回同站 iframe 地址。

    这是官网自己声明的入口，不是拼路径。不跟它，整站静态阶段必然空手而归。
    """
    m = re.search(r"<iframe[^>]+src\s*=\s*[\"']([^\"']+)[\"']", html or "", re.I)
    if not m:
        return ""
    u = urljoin(base_url, m.group(1).strip())
    return u if u.startswith("http") and same_site(u, base_url) else ""


def fetch_or_render(url, timeout=20, wait_ms=2500, use_proxy=True):
    """静态拿不到（封锁/JS 壳）→ 渲染兜底。首页在浏览器里能看到导航，
    静态 HTML 却只有壳的门户（承德 46649 字节渲染后才出现「政府信息公开」）。"""
    h, m = fetch(url, timeout=timeout)
    if h and len(h) < 1500:
        tgt = iframe_home(h, url)
        if tgt:
            h2, m2 = fetch(tgt, timeout=timeout)
            if h2 and len(h2) > len(h):
                return h2, f"{m2}+iframe"
    if h and len(h) >= 1500:
        return h, m
    h2 = render_page(url, wait_ms=wait_ms, use_proxy=use_proxy)
    if h2 and len(h2) > len(h or ""):
        return h2, "render"
    return h, m


DEFAULT_BUDGET = 75   # 每站时间预算（秒）：用户指令「不在一个网站耽误太多时间」
BUDGET = float(os.environ.get("P246_BUDGET", DEFAULT_BUDGET))


def collect_links(page_url, html, portal_url, deadline, limit=5, max_tries=8,
                  skip_kinds=()):
    """一页 HTML → 候选锚文本 → 逐个回抓验证；跨类别覆盖，同类最多 2 条。

    先测「当前页自身是否就是目标栏目」（枢纽页直达形态），再扫页内锚点。
    `skip_kinds`：扩围补采时排除已收类别，把预算留给还没拿到的类别。
    """
    links, seen, by_kind = [], set(), {}
    own = self_candidate(page_url, html)
    # 同站校验：9222 是共享 context，并发点击可能抓到别的 worker 的 tab
    # （郴州曾收到益阳的「政府机构」页），跨站一律不认
    if own and same_site(own["u"], portal_url) and own["kind"] not in skip_kinds:
        links.append(own)
        seen.add(own["u"])
        by_kind[own["kind"]] = 1
    cands = link_candidates(html, portal_url)
    tries = 0
    for score, text, url, kind in cands:
        if len(links) >= limit or tries >= max_tries or time.time() > deadline:
            break
        if url in seen:
            continue
        seen.add(url)
        if kind in skip_kinds or by_kind.get(kind, 0) >= 2:
            continue
        tries += 1
        h2, m2 = fetch(url, timeout=15)
        ok, s2, title, why = page_score(url, h2, kind)
        if ok:
            by_kind[kind] = by_kind.get(kind, 0) + 1
            links.append(dict(kind=kind, u=url, title=title,
                              src=f"锚文本「{text}」(打分{score}) → 验证 {why}",
                              method=m2, score=s2))
    return links


CORE_KINDS = ("机构设置", "内设机构", "直属单位", "事业单位", "直属企业")


def dedupe_links(links):
    """同内容多 URL 去重：海南 `zfjgg/zfjg.shtml` 与 `zfjg/zfjg.shtml?ddtab=true`
    是同一张「政府机构」页的两个入口——同类别 + 同标题只留第一条
    （标题为空时退化为 同类别 + 同 path）。"""
    seen, out = set(), []
    for l in links or []:
        title = norm_text(l.get("title") or "")
        k = ((l.get("kind"), title) if title
             else (l.get("kind"), urlparse(l.get("u") or "").path))
        if k in seen:
            continue
        seen.add(k)
        out.append(l)
    return out


def make_rec(links, src_prefix="", method="static"):
    """links → 记录（u=核心类别中最优先的一页；公积金/高校单列时标 partial）。"""
    links = dedupe_links(links)
    if not links:
        return None
    links = sorted(links, key=lambda l: KIND_ORDER.index(l["kind"])
                   if l["kind"] in KIND_ORDER else 99)
    top = dict(links[0])
    if src_prefix:
        top["src"] = src_prefix + top["src"]
    rec = dict(u=top["u"], title=top["title"], src=top["src"],
               method=method, score=top["score"], verified_at=TODAY,
               links=links)
    # 只命中公积金/高校（门户导航外链）→ 不算机构栏目已找到，后续阶段继续找
    if not any(l["kind"] in CORE_KINDS for l in links):
        rec["partial"] = True
    return rec


def try_portal_static(t):
    """静态阶段：门户首页 → 候选锚文本 → 多类别验证（机构/内设/直属/企事业/公积金/高校）。"""
    deadline = time.time() + BUDGET
    html, method = fetch(t["url"], timeout=20)
    if html and len(html) < 1500:          # iframe 外壳首页（海南 /hainan/）
        tgt = iframe_home(html, t["url"])
        if tgt:
            h2, m2 = fetch(tgt, timeout=20)
            if h2 and len(h2) > len(html):
                html, method = h2, f"{m2}+iframe"
    if not html or len(html) < 1500:
        return None, f"portal-{method}-short"
    links = collect_links(t["url"], html, t["url"], deadline)
    if links:
        return make_rec(links, method=f"static/{method}"), ""
    return None, f"no-verified-candidate (候选{len(link_candidates(html, t['url']))}, portal-{method})"


def _playwright_proxy(url):
    """该站是否走 dps 私密代理 → playwright proxy 字典。

    2026-11-18 用户指令「浏览器也可以搭配代理使用」：浏览器渲染兜底走代理，
    与 fetch() 共用站级粘性 IP（同 host 同一出口，瑞数/WAF 会话不断）。
    开关独立于 PROXY_MODE：`P246_RENDER_PROXY=1` 才启用——PROXY_MODE=dps 会让
    collect_links 里每一次候选回抓也去排队提取 IP（5s/个全局节流），把整轮渲染
    压到 1~5 站/分钟。
    """
    if (os.environ.get("P246_RENDER_PROXY") or "").strip().lower() not in ("1", "true", "yes"):
        return None
    host = urlparse(url).hostname or ""
    if not host:
        return None
    try:
        from dps_proxy import get_proxies_for_host
        px = get_proxies_for_host(host)
    except Exception:
        return None
    if not px:
        return None
    u = urlparse(px.get("http") or "")
    if not u.hostname or not u.port:
        return None
    d = {"server": f"{u.scheme}://{u.hostname}:{u.port}"}
    if u.username:
        d["username"] = u.username
        d["password"] = u.password or ""
    return d


def _render_with(page, url, wait_ms):
    """页面上跑导航 + 滚动 → DOM HTML。"""
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=25000)
    except Exception:
        return ""
    page.wait_for_timeout(wait_ms)
    try:
        page.mouse.wheel(0, 6000)
        page.wait_for_timeout(1200)
        page.mouse.wheel(0, -6000)
    except Exception:
        pass
    return page.content() or ""


def render_page(url, wait_ms=2500, use_proxy=False):
    """CDP 渲染一页（滚动触发懒加载）→ 返回 DOM HTML。

    `use_proxy=True`：**先直连渲染，页面拿不到内容（封锁/空壳）才走 dps 代理**
    重渲染一次（2026-11-18 用户指令「浏览器也可以搭配代理使用」）。
    不做「一律走代理」——dps 每提取一个 IP 有全局节流，全量走代理会把
    每站成本抬到 5 秒级，实测吞吐掉到 1.4 站/分钟。
    """
    from cdp_util import cdp_page
    with cdp_page() as (page, _ctx):
        html = _render_with(page, url, wait_ms)
    if not use_proxy or len(html or "") >= 3000:
        return html
    with _proxied_page(url) as pp:
        if not pp:
            return html
        try:
            h2 = _render_with(pp[0], url, wait_ms)
        except Exception:
            h2 = ""
    return h2 if len(h2 or "") > len(html or "") else html


def hub_entries(html, base_url, limit=4):
    """同站枢纽页（政务公开/省政府/政府机构/走进XX）入口 URL 列表。"""
    out = []
    for m in re.finditer(ANCHOR_RE, html or ""):
        href = re.search(r"href\s*=\s*[\"']([^\"']+)[\"']", m.group(1), re.I)
        if not href:
            continue
        text = norm_text(m.group(2))
        if not text or len(text) > 20 or not PUBLIC_KW.search(text):
            continue
        url = urljoin(base_url, href.group(1).strip())
        if url.startswith("http") and same_site(url, base_url) and url not in out:
            out.append(url)
    return out[:limit]


def try_portal_render(t):
    """渲染阶段：CDP 渲染首页（滚动触发懒加载）→ 同套多类别候选/验证。
    首页渲染后仍无锚点时，再渲染 1 个枢纽页（JS 菜单常只在枢纽页展开）。"""
    deadline = time.time() + BUDGET
    html = render_page(t["url"], use_proxy=True)
    if not html or len(html) < 1500:
        return None, "render-short"
    links = collect_links(t["url"], html, t["url"], deadline)
    if links:
        return make_rec(links, method="render"), ""
    for entry in hub_entries(html, t["url"], limit=2):
        if time.time() > deadline:
            break
        h2 = render_page(entry, wait_ms=1500, use_proxy=True)
        if not h2 or len(h2) < 1500:
            continue
        l2 = collect_links(entry, h2, t["url"], deadline)
        if l2:
            for x in l2:
                x["src"] = f"渲染枢纽页「{entry}」→ " + x["src"]
            return make_rec(l2, method="render-hub"), ""
    return None, f"render-no-verified (候选{len(link_candidates(html, t['url']))})"


PUBLIC_KW = re.compile(r"政府信息公开|政务公开|信息公开|政务公开专栏|公开目录|"
                       r"公开指南|政府信息公开目录|法定主动公开|政务信息公开|"
                       # 「省政府 / 市政府 / 政府机构 / 走进XX」等枢纽页——
                       # 机构设置入口常挂在枢纽页而非首页（黑龙江 /hlj/c107864/szf.shtml）
                       r"^(省|市|县|区)?政府$|政府机构|走进|概况|省情|市情|政府领导")
SUB_KW = re.compile(r"公开内容|公开目录|法定主动公开|政府机构|机构职能|机构设置|"
                    r"组织机构|工作机构|部门|政府领导|政府组成")
CLICK_JS = r"""() => {
  const kw = /组织机构|机构设置|机构职能|政府机构|机构概况|内设机构|直属单位|事业单位|直属企业|公积金|高校/;
  const els = [...document.querySelectorAll('a,li,span,div,button')].filter(e => {
    const t = (e.innerText || '').trim();
    return t && t.length <= 14 && kw.test(t) && e.offsetParent !== null;
  });
  // 只要「最内层」命中元素：父容器 innerText 会连带整段导航文案，
  // 点父容器等于点了整块导航，落点不可控（七台河 点 li 落到模板 404 dept38）
  const inner = els.filter(e => !els.some(o => o !== e && e.contains(o)));
  const out = [];
  for (const e of inner.slice(0, 4)) {
    const a = e.closest('a');
    out.push({i: out.length + 1,
              label: (e.innerText || '').trim().slice(0, 20),
              href: a ? (a.getAttribute('href') || '') : ''});
    e.setAttribute('data-p246-click', String(out.length));
  }
  return out;
}"""


def self_candidate(url, html, method="static"):
    """当前页自身即目标栏目（导航直达的「机构设置」页本身）→ 直接作为一条 link。

    搜「页面里的链接」永远找不到「导航到的这一页本身」，而大量门户的机构设置页
    恰恰是枢纽页直达（黑龙江 /hlj/c108396/jgsz.shtml 由「省政府」页的锚点进入）。

    从严：标题必须自证类别（江苏「政府信息公开指南」正文里满屏机构字样，
    只靠 body 特征会被误收），正文特征只作辅助。
    """
    if not html or len(html) < 800:
        return None
    tm = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
    title = norm_text(tm.group(1)) if tm else ""
    if not title or re.search(r"指南|年报|年报|依申请|公开制度|公开目录|条例|办法|通知|公告",
                              title):
        return None
    for kind in KIND_ORDER:
        if not dict(KIND_RULES)[kind].search(title):
            continue
        ok, score, t2, why = page_score(url, html, kind)
        if ok:
            return dict(kind=kind, u=url, title=t2,
                        src=f"导航直达该页 → 验证 {why}",
                        method=method, score=score)
    return None


# 门户首页内嵌机构名录（西藏首页底部「自治区政府部门网站」下拉：组成部门/
# 直属特设机构/直属机构；甘肃首页「省政府直属特设机构/直属机构/部门管理机构」版块）：
# 机构清单**就写在首页里**，全站没有独立栏目页。这类门户前五阶段必然全灭，
# 但它给出的是真实、完整、官方的机构名录 —— 作最后一档兜底收首页，来源留痕。
BLOCK_TITLE = re.compile(r"组成部门|政府工作部门|机关各部门|直属特设机构|直属机构|"
                         r"部门管理机构|派出机构|直属事业单位|直属单位|直属企业|"
                         r"各师市|市委|市政府|党政机关|群众团体|垂直管理部门|"
                         r"重点网站|事业单位|市属企业|省属企业|国有企业|"
                         r"(?:省|市|自治区|县|区|国务院)?政府部门网站|部门网站|"
                         r"政府机构网站|政府机构|机构网站|集约化网站|网站群")
# 新闻标题/法规标题会偶然命中上面的词（北京「习近平对国有企业…作出重要指示」、
# 甘肃「事业单位登记管理条例」）—— 分组标题必须是「结构性标签」而非句子
BLOCK_NEG = re.compile(r"条例|办法|规定|通知|公告|意见|决定|细则|方案|报告|指南|"
                       r"新闻|会议|指示|讲话|重要|动态|解读|问答|登记|公示|批复|"
                       r"关于|如下|全文|图解|视频|巡察|巡视|进驻|召开|举行|举办")
_BLOCK_EL = re.compile(r"<(h[1-6]|div|span|p|strong|b|dt|dd|li|a)\b[^>]*>(.*?)</\1\s*>",
                       re.S | re.I)


def _block_titles(html):
    """首页里的「机构分组标题」（组成部门/直属机构…）。

    正则切「元素」对嵌套 div 无用（非贪婪会在内层开标签处截断），
    改为：先剥掉 script/style，再把所有标签替换成换行 —— 叶子文本自然成行，
    分组标题就是一行短文本。
    """
    body = re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>", " ",
                  (html or "")[:400000], flags=re.I)
    out = []
    for line in re.split(r"<[^>]*>", body):
        t = norm_text(line)
        if t and 2 <= len(t) <= 16 and BLOCK_TITLE.search(t) and not BLOCK_NEG.search(t):
            out.append(t)
    return out


def _dept_list(html, base_url, max_pos=None):
    """首页里的「机构链接」→ [{n, u}]（按锚文本去重）。

    机构名录的链接形态是**站点根址**（连云港 `http://fgw.lyg.gov.cn/`、
    甘肃 `http://fzgg.gansu.gov.cn/`），不是文章页——新闻首页的标题里也有
    大量「XX局」字样，只按文本匹配会把新闻页算成机构名录。故要求 URL 不带
    文件名扩展、路径不超过 3 段。
    `max_pos`：只看到第 N 个字符为止（分组段内机构链接必须**紧挨着标题**）。
    """
    seen, out = set(), []
    for m in re.finditer(ANCHOR_RE, html):
        if max_pos is not None and m.start() > max_pos:
            break
        href = re.search(r"href\s*=\s*[\"']([^\"']+)[\"']", m.group(1), re.I)
        if not href or href.group(1).strip().startswith(("#", "javascript:", "mailto:", "tel:")):
            continue
        t = norm_text(m.group(2))
        if not t or len(t) > 24:
            continue
        if not (DEPT_RE.search(t) or ENTITY_RE.search(t)):
            continue
        u = urljoin(base_url or "http://x/", href.group(1).strip())
        p = urlparse(u).path or "/"
        if re.search(r"\.[A-Za-z0-9]{2,5}$", p) or p.count("/") > 3:
            continue                      # 文章/详情页不算机构站点
        if t in seen:
            continue
        seen.add(t)
        out.append(dict(n=t, u="" if base_url is None else u))
    return out


def _dept_anchors(html, base_url, max_pos=None):
    return {d["n"] for d in _dept_list(html, base_url, max_pos)}


_TEXT_NODE = re.compile(r">([^<>]+)<")


def _block_segments(html):
    """按「分组标题」出现位置切段 → {标题: 该标题之后的那段 HTML}。

    只靠「页面里有分组标题 + 有机构链接」会把新闻首页误判成机构名录
    （呼和浩特一条「十四届市委第一轮巡察完成进驻」标题 + 41 个部门链接就够门槛）。
    真正成立的是**标题后面紧跟一列机构站点**，所以要按段验证。
    """
    body = re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>", " ",
                  (html or "")[:400000], flags=re.I)
    # 标题必须是**分组标签本身**，不能是名录里某条链接的文字：合肥首页的
    # 「政府机构网站」列表最后一条是「市委老干部局」，按纯文本取标题会把它
    # 当成分组名（49 个部门全挂在老干部局名下）。判据不是「在不在 li 里」——
    # 兵团「机关各部门」也是 tab 列表里的一项，却是真标题——而是**它是不是
    # 名录自身的一项**：标题所在 <ul> 内、在它之前已经排了 ≥5 个机构链接，
    # 说明它是名录成员，丢掉换前一个标题。
    uls = [(m.start(), m.end()) for m in _UL_BLOCK.finditer(body)]
    marks = []
    for m in _TEXT_NODE.finditer(body):
        t = norm_text(m.group(1))
        if not t or not (2 <= len(t) <= 16) or not BLOCK_TITLE.search(t) or BLOCK_NEG.search(t):
            continue
        pos = m.start()
        host = None
        for a, b in uls:
            if a < pos < b and (host is None or a > host[0]):
                host = (a, b)
        if host and not _in_heading(body, pos) and _dept_anchor_count(body[host[0]:pos]) >= 5:
            continue
        marks.append((pos, t))
    segs = {}
    for i, (pos, t) in enumerate(marks):
        nxt = marks[i + 1][0] if i + 1 < len(marks) else len(body)
        seg = body[pos:nxt]
        if len(seg) > len(segs.get(t, "")):
            segs[t] = seg
    return segs


def _in_heading(body, pos):
    """pos 处文本是否在 <h1..h6> 里（郴州 `li > h2 > a「本市集约化网站」`）。"""
    seg = body[max(0, pos - 500):pos]
    opens = [m.start() for m in re.finditer(r"<h[1-6]\b", seg, re.I)]
    closes = [m.start() for m in re.finditer(r"</h[1-6]\s*>", seg, re.I)]
    return bool(opens) and (not closes or opens[-1] > closes[-1])


_UL_BLOCK = re.compile(r"<(ul|ol)\b[^>]*>[\s\S]*?</\1\s*>", re.I)


def _dept_anchor_count(s):
    """s 里「像机构站点」的链接条数（_dept_list 的轻量版，只数不收集）。"""
    n = 0
    for m in ANCHOR_RE.finditer(s):
        href = re.search(r"href\s*=\s*[\"']([^\"']+)[\"']", m.group(1), re.I)
        if not href or href.group(1).strip().startswith(("#", "javascript:", "mailto:", "tel:")):
            continue
        t = norm_text(m.group(2))
        if t and len(t) <= 24 and (DEPT_RE.search(t) or ENTITY_RE.search(t)):
            p = urlparse(href.group(1).strip()).path or "/"
            if not re.search(r"\.[A-Za-z0-9]{2,5}$", p) and p.count("/") <= 3:
                n += 1
    return n


_FOREIGN_DEPT = re.compile(r"^(?:国家|中国|国务院|中央)|部$")
_PROV_DEPT = re.compile(r"^省")


def _own_list(depts, level="", base_url=""):
    """分组里的链接是不是**本地**机构名录。

    市级门户的机构名录不会满屏「国家××部」「省××厅」——那是首页底部的
    「国家部委/省政府部门/兄弟城市」友链区（绥化 84 条、牡丹江 35 条、武汉
    65 条全是这一类，误当成本市名录收进来就是错数据）。
    省级门户自己的厅局就以「省」开头，故只在市及以下把「省」算外来。

    第二道判据是**域名**：本地名录的站点几乎都在门户同域下（甘肃 23/23、
    西藏 22/23、青海 24/24、合肥 45/47 全是 *.gov.cn 子域），而伊春那条
    「省内地市政府网站」34 条全部指向 ndrc/seac/mohrss 等外部域（同域 0%）。
    """
    if not depts:
        return False
    bad = 0
    for d in depts:
        n = d["n"]
        if _FOREIGN_DEPT.search(n) or (level != "省" and _PROV_DEPT.search(n)):
            bad += 1
    if bad >= max(3, len(depts) * 0.4):
        return False
    anchors = [d for d in depts if d.get("u")]
    if base_url and anchors:
        same = sum(1 for d in anchors if same_site(d["u"], base_url))
        if same < max(2, len(anchors) * 0.3):
            return False
    return True


def _block_groups(html, base_url, min_depts=8, level=""):
    """首页内嵌机构名录 → [{t, n, depts:[{n,u}]}]（只留 ≥min_depts 个机构链接的分组）。

    甘肃首页 `div.item-item > h3「省政府组成部门」+ ul > li > a`（省发展改革委/
    省教育厅/…23 个）、连云港页脚 `div_6.daohang_list`（市委/市政府/群众团体/
    垂直管理部门 + div_7 市属企业/高校），都是这个形状 —— 分组标题后面的 `ul`
    就是官方名录本身。收进记录里一并留档，便于核对「首页确实公布了名录」。
    """
    out = []
    for t, seg in _block_segments(html).items():
        ds = _dept_list(seg, base_url, max_pos=20000)
        if len(ds) >= min_depts and _own_list(ds, level, base_url):
            # 标题偶尔会取到名录里最后一条链接的文字（苏州「市委书记信箱」、
            # 许昌「长葛市政府」）——那是链接名不是分组名，换成中性标签，
            # 不把单个部门冒充成一组。
            if (DEPT_RE.search(t) or t.endswith("政府") or t.endswith("党校")
                    or "信箱" in t):
                t = "首页机构名录"
            out.append(dict(t=t, n=len(ds), depts=ds))
    out.sort(key=lambda g: -g["n"])
    return out


def homepage_block(html, level="", base_url=""):
    """首页内嵌机构名录判定 → (ok, 说明)。

    成立条件：某个分组标题**紧跟 ≥8 个本地机构站点链接**，且整页机构站点
    链接 ≥15。这样既认「组成部门/直属机构/机关各部门/市委市政府」这类真名录，
    又不认「新闻标题里带个市政府 + 页面别处有部门链接」的假名录。
    """
    if not html or len(html) < 5000:
        return False, "home-short"
    depts = _dept_anchors(html, "")
    # 第 8 个机构锚必须出现在段首 20000 字符内：真名录是紧凑的页脚一列
    # （实测西藏 3674 / 甘肃 1322 / 兵团 1055 / 天津 10974），而呼和浩特那条
    # 「十四届市委第一轮巡察…」后面拖了 6 万字符才凑够 8 个部门链接（新闻正文 +
    # 全站导航），不是名录，靠这个距离阈值挡住。
    groups = _block_groups(html, base_url, min_depts=8, level=level)
    if groups and len(depts) >= 15:
        return True, f"分组{len(groups)}组（{','.join(g['t'] for g in groups[:3])}）/机构{len(depts)}个"
    return False, f"home-no-block(分组{len(groups)}/机构{len(depts)})"


def try_portal_homeblock(t):
    """兜底阶段：机构名录内嵌在门户首页、全站无独立栏目页的门户，收首页留痕。

    用户指令「尽可能全部」下，这比留空更接近事实：首页确实是该门户公布机构
    名录的地方（西藏/甘肃形态），且 URL 与来源全部来自官网真实 HTML。
    """
    home, hm = fetch_or_render(t["url"], timeout=20)
    ok, why = homepage_block(home, t.get("level", ""), t["url"])
    if not ok and "render" not in (hm or ""):
        # 静态 HTML 里页脚容器有、部门名却是 JS 注入的（连云港 `div_6.daohang_list`：
        # 静态 81KB 只含 3 个机构锚，渲染后才是完整的 市委/市政府/群众团体/垂直管理部门
        # 四组 ~60 个部门站）。fetch_or_render 只在静态 <1500 字节时才渲染，
        # 这种「页面够大但名录是 JS 拼的」必须在这里显式再渲染一次。
        h2 = render_page(t["url"], wait_ms=4000, use_proxy=True)
        if h2 and len(h2) > len(home or ""):
            ok2, why2 = homepage_block(h2, t.get("level", ""), t["url"])
            home, ok, why = h2, ok2, why2
            hm = "render"
    if not ok:
        return None, f"homeblock:{why}"
    groups = _block_groups(home, t["url"], level=t.get("level", ""))
    lk = dict(kind="机构设置", u=t["url"], title=f"{t['name']}门户首页·内嵌机构名录",
              src=f"门户首页内嵌机构名录（前序阶段未发现独立栏目页）→ {why}",
              method=f"homeblock/{hm}", score=5, homeblock=True,
              n_groups=len(groups), n_depts=sum(g["n"] for g in groups),
              groups=groups)
    return dict(u=t["url"], title=lk["title"], src=lk["src"],
                method=f"homeblock/{hm}", score=5, verified_at=TODAY,
                links=[lk]), ""


def try_portal_deep(t):
    """深挖阶段：门户首页 → 政府信息公开/政务公开 索引 → 机构/企事业栏目。

    省市门户的「组织机构」常挂在政务公开目录下（如上海：首页「政府信息公开」
    →/nw49255/ →「工作机构」/nw2405/），只扫首页会漏。仍全部来自官方真实 HTML。
    """
    deadline = time.time() + BUDGET
    home, hm = fetch_or_render(t["url"], timeout=20)
    if not home:
        return None, f"deep-portal-{hm}"
    links = collect_links(t["url"], home, t["url"], deadline)
    if links:
        return make_rec(links, method=f"deep/{hm}"), ""
    # 找政务公开/信息公开入口（同站）
    entries = []
    for m in re.finditer(ANCHOR_RE, home):
        href = re.search(r"href\s*=\s*[\"']([^\"']+)[\"']", m.group(1), re.I)
        if not href:
            continue
        text = norm_text(m.group(2))
        if not text or len(text) > 20 or not PUBLIC_KW.search(text):
            continue
        url = urljoin(t["url"], href.group(1).strip())
        if not url.startswith("http") or not same_site(url, t["url"]):
            continue
        if url not in entries:
            entries.append(url)
    for entry in entries[:4]:
        if time.time() > deadline:
            break
        h2, m2 = fetch_or_render(entry, timeout=15)
        if not h2 or len(h2) < 3000:
            continue
        own = self_candidate(entry, h2, m2)
        if own and own["kind"] in CORE_KINDS:
            own["src"] = f"枢纽页「{entry}」即目标 → " + own["src"]
            return make_rec([own], method=f"deep/{hm}+{m2}"), ""
        l2 = collect_links(entry, h2, t["url"], deadline)
        if l2:
            for x in l2:
                x["src"] = f"政务公开索引「{entry}」→ " + x["src"]
            return make_rec(l2, method=f"deep/{hm}+{m2}"), ""
        # 再下钻一层：公开内容/公开目录/机构
        subs = []
        for m in re.finditer(ANCHOR_RE, h2):
            href = re.search(r"href\s*=\s*[\"']([^\"']+)[\"']", m.group(1), re.I)
            if not href:
                continue
            text = norm_text(m.group(2))
            if not text or len(text) > 20 or not SUB_KW.search(text):
                continue
            url = urljoin(entry, href.group(1).strip())
            if url.startswith("http") and same_site(url, t["url"]) and url not in subs:
                subs.append(url)
        for sub in subs[:3]:
            if time.time() > deadline:
                break
            h3, m3 = fetch_or_render(sub, timeout=15)
            own3 = self_candidate(sub, h3, m3)
            if own3 and own3["kind"] in CORE_KINDS:
                own3["src"] = f"政务公开索引「{entry}」→「{sub}」即目标 → " + own3["src"]
                return make_rec([own3], method=f"deep/{hm}+{m3}"), ""
            l3 = collect_links(sub, h3, t["url"], deadline)
            if l3:
                for x in l3:
                    x["src"] = f"政务公开索引「{entry}」→「{sub}」→ " + x["src"]
                return make_rec(l3, method=f"deep/{hm}+{m3}"), ""
    return None, f"deep-no-verified (入口{len(entries)})"


# 用户直接给出的已验证入口（示例）
_SEED_HN = "http://www.huangnan.gov.cn/html/channels/30.html?type=zzjg&cid=7"
SEEDS = {
    # 字段与正常记录对齐（含 links），否则报告按类别统计时会多出一个「?」类
    "市|黄南藏族自治州": dict(
        u=_SEED_HN,
        title="黄南州人民政府·组织机构（用户示例）",
        src="用户示例: 门户首页点击「组织机构」跳转", method="user",
        score=9, verified_at=TODAY, kind="机构设置",
        links=[dict(kind="机构设置", u=_SEED_HN,
                    title="黄南州人民政府·组织机构（用户示例）",
                    src="用户示例: 门户首页点击「组织机构」跳转",
                    method="user", score=9)]),
}



def _is_404(html):
    """落点是模板占位 404（七台河 /dept38、三门峡 /dept103 这类 href 全站失效）"""
    tm = re.search(r"<title[^>]*>(.*?)</title>", html or "", re.S | re.I)
    title = norm_text(tm.group(1)) if tm else ""
    if re.search(r"^\s*404\b|404\s*(not\s*found|错误)|页面不存在|页面未找到|"
                 r"找不到(该)?页面|Not Found", title, re.I):
        return True
    body = re.sub(r"<[^>]+>", "", (html or ""))[:2000]
    return bool(re.search(r"^\s*(404|页面不存在|页面未找到)\s*$", body.strip()[:60], re.M))


def _click_loop(page, pages_fn, t, rerender=None):
    """在一个已就绪的门户页上跑「点候选 → 收链接」。返回 (rec, err)。

    2026-11-18 加固（62 个缺口里 40 个卡在点击）：
      ① 候选从 1 个扩到最多 4 个（只取最内层命中元素——点父容器等于点整块导航）
      ② 落点是模板 404 → 回门户换下一个候选，而不是整站判死
      ③ 点了不跳转（导航是 hover/折叠展开）→ 扫展开后 DOM 里的锚点再验证
      ④ 落点是 JS 空壳列表页 → 再渲染一次落地页（赤峰 ?gk=3&cid=59 形态）
    """
    try:
        page.goto(t["url"], wait_until="domcontentloaded", timeout=45000)
    except Exception as e:
        return None, f"click-goto:{str(e)[:50]}"
    page.wait_for_timeout(2500)
    deadline = time.time() + BUDGET
    tried, last = set(), "click-no-element"
    rerender = rerender if rerender is not None else {}
    for _ in range(4):
        if time.time() > deadline:
            break
        if page.url.rstrip("/") != t["url"].rstrip("/"):
            try:      # 上一次点击跳走了（404/无验证），回门户重来
                page.goto(t["url"], wait_until="domcontentloaded", timeout=45000)
                page.wait_for_timeout(1800)
            except Exception:
                break
        try:
            cands = page.evaluate(CLICK_JS) or []
        except Exception:
            cands = []
        hit = next((c for c in cands if c.get("label") not in tried), None)
        if not hit:
            break
        tried.add(hit["label"])
        label = hit["label"]
        pages_before = set(pages_fn())
        try:
            page.click(f"[data-p246-click='{hit['i']}']", timeout=6000)
        except Exception as e:
            last = f"click-fail:{str(e)[:40]}"
            continue
        page.wait_for_timeout(2200)
        # 9222 的 context 是全局共享的：并发时 ctx.pages 里会混进别的 worker
        # 刚开的 tab，必须按「同站」筛选，否则会把别市的机构页记到本市头上
        new_pages = [p for p in pages_fn()
                     if p not in pages_before and same_site(p.url, t["url"])]
        target = new_pages[-1] if new_pages else page
        try:
            target.wait_for_load_state("domcontentloaded", timeout=15000)
        except Exception:
            pass
        url = target.url
        try:
            html = target.content()
        except Exception:
            html = ""
        finally:
            if new_pages:
                try:
                    target.close()
                except Exception:
                    pass
        if not same_site(url, t["url"]):
            last = f"click-cross-site:{url[:60]}"
            continue
        # ③ 没跳转：导航是展开式的，扫展开后 DOM 里新出现的锚点
        if url.rstrip("/") == t["url"].rstrip("/"):
            links = collect_links(url, html, t["url"], deadline, limit=3)
            if links:
                for x in links:
                    x["src"] = f"点击「{label}」展开后 → " + x["src"]
                return make_rec(links, method="click+expand"), ""
            last = "click-no-nav"
            continue
        if _is_404(html):
            last = f"click-404:{url[:60]}"
            continue
        links = collect_links(url, html, t["url"], deadline)
        if links:
            for x in links:
                x["src"] = f"点击「{label}」后跳转 → " + x["src"]
            return make_rec(links, method="click+verify"), ""
        ok, s2, title, why = page_score(url, html)
        last = f"click-no-verified ({url[:80]} {why})"
        # ④ 机构路径/机构标题但正文空壳 → 落地页需要再渲染一次。
        #    不能在 cdp_page 的 with 里再开 playwright（同线程嵌套 sync API 会
        #    抛「Please use the Async API instead」），只登记，出了 with 再渲染。
        if (ORG_PATH.search(url) or VERIFY_TITLE.search(title)) and time.time() < deadline:
            rerender["url"], rerender["label"] = url, label
            break
    return None, last


_CLICK_PROXY_SIGNALS = ("click-no-element", "click-no-nav", "blocked")


def _click_needs_proxy(err):
    e = err or ""
    return e in _CLICK_PROXY_SIGNALS or e.startswith("click-goto:")


@contextmanager
def _proxied_page(url):
    """带 dps 代理的独立 context（租 9222 常驻浏览器的 tab，只关 context 不关浏览器）。
    与 cdp_page() 同等的反检测注入（webdriver 隐藏 + UA 覆盖）。"""
    from playwright.sync_api import sync_playwright
    from cdp_util import _CDP_URL
    proxy = _playwright_proxy(url)
    if not proxy:
        yield None
        return
    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp(_CDP_URL, timeout=15000)
            ctx = browser.new_context(proxy=proxy)
            page = ctx.new_page()
        except Exception:
            yield None
            return
        try:
            try:
                from cdp_util import _STEALTH_JS, _STEALTH_FULL, _STEALTH_UA
                page.add_init_script(_STEALTH_JS)
                if _STEALTH_FULL:
                    page.add_init_script(_STEALTH_FULL)
                s = ctx.new_cdp_session(page)
                s.send("Network.setUserAgentOverride", {"userAgent": _STEALTH_UA})
            except Exception:
                pass
            yield page, ctx
        finally:
            try:
                ctx.close()
            except Exception:
                pass


def _verify_by_render(t, url, label):
    """点击落点是 JS 空壳列表页 → 渲染该页再验证（必须在 cdp_page 之外调用）。"""
    deadline = time.time() + BUDGET
    h3 = render_page(url, wait_ms=2500, use_proxy=True)
    if not h3:
        return None
    links = collect_links(url, h3, t["url"], deadline)
    if links:
        for x in links:
            x["src"] = f"点击「{label}」后跳转 → 渲染 " + x["src"]
        return make_rec(links, method="click+render")
    ok3, s3, t3, why3 = page_score(url, h3)
    if ok3:
        return make_rec([dict(kind="机构设置", u=url, title=t3,
                              src=f"点击「{label}」后跳转 → 渲染后验证 {why3}",
                              method="render", score=s3)])
    return None


def try_portal_click(t):
    """点击阶段：渲染后按关键词点击导航元素，捕获跳转后的页面再验证。
    直连一轮拿不到（WAF 封锁 / 导航全靠 JS）→ 换 dps 代理独立 context 再点一轮
    （2026-11-18 用户指令「浏览器也可以搭配代理使用」）。"""
    from cdp_util import cdp_page
    rerender = {}
    with cdp_page() as (page, ctx):
        rec, err = _click_loop(page, lambda: ctx.pages, t, rerender)
    if not rec and rerender.get("url"):
        rec = _verify_by_render(t, rerender["url"], rerender.get("label", ""))
        if rec:
            return rec, ""
    if rec or not _click_needs_proxy(err):
        return rec, err
    try:
        with _proxied_page(t["url"]) as pp:
            if pp:
                rerender2 = {}
                rec2, err2 = _click_loop(pp[0], lambda: pp[1].pages, t, rerender2)
                if not rec2 and rerender2.get("url"):
                    rec2 = _verify_by_render(t, rerender2["url"], rerender2.get("label", ""))
                if rec2:
                    return rec2, ""
                return None, f"{err} | proxy:{err2}"
    except Exception as e:
        return None, f"{err} | proxy-exc:{str(e)[:40]}"
    return None, err


def try_portal_candrender(t):
    """候选渲染阶段：静态找到强锚点但落地页是 JS 列表（信息公开目录式）时，
    渲染候选页再验证（如赤峰「政府机构」?gk=3&cid=59）。"""
    deadline = time.time() + BUDGET
    home, hm = fetch_or_render(t["url"], timeout=20)
    if not home:
        return None, f"candrender-portal-{hm}"
    # 候选排序：**类别优先级 > 分数**。营口实锤：首页只给到两条候选，
    # 「公共企事业单位信息」(事业单位, score8) 与「公开机构与联系方式」
    # (机构设置, score5)，旧口径只试 score>=8 的，真正的机构页永远轮不到。
    cands = [c for c in link_candidates(home, t["url"]) if c[0] >= 4]
    cands.sort(key=lambda c: (-KIND_BASE.get(c[3], 0), -c[0]))
    for score, text, url, kind in cands[:3]:
        if time.time() > deadline:
            continue
        html = render_page(url, wait_ms=2500, use_proxy=True)
        links = collect_links(url, html, t["url"], deadline)
        if links:
            for x in links:
                x["src"] = f"「{text}」(打分{score}) → 渲染后 " + x["src"]
            return make_rec(links, method="candrender"), ""
        own = self_candidate(url, html, "render")
        if not own and KIND_BASE.get(kind, 0) >= 8:
            # 入口锚文本自证类别 + 页面验证通过，而页面标题只是站模板名
            # （营口「公开机构与联系方式」→ title=政务公开-营口市人民政府，
            # 正文是 45 个部门名+联系方式的表格、无部门链接）。锚文本是门户
            # 自己给的类别标识，与页面证据叠加足够——比页面里的零散链接可靠。
            ok2, sc2, t2, why2 = page_score(url, html, kind)
            if ok2:
                own = dict(kind=kind, u=url, title=t2 or text,
                           src=f"入口锚「{text}」直达该页 → 验证 {why2}",
                           method="render", score=sc2)
        if own and own["kind"] in CORE_KINDS:
            own["src"] = f"「{text}」(打分{score}) → 渲染后 " + own["src"]
            return make_rec([own], method="candrender"), ""
    return None, "candrender-none"


PHASES = {"static": try_portal_static, "render": try_portal_render,
          "deep": try_portal_deep, "candrender": try_portal_candrender,
          "click": try_portal_click, "homeblock": try_portal_homeblock}


# ── 状态与产物 ────────────────────────────────────────────────────────
_lock = threading.Lock()


def load_state():
    if os.path.exists(STATE_F):
        return json.load(open(STATE_F, encoding="utf-8"))
    return {"done": {}, "fail": {}}


def save_state(state):
    json.dump(state, open(STATE_F, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)


def merge_out(key, rec):
    data = {}
    if os.path.exists(OUT_F):
        data = json.load(open(OUT_F, encoding="utf-8"))
    data[key] = rec
    json.dump(data, open(OUT_F, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)


def merge_links(key, rec):
    """增量并入：已有记录的 links 与新 links 按 URL 取并集（扩围补采不丢老结果）。"""
    data = {}
    if os.path.exists(OUT_F):
        data = json.load(open(OUT_F, encoding="utf-8"))
    old = data.get(key) or {}
    old_links = list(old.get("links") or [])
    if not old_links and old.get("u"):
        old_links = [dict(kind="机构设置", u=old["u"], title=old.get("title", ""),
                          src=old.get("src", ""), method=old.get("method", ""),
                          score=old.get("score", 0))]
    by_url = {l["u"]: l for l in old_links if l.get("u")}
    added = 0
    for l in rec.get("links") or []:
        if l.get("u") and l["u"] not in by_url:
            by_url[l["u"]] = l
            added += 1
    links = sorted(by_url.values(),
                   key=lambda l: KIND_ORDER.index(l["kind"]) if l.get("kind") in KIND_ORDER else 99)
    if not links:
        return 0
    top = links[0]
    base = dict(old)
    base.update(dict(u=top.get("u", ""), title=top.get("title", ""),
                     src=top.get("src", ""), score=top.get("score", 0),
                     method=rec.get("method") or old.get("method", ""),
                     verified_at=TODAY, links=links))
    # partial 随合并后的类别重算：扩围补到核心类别后要摘掉 partial，
    # 否则后续阶段会反复重采（曾出现已收机构设置却仍标 partial 的死循环入口）
    if any(l.get("kind") in CORE_KINDS for l in links):
        base.pop("partial", None)
    else:
        base["partial"] = True
    data[key] = base
    json.dump(data, open(OUT_F, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    return added


def refresh_extras(targets, workers):
    """扩围补采：对已命中门户做两轮扫描 —— ① 门户首页 ② 已入库的主栏目页
    （机构设置页里往往才挂着「内设机构 / 直属单位 / 事业单位 / 企业 / 高校」入口）。
    新链接按 URL 去重并入 links。"""
    data = json.load(open(OUT_F, encoding="utf-8")) if os.path.exists(OUT_F) else {}
    todo = [t for t in targets if t["key"] in data]
    log(f"== 扩围补采: {len(todo)} 个已命中门户")
    n_new = n_ok = 0
    t0 = time.time()

    def job(t):
        deadline = time.time() + BUDGET
        have = {l.get("kind") for l in (data.get(t["key"], {}).get("links") or [])}
        found, m0 = [], "static"
        # 首页静态拿不到（WAF 空壳 / JS 导航 / iframe 外壳）→ 渲染兜底，
        # 否则 render/deep 阶段命中的那批门户在扩围轮会一律空手（fetch_or_render 已含 iframe）
        html, m = fetch_or_render(t["url"], timeout=20)
        if html and len(html) >= 1500:
            m0 = m
            found += collect_links(t["url"], html, t["url"], deadline, limit=3,
                                   skip_kinds=have)
        # 主栏目页再扫一轮（题干页常是唯一挂载子栏目入口的地方）
        base_links = [l for l in (data.get(t["key"], {}).get("links") or [])
                      if l.get("u") and l.get("kind") in CORE_KINDS][:2]
        for bl in base_links:
            if time.time() > deadline:
                break
            h2, _m2 = fetch(bl["u"], timeout=15)
            if not h2 or len(h2) < 800:
                h2 = render_page(bl["u"], wait_ms=2000, use_proxy=True)
            if not h2 or len(h2) < 800:
                continue
            logged = {l["u"] for l in found}
            for extra in collect_links(bl["u"], h2, t["url"], deadline, limit=3,
                                       skip_kinds=have | {l.get("kind") for l in found}):
                if extra["u"] not in logged:
                    found.append(extra)
                    logged.add(extra["u"])
        return (make_rec(found, method=f"extra/{m0}") if found else None), m0

    with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        futs = {ex.submit(job, t): t for t in todo}
        for fut in as_completed(futs):
            t = futs[fut]
            try:
                rec, m = fut.result()
            except Exception:
                continue
            if not rec:
                continue
            with _lock:
                n_ok += 1
                n = merge_links(t["key"], rec)
                n_new += n
                if n:
                    log(f"[extra][+] {t['key']} +{n} → 共 {len(rec['links'])} 类")
    log(f"== 扩围补采完成: 处理 {n_ok}，新增链接 {n_new}，耗时 {time.time() - t0:.0f}s")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", default="static", choices=list(PHASES) + ["all"])
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--only", default="")
    ap.add_argument("--sync-registry", action="store_true")
    ap.add_argument("--retry-fail", action="store_true", help="重试该阶段有失败记录的")
    ap.add_argument("--reaudit", action="store_true", help="按当前口径复验已落库结果")
    ap.add_argument("--reaudit-only", default="",
                    help="只复验这些 key（空格分隔，如 '市|合肥市 省|青海省'）")
    ap.add_argument("--refresh-extras", action="store_true",
                    help="扩围补采：重扫已命中门户首页，补直属单位/事业单位/企业/公积金/高校等栏目")
    ap.add_argument("--budget", type=float, default=0,
                    help="每站时间预算秒（默认 75，不在此站死磕）")
    args = ap.parse_args()

    global BUDGET
    if args.budget and args.budget > 0:
        BUDGET = args.budget

    if args.reaudit:
        reaudit(workers=args.workers,
                only_keys=[x for x in re.split(r"[,，\s]+", args.reaudit_only) if x] or None)
        return

    targets = load_targets()
    only = [x for x in re.split(r"[,，\s]+", args.only) if x]
    if only:
        targets = [t for t in targets if t["name"] in only or t["key"] in only]
    state = load_state()

    # 用户给出的已验证入口先落库
    for key, rec in SEEDS.items():
        merge_out(key, rec)
        state["done"].setdefault(key, "seed")
        state["fail"].pop(f"static:{key}", None)
        state["fail"].pop(f"render:{key}", None)
        state["fail"].pop(f"deep:{key}", None)
        state["fail"].pop(f"click:{key}", None)

    phases = (["static", "render", "deep", "candrender", "click", "homeblock"]
              if args.phase == "all" else [args.phase])
    for phase in phases:
        fn = PHASES[phase]
        todo = []
        for t in targets:
            if t["key"] in state["done"]:
                continue
            fk = f"{phase}:{t['key']}"
            if fk in state["fail"] and not args.retry_fail:
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
                        hit_n += 1
                        merge_out(t["key"], rec)
                        if rec.get("partial"):
                            log(f"[{phase}][~] {t['key']} 仅公积金/高校外链，继续找机构栏目")
                        else:
                            state["done"][t["key"]] = phase
                        state["fail"].pop(f"{phase}:{t['key']}", None)
                        log(f"[{phase}][OK] {t['key']} -> {rec['u']}  ({rec['title'][:30]})")
                    else:
                        state["fail"][f"{phase}:{t['key']}"] = err
                        log(f"[{phase}][--] {t['key']} {err}")
                    if done_n % 10 == 0:
                        save_state(state)
        save_state(state)
        log(f"== 阶段 {phase} 完成: 处理 {done_n}，命中 {hit_n}，"
            f"耗时 {time.time() - t0:.0f}s")

    if args.refresh_extras:
        refresh_extras(targets, args.workers)

    if args.sync_registry:
        sync_registry()

    data = json.load(open(OUT_F, encoding="utf-8")) if os.path.exists(OUT_F) else {}
    log(f"== 累计命中 {len(data)} / 目标 {len(targets)}")


def reaudit(workers=6, only_keys=None):
    """用当前评分口径复验已落库结果（含 links 全量）：
    剔除不合格链接；一个门户全部链接不合格则整条剔除到 zzjg_pages_rejected.json，
    并从 state.done 移除以便后续阶段重采。

    2026-11-18 修复：静态抓不到时**渲染兜底再判一次**——合肥（JS 注入 ul）、
    衡阳（二次跳转）、郴州（点击展开）这类站点静态 HTML 里根本没有机构名录，
    旧复验会把用户点名确认过的正确结果整条误删（实测一次删掉 22 条）。

    2026-11-18 修复 2：`only_keys` 是**子集复验**——旧实现把子集结果直接覆盖写回
    整份产物，定向复验会把未参与的 300+ 条全部抹掉。改为与全量合并后写回。
    """
    full = json.load(open(OUT_F, encoding="utf-8"))
    data = dict(full)
    keep, rej = {}, {}
    lock = threading.Lock()
    if only_keys:
        want = set(only_keys)
        data = {k: v for k, v in full.items() if k in want}

    def check(item):
        key, rec = item
        if key in SEEDS:          # 用户直接给出的入口：不因当前抓不到就剔除
            return key, dict(rec), [], ""
        links = list(rec.get("links") or [])
        if not links and rec.get("u"):
            links = [dict(kind="机构设置", u=rec["u"], title=rec.get("title", ""),
                          src=rec.get("src", ""), score=rec.get("score", 0))]
        good, bad = [], []

        def judge(l, html, m):
            if l.get("homeblock"):
                # 首页内嵌机构名录：用同一判定器复验（page_score 不适用于首页）
                ok, why = homepage_block(html, key.split("|")[0], l["u"])
                return ok, (dict(l, method=l.get("method") or m) if ok
                            else dict(l, reject_reason=why))
            ok, s2, title, why = page_score(l["u"], html, l.get("kind") or "机构设置")
            return ok, (dict(l, title=title or l.get("title", ""), score=s2,
                             method=l.get("method") or m) if ok
                        else dict(l, reject_reason=why))

        for l in links:
            html, m = fetch(l["u"], timeout=15)
            ok, ent = judge(l, html, m)
            if not ok:                      # 静态不过 → 渲染（必要时走代理）再判
                html2 = render_page(l["u"], wait_ms=1800, use_proxy=True)
                if html2 and len(html2) > len(html or ""):
                    ok2, ent2 = judge(l, html2, "render")
                    if ok2:
                        ok, ent = True, ent2
            (good if ok else bad).append(ent)
        if not good:
            return key, None, bad, "all-links-rejected"
        good = dedupe_links(good)
        good.sort(key=lambda l: KIND_ORDER.index(l["kind"]) if l.get("kind") in KIND_ORDER else 99)
        top = good[0]
        new = dict(rec, u=top["u"], title=top.get("title", ""), src=top.get("src", ""),
                   score=top.get("score", 0), verified_at=TODAY, links=good)
        if not any(l["kind"] in CORE_KINDS for l in good):
            new["partial"] = True
        else:
            new.pop("partial", None)
        return key, new, bad, ""

    with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        futs = {ex.submit(check, kv): kv[0] for kv in data.items()}
        for fut in as_completed(futs):
            key = futs[fut]
            try:
                key, new, bad, err = fut.result()
            except Exception as e:
                log(f"[reaudit][!] {key} exc:{str(e)[:50]}")
                continue
            with lock:
                if new:
                    keep[key] = new
                    for b in bad:
                        log(f"[reaudit][-] {key} 剔除 {b.get('kind')} {b['u'][:80]} {b.get('reject_reason')}")
                else:
                    rej[key] = dict(data[key], reject_reason=err)
                    log(f"[reaudit][X] {key} {err}")
    merged = dict(full)
    merged.update(keep)
    for key in rej:
        merged.pop(key, None)
    json.dump(merged, open(OUT_F, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    rej_f = os.path.join(HERE, "zzjg_pages_rejected.json")
    old_rej = json.load(open(rej_f, encoding="utf-8")) if os.path.exists(rej_f) else {}
    for key in keep:
        old_rej.pop(key, None)          # 本次复验通过的，从剔除清单撤销
    old_rej.update(rej)
    json.dump(old_rej, open(rej_f, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    st = load_state()
    for key in rej:
        st["done"].pop(key, None)
    for key, rec in keep.items():
        if rec.get("partial"):
            st["done"].pop(key, None)   # 仅公积金/高校外链 → 后续阶段继续找机构栏目
    save_state(st)
    log(f"== 复验: 保留 {len(keep)} / 整条剔除 {len(rej)}")


def sync_registry():
    """把 zzjg 写入 site_registry.json（省级缺条目则补建）。"""
    tree = json.load(open(os.path.join(HERE, "tree.json"), encoding="utf-8"))
    portals = {}

    def walk(n):
        for ch in n.get("ks") or []:
            if ch.get("k") == "人民政府" and ch.get("l") in ("省", "市") and ch.get("u"):
                portals[f"{ch.get('l')}|{ch.get('n')}"] = ch
            walk(ch)

    walk(tree)
    data = json.load(open(OUT_F, encoding="utf-8"))
    reg_path = os.path.join(HERE, "site_registry.json")
    reg = json.load(open(reg_path, encoding="utf-8"))
    n_new = n_upd = 0
    for key, rec in data.items():
        lvl, name = key.split("|", 1)
        if lvl == "市":
            rk = f"地级市人民政府|{name}"
        else:
            rk = f"省级人民政府|{name}"
        if rk not in reg:
            node = portals.get(key) or {}
            if not node.get("u"):
                continue
            reg[rk] = dict(u=node["u"], n=name, locations=["块"],
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
    log(f"== registry 同步: 更新 {n_upd}，新建省级条目 {n_new}")


if __name__ == "__main__":
    main()
