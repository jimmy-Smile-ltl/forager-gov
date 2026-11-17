#!/usr/bin/env python
# p206 五系统缺口·市门户导航深挖（2026-11-17 用户指令「本级同级人民
# 政府导航找一遍」）: 抓市门户首页 + 组织机构/机构设置类栏目页, 提取
# 人大/政协/法院/检察院/纪委链接——独立域名直收, 门户子路径频道也收
# （官方入口形态, s 留痕「市门户导航频道」）。title 验证(市名边界+机构词)。
import json, os, re, sys, tempfile, threading, urllib.parse
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "util"))
sys.path.insert(0, os.path.join(ROOT, "data"))
from site_contract import five_key, five_name, upsert_registry
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
OWS = {"市人大": ("人民代表大会常务委员会", "人民代表大会", "人大"),
       "市政协": ("政协委员会", "政协"),
       "市中级人民法院": ("中级人民法院", "人民法院", "法院"),
       "市人民检察院": ("人民检察院", "检察院"),
       "市监委": ("监察委员会", "纪委监委", "监委")}
NAV_KW = re.compile(r"(组织机构|机构设置|政府机构|部门导航|部门网站|机构职能|单位导航|机关|领导|市政府领导|政府组成)")
NEWS_PATH = re.compile(r"/(news|content|article|detail|info|tzgg|art|columns|html)[/._]|/\d{6}/", re.I)
BAD_DOM = {"cppcc.gov.cn","npc.gov.cn","people.com.cn","ccdi.gov.cn","spp.gov.cn",
           "chinacourt.org","court.gov.cn","ccgp.gov.cn","mzfzw.net","zgsjzsjw.gov.cn",
           "hainanzx.gov.cn","nxzx.gov.cn","hljzx.gov.cn","ynzx.gov.cn","gzrd.gov.cn",
           "shanxizx.gov.cn","jlrd.gov.cn","xzrd.gov.cn","zjsfgkw.gov.cn","xzjjw.gov.cn",
           "qhjc.gov.cn","jsjc.gov.cn","hbjc.gov.cn","jcy.gov.cn"}
def fetch(u, timeout=14):
    """smart_fetch(curl_cffi 指纹链): 门户反爬裸 curl 全废, curl_cffi 秒回"""
    try:
        from smart_fetch import smart_fetch
        h, _ = smart_fetch(u)
        return h if h and len(h) > 300 else None
    except Exception:
        return None
def title_of(h):
    m = re.search(r"<title[^>]*>(.*?)</title>", h or "", re.S | re.I)
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else ""
def links_of(h):
    out = []
    for m in re.finditer(r'href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', h or "", re.S):
        txt = re.sub(r"<[^>]+>", "", m.group(2))
        txt = re.sub(r"[\s　]+", "", txt)
        if 2 <= len(txt) <= 30:
            out.append((m.group(1), txt))
    return out
def _atomic(obj, path):
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
    with os.fdopen(fd, "w") as f:
        json.dump(obj, f, ensure_ascii=False)
    os.replace(tmp, path)

def main():
    t = json.load(open("tree.json", encoding="utf-8"))
    st = {"done": {}}
    if os.path.exists("p206_state.json"):
        try: st = json.load(open("p206_state.json", encoding="utf-8"))
        except Exception: pass
    blk = next(g for g in t.get("ks") if g.get("n", "").startswith("省级"))
    reg = json.load(open("site_registry.json", encoding="utf-8"))
    tasks = []
    for p in (blk.get("ks") or []):
        pn = p.get("n", "")
        if "兵团" in pn: continue
        for c in (p.get("ks") or []):
            if c.get("c") not in ("地级市人民政府", "市辖区（地级行政区划）"): continue
            for jg in (c.get("ks") or []):
                if jg.get("c") != "并列机关": continue
                for o in (jg.get("ks") or []):
                    if o.get("n") in OWS and not (o.get("u") or "").strip() and c.get("u"):
                        tasks.append((pn, c, o))
    print("缺口任务:", len(tasks))
    def work(it):
        pn, c, o = it
        city = c.get("n", "")
        cn = base(city)
        port = c.get("u", "")
        ows = OWS[o.get("n")]
        got = None
        h = fetch(port)
        if not h:
            return (pn, city, o.get("n"), None, "门户抓取失败")
        phost = urlparse(port).netloc
        # 候选: 首页全部链接(文本含机构词) + 导航栏目页
        navs = [u for u, txt in links_of(h) if NAV_KW.search(txt)]
        pages = [port] + [urljoin(port, u) for u in navs[:3]]
        for pg in pages:
            ph = h if pg == port else fetch(pg)
            if not ph: continue
            for u, txt in links_of(ph):
                if not any(w in txt for w in ows): continue
                if u.startswith("//"): u = "https:" + u
                elif u.startswith("/"): u = "https://" + phost + u
                if NEWS_PATH.search(u) or re.search(r"/\d{6}/|news-show-", u): continue
                dom = urlparse(u).netloc.lower()
                if dom in BAD_DOM: continue
                if any(b in dom for b in ("mzfzw.net",)): continue
                if not (cn in txt or any(w in txt for w in ows)): continue
                th = fetch(u)
                tt = title_of(th) if th else ""
                if not tt: continue
                if not re.search(r"(^|[^一-鿿]|[省区])" + re.escape(cn), tt): continue
                if not any(w in tt for w in ows): continue
                got = u
                break
            if got: break
        if got:
            o["u"] = got
            o["s"] = "来源:市门户导航(首页/组织机构栏目) HTML 提取+title验证"
            return (pn, city, o.get("n"), got, "HIT")
        return (pn, city, o.get("n"), None, "miss")
    results = []
    with ThreadPoolExecutor(8) as ex:
        results = list(ex.map(work, tasks))
    filled = 0
    for pn, city, onm, u, tag in results:
        st["done"][f"{pn}|{city}|{onm}"] = tag.lower()
        if u:
            filled += 1
            src = "来源:市门户导航(首页/组织机构栏目) HTML 提取+title验证"
            upsert_registry(reg, five_key(city, onm), u,
                            name=five_name(city, onm), source_level="L2",
                            source=src, locations=["块"])
            print(f"HIT {pn}|{city}|{onm}: {u[:60]}")
    _atomic(st, "p206_state.json")
    _atomic(t, "tree.json")
    _atomic(reg, "site_registry.json")
    print(f"p206 done, filled: {filled}")
from urllib.parse import urljoin
if __name__ == "__main__":
    main()
