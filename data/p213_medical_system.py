#!/usr/bin/env python
# p213 医疗系统（卫生健康）条系统建设（2026-11-17 用户指令「添加医疗系统」）
# 结构: 国家卫健委(+委管国家局 中医药局/疾控局 + 中国疾控中心) → 省级卫健委(32)
#       → 市级卫健委（333 地级市 + 直辖市 86 区，块树城市级区划全量建节点）
#       + 省级疾控中心（31，2026-11-17 用户指令: 疾控官网无导航 → SERP 筛选）
# 体制（用户强调, 写入根节点 m）: 卫健委「本级政府领导为主」——各级卫健委是
#       本级政府组成部门, 上级卫健委仅业务指导, 非海关/税务式垂直管理;
#       挂条模块为展示行业系统全貌, 与药监/气象同列。
# 渠道（权威源体系, 禁域名猜测）:
#   ①块树/registry 存量(市门户部门导航 L2, 已 title 验证)
#   ②省卫健委官网「市级卫健委」链接区块(L1)
#   ③市政府门户部门导航(L2)
#   ④百度 SERP 线索 + title 严格验证(市名+机构词双验, 兜底 L3)
# 疾控中心渠道: SERP 搜索 + title 筛选(事业单位, 官网无省级导航, 用户指示)。
# 运行: (cd data && BROWSER_TIERS=off uv run python p213_medical_system.py)
#   后续挂 p198_loop 顺序执行(单写者纪律), miss 项轮间重试。
import json, os, re, socket, sys, tempfile, threading, time, urllib.parse
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "util"))
from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, ".env"))
TREE_F = os.path.join(ROOT, "data", "tree.json")
REG_F = os.path.join(ROOT, "data", "site_registry.json")
STATE_F = os.path.join(ROOT, "data", "p213_state.json")
TODAY = "2026-11-17"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
_TUNNEL = os.environ.get("TUNNEL_PROXY", "")
_tl = threading.local()

ETH = r"(哈萨克族?|维吾尔族?|柯尔克孜族?|朝鲜族?|蒙古族?|藏族?|回族?|壮族?|苗族?|黎族?|侗族?|满族?|白族?|傣族?|彝族?|哈尼族?|拉祜族?|傈僳族?|佤族?|水族?|羌族?|布依族?|仡佬族?|仫佬族?|毛南族?|瑶族?|畲族?|土家族?|锡伯族?|达斡尔族?|鄂温克族?|鄂伦春族?|赫哲族?|俄罗斯族?|塔塔尔族?|乌孜别克族?|塔吉克族?|撒拉族?|保安族?|裕固族?|东乡族?|纳西族?|景颇族?|阿昌族?|普米族?|怒族?|德昂族?|独龙族?|基诺族?|门巴族?|珞巴族?|京族?|自治)$"
ETH_RE = re.compile(ETH)
WJW_KW = re.compile(r"(卫生健康委员会|卫健委|卫生健康局|卫生计生委|卫生局)")
BAD_KW = re.compile(r"(医疗保障|医保局|疾控中心|疾病预防控制中心|卫生监督|监督所|血站|血液中心|急救|红十字会|计划生育|计生协|爱卫办|医院|学院|学校|服务中心|采购|人才|考试|献血|招聘|公示|拟聘|事业单位|工作年度|年报)")
TT_KW = ("卫生健康委员会", "卫健委", "卫生健康局", "卫生局", "卫生计生委")
NEWS_PATH = re.compile(r"/(news|content|article|detail|info|tzgg|通知|公示|zhengce|zwgk)[/._]|/\d{4}[/-]\d{2}[/-]", re.I)
BAD_DOM = {"nhc.gov.cn", "www.gov.cn", "baike.baidu.com", "people.com.cn", "xinhuanet.com",
           "medlive.cn", "dxy.cn", "yiigle.com", "zhzyw.com", "cntcm.com.cn", "jkb.com.cn"}
SERP_LOCK = threading.Lock()


def _atomic(obj, path):
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
    with os.fdopen(fd, "w") as f:
        json.dump(obj, f, ensure_ascii=False)
    os.replace(tmp, path)


def find(n, name):
    if n.get("n") == name:
        return n
    for k in n.get("ks") or []:
        r = find(k, name)
        if r:
            return r
    return None


def base(nm):
    """机构/区划名基底: 剥括号+行政区后缀+民族串+机构词"""
    t = re.sub(r"[（(][^（）)]*[）)]$", "", nm or "")
    t = re.sub(r"(卫生健康委员会|卫健委|卫生健康局|卫生计生委|卫生局)$", "", t)
    # 自治区先剥（宁夏回族自治区→宁夏回族→民族串=宁夏）; 否则尾部「区」误剥成「宁夏自治」
    t = re.sub(r"(自治区|特别行政区)$", "", t)
    t = re.sub(r"(自治州|自治县|自治旗|地区|盟|市|县|区|旗|州)$", "", t)
    for _ in range(8):
        t2 = ETH_RE.sub("", t)
        if t2 == t or len(t2) < 2:
            break
        t = t2
    return t


# 深路径文章特征（2026-11-17 URL 正确性检验：门户文章页/公告页不得作为机构官网）
ARTICLE_MARK = re.compile(
    r"(/info/|/art(icle)?/|/contents?/|/col/|/post_|/c/\d{4}|/t\d{8}|/\d{6}/|\d{4}-\d{2}-\d{2}|/aritcle/)")
ARTICLE_TITLE = re.compile(
    r"(公告|通知|通报|批复|决算|预算|名单|简介|职责|分工|目录|招聘|公示|工作动态|新闻|考察|"
    r"招标|采购|报告|解读|政策|规划|方案|意见|办法|规定|标准|指南|问答|访谈|会议|活动|"
    r"项目|公开指南|依申请|领导成员|概况|汇总)")


def is_org_home_deep(cn, u, tt):
    """深路径是否机构子站首页: 标题≈机构全名 且 路径无文章特征。
    吉林市 jlcity.gov.cn/bmwz/wjw/（标题=吉林市卫生健康委员会）类保留;
    通州 wjw.beijing.gov.cn/.../t20241224_xxx.html（批复文章）类拒绝。"""
    p = urlparse(u)
    if not p.path or p.path in ("/", ""):
        return False
    if ARTICLE_MARK.search(p.path):
        return False
    core = re.split(r"[_|]", _clean_title(tt or ""))[0].strip()
    if core != cn:
        return False
    return not ARTICLE_TITLE.search(core)


def norm_host(u):
    """主机名小写（http://Sxwjw.shaanxi.gov.cn 类大小写混杂清洗）"""
    if not u:
        return u
    return re.sub(r"(?i)^(https?://)([^/]+)", lambda m: m.group(1) + m.group(2).lower(), u.strip())


def clean_url(u, host):
    u = (u or "").strip()
    if not u or u.startswith(("#", "javascript:", "mailto:", "tel:")):
        return ""
    if u.startswith("//"):
        u = "https:" + u
    elif u.startswith("/"):
        u = "https://" + host + u
    if NEWS_PATH.search(u) or ".pdf" in u.lower():
        return ""
    return re.sub(r"\s+", "", u)


def get_client():
    from http_client import get_client as gc
    return gc()


def _dns_ok(host):
    """DNS 预检（死域名快速失败, 避免抓取层长重试卡轮）。
    注意: macOS getaddrinfo 不支持 timeout 关键字（TypeError）→ 无参回退,
    回退路径同样要兜住解析失败。"""
    try:
        socket.getaddrinfo(host, None, timeout=5)
    except TypeError:
        try:
            socket.getaddrinfo(host, None)
        except Exception:
            return False
    except Exception:
        return False
    return True


def fetch(u, timeout=15):
    """通用抓取: 每线程独立 curl_cffi Session(impersonate=chrome124)。
    关键教训（p204/p213 2026-11-17）: http_client.UnifiedClient 有模块级
    共享状态, 多线程并发实例化 AttributeError 全灭（首个线程可用其余全挂）;
    裸 requests 被 gov 站 WAF 403。curl_cffi 指纹可过 WAF 且 Session
    实例独立线程安全。"""
    if not u:
        return None
    if not _dns_ok(urlparse(u).netloc):
        return None
    try:
        if not hasattr(_tl, "crs"):
            import curl_cffi.requests as _cr
            _tl.crs = _cr.Session(impersonate="chrome124")
        r = _tl.crs.get(u, timeout=timeout, verify=False)
        return r.text if r and r.text and len(r.text) > 200 else None
    except Exception:
        return None


def serp_fetch(q, timeout=20):
    """百度 SERP: 全局锁串行 + 2s 间隔防限流（2026-11-17 实测: 并发 len=0/
    静默挂起）; curl_cffi 指纹会话（同 fetch 教训）。"""
    with SERP_LOCK:
        time.sleep(2.0)
        try:
            if not hasattr(_tl, "crs"):
                import curl_cffi.requests as _cr
                _tl.crs = _cr.Session(impersonate="chrome124")
            r = _tl.crs.get(f"https://www.baidu.com/s?wd={q}&rn=10", timeout=timeout, verify=False)
            return r.text if r and r.text and len(r.text) > 500 else None
        except Exception:
            return None


def title_of(h):
    m = re.search(r"<title[^>]*>(.*?)</title>", h or "", re.S | re.I)
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else ""


def _clean_title(tt):
    """标题取段: 重复标题「民和县人民政府—民和县人民政府」取首段;
    中性前缀「首页 - 河北省疾病预防控制中心」取后段（信息在后）"""
    parts = re.split(r"[—–-]", tt or "")
    if len(parts) > 1 and re.match(r"^\s*(首页|欢迎|网站首页|Home)\s*$", parts[0]):
        return parts[1].strip()
    return parts[0].strip()


def verify_title(city_full, city_base, tt, strict=False):
    """title 严格验证: 城市基底 + 卫健委机构词, 排除医保/疾控/事业单位;
    strict=基底与省名同名时（海南藏族自治州 vs 海南省、吉林市 vs 吉林省）
    要求全名/州/市全称出现——基底子串会误放行省站。"""
    if not tt:
        return False
    tt1 = _clean_title(tt)
    if BAD_KW.search(tt1):
        return False
    if strict:
        if not any(x in tt1 for x in (city_full, city_base + "州", city_base + "市")):
            return False
    elif city_base not in tt1 and city_full not in tt1:
        return False
    return any(w in tt1 for w in TT_KW)


def anchors_of(h):
    out = []
    for m in re.finditer(r'href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', h or "", re.S):
        u, raw = m.group(1), m.group(2)
        txt = re.sub(r"<[^>]+>", "", raw)
        txt = re.sub(r"[\s　]+", "", txt)
        if 2 <= len(txt) <= 24:
            out.append((u, txt))
    return out


NEUTRAL_RE = re.compile(r"^(首页|网站首页|欢迎|Welcome|index|-)?\s*$", re.I)


def resolve_city_url(cn, cbase, v, strict=False):
    """存量/缓存/候选 URL 统一复验（2026-11-17 URL 正确性检验后固化）:
    - DNS 死 → None（汉中 wj.hanzhong.gov.cn 类不可保留）
    - 深路径: ①机构子站首页（标题=机构全名, 无文章特征）保留;
              ②否则根址 title 验证通过则根化; ③都不过 → None（列名）
    - 根址: title 机构验证; 中性/空 title(JS 壳) 存疑保留; 不符 → None
    门户文章页/公告页/他部门页面一律不采（用户红线: URL 必须是机构官网/权威入口）。"""
    if not v:
        return None
    p = urlparse(v)
    if not _dns_ok(p.netloc):
        return None
    deep = p.path not in ("", "/")
    tt = title_of(fetch(v))
    if deep:
        root = f"{p.scheme}://{p.netloc}/"
        rt = title_of(fetch(root))
        if rt and verify_title(cn, cbase, rt, strict=strict):
            return norm_host(root)
        if tt and is_org_home_deep(cn, v, tt):
            return norm_host(v)
        return None
    if not tt:
        return v
    tt1 = _clean_title(tt)
    if NEUTRAL_RE.match(tt1):
        return v
    if verify_title(cn, cbase, tt, strict=strict):
        return norm_host(v)
    return None


def main():
    t = json.load(open(TREE_F, encoding="utf-8"))
    st = {"prov": {}, "city": {}}
    if os.path.exists(STATE_F):
        try:
            st = json.load(open(STATE_F, encoding="utf-8"))
        except Exception:
            pass
    reg = json.load(open(REG_F, encoding="utf-8"))
    blk = next((g for g in t.get("ks", []) if g.get("n", "").startswith("省级")), None)
    if not blk:
        print("省级组未找到")
        return

    # ═══ 1. 城市清单 ═══
    prov_cities = {}
    for p in (blk.get("ks") or []):
        pn = p.get("n", "")
        if "兵团" in pn:
            continue
        cities = []
        for c in (p.get("ks") or []):
            if c.get("c") == "地级市人民政府":
                cities.append(c)
            elif c.get("c") in ("直辖市辖区", "直辖市辖县"):
                cities.extend(c.get("ks") or [])
        prov_cities[pn] = cities
    total_cities = sum(len(v) for v in prov_cities.values())
    print(f"城市级节点: {total_cities} (省份 {len(prov_cities)})")

    # ═══ 2. 省级 URL: 块树厅局组 → registry → SERP 验证 ═══
    prov_url = {}
    for p in (blk.get("ks") or []):
        pn = p.get("n", "")
        if "兵团" in pn:
            continue
        u = ""
        for grp in (p.get("ks") or []):
            if "部门" in grp.get("n", "") or grp.get("c") == "厅局":
                for o in (grp.get("ks") or []):
                    n = o.get("n", "")
                    if WJW_KW.search(n) and "国家" not in n:
                        v = (o.get("u") or "").strip()
                        if v and "nhc.gov.cn" not in v:
                            u = v
        if not u:
            pbase = base(pn)
            for k, v in reg.items():
                cat, name = k.split("|", 1)
                if cat in ("省政府组成部门", "省政府组成部门/直属机构") and WJW_KW.search(name) \
                        and pbase in name and "nhc.gov.cn" not in (v.get("u") or ""):
                    u = v.get("u", "")
                    break
        prov_url[pn] = norm_host(u)
    # 省级缺口 SERP 兜底
    for pn, u in list(prov_url.items()):
        if u:
            continue
        pbase = base(pn)
        sh = serp_fetch(urllib.parse.quote(pn + '卫生健康委员会官网'))
        if not sh:
            continue
        for cu in re.findall(r'mu="(https?://[^"]+)"', sh):
            dom = urlparse(cu).netloc.lower()
            if any(d in dom for d in ("baidu.com", "baike", "zhidao")) or dom in BAD_DOM:
                continue
            if ".gov.cn" not in dom:
                continue
            th = fetch(cu)
            tt = title_of(th)
            if verify_title(pn, pbase, tt):
                prov_url[pn] = norm_host(cu)
                break
    print("省级 URL:", sum(1 for v in prov_url.values() if v), "/", len(prov_url))
    for pn, u in prov_url.items():
        if not u:
            print("  省级缺口:", pn)
    # 省级 URL 根化: 深路径(如河南挂 zfxxgk 子路径)验证根址可用后改根
    for pn, u in list(prov_url.items()):
        if not u:
            continue
        p = urlparse(u)
        if p.path and p.path not in ("/", ""):
            root = f"{p.scheme}://{p.netloc}/"
            tt = title_of(fetch(root))
            if verify_title(pn, base(pn), tt):
                prov_url[pn] = root

    # ═══ 3. 省级疾控中心（2026-11-17 用户指令: 疾控中心官网无省级导航 → SERP 搜索筛选）═══
    def cdc_verify(pn, pbase, tt):
        if not tt:
            return False
        tt1 = _clean_title(tt)
        # 负面词不含疾控本身（BAD_KW 用于卫健委采集排除疾控, 此处反向）
        if re.search(r"(招聘|公示|拟聘|医院|学院|学校|采购|考试|年度报告)", tt1):
            return False
        if pbase not in tt1:
            return False
        return ("疾病预防控制中心" in tt1) or ("疾控中心" in tt1)

    cdc_urls = {}
    cdc_urls = {pn: u for pn, u in st.get("cdc", {}).items() if isinstance(u, str) and u.startswith("http")}
    cdc_pending = [pn for pn in prov_cities if pn not in cdc_urls]
    print("省级疾控中心待采:", len(cdc_pending))
    for pn in cdc_pending:
        pbase = base(pn)
        sh = serp_fetch(urllib.parse.quote(pn + "疾病预防控制中心官网"))
        if not sh:
            continue
        cands = []
        for u in re.findall(r'mu="(https?://[^"]+)"', sh):
            dom = urlparse(u).netloc.lower()
            if any(d in dom for d in ("baidu.com", "baike", "zhidao")) or dom in BAD_DOM:
                continue
            cands.append(u)
            if len(cands) >= 6:
                break
        for u in cands:
            # 域名特征: 疾控官网域名普遍含 cdc（bjcdc.org/sxcdc.cn/lncdc.com）
            # 或为 gov.cn——过滤第三方名录页（antso.cn 类 title 伪装）
            dom = urlparse(u).netloc.lower()
            if "cdc" not in dom and ".gov.cn" not in dom:
                continue
            if re.search(r"/\d{8}", u):  # t20190808 类机构介绍文章页非门户入口
                continue
            tt = title_of(fetch(u))
            if cdc_verify(pn, pbase, tt):
                # 深路径: 机构子站首页(标题=机构全名, 如海南 sjkzx)保留;
                # 否则根址验证通过则根化; 都不过拒（文章页/直属单位页不采）
                p = urlparse(u)
                if p.path and p.path not in ("/", ""):
                    root = f"{p.scheme}://{p.netloc}/"
                    rt = title_of(fetch(root))
                    if cdc_verify(pn, pbase, rt):
                        u = root  # 专属域名根址优先（jscdc.cn/）
                    elif not is_org_home_deep(pn + "疾病预防控制中心", u, tt):
                        continue  # 文章页/直属单位页不采（海南 sjkzx 官方频道页保留）
                cdc_urls[pn] = norm_host(u)
                break
        st.setdefault("cdc", {})[pn] = cdc_urls.get(pn) or "miss"
        _atomic(st, STATE_F)
        print(f"CDC {pn}: {'HIT ' + cdc_urls[pn][:45] if pn in cdc_urls else 'miss'}")
    print("省级疾控中心:", sum(1 for v in cdc_urls.values() if v), "/", len(prov_cities))

    # ═══ 4. 市级种子 ═══
    WHC_F = os.path.join(os.path.dirname(ROOT), "医院", "data", "whc_cities.jsonl")
    whc = {}
    whc_fail = {}
    if os.path.exists(WHC_F):
        for line in open(WHC_F, encoding="utf-8"):
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get("verdict") == "PASS":
                whc[r.get("city", "")] = r
            elif r.get("verdict") == "FAIL":
                whc_fail[r.get("city", "")] = r
        print(f"医院项目 whc 导入: PASS {len(whc)} / FAIL {len(whc_fail)}")
    else:
        print("医院项目 whc_cities.jsonl 未找到, 跳过导入")
    city_seed = {}
    NEUTRAL_RE = re.compile(r"^(首页|网站首页|欢迎|Welcome|index|-)?\s*$", re.I)
    for pn, cities in prov_cities.items():
        for c in cities:
            cn = c.get("n", "")
            key = f"{pn}|{cn}"
            cbase = base(cn)
            u, src = "", ""

            def soft_verify(v):
                """存量 URL 统一复验（见 resolve_city_url: 深路径根化/文章页拒绝/
                title 机构验证; 中立标题 JS 壳存疑保留）。"""
                collide_seed = len(cbase) >= 2 and any(cbase in base(p) for p in prov_cities)
                return resolve_city_url(cn, cbase, v, strict=collide_seed)

            for grp in (c.get("ks") or []):
                if grp.get("c") != "市级政府部门":
                    continue
                for o in (grp.get("ks") or []):
                    n = o.get("n", "")
                    if not WJW_KW.search(n) or "国家" in n:
                        continue
                    v = (o.get("u") or "").strip()
                    if v and "nhc.gov.cn" not in v:
                        sv = soft_verify(v)
                        if sv:
                            u, src = sv, o.get("s", "") or "来源:市政府门户部门导航 HTML 提取"
            if not u:
                for k, v in reg.items():
                    cat, name = k.split("|", 1)
                    # 基底全等 + 省/国家名排除: 子串匹配曾把 大兴⊂大兴安岭、
                    # 吉林⊂吉林省四平市、海南⊂海南省三亚市 的错配 URL 挂上
                    if cat == "市级政府部门" and WJW_KW.search(name) \
                            and not re.search(r"(国家|省|自治区)", name) \
                            and base(name) == cbase \
                            and "nhc.gov.cn" not in (v.get("u") or "") \
                            and not BAD_KW.search(name):
                        sv = soft_verify(v.get("u", ""))
                        if sv:
                            u = sv
                            src = "registry 存量(市门户部门导航)"
                            break
            if not u:
                # 医院项目 whc_cities.jsonl PASS 导入（统一复验: 深路径根化/文章页拒绝）
                wr = whc.get(cn) or next((v for cn2, v in whc.items() if base(cn2) == cbase and cbase), None)
                if wr:
                    wu = wr.get("url", "")
                    if wu and "zwfw" not in wu and "政务服务网" not in (wr.get("title") or ""):
                        collide_w = len(cbase) >= 2 and any(cbase in base(p) for p in prov_cities)
                        sv = resolve_city_url(cn, cbase, wu, strict=collide_w)
                        if sv:
                            u = sv
                            src = "来源:医院项目 whc PASS 导入(title 复验)"
            if u:
                city_seed[key] = (norm_host(u), src)
    print("市级种子(存量):", len(city_seed))

    # ═══ 4. 采集缺口: 省卫健委官网 → 市门户 → SERP ═══
    prov_home = {}
    missing = [(pn, c) for pn, cities in prov_cities.items() for c in cities
               if f"{pn}|{c.get('n')}" not in city_seed
               and not str(st["city"].get(f"{pn}|{c.get('n')}") or "").startswith("http")]
    if os.environ.get("P213_LIMIT"):
        missing = missing[:int(os.environ["P213_LIMIT"])]
    print("本轮待采:", len(missing))

    def collect(item):
        pn, c = item
        cn = c.get("n", "")
        key = f"{pn}|{cn}"
        cbase = base(cn)
        # 基底名是任一省级名子串即 strict（吉林市/吉林省、青海海南州/海南省、
        # 天津河北区/河北省）：base() 不剥「省」，等值比较会漏跨省同名
        collide = len(cbase) >= 2 and any(cbase in base(p) for p in prov_cities)
        port = (c.get("u") or "").strip()

        def try_pages(pages, host, src_lv, src_tag, require_base_in_txt):
            """在页面列表里找市级链接: 锚文本机构词 + 基底匹配 + title 验证"""
            for hpage in pages:
                if not hpage:
                    continue
                for u, txt in anchors_of(hpage):
                    if not WJW_KW.search(txt) or BAD_KW.search(txt):
                        continue
                    if require_base_in_txt:
                        if cbase not in txt and cn not in txt:
                            continue
                    elif base(txt) != cbase:
                        continue
                    u = clean_url(u, host)
                    if not u or ".gov.cn" not in urlparse(u).netloc:
                        continue
                    tt = title_of(fetch(u))
                    if verify_title(cn, cbase, tt, strict=collide):
                        return key, "hit", u, src_lv, src_tag
            return None

        # 渠道2: 省卫健委官网市级链接区块 (L1) —— 首页直链 + 「地市/市州卫健委」栏目页
        if key not in prov_home:
            prov_home[key] = fetch(prov_url.get(pn, ""))
        h = prov_home[key]
        if h:
            host = urlparse(prov_url.get(pn, "")).netloc
            r = try_pages([h], host, "L1", "来源:省卫健委官网市级链接区块 HTML 提取(title 验证)", require_base_in_txt=False)
            if r:
                return r
            # 栏目页: 文本含 地市/市州/市县 且含卫健委关键词
            sub = ""
            for u, txt in anchors_of(h):
                if re.search(r"(地市|市州|市县|各地市|设区市|区市)", txt) and WJW_KW.search(txt) \
                        and not BAD_KW.search(txt):
                    sub = clean_url(u, host)
                    if sub:
                        break
            if sub:
                r = try_pages([fetch(sub)], host, "L1", "来源:省卫健委官网「地市卫健委」栏目页 HTML 提取(title 验证)", require_base_in_txt=False)
                if r:
                    return r
        # 渠道3: 市门户部门导航 (L2)
        if port:
            r = try_pages([fetch(port)], urlparse(port).netloc, "L2",
                          "来源:市政府门户部门导航 HTML 提取(title 验证)", require_base_in_txt=True)
            if r:
                return r
        # 渠道4: SERP 线索 + title 严格验证 (L3; dps 代理+全局锁串行)
        q = urllib.parse.quote((pn if cn.endswith("区") else "") + cn + "卫生健康委员会")
        cands = []
        for attempt in range(2):
            sh = serp_fetch(q)
            if sh:
                for u in re.findall(r'mu="(https?://[^"]+)"', sh):
                    dom = urlparse(u).netloc.lower()
                    if any(d in dom for d in ("baidu.com", "baike", "zhidao")) or dom in BAD_DOM:
                        continue
                    if ".gov.cn" in dom and not dom.startswith("www."):
                        cands.append(u)
                    if len(cands) >= 5:
                        break
            if cands or attempt == 1:
                break
            time.sleep(2.0)
        for u in cands:
            # 统一复验: 文章页/公告页拒绝; 机构子站首页或可根化的官网根址保留
            sv = resolve_city_url(cn, cbase, u, strict=collide)
            if sv:
                return key, "hit", sv, "L3", "来源:SERP线索+title严格验证(市名+机构词双验)"
        return key, "miss", "", "", ""

    results = []
    with ThreadPoolExecutor(4) as ex:
        results = list(ex.map(collect, missing))
    for key, got, u, lv, src in results:
        st["city"][key] = norm_host(u) if got == "hit" else "miss"
        if got == "hit":
            city_seed[key] = (norm_host(u), src + f" ({lv})")
            print(f"{key}: HIT {norm_host(u)[:52]} [{lv}]")
        else:
            print(f"{key}: miss")
    # 上轮 state 缓存的 hit URL 并入（防重建丢 URL——p213 幂等性）
    # 2026-11-17 复验纪律: 缓存 URL 必须重新验证（历史缓存曾含门户根址/文章页污染,
    # 无条件并入会把已清除的错配重新挂回树）
    prov_of = {f"{pn}|{c.get('n')}": c for pn, cs in prov_cities.items() for c in cs}
    for key, u in list(st["city"].items()):
        if isinstance(u, str) and u.startswith("http") and key not in city_seed:
            c = prov_of.get(key)
            cn2 = (c or {}).get("n", "")
            if not cn2:
                continue
            cb = base(cn2)
            col = len(cb) >= 2 and any(cb in base(p) for p in prov_cities)
            sv = resolve_city_url(cn2, cb, u, strict=col)
            if sv:
                city_seed[key] = (sv, "来源:上轮采集 state 缓存(复验)")
            else:
                st["city"][key] = "miss"  # 污染缓存清除
    _atomic(st, STATE_F)

    # ═══ 5. 构建医疗系统子树并挂载 ═══
    tiao = next((g for g in t.get("ks", []) if g.get("n", "").startswith("条")), None)
    med_root = {
        "n": "医疗系统（卫生健康）",
        "l": "条", "k": "分组", "c": "医疗系统", "u": "", "x": "", "s": "",
        "m": "卫生健康体制=块管为主、条块结合：各级卫健委是本级政府组成部门（本级政府领导为主），国家卫健委仅业务指导，并非海关/税务式垂直管理——挂条模块为展示行业系统全貌。地方中医药/疾控机构多并入卫健委官网不另设站；疾控中心为卫健委直属事业单位（独立建站普遍，官网无省级导航→SERP 筛选采集）；医疗保障局为独立系统未含。",
    }
    central = [
        {"n": "国家卫生健康委员会", "l": "中央", "k": "医疗系统", "c": "医疗系统",
         "u": "http://www.nhc.gov.cn/", "x": "http://www.nhc.gov.cn/wjw/zfxxgk/zfxxgk.shtml",
         "s": "来源:国务院组成部门节点存量", "m": ""},
        {"n": "国家中医药管理局", "l": "中央", "k": "医疗系统", "c": "医疗系统",
         "u": "http://www.natcm.gov.cn/", "x": "",
         "s": "来源:国家卫健委官网首页链接区块 HTML 提取(2026-11-17 title 验证)", "m": "国家卫健委管理的国家局"},
        {"n": "国家疾病预防控制局", "l": "中央", "k": "医疗系统", "c": "医疗系统",
         "u": "https://www.ndcpa.gov.cn/", "x": "",
         "s": "来源:国家卫健委管理的国家局(2026-11-17 title 验证)", "m": "国家卫健委管理的国家局"},
        {"n": "中国疾病预防控制中心", "l": "中央", "k": "医疗系统", "c": "医疗系统",
         "u": "https://www.chinacdc.cn/", "x": "",
         "s": "来源:SERP线索+title严格验证(2026-11-17)", "m": "国家疾控局直属事业单位"},
    ]
    cdc_grp = {"n": "省级疾控中心（31）", "l": "条", "k": "分组", "c": "医疗系统",
               "u": "", "x": "", "s": "", "m": "疾控中心为卫健委直属事业单位, 官网普遍无省级导航——按用户指令 SERP 搜索+title 筛选采集。", "ks": []}
    for pn in prov_cities:
        cu = cdc_urls.get(pn, "")
        cdc_grp["ks"].append({"n": pn + "疾病预防控制中心", "l": "省", "k": "医疗系统",
                              "c": "医疗系统", "u": cu, "x": "",
                              "s": "来源:SERP线索+title严格验证" if cu else "", "m": ""})
    prov_grp = {"n": "省级卫生健康委员会（32）", "l": "条", "k": "分组", "c": "医疗系统",
                "u": "", "x": "", "s": "", "m": "", "ks": []}
    for pn, cities in prov_cities.items():
        pu = prov_url.get(pn, "")
        pnode = {"n": pn + "卫生健康委员会",
                 "l": "省", "k": "医疗系统", "c": "医疗系统", "u": pu,
                 "x": "", "s": "来源:块树厅局存量(门户部门导航)" if pu else "", "m": "", "ks": []}
        for c in cities:
            key = f"{pn}|{c.get('n')}"
            u, src = city_seed.get(key, ("", ""))
            mnote = ""
            if not u:
                fr = whc_fail.get(c.get("n", "")) or next((v for cn2, v in whc_fail.items() if base(cn2) == base(c.get("n", "")) and base(c.get("n", ""))), None)
                if fr:
                    mnote = "医院项目双引擎确认无独立卫健委官网（门户子站形态为主）待人工复核"
            cnode = {"n": c.get("n", "") + "卫生健康委员会",
                     "l": "地级区" if c.get("n", "").endswith("区") else "市",
                     "k": "医疗系统", "c": "医疗系统",
                     "u": u, "x": "", "s": src, "m": mnote}
            pnode["ks"].append(cnode)
        prov_grp["ks"].append(pnode)
    prov_grp["ks"].append({"n": "新疆生产建设兵团卫生健康委员会", "l": "省", "k": "医疗系统",
                           "c": "医疗系统", "u": "", "x": "", "s": "", "m": "兵团卫健委无独立公开官网（列名）"})
    med_root["ks"] = central + [prov_grp, cdc_grp]

    old = next((g for g in (tiao.get("ks") or []) if g.get("n", "").startswith("医疗系统")), None)
    if old:
        tiao["ks"][tiao["ks"].index(old)] = med_root
    else:
        yaojian = next((i for i, g in enumerate(tiao.get("ks") or []) if "药监" in g.get("n", "")), None)
        if yaojian is not None:
            tiao["ks"].insert(yaojian, med_root)
        else:
            tiao["ks"].append(med_root)

    # ═══ 6. registry 同步（条块同源: 同名/同基底条目更新, locations 加"条"）═══
    RANK = {"L1": 3, "L2": 2, "L3": 1}

    def reg_sync(cat, name, u, lv):
        nb = base(name)
        for k in list(reg.keys()):
            rcat, rname = k.split("|", 1)
            if rcat != cat or not WJW_KW.search(rname):
                continue
            if base(rname) != nb:
                continue
            v = reg[k]
            if "nhc.gov.cn" in (v.get("u") or "") or RANK.get(lv, 2) >= RANK.get(v.get("source_level", ""), 2):
                if "nhc.gov.cn" in (v.get("u") or ""):
                    v["u"] = u
                elif RANK.get(lv, 2) > RANK.get(v.get("source_level", ""), 2):
                    v["u"] = u
                v["source_level"] = v.get("source_level") or lv
            v.setdefault("locations", [])
            if "条" not in v["locations"]:
                v["locations"].append("条")
            if not v.get("verified_at"):
                v["verified_at"] = TODAY
            return
        reg[f"{cat}|{name}"] = {"u": u, "n": name, "locations": ["条"],
                                "source_level": lv, "verified_at": TODAY, "status": "ok", "snapshot": ""}

    for pn in prov_cities:
        pu = prov_url.get(pn, "")
        if pu and "nhc.gov.cn" not in pu:
            reg_sync("省政府组成部门", pn + "卫生健康委员会", pu, "L2")
    for pn, cities in prov_cities.items():
        for c in cities:
            key = f"{pn}|{c.get('n')}"
            u, src = city_seed.get(key, ("", ""))
            if not u:
                continue
            lv = "L1" if "省卫健委官网" in src else ("L3" if "SERP" in src else "L2")
            reg_sync("市级政府部门", c.get("n", "") + "卫生健康委员会", u, lv)
    for pn, cu in cdc_urls.items():
        if cu:
            reg_sync("疾控中心", pn + "疾病预防控制中心", cu, "L3")
    reg_sync("疾控中心", "中国疾病预防控制中心", "https://www.chinacdc.cn/", "L3")

    _atomic(t, TREE_F)
    _atomic(reg, REG_F)
    print(f"p213 done: 条树挂载完成, 市级有URL {len(city_seed)}/{total_cities}")


if __name__ == "__main__":
    main()
