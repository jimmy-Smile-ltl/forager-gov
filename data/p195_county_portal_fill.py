# -*- coding: utf-8 -*-
"""P195: 全国县级人民政府门户补全 — 上级政府门户区县导航 HTML 提取（禁用搜索引擎）。

用户指令（2026-11-11）：
- 县级人民政府 URL 理论齐全，缺 URL 就补全（甘孜等民族自治州广泛存在类似
  凉山的情况）。
- 补全禁止使用搜索引擎（SERP/百度/必应一律不碰）——只能从上级人民政府官网
  真实 HTML 提取区县导航 URL（smart_fetch 直接抓上级门户）；上级门户确无
  导航的县一律列名并在报告中列出。
- 范式 = p194 凉山 17 县：上级门户导航提取（官网锚文本简称如「木里县」与树
  全名「木里藏族自治县」用基底名归一匹配）→ 逐条 smart_fetch title 验证 →
  块树 u 回填 + s 留痕 → registry 登记（source_level=L2）。

缺口盘点（2026-11-11）：块树 k=人民政府 且 c∈{县级人民政府, 市辖区（地级
行政区划）, 直辖市辖县（县级行政区划）, 省直辖县级市/县/林区, 兵团直辖县级市
（自治区直辖县级市）} 且 u 为空的节点 1114 个，按父链最近有 u 的 k=人民政府
上级门户分组为 238 个上级单元。

流程：上级门户首页 →（无命中则顺链「网站导航/区县之窗/网站地图」栏目页，最多
2 页，均为首页真实链接进入）→ 全量 <a>/<option> 链接提取 → 基底名归一匹配县
节点（同父域名链接=门户自身占位，剔除）→ 候选逐条 title 验证 → 落库（树 +
registry）。断点续跑 state 文件 data/p195_state.json，重复运行跳过已处理上级单元。
"""
import json, os, re, sys, time, datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin, urlparse

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, "util"))
os.chdir(BASE)

# 浏览器层开启：JS 壳门户/县级站点需要渲染（CloakBrowser 会话有信号量锁 1）
os.environ.setdefault("BROWSER_TIERS", "on")
from smart_fetch import smart_fetch  # noqa: E402

TREE_F = "data/tree.json"
REG_F = "data/site_registry.json"
STATE_F = "data/p195_state.json"
today = datetime.date.today().strftime("%Y-%m-%d")

CTYPES = {"县级人民政府", "市辖区（地级行政区划）", "直辖市辖县（县级行政区划）",
          "省直辖县级市/县/林区", "兵团直辖县级市（自治区直辖县级市）"}

# ── 基底名归一（p194 范式：剥行政区后缀 + 循环剥离民族串）──
# 2026-11-12 修复: ①补「土族」（青海互助/民和/大通 土族系县名, 原名单只有
# 土家族≠土族）——「回族土族」堆叠靠 8 轮循环逐轮剥末尾; ②单字民族名（白/回/
# 满/苗/侗/傣/彝/黎/京/水/畲/羌/怒/土/壮）「族」必带——族? 可选项会让「长白」
# 第 2 轮被误剥成「长」; 多字民族名族可省（官方名「木里藏族」不带族）;
# ③整词剥空回退为去「族」保留族名本体（鄂温克族自治旗→鄂温克, 不是空）。
ETH_PY = re.compile(
    r"(哈萨克族?|维吾尔族?|柯尔克孜族?|蒙古族?|藏族?|回族|壮族|苗族|黎族"
    r"|侗族|满族|白族|傣族|彝族|哈尼族?|拉祜族?|傈僳族?|佤族?|水族"
    r"|羌族|布依族?|仡佬族?|仫佬族?|毛南族?|瑶族?|畲族|土家族?|土族"
    r"|锡伯族?|达斡尔族?|鄂温克族?|鄂伦春族?|赫哲族?|俄罗斯族?|塔塔尔族?|乌孜别克族?"
    r"|塔吉克族?|撒拉族?|保安族?|裕固族?|东乡族?|纳西族?|景颇族?|阿昌族?"
    r"|普米族?|怒族|德昂族?|独龙族?|基诺族?|门巴族?|珞巴族?|京族"
    r"|朝鲜族?|各族|自治)$")


def base(nm):
    """基底名归一: 行政区/功能区后缀循环剥离 + 民族串循环剥离。

    2026-11-12 用户指令「缩写/简称/全名匹配」扩展: 后缀补 管委会/管理区/
    新区/园区/示范区（乌拉盖管理区管委会→乌拉盖、德州天衢新区→德州天衢）,
    单轮剥不净的堆叠后缀（管委会→管理区）靠循环逐轮剥。"""
    t = nm or ""
    for _ in range(10):
        t0 = t
        t = re.sub(r"(自治州|自治县|自治旗|地区|盟|市|县|区|旗|行政委员会|行委|管委会|管理委员会|管理区|高新技术产业开发区|经济技术开发区|经济开发区|经开区|高新区|产业园区|工业园区|开发区|新区|园区|示范区)$",
                   "", t)
        if not t:
            # 后缀剥空 → 回退: 去「族」保留族名本体（鄂温克族→鄂温克）
            return re.sub(r"族$", "", t0) or t0
        pre = t
        t = ETH_PY.sub("", t)
        if not t:
            # 民族串整词剥空（鄂温克族→""）→ 回退去「族」（鄂温克）
            return re.sub(r"族$", "", pre) or pre
        if t == t0:
            break
    return t


# 蒙旗/民族县/功能区 常用简称 ↔ 全名（门户锚文本常用简称, 双向查表——
# 2026-11-12 用户指令「缩写 简称 全名等等的匹配」）
ABBR = {
    "科左中旗": "科尔沁左翼中旗", "科左后旗": "科尔沁左翼后旗",
    "科右前旗": "科尔沁右翼前旗", "科右中旗": "科尔沁右翼中旗",
    "达茂旗": "达尔罕茂明安联合旗",
    "察右前旗": "察哈尔右翼前旗", "察右中旗": "察哈尔右翼中旗",
    "察右后旗": "察哈尔右翼后旗",
    "东乌旗": "东乌珠穆沁旗", "西乌旗": "西乌珠穆沁旗",
    "阿左旗": "阿拉善左旗", "阿右旗": "阿拉善右旗",
    "前郭县": "前郭尔罗斯蒙古族自治县", "前郭": "前郭尔罗斯蒙古族自治县",
    "莫旗": "莫力达瓦达斡尔族自治旗", "鄂温克旗": "鄂温克族自治旗",
    "鄂伦春旗": "鄂伦春自治旗",
    "扎旗": "扎鲁特旗", "喀旗": "喀喇沁旗", "翁旗": "翁牛特旗",
    "克旗": "克什克腾旗", "阿旗": "阿鲁科尔沁旗", "陈旗": "陈巴尔虎旗",
    "新左旗": "新巴尔虎左旗", "新右旗": "新巴尔虎右旗",
    "达旗": "达拉特旗", "准旗": "准格尔旗", "伊旗": "伊金霍洛旗",
    "杭旗": "杭锦旗", "鄂旗": "鄂托克旗", "鄂前旗": "鄂托克前旗",
    "乌旗": "乌审旗", "太旗": "太仆寺旗", "白旗": "正镶白旗",
    "蓝旗": "正蓝旗", "黄旗": "镶黄旗", "镶黄": "镶黄旗",
    "和林县": "和林格尔县", "和林": "和林格尔县",
    "营子区": "鹰手营子矿区", "营子": "鹰手营子矿区",
    "阜合产业园": "阜阳合肥现代产业园区", "阜合园区": "阜阳合肥现代产业园区",
    "苏滁产业园": "中新苏滁高新技术产业开发区",
    "宿马园区": "宿州马鞍山现代产业园区",
}
# 仅正向: 简称→全名（全名自身 base 归一即可匹配; 一个全名可有多个简称,
# 反向展开会互相覆盖——前郭县/前郭 都指 前郭尔罗斯蒙古族自治县）


COUNTY_RE = re.compile(r"^[一-鿿]{1,10}(自治县|自治旗|县|市|区|旗|林区|矿区)$")
NAV_KW = re.compile(r"(区县|县区|旗县|盟市|区市|各区市|所辖|辖属|县市区|区县政府|区县之窗|县区网站|各级政府|下级政府|各区概览|区县（市）政府网站|区县市政府网站|园区|开发区|经济区|管理区|功能区|示范区|新区|网站导航|网站地图|地方网站|政府网站|下属|下级|名片|风采|站群|群导航|网站群|友情链接|相关链接|子站)")
A_RE = re.compile(r'''<a\s[^>]*?href=["']([^"']+)["'][^>]*>\s*([^<>]{1,20}?)\s*</a>''', re.S)
OPT_RE = re.compile(r'''<option\s[^>]*?value=["']([^"']*)["'][^>]*>\s*([^<>]{1,20}?)\s*</option>''', re.S)
GOV_HOST = re.compile(r"gov\.cn$", re.I)


def match_token(node_name):
    """功能区节点的匹配令牌：高新→高新, 经开/经济开发→经开, 滨海→滨海。
    管理区/管委会/新区/园区/示范区 由 base() 后缀剥离归一, 不再走令牌
    （乌拉盖管理区管委会→乌拉盖 比「含管理区字样」更宽松且仍有歧义保护）。"""
    if "高新技术产业开发区" in node_name or "高新区" in node_name:
        return "高新"
    if "经济技术开发区" in node_name or "经开区" in node_name or "经济开发区" in node_name:
        return "经开"
    if "滨海" in node_name:
        return "滨海"
    return None


SFX = ("自治县", "自治旗", "林区", "矿区", "县", "市", "区", "旗")


def sfx_of(nm):
    """行政区后缀（自治县优先于县）。无后缀返回 ""。"""
    for s in SFX:
        if nm.endswith(s):
            return s
    return ""


def sfx_compat(nsfx, csfx):
    """后缀相容判定。

    用户定稿（2026-11-11）：县级市本质是县——本脚本域内全部是县级节点
    （c∈县级人民政府类），县/县级市/市辖区/旗/自治县/林区/矿区 均为县级,
    后缀互容（寿光县→寿光市=撤县设市同址, 应匹配）。
    地级同名陷阱（通化市 vs 通化县）由 process_parent 的「上级自身链接
    排除」兜底: 与上级门户同名的候选一律跳过。"""
    return True


def county_hit(node_name, cand_text, parent_base=""):
    """县节点名 vs 官网锚文本 是否同一机构（缩写/简称/全名互认）。

    正则只做候选粗筛, 不是最终手段——最终以 title 全名验证（verify_title）为准。
    这里先按「行政区后缀语义」拦截同名不同类的错误候选: 寿光县≠寿光市。"""
    cand_text = norm_text(cand_text)   # 幂等归一（门户网站/政府等修饰剥除）
    # 简称↔全名 查表展开（达茂旗↔达尔罕茂明安联合旗、前郭↔前郭尔罗斯…）
    cand_full = ABBR.get(cand_text) or ABBR.get(base(cand_text))
    if cand_full:
        cand_text = cand_full
    node_full = ABBR.get(node_name) or ABBR.get(base(node_name))
    if node_full:
        node_name = node_full
    # 合署/更名别名（真实 HTML 锚文本用现名, 树节点用旧名; title 验证兜底裁决）:
    # 烟台经开区与黄渤海新区合署办公, 门户 footer 现名「黄渤海新区」,
    # 官网 www.yeda.gov.cn title=「烟台经济技术开发区」
    if node_name == "烟台经济技术开发区" and cand_text == "黄渤海新区":
        return True
    tok = match_token(node_name)
    if tok:
        # 2026-11-12 地名约束: 令牌「经开/高新」宽泛命中会让蚌埠经开区误配
        # 安庆经开区的链接（安徽轮实测候选全指向 aqdz.anqing.gov.cn）——
        # 令牌命中后须地名基底一致（蚌埠 vs 安庆 → 拒; 裸词无地名 → 放行）
        nb2, cb2 = base(node_name), base(cand_text)
        # 级别前缀兼容: 国家漯河经济技术开发区=漯河经济技术开发区
        cb2 = re.sub(r"^(国家|国家级)", "", cb2)
        if nb2 and cb2 and nb2 != cb2:
            return False
        # 全名候选「经济技术开发区」不含连续子串「经开」——令牌须展开匹配
        pat = {"经开": r"经开|经济技术开发|经济开发", "高新": r"高新|高新技术产业",
               "滨海": r"滨海"}.get(tok)
        return bool(pat and re.search(pat, cand_text))
    nb, cb = base(node_name), base(cand_text)
    # 2026-11-12 合署括号形态: 锚文本「金义新区(金东区)」（金义新区与金东区
    # 合署办公, 金华门户区县导航现名）——拆出括号内外组合（外+内/外/内）参与匹配
    cand_variants = {cand_text}
    _m = re.search(r"[(（]([^)）]{2,14})[)）]$", cand_text)
    if _m:
        _inner, _outer = _m.group(1), cand_text[:_m.start()]
        cand_variants |= {_outer + _inner, _outer, _inner}
    # 父前缀变体: 德州天衢新区 vs 天衢新区（锚文本省父名）、反向亦然
    pb = base(parent_base) if parent_base else ""
    for cv in cand_variants:
        nb2, cb2 = base(node_name), base(cv)
        if nb2 == cb2:
            return True
        if pb:
            for a, b in ((nb2, cb2), (cb2, nb2)):
                if a.startswith(pb) and len(a) > len(pb) + 1 \
                        and a[len(pb):] == b:
                    return True
    return False


def norm_text(t):
    t = re.sub(r"[\s　]+", "", t or "")
    # 2026-11-12: 列表项装饰符前缀（广州网站地图页「· 越秀区 」形态）剥除
    # 2026-11-16: option 文本「--路北区--」形态（唐山门户）——首尾 -- 全剥
    t = t.strip("-").strip()
    t = t.lstrip("·•●○◆▪▫-|")
    while True:
        t0 = t
        for suf in ("人民政府", "门户网站", "政府", "网站", "门户", "网"):
            if t.endswith(suf):
                t = t[: -len(suf)]
                break
        # 石家庄县区名片类列表锚文本带日期（「赞皇2026-04-28」）——剥日期
        t = re.sub(r"(\d{4}-\d{1,2}-\d{1,2}|\d{4}-\d{1,2}|\d{4}\.\d{1,2}\.\d{1,2})$", "", t)
        if t == t0 or not t:
            break
    return t


def resolve_url(parent_u, href):
    href = (href or "").replace("&amp;", "&").strip()
    if not href or href.startswith("javascript:") or href.startswith("mailto:") \
            or href.startswith("#"):
        return ""
    u = urljoin(parent_u, href)
    p = urlparse(u)
    if p.scheme not in ("http", "https") or not p.netloc:
        return ""
    return u.split("#")[0].rstrip("/")


TAG_RE = re.compile(r"<[^>]+>")
A_RE2 = re.compile(r"""<a\s[^>]*?href=["']([^"']+)["'][^>]*>(.*?)</a>""", re.S)
OPT_RE2 = re.compile(r"""<option\s[^>]*?value=["']([^"']*)["'][^>]*>(.*?)</option>""", re.S)
# 2026-11-13 onclick 跳转通道（鄂州 zqdh 形态: href=javascript:void(0) +
# onclick="MM_jumpMenuA('http://www.echeng.gov.cn/...')"）——URL 取函数
# 调用首个引号参数（单引号在双引号属性内 / 双引号转义均可）
ONCLICK_RE = re.compile(
    r"""<a\s[^>]*?onclick=["'][^"']*?[(]["']([^"']+)["'][)][^>]*>(.*?)</a>""", re.S)
# 2026-11-13 el-option 通道（昭通 Vue 门户形态: el-select 县区下拉在静态
# HTML 里是 <el-option label="昭阳区人民政府" value="http://www.zyq.gov.cn">）
# label/value 属性顺序不固定, 两次扫描兜住两序
EL_OPT_RE = re.compile(
    r"""<el-option\s+label=["']([^"']*)["']\s+value=["']([^"']*)["'][^>]*/?>""", re.S)
EL_OPT_RE2 = re.compile(
    r"""<el-option\s+value=["']([^"']*)["']\s+label=["']([^"']*)["'][^>]*/?>""", re.S)


def el_label_ok(t):
    """el-option label 判定: 「昭阳区人民政府」剥人民政府/政府/门户后缀后
    须为行政区名（COUNTY_RE）或裸地名（BARE_RE）。"""
    t2 = t
    for suf in ("人民政府门户网站", "人民政府", "政府门户网站", "政府", "门户网站"):
        if t2.endswith(suf):
            t2 = t2[: -len(suf)]
            break
    return bool(COUNTY_RE.match(t2) or BARE_RE.match(t2))
BARE_RE = re.compile(r"^[一-鿿]{2,6}$")


def clean_html_text(s):
    return re.sub(r"[\s　]+", "", TAG_RE.sub("", s or ""))


def extract_candidates(parent_u, html):
    """门户 HTML → (文本, 解析后 URL) 候选对（URL 去重）。

    双通道提取（2026-11-11 用户指正「渲染后底部导航有区县 URL 但没提取到」）：
    ① 导航区块锚定——NAV_KW 标题（区县/县市区/网站导航…）附近 6KB 窗口内
       链接, 文本放宽为裸地名 2-6 字（底部导航常用纯地名/简称, 无行政区后缀）;
    ② 全页兜底——锚文本带行政区后缀（XX县/XX市/XX区…）的链接。
    嵌套标签文本经 clean_html_text 合并（<a>临朐<span>县</span></a>→临朐县）。"""
    parent_host = urlparse(parent_u).netloc.lower()
    cands, seen = [], set()

    def push(txt, href):
        if not txt:
            return
        u = resolve_url(parent_u, href)
        if not u or "gov.cn" not in urlparse(u).netloc.lower():
            return
        if "zwfw" in urlparse(u).netloc.lower():
            # 2026-11-13 荆门实证: 省级政务服务平台聚合页（zwfw.hubei.gov.cn
            # /index.html?areaId=420802000000 形态, 一个域名被全部县共用）
            # 不是县政府门户, 直接剔除——否则 title「XX县政务服务网」会被
            # 「政务网」后缀误放行
            return
        if urlparse(u).netloc.lower() == parent_host:
            # 门户自身链接=占位, 剔除（同域深链亦是本门户 CMS 内容页,
            # 如「政府网站年度报表」栏目——曾把 col/col42385 误当县门户）
            return
        # 2026-11-12: 跨域深链不再剔除——官方名录页给的县站入口常是
        # 「根址+栏目」形态（石家庄县区名片 → 赵县 zhaoxian.gov.cn/columns/xxx/
        # index.html）。误入的内容页由 title 全名验证兜底拒绝。
        if u in seen:
            return
        seen.add(u)
        cands.append((txt, u))

    for m in NAV_KW.finditer(html):
        window = html[m.start(): m.start() + 12000]
        for hm in A_RE2.finditer(window):
            t = norm_text(clean_html_text(hm.group(2)))
            if BARE_RE.match(t) or COUNTY_RE.match(t):
                push(t, hm.group(1))
        # 2026-11-13 onclick 跳转通道（鄂州 zqdh 形态）:
        # <a href="javascript:void(0)" onclick="MM_jumpMenuA('http://xx.gov.cn/')">鄂城区</a>
        for cm in ONCLICK_RE.finditer(window):
            t = norm_text(clean_html_text(cm.group(2)))
            if BARE_RE.match(t) or COUNTY_RE.match(t):
                push(t, cm.group(1))
        for om in OPT_RE2.finditer(window):
            t = norm_text(clean_html_text(om.group(2)))
            if BARE_RE.match(t) or COUNTY_RE.match(t):
                push(t, om.group(1))
        # 2026-11-13 el-option 通道（昭通 Vue el-select 下拉, label/value 两序）
        for em in EL_OPT_RE.finditer(window):
            t = norm_text(clean_html_text(em.group(1)))
            if el_label_ok(t):
                push(t, em.group(2))
        for em in EL_OPT_RE2.finditer(window):
            t = norm_text(clean_html_text(em.group(2)))
            if el_label_ok(t):
                push(t, em.group(1))
    DATE_RE = re.compile(r"\d{4}-\d{1,2}-\d{1,2}")
    for hm in A_RE2.finditer(html):
        raw = clean_html_text(hm.group(2))
        t = norm_text(raw)
        if COUNTY_RE.match(t):
            push(t, hm.group(1))
        elif DATE_RE.search(raw) and BARE_RE.match(t):
            # 「县名2026-04-28」类列表锚文本（石家庄县区名片·最新更新列）
            push(t, hm.group(1))
    for cm in ONCLICK_RE.finditer(html):
        raw = clean_html_text(cm.group(2))
        t = norm_text(raw)
        if COUNTY_RE.match(t) or BARE_RE.match(t):
            push(t, cm.group(1))
    for om in OPT_RE2.finditer(html):
        raw = clean_html_text(om.group(2))
        t = norm_text(raw)
        if COUNTY_RE.match(t):
            push(t, om.group(1))
        elif DATE_RE.search(raw) and BARE_RE.match(t):
            push(t, om.group(1))
    for em in EL_OPT_RE.finditer(html):
        t = norm_text(clean_html_text(em.group(1)))
        if el_label_ok(t):
            push(t, em.group(2))
    for em in EL_OPT_RE2.finditer(html):
        t = norm_text(clean_html_text(em.group(2)))
        if el_label_ok(t):
            push(t, em.group(1))
    return cands


def extract_nav_pages(parent_u, html):
    """从首页找「网站导航/区县之窗/网站地图」类栏目页真实链接，最多 3 个。
    两轮：先精确匹配（区县/旗县/县市区/网站地图/网站导航/区县政府等栏目名），
    再模糊匹配（含关键字但排除 动态/专题/新闻 类）；首轮命中优先。"""
    exact = re.compile(r"^(区县|旗县|盟市|县市区|区县政府|区县之窗|网站地图|网站导航|地方网站|政府网站|各县市|旗县市|县市区政府|各市区县|县区名片|区县名片|县市区名片|各县名片|县区风采|区县风采|站群导航|站群|网站群|友情链接|相关链接)$")
    fuzzy = NAV_KW
    pages = []
    for href, txt in A_RE.findall(html):
        t = (txt or "").strip()
        if not exact.search(t):
            continue
        u = resolve_url(parent_u, href)
        if u and u not in pages:
            pages.append(u)
        if len(pages) >= 5:
            break
    if len(pages) < 5:
        for href, txt in A_RE.findall(html):
            t = (txt or "").strip()
            if re.search(r"(动态|专题|新闻|时讯)", t):
                continue
            if not fuzzy.search(t):
                continue
            u = resolve_url(parent_u, href)
            if u and u not in pages:
                pages.append(u)
            if len(pages) >= 5:
                break
    return pages


# ── title 验证 ──
def render_pass(parent_u, html, _hard_timeout=90):
    """JS 壳门户渲染: 子进程隔离（data/p195_render_one.py）。

    2026-11-12 第三次修正: 前两次在本进程内用 DrissionPage, 其 ws 断连
    收尾异常会拖垮主采集进程（worker 线程死亡 → 线程池永久等待/进程死亡）。
    改为每次渲染一个独立子进程, 崩溃不传染; os._exit 硬退出不收尾。"""
    try:
        from smart_fetch import _cloak_sem
        if not _cloak_sem.acquire(timeout=150):
            if os.environ.get("P195_DEBUG"):
                print(f"[debug render {parent_u}] semaphore acquire 失败", flush=True)
            return None
        try:
            import subprocess as _sp
            import sys as _s
            out = ""
            # 2026-11-12 第四次修正: 60s 超时在并发负载下常假失败（r8 烟台 no_nav
            # 即此因）→ 超时提到 90s, 失败/短输出重试 1 次（子进程隔离, 重试无害）
            for _try in range(2):
                try:
                    r = _sp.run([_s.executable,
                                 os.path.join(BASE, "data", "p195_render_one.py"),
                                 parent_u],
                                capture_output=True, text=True, timeout=120)
                    out = (r.stdout or "").strip()
                    if len(out) > 1000:
                        return out
                    if os.environ.get("P195_DEBUG"):
                        print(f"[debug render {parent_u}] try{_try} rc={r.returncode} "
                              f"outlen={len(r.stdout or '')} err={ (r.stderr or '')[-150:]!r}",
                              flush=True)
                except Exception as e:
                    if os.environ.get("P195_DEBUG"):
                        print(f"[debug render {parent_u}] try{_try} 异常 {type(e).__name__}: {str(e)[:80]}",
                              flush=True)
            return None
        finally:
            try:
                _cloak_sem.release()
            except Exception:
                pass
    except Exception:
        return None
def _check_title(county, h):
    """对已取得的 HTML 做全名级 title 校验。返回 (ok, title) 或 None。"""
    mt = re.search(r"<title>(.*?)</title>", h or "", re.S | re.I)
    t = (mt.group(1).strip() if mt else "")[:60]
    if not t:
        return None
    if re.search(r"404|无法访问|页面不存在|错误|ERROR", t, re.I):
        return False, f"异常页: {t}"
    t2 = t
    # 2026-11-12: 破折号重复标题（民和县人民政府—民和县人民政府）取首段
    t2 = re.split(r"[—-]", t2, maxsplit=1)[0].strip()
    # 中性标题（JS 壳站 title=网站首页/首页）——URL 来自上级门户权威导航且
    # 可达, 标题无矛盾即放行（须在修饰剥离前判, 否则「网站首页」被剥成空）
    if t2 in ("网站首页", "首页"):
        return True, t
    # 循环剥离修饰（「福山区政府网站」→网站→政府→福山区, 单轮会漏;
    # 「大通回族土族自治县人民政府门户网」→门户网→人民…）
    while True:
        t0 = t2
        # 2026-11-13 补「网/政务网」后缀: 曲阜「中国曲阜网」、青岛「崂山政务网」
        # （门户网站形态不带政府字样）, 剥后缀后滑窗基底可匹配
        for suf in ("人民政府", "门户网站", "门户网", "政府网", "政务网", "人民", "政府", "官方网站",
                    "门户", "网站", "官网", "首页", "欢迎光临", "网"):
            if t2.endswith(suf):
                t2 = t2[: -len(suf)].rstrip(" _-|·")
                break
        if t2 == t0 or not t2:
            break
    # 全名校验须兼容「市前缀」: 烟台市芝罘区人民政府 → 芝罘区
    if base(t2) != base(county) and not t2.endswith(county):
        # 前缀变体（大连.普兰店 / 大连瓦房店- / 广东惠来）: 逐位置滑窗试后缀
        t2r = t2.rstrip(".·—|_-")
        ok_seg = False
        for i in range(len(t2r) - 1):
            seg = t2r[i:]
            if base(seg) == base(county) or seg.endswith(county):
                ok_seg = True
                break
        if not ok_seg:
            return False, f"名称不符: {t}"
        return True, t
    # 名称已对上; 兜底只拦无中文的垃圾标题（如纯域名停放页）
    if not re.search(r"[一-鿿]", t2):
        return False, f"名称不符: {t}"
    return True, t


def verify_title(county, u):
    """验证县节点对应 URL 的 title 合理性。返回 (ok, title, final_u)。

    最终裁决链: curl 直取 title 全名校验 → 失败/无 title 时渲染兜底
    （县级站点大量是 JS 壳, curl 拿不到 title）→ 仍不行时**根化重验**
    （2026-11-13 石家庄教训: 门户网站地图给的县站入口是「根址+栏目」
    深链, 栏目页 title=「魅力赵州/平山概览」非首页「XX县人民政府」——
    取根首页再验, 成功则 final_u=根地址, 落库用根更规范）→ 拒。"""
    try:
        h, m = smart_fetch(u, timeout=25)
        if not h or len(h) < 300:
            h2, m2 = fetch_via_dps(u)
            if h2:
                h, m = h2, m2
        res = _check_title(county, h) if h else None
        if res and res[0]:
            return res[0], res[1], u
        if not res or not res[0]:
            # 渲染兜底（子进程隔离, 见 render_pass）——JS 壳县级站点靠它过验证
            rh = None
            try:
                from smart_fetch import _cloak_sem
                if _cloak_sem.acquire(timeout=120):
                    try:
                        import subprocess as _sp
                        import sys as _s
                        r = _sp.run([_s.executable,
                                     os.path.join(BASE, "data", "p195_render_one.py"), u],
                                    capture_output=True, text=True, timeout=60)
                        rh = (r.stdout or "").strip()
                    finally:
                        try:
                            _cloak_sem.release()
                        except Exception:
                            pass
            except Exception:
                rh = None
            if rh and len(rh) > 500:
                res2 = _check_title(county, rh)
                if res2 and res2[0]:
                    return res2[0], res2[1], u
        # 根化重验: 深链（有 path）失败时取根首页（curl → dps → 渲染 同链）
        from urllib.parse import urlsplit, urlunsplit
        try:
            parts = urlsplit(u)
            root = urlunsplit((parts.scheme or "https", parts.netloc, "/", "", ""))
        except Exception:
            root = ""
        if root and root.rstrip("/") != u.rstrip("/"):
            for fetcher in (lambda x: smart_fetch(x, timeout=25),
                            lambda x: fetch_via_dps(x)):
                try:
                    rh2, mm2 = fetcher(root)
                    if rh2 and len(rh2) >= 300:
                        res3 = _check_title(county, rh2)
                        if res3 and res3[0]:
                            return res3[0], res3[1], root
                        if res3:
                            break   # 根页 title 明确但不符合, 不再渲染
                except Exception:
                    pass
            # 根渲染兜底
            try:
                from smart_fetch import _cloak_sem
                if _cloak_sem.acquire(timeout=120):
                    try:
                        import subprocess as _sp
                        import sys as _s
                        r = _sp.run([_s.executable,
                                     os.path.join(BASE, "data", "p195_render_one.py"), root],
                                    capture_output=True, text=True, timeout=60)
                        rrh = (r.stdout or "").strip()
                    finally:
                        try:
                            _cloak_sem.release()
                        except Exception:
                            pass
                    if rrh and len(rrh) > 500:
                        res4 = _check_title(county, rrh)
                        if res4 and res4[0]:
                            return res4[0], res4[1], root
            except Exception:
                pass
        if res:
            return res[0], res[1], u
        return False, f"无title[{m}]", u
    except Exception as e:
        return False, f"异常: {str(e)[:30]}", u


# ── 断点 state ──
def load_state():
    if os.path.exists(STATE_F):
        return json.load(open(STATE_F, encoding="utf-8"))
    return {"parents": {}, "verified": {}}


def save_state(st):
    tmp = STATE_F + ".tmp"
    json.dump(st, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    os.replace(tmp, STATE_F)


# ── 1. 枚举缺口（每次从树重读，已填自动跳过）──
def walk(n, path):
    yield n, path
    for k in n.get("ks", []) or []:
        yield from walk(k, path + [n])


def find_ancestor(path):
    """父链中最近的 k=人民政府 且 u 非空节点 → (name, u)；没有则省级门户。"""
    for p in reversed(path):
        if p.get("k") == "人民政府" and p.get("u"):
            return p.get("n"), p.get("u")
    for p in reversed(path):
        if p.get("k") == "人民政府":
            return p.get("n"), p.get("u") or ""
    return None, None


tree = json.load(open(TREE_F, encoding="utf-8"))
reg = json.load(open(REG_F, encoding="utf-8"))
st = load_state()

# 直筒子市孪生节点同源回填（2026-11-12 全省审计发现）: 东莞/中山/儋州/
# 嘉峪关 不设区, 树里同时有「地级市人民政府」(有 u) 与「县级人民政府」(u 空)
# 两个节点——同一政府同一门户, 县级孪生节点直接继承地级 u, 不再当缺口采。
_twin = {}
for _n, _path in walk(tree, []):
    if _n.get("k") == "人民政府" and _n.get("c") == "地级市人民政府" and _n.get("u"):
        _twin[_n["n"]] = _n["u"]

gaps_by_parent = {}          # parent_name -> {county_full: {"node":..., "c":..., "base":...}}
county_node = {}             # (parent_name, county_full) -> node
for n, path in walk(tree, []):
    if n.get("k") != "人民政府" or n.get("c") not in CTYPES:
        continue
    if n.get("u"):
        continue
    if n.get("n") in _twin:
        n["u"] = _twin[n["n"]]
        n["s"] = "来源：地级市政府门户同源（直筒子市县级孪生节点）"
        continue
    pn, pu = find_ancestor(path)
    if not pn:
        continue
    prov_u = ""
    for p2 in reversed(path):
        if p2.get("k") == "人民政府" and p2.get("u") and (
                p2.get("c", "").startswith("省级") or "省级" in p2.get("n", "")
                or p2.get("n", "").endswith(("省", "自治区"))):
            prov_u = p2["u"]
            break
    prov = path[2].get("n", "") if len(path) > 2 else ""
    gaps_by_parent.setdefault(pn, {"u": pu, "prov_u": prov_u, "prov": prov,
                                   "counties": {}})
    gaps_by_parent[pn]["counties"][n["n"]] = {"node": n, "c": n.get("c", ""),
                                              "base": base(n["n"])}
    county_node[(pn, n["n"])] = n

# 树是唯一事实: 只要该上级单元在当前树里仍有缺 u 的县, 就（重）处理
# （state 曾与并发进程互踩回退, 以树为准做对账; 幂等——空才填）
parents = [p for p in gaps_by_parent]
# 用户追加优先级（2026-11-11）：6 个市级单位优先，处理完再继续全国其余缺口
# 2026-11-12 用户重点: 山东 + 全国大缺口城市（渲染轮主攻）
PRIORITY = ["济南市", "青岛市", "烟台市", "潍坊市", "济宁市", "聊城市", "威海市",
            "菏泽市", "东营市", "日照市", "临沂市", "德州市", "淄博市", "滨州市",
            "泰安市", "枣庄市", "石家庄市", "唐山市", "杭州市", "合肥市", "南京市",
            "苏州市", "广州市", "黔南布依族苗族自治州", "昭通市", "廊坊市",
            "常德市", "郴州市", "佳木斯市", "湘潭市", "肇庆市", "梅州市"]
parents.sort(key=lambda p: (p not in PRIORITY, PRIORITY.index(p) if p in PRIORITY else 0))
# 调试/定向跑: P195_ONLY=烟台市 只处理匹配上级单元（逗号分隔可多个）;
# P195_PROV=广东省 按省过滤（2026-11-12 用户指令「一个省一个省补全」）
_only = [x.strip() for x in os.environ.get("P195_ONLY", "").split(",") if x.strip()]
if _only:
    parents = [p for p in parents if any(o in p for o in _only)]
_prov = os.environ.get("P195_PROV", "").strip()
if _prov:
    parents = [p for p in parents if gaps_by_parent[p].get("prov") == _prov]
print(f"缺口总数 {sum(len(v['counties']) for v in gaps_by_parent.values())} 个, "
      f"上级单元 {len(gaps_by_parent)} 个, 待处理 {len(parents)} 个", flush=True)
if parents:
    print("处理顺序: 优先级", [p for p in parents if p in PRIORITY],
          "→ 其余", len([p for p in parents if p not in PRIORITY]), "个", flush=True)


# ── 2. 提取（每上级单元：首页 + 导航栏目页 + 省级兜底 + 渲染兜底）──
def _fetch_ok(u):
    """smart_fetch → dps → https/http 协议降级 三链取页。返回 (html, mode)。"""
    h, m = smart_fetch(u, timeout=25)
    if h and len(h) >= 500:
        return h, m
    # 2026-11-12: http 协议降级（部分市县门户 https TLS 部署不齐,
    # 官方同域名 http 可访问——如全国人大 http:// 模式）
    if u.startswith("https://"):
        h2, m2 = smart_fetch("http://" + u[len("https://"):], timeout=25)
        if h2 and len(h2) >= 500:
            return h2, m2 + "/http"
    h3, m3 = fetch_via_dps(u)
    if h3 and len(h3) >= 500:
        return h3, m3
    return None, m


def _absorb(cands, pages_html):
    """提取候选并追加; pages_html: [(base_url, html)]"""
    for bu, hh in pages_html:
        cands += extract_candidates(bu, hh)


def process_parent(pn):
    info = gaps_by_parent[pn]
    pu = info["u"]
    if not pu:
        return pn, {"status": "no_parent_url", "counties": {}}
    try:
        pages = []          # [(base_url, html)] 已取得的真实页面
        html, m = _fetch_ok(pu)
        if html:
            pages.append((pu, html))
        prov_u = info.get("prov_u", "")
        # 父级门户失败时（fetch_fail/无 u 兜底）省级门户直接参与提取:
        # 省直辖县/省管县级市（湖北仙桃、新疆兵团市等）的导航在省级页面
        if not html and prov_u and prov_u != pu:
            ph, pm = _fetch_ok(prov_u)
            if ph:
                pages.append((prov_u, ph))
                m = f"{m}→prov[{pm}]"
        parent_fetch = bool(html)
        # 2026-11-12 用户指令「请求不到的不用管, 重点是能请求到的 HTML 提取」:
        # 父门户 curl/http/dps 三链都取不到 → 直接 fetch_fail, 不渲染不纠缠
        # （渲染留给能取到静态页的 JS 壳门户）
        if not pages:
            return pn, {"status": f"fetch_fail[{m}]", "counties": {}}
        _cache = {}

        def grab(u):
            if u in _cache:
                return _cache[u]
            h2, _ = _fetch_ok(u)
            _cache[u] = h2 or ""
            return _cache[u]

        cands = []
        for bu, hh in pages:
            cands += extract_candidates(bu, hh)
        # 去重（同 URL 只留一个，保持「首页优先」顺序）
        dedup, seen = [], set()
        for t, u in cands:
            if u in seen:
                continue
            seen.add(u)
            dedup.append((t, u))
        cands = dedup
        # 基底名匹配（首中即止；同父内基底名/功能区令牌撞车=歧义，均不采）
        amb = set()
        base_cnt = {}
        for cname, cinfo in info["counties"].items():
            base_cnt.setdefault(cinfo["base"], []).append(cname)
        for cs in base_cnt.values():
            if len(cs) > 1:
                amb.update(cs)
        tok_cnt = {}
        for cname, cinfo in info["counties"].items():
            tk = match_token(cname)
            if tk:
                tok_cnt.setdefault(tk, []).append(cname)
        for cs in tok_cnt.values():
            if len(cs) > 1:
                amb.update(cs)
        parent_base, parent_sfx = base(pn), sfx_of(pn)

        def match_all(cands):
            found = {}
            for cname, cinfo in info["counties"].items():
                if cname in amb:
                    continue
                hit = None
                for t, u in cands:
                    # 上级门户自身同名链接（地级市链接）: 通化市↔通化县 陷阱排除
                    if base(t) == parent_base and sfx_of(t) == parent_sfx:
                        continue
                    if county_hit(cname, t, parent_base):
                        hit = u
                        break
                if hit:
                    found[cname] = hit
            return found

        def merge(found, found2):
            for cname, u in found2.items():
                found.setdefault(cname, u)

        def add_page(bu, hh):
            """追加页面候选并重新匹配（去重保持「先到先得」）"""
            nonlocal cands
            for t, u in extract_candidates(bu, hh):
                if u not in seen:
                    seen.add(u)
                    cands.append((t, u))

        found = match_all(cands)
        need = lambda: len(found) < len(info["counties"]) - len(amb)

        # 2026-11-12 分级升级链（用户指正「首页数据一般就有了, BFS 必要性不大,
        # 但部分确实需要」→ 懒加载, 不足才升级）:
        # L0 首页静态 → L1 渲染首页 → L2 BFS 栏目页 → L3 省级兜底(静态/渲染/栏目页)
        if need():
            rh = render_pass(pu, None)
            if rh and len(rh) > 1000:
                add_page(pu, rh)
                merge(found, match_all(cands))
        if need():
            for bu, hh in pages:
                for l1 in extract_nav_pages(bu, hh)[:5]:
                    h1 = grab(l1)
                    if not h1:
                        continue
                    add_page(l1, h1)
                    merge(found, match_all(cands))
                    if not need():
                        break
                    for l2 in extract_nav_pages(l1, h1)[:3]:
                        h2 = grab(l2)
                        if h2:
                            add_page(l2, h2)
                            merge(found, match_all(cands))
                if not need():
                    break
        if need() and prov_u and prov_u != pu and not any(b == prov_u for b, _ in pages):
            ph, pm = _fetch_ok(prov_u)
            if ph:
                add_page(prov_u, ph)
                merge(found, match_all(cands))
        if need() and prov_u and prov_u != pu:
            rh2 = render_pass(prov_u, None)
            if rh2 and len(rh2) > 1000:
                add_page(prov_u, rh2)
                merge(found, match_all(cands))
        if need() and prov_u and prov_u != pu:
            for l1 in extract_nav_pages(prov_u, grab(prov_u) or "")[:5]:
                h1 = grab(l1)
                if not h1:
                    continue
                add_page(l1, h1)
                merge(found, match_all(cands))
                if not need():
                    break
        if found:
            status = "ok"
        elif not parent_fetch and not any(b != pu for b, _ in pages):
            status = f"fetch_fail[{m}]"   # 父/省均取不到且渲染无果
        else:
            status = "no_nav"
        return pn, {"status": status, "counties": found}
    except Exception as e:
        return pn, {"status": f"exception:{str(e)[:40]}", "counties": {}}


# ── dps 私密代理（用户指令 2026-11-12: 德阳等站 IP 封禁, 用站级粘性代理兜底）
#    路径由环境变量 DPS_PROXY_PATH 指定——代理模块含密钥，不入本仓库；
#    未设置则跳过代理兜底（直连照跑）。此前写死本机绝对路径会连带泄漏目录结构 ──
DPS_MOD = None
try:
    _dps_path = os.environ.get("DPS_PROXY_PATH", "")
    if not _dps_path:
        raise ImportError("DPS_PROXY_PATH 未设置")
    import importlib.util as _ilu
    _spec = _ilu.spec_from_file_location("dps_proxy", _dps_path)
    if _spec and _spec.loader:
        DPS_MOD = _ilu.module_from_spec(_spec)
        _spec.loader.exec_module(DPS_MOD)
except Exception:
    DPS_MOD = None


def fetch_via_dps(url, tries=3):
    """站级粘性代理兜底: 直连被封(403/空响应)的 host 走 dps 私密代理。
    失败 mark_host_failed 轮换节点, 全部失败返回 (None, 原因)。"""
    if DPS_MOD is None:
        return None, "no_dps"
    host = urlparse(url).netloc
    for i in range(tries):
        px = DPS_MOD.get_proxies_for_host(host)
        if not px:
            return None, "dps_no_proxy"
        try:
            from curl_cffi import requests as _cfreq
            r = _cfreq.get(url, timeout=20, impersonate="chrome131", proxies=px)
            if r.status_code == 200 and len(r.text or "") > 200:
                return r.text, f"dps{i + 1}"
            DPS_MOD.mark_host_failed(host)
        except Exception:
            try:
                DPS_MOD.mark_host_failed(host)
            except Exception:
                pass
    return None, "dps_failed"


WORKERS = int(os.environ.get("P195_WORKERS", "8"))
if parents:
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(process_parent, p): p for p in parents}
        # 优先级批完成后立即落盘（断点保证）；其余每 10 个落盘
        pri_done = 0
        done_n = 0
        for fut in as_completed(futs):
            pn, res = fut.result()
            st["parents"][pn] = res
            done_n += 1
            if pn in PRIORITY:
                pri_done += 1
            if done_n % 10 == 0 or (pri_done >= len(PRIORITY) and done_n % 5 == 0):
                save_state(st)
                n_found = sum(1 for r in st["parents"].values() if r["counties"])
                print(f"  提取 {done_n}/{len(parents)} 上级单元, 有命中 {n_found}", flush=True)
    save_state(st)

ext_ok = {c: u for r in st["parents"].values() for c, u in r["counties"].items()}
print(f"提取阶段完成: 候选 {len(ext_ok)} 个县", flush=True)

# ── 3. title 验证（按 URL 去重；verified 键=(上级,县全名) 防重名碰撞）──
todo = []
seen_u = set()
for (pn, cname), node in county_node.items():
    vk = f"{pn}|{cname}"
    u = st["parents"].get(pn, {}).get("counties", {}).get(cname)
    if not u:
        continue
    v0 = st["verified"].get(vk)
    if v0 and v0.get("u") == u:
        # 通过的同 URL 永久跳过; 不过的同 URL 每轮都复验
        # （2026-11-12: title 校验规则多轮修复, 假阴性须尽快重验;
        #   封禁站多无候选, 不产生额外验证开销）
        if v0.get("ok"):
            continue
    if u in seen_u:
        continue
    seen_u.add(u)
    todo.append((pn, cname, u))
print(f"待验证 {len(todo)} 个", flush=True)


def verify_one(item):
    pn, cname, u = item
    ok, t, final_u = verify_title(cname, u)
    return pn, cname, u, ok, t, final_u


if todo:
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(verify_one, it): it for it in todo}
        for i, fut in enumerate(as_completed(futs)):
            pn, cname, u, ok, t, final_u = fut.result()
            st["verified"][f"{pn}|{cname}"] = {"u": final_u, "ok": ok, "title": t, "t": time.time()}
            if (i + 1) % 100 == 0:
                save_state(st)
                print(f"  验证 {i+1}/{len(todo)}", flush=True)
    save_state(st)

# ── 4. 落库（块树 u + s；registry L2 登记）──
filled = 0
for (pn, cname), node in county_node.items():
    v = st["verified"].get(f"{pn}|{cname}")
    u_cand = st["parents"].get(pn, {}).get("counties", {}).get(cname)
    # 2026-11-13 根化重验: verified 的 u 可能是栏目深链根化后的根地址,
    # 不再与候选 u_cand 全等——候选存在 + ok 即落库, 落库用 v["u"]（final_u）
    if not v or not v["ok"] or not u_cand:
        continue
    if node.get("u"):
        continue
    node["u"] = v["u"]
    pd = urlparse(v["u"]).netloc
    node["s"] = f"来源：{pn}政府门户({pd})区县导航 HTML 提取（title 验证）"
    filled += 1

reg_filled = 0
for (pn, cname), node in county_node.items():
    if not node.get("u"):
        continue
    v = st["verified"].get(f"{pn}|{cname}")
    if not v or not v["ok"]:
        continue
    key = f"{node.get('c', '县级人民政府')}|{cname}"
    if key in reg and reg[key].get("u"):
        continue
    reg[key] = {"u": node["u"], "n": cname, "locations": ["块"],
                "source_level": "L2", "verified_at": today,
                "status": "ok", "snapshot": "", "xxgk": "", "xxgk_src": ""}
    reg_filled += 1


def _atomic_dump(obj, path):
    """原子写 JSON (2026-11-15 并发写互踩损坏根治)"""
    import os as _os, json as _json, tempfile as _tf
    d = _os.path.dirname(path)
    fd, tmp = _tf.mkstemp(dir=d, prefix=".atomic_", suffix=".tmp")
    try:
        with _os.fdopen(fd, "w", encoding="utf-8") as f:
            _json.dump(obj, f, ensure_ascii=False, indent=1)
        _os.replace(tmp, path)
    except Exception:
        try:
            _os.unlink(tmp)
        except Exception:
            pass
        raise


_atomic_dump(tree, TREE_F)
json.dump(reg, open(REG_F, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

# ── 5. 报告 ──
n_gap = sum(len(v["counties"]) for v in gaps_by_parent.values())
n_ok = sum(1 for c in st["verified"].values() if c["ok"])
n_bad = sum(1 for c in st["verified"].values() if not c["ok"])
stat_p = {}
for pn, r in st["parents"].items():
    stat_p.setdefault(r["status"], []).append(pn)
no_nav_ct = sum(len(gaps_by_parent[p]["counties"]) for p, r in st["parents"].items()
                if r["status"] in ("no_nav", "fetch_fail", "no_parent_url", "exception")
                and p in gaps_by_parent)   # P195_ONLY/PROV 过滤时 st 含未处理父级
print("\n═══ P195 报告 ═══")
print(f"缺口总数 {n_gap} | 已补 {filled} | 验证通过 {n_ok} | 验证不过 {n_bad}")
print("上级门户状态分布:", {k: len(v) for k, v in stat_p.items()})
for k, v in stat_p.items():
    print(f"  {k} ({len(v)}): {', '.join(v[:10])}{'...' if len(v) > 10 else ''}")
print(f"门户无导航/失败覆盖县数(列名): {no_nav_ct}")
# 覆盖率前后对比
tree2 = json.load(open(TREE_F, encoding="utf-8"))
cov_old = sum(1 for n, _ in walk(tree, [])
              if n.get("k") == "人民政府" and n.get("c") in CTYPES and n.get("u"))
tot = sum(1 for n, _ in walk(tree2, [])
          if n.get("k") == "人民政府" and n.get("c") in CTYPES)
cov_new = sum(1 for n, _ in walk(tree2, [])
              if n.get("k") == "人民政府" and n.get("c") in CTYPES and n.get("u"))
print(f"县级门户覆盖率: {cov_old}/{tot} → {cov_new}/{tot} "
      f"({cov_old/tot*100:.1f}% → {cov_new/tot*100:.1f}%)")
print(f"registry 新增 {reg_filled} 条")
print("P195 done")
