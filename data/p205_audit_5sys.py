#!/usr/bin/env python
# p205 五系统填充质量审计（2026-11-17 用户指令「检查结果,权威,正确性核验」）
# 对 p203/p204 填充的五系统市节点 URL 全量复验:
# ①本地规则(门户/上级域名、新闻路径、域名机构特征、old./m. 旧站子域)
# ②title 复验(市名前字边界+机构词) ③可疑清单人工复核标记
import json, os, re, socket, sys, tempfile, threading, time, html, urllib.parse
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "util"))
from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, ".env"))
_TUNNEL = os.environ.get("TUNNEL_PROXY", "")
_tl = threading.local()
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

ETH = r"(哈萨克族?|维吾尔族?|柯尔克孜族?|朝鲜族?|蒙古族?|藏族?|回族?|壮族?|苗族?|黎族?|侗族?|满族?|白族?|傣族?|彝族?|哈尼族?|拉祜族?|傈僳族?|佤族?|水族?|羌族?|布依族?|仡佬族?|仫佬族?|毛南族?|瑶族?|畲族?|土家族?|锡伯族?|达斡尔族?|鄂温克族?|鄂伦春族?|赫哲族?|俄罗斯族?|塔塔尔族?|乌孜别克族?|塔吉克族?|撒拉族?|保安族?|裕固族?|东乡族?|纳西族?|景颇族?|阿昌族?|普米族?|怒族?|德昂族?|独龙族?|基诺族?|门巴族?|珞巴族?|京族?|自治)$"
def base(nm):
    x = re.sub(r"[（(][^（）)]*[）)]$", "", nm or "")
    x = re.sub(r"(自治州|自治县|自治旗|地区|盟|市|县|区|旗|州)$", "", x)
    for _ in range(8):
        x2 = re.sub(ETH, "", x)
        if x2 == x or len(x2) < 2: break
        x = x2
    return x

OFEAT = {"市人大": r"(rd|renda|spc|pc)", "市政协": r"(zx|cppcc|zhengxie)",
         "市中级人民法院": r"(court|fy|zy)", "市人民检察院": r"(jcy|jc|jiancha)",
         "市监委": r"(jjw|jjjc|jcj|jiwei|lz|lj|lx|ql|qf|qinfeng|cdi|di|12388|subsite|lzw|jj|jc|jw)"}
OWS = {"市人大": ("人民代表大会常务委员会", "人民代表大会", "人大常委会", "人大"),
       "市政协": ("政协委员会", "政治协商会议", "政协", "协商"),
       "市中级人民法院": ("中级人民法院", "人民法院", "法院", "中院"),
       "市人民检察院": ("人民检察院", "检察院", "检察"),
       "市监委": ("监察委员会", "纪委监委", "纪律检查委员会", "纪委", "纪检监察",
                "监委", "廉政", "清风", "清廉", "廉洁")}
# 人工复核确认的官方站（域名无机构特征/标题为站点简称导致规则误判）
# 2026-11-17 加：elsz(廉洁深圳)/ljcd(清廉蓉城)/njjj(钟山清风)/yxlz(碧玉清溪)/lasrd?(六安人大=错,不加)
KNOWN_OK = {"lianshi.gov.cn", "www.china-xa.gov.cn", "www.xiangtan.com.cn",
            "www.jygzhx.cn", "hzzy.sdcourt.gov.cn",
            "ljsz.gov.cn", "ljcd.gov.cn", "njjj.gov.cn", "yxlz.gov.cn",
            "lajjjc.gov.cn", "tljw.gov.cn"}
# 省级机关官网的「市级频道/子站」= 官方入口（湖南人大 channel、江苏检察网
# wx./sz./zj. 子域、福建政协 /nds/、浙江法院网 col/、青海纪委 /subsite/ 等）
PROV_CHANNEL = ("jsjc.gov.cn", "fjzx.gov.cn", "hnrd.gov.cn", "sx.jcy.gov.cn",
                "sn.jcy.gov.cn", "sdjcy.gov.cn", "hi.jcy.gov.cn", "nx.jcy.gov.cn",
                "zjsfgkw.gov.cn", "qhjc.gov.cn")
BAD_DOM = {"cppcc.gov.cn","www.gov.cn","gov.cn","npc.gov.cn","people.com.cn","ccdi.gov.cn",
           "spp.gov.cn","chinacourt.org","court.gov.cn","ccgp.gov.cn","baike.baidu.com",
           "hainanzx.gov.cn","nxzx.gov.cn","hljzx.gov.cn","ynzx.gov.cn","gzrd.gov.cn",
           "shanxizx.gov.cn","jlrd.gov.cn","xzrd.gov.cn","zjsfgkw.gov.cn","xzjjw.gov.cn",
           "qhjc.gov.cn","jsjc.gov.cn","hbjc.gov.cn","jcy.gov.cn","mzfzw.net","zgsjzsjw.gov.cn"}
NEWS_PATH = re.compile(r"/(news|content|article|detail|info|tzgg|art|columns|html|item)[/._]"
                       r"|/\d{6}/|/zxww/|/dfzx/|content_|/t\d{8}_", re.I)
ARTICLE_ID = re.compile(r"/\d{6,}\.(s?html?|jsp|aspx)$", re.I)   # /ldjj/57915356.html 类文章页
NEUTRAL_TITLE = re.compile(r"^(首页|网站首页|门户网站|正在加载.*|加载中.*|.*维护.*|Welcome.*|-)?\s*$", re.I)
ADMIN_SUF = "区县市旗"



_dns_cache = {}
_dns_lock = threading.Lock()


def dns_dead(host):
    """域名是否 NXDOMAIN（2026-11-17 p220 加）。
    权威来源也可能已整站下线/迁域——仅凭「来源权威」不能放过死域名。
    实测: 新疆 xjcourt.org 子域、glzy.chinacourt.gov.cn 等 23 个域名公共
    DNS 判定 NXDOMAIN，而 p205 旧版把它们归入「title空(权威源)」存疑，
    长期掩盖了站点已不存在的事实。"""
    if not host:
        return False
    with _dns_lock:
        v = _dns_cache.get(host)
    if v is not None:
        return v
    try:
        socket.getaddrinfo(host, 80, proto=socket.IPPROTO_TCP)
        v = False
    except Exception:
        v = True
    with _dns_lock:
        _dns_cache[host] = v
    return v


def county_level(tt, sysn):
    """title 是县/区级机构（2026-11-17 p217 加）:
    机构词紧邻前一字为 县/区/旗 → 该站实为县区级机构，不该挂地级市节点。
    例: 湖南省长沙县人民法院 / 南京市建邺区人民检察院 / 中共梅州市梅县区纪委。"""
    for kw in OWS.get(sysn, ()):
        i = tt.find(kw)
        if i <= 0:
            continue
        prev = tt[:i].rstrip(" 　·-—|：:（()【[《")
        if prev and prev[-1] in "县区旗":
            return True
        break
    return False


def city_match(tt, city_full, cn, provs, prov_bases, all_bases):
    """市名匹配（2026-11-17 修）:
    旧版「市名前必须是边界/[省区]」把「内蒙古呼和浩特市」「中共包头市纪委」
    「中国人民政治协商会议大同市委员会」这类正常标题全部误杀(149 条)。
    改为: 剥省级全名 → 剥开头裸省名(后接区县市旗则不剥) → 剥更大的同名地名
    (马鞍山 vs 鞍山、海南省 vs 海南州) → 含市名即通过。"""
    t = tt
    for p in provs:
        if p and p in t:
            t = t.replace(p, "·")
    for pb in prov_bases:
        if pb and t.startswith(pb) and t[len(pb):len(pb) + 1] not in ADMIN_SUF:
            t = t[len(pb):]
            break
    for cf in all_bases:
        if cf and cf != cn and cf.endswith(cn) and cf in t:
            t = t.replace(cf, "·")
    return (cn and cn in t) or (city_full and city_full in tt)

def _decode(raw):
    m = re.search(rb'charset=["\']?([a-zA-Z0-9-]+)', raw[:4096])
    enc = m.group(1).decode() if m else None
    for e in (enc, "utf-8", "gb18030"):
        if not e:
            continue
        try:
            return raw.decode(e)
        except Exception:
            continue
    return raw.decode("utf-8", errors="ignore")


def fetch(u, timeout=15):
    """curl_cffi 指纹直连优先, 隧道代理 requests 回退。
    2026-11-17 复验: 隧道代理对 gov 站批量请求大量空响应/超时, 178 条
    「title 空」抽样 18 条里 16 条 curl_cffi 直连正常返回 title——审计
    取页层必须用指纹链, 否则误报淹没真问题。
    2026-11-17 二改: 河南纪委统一 CMS 偶发 15s 无响应, 单次超时误报
    title 空 → 指纹链重试 2 次。"""
    for attempt in range(2):
        try:
            if not hasattr(_tl, "crs"):
                import curl_cffi.requests as _cr
                _tl.crs = _cr.Session(impersonate="chrome124")
            r = _tl.crs.get(u, timeout=timeout, verify=False)
            if r.status_code == 200 and r.text and len(r.text) > 300:
                return _decode(r.content)
        except Exception:
            pass
        time.sleep(1.0)
    try:
        import requests, urllib3
        urllib3.disable_warnings()
        if not hasattr(_tl, "sess"):
            s = requests.Session()
            if _TUNNEL: s.proxies = {"http": _TUNNEL, "https": _TUNNEL}
            s.headers["User-Agent"] = UA; s.headers["Connection"] = "close"
            _tl.sess = s
        r = _tl.sess.get(u, timeout=timeout, verify=False)
        if r.status_code != 200 or not r.text or len(r.text) < 300:
            return None
        return _decode(r.content)
    except Exception:
        return None

def title_of(h):
    m = re.search(r"<title[^>]*>(.*?)</title>", h or "", re.S | re.I)
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else ""

def main():
    t = json.load(open("tree.json", encoding="utf-8"))
    blk = next(g for g in t.get("ks") if g.get("n", "").startswith("省级"))
    PORTAL = set()
    for p in (blk.get("ks") or []):
        if p.get("u"): PORTAL.add(urlparse(p["u"]).netloc.lower())
        for jg in (p.get("ks") or []):
            if jg.get("c") == "并列机关":
                for o in (jg.get("ks") or []):
                    if (o.get("u") or "").strip(): PORTAL.add(urlparse(o["u"]).netloc.lower())
    items = []
    all_bases = set()
    for p in (blk.get("ks") or []):
        pn = p.get("n", "")
        all_bases.add(base(pn))
        for c in (p.get("ks") or []):
            all_bases.add(base(c.get("n", "")))
        if "兵团" in pn: continue
        for c in (p.get("ks") or []):
            if c.get("c") not in ("地级市人民政府", "市辖区（地级行政区划）"): continue
            for jg in (c.get("ks") or []):
                if jg.get("c") != "并列机关": continue
                for o in (jg.get("ks") or []):
                    u = (o.get("u") or "").strip()
                    if u and o.get("n") in OFEAT:
                        items.append((pn, c, o))
    provs = [p.get("n", "") for p in (blk.get("ks") or []) if p.get("n")]
    prov_bases = {base(p) for p in provs}
    print("审计对象:", len(items))
    bad = []
    def chk(it):
        pn, c, o = it
        u = o["u"]
        dom = urlparse(u).netloc.lower()
        path = urlparse(u).path or "/"
        city = c.get("n", "")
        cn = base(city)
        cdom = urlparse(c.get("u") or "").netloc.lower()
        known = dom in KNOWN_OK or dom[4:] in KNOWN_OK
        src_serp = "SERP" in (o.get("s") or "")
        # ①本地硬规则（取页前）
        if dns_dead(dom.split(":")[0]):
            return ("hard", pn, city, o["n"], u, "域名已失效(NXDOMAIN)")
        if dom in BAD_DOM: return ("hard", pn, city, o["n"], u, "上级/黑名单域名")
        if any(dom.endswith("." + d) for d in ("12388.gov.cn",)) and o["n"] != "市监委":
            return ("hard", pn, city, o["n"], u, "12388频道挂错系统")
        if dom.startswith(("old.",)): return ("hard", pn, city, o["n"], u, "旧站子域(可疑)")
        # 文章页规则: 地区行署的工作委员会栏目常是 c13_xxxx.shtml 形态; /html/ 目录页以 / 结尾
        is_region = city.endswith("地区")
        if ARTICLE_ID.search(path) or \
                (NEWS_PATH.search(u) and not path.endswith("/")
                 and not is_region
                 and not re.search(r"index\.\w+$", path, re.I)):
            return ("hard", pn, city, o["n"], u, "文章/新闻页(非机构站)")
        if cdom and dom == cdom and (path in ("", "/") or re.match(r"^/index\.", path, re.I)):
            return ("hard", pn, city, o["n"], u, "市门户自身域名")
        # ②title 复验
        h = fetch(u)
        tt = html.unescape(title_of(h))
        if not tt:
            if src_serp and not re.search(OFEAT[o["n"]], dom):
                return ("hard", pn, city, o["n"], u, "title空且域名无机构特征")
            return ("soft", pn, city, o["n"], u, "title空(权威源/原已验证)")
        # 法院统一司法公开平台 elink: 旧版直接放行——2026-11-17 p220 起
        # 解析 elid 目标做存活核验（乌鲁木齐 elink 目标全路径 404 曾被漏掉）
        if "elink.chinacourt" in dom:
            mq = re.search(r"[?&]elid=(.+)$", u)
            tgt = urllib.parse.unquote(mq.group(1)) if mq else ""
            if tgt.startswith(("http://", "https://")):
                th = urlparse(tgt).netloc.split(":")[0]
                if dns_dead(th):
                    return ("hard", pn, city, o["n"], u, "elink目标域名已失效(NXDOMAIN)")
                t_t = html.unescape(title_of(fetch(tgt)))
                if t_t and re.search(r"404|not\s*found|页面没有找到|找不到", t_t, re.I):
                    return ("hard", pn, city, o["n"], u, f"elink目标站404: {t_t[:24]}")
            return None
        if known: return None
        # 县级机构误挂市级（长沙县法院挂长沙市）——城市节点本身是区/县/旗时豁免
        if not city.endswith(("区", "县", "旗", "市辖区")) and county_level(tt, o["n"]):
            return ("hard", pn, city, o["n"], u, f"县级机构误挂市级: {tt[:32]}")
        okcity = city_match(tt, city, cn, provs, prov_bases, all_bases)
        okkw = any(w in tt for w in OWS[o["n"]])
        if okcity and okkw: return None
        if any(dom == d or dom.endswith("." + d) for d in PROV_CHANNEL):
            return ("soft", pn, city, o["n"], u, f"省级官网市级频道: {tt[:30]}")
        if okcity and NEUTRAL_TITLE.match(tt):
            return ("soft", pn, city, o["n"], u, f"title中性: {tt[:30]}")
        if not okcity:
            # 地区行署「工作委员会」栏目: 标题无市名但有机构全称
            if city.endswith("地区") and "工作委员会" in tt and okkw:
                return None
            # 标题只有「市人大」类短名, 但域名带机构特征 → 存疑待核
            if okkw and len(tt) <= 6 and re.search(OFEAT[o["n"]], dom):
                return ("soft", pn, city, o["n"], u, f"title无市名(简称): {tt[:30]}")
            if NEUTRAL_TITLE.match(tt) or not okkw:
                if re.search(OFEAT[o["n"]], dom):
                    return ("soft", pn, city, o["n"], u, f"title无市名(站点简称): {tt[:30]}")
                return ("soft", pn, city, o["n"], u, f"title无市名: {tt[:30]}")
            return ("hard", pn, city, o["n"], u, f"title无市名: {tt[:30]}")
        if okcity and not okkw:
            return ("hard", pn, city, o["n"], u, f"title无机构词: {tt[:30]}")
        return None
    with ThreadPoolExecutor(16) as ex:
        rs = list(ex.map(chk, items))
    hard = [r[1:] for r in rs if r and r[0] == "hard"]
    soft = [r[1:] for r in rs if r and r[0] == "soft"]
    print("问题条目:", len(hard), "/", len(items), "（存疑待核", len(soft), "）")
    for b in hard: print("❌", b[0], b[1], b[2], "|", b[4], "|", b[3][:70])
    print("\n存疑（中性标题/JS壳/权威源 title 空，不判错）:")
    for b in soft: print("  ~", b[0], b[1], b[2], "|", b[4], "|", b[3][:70])
    json.dump(hard, open("/tmp/audit_bad.json", "w"), ensure_ascii=False)
    json.dump(soft, open("/tmp/audit_soft.json", "w"), ensure_ascii=False)

if __name__ == "__main__":
    main()
