#!/usr/bin/env python
# p204 五系统地级市补全·渠道2+3（2026-11-16 用户指令）
# 渠道2: 市政府门户首页「人大/政协/法院/检察院/纪委」导航链接提取
# 渠道3: 百度 SERP 搜索兜底, title 严格验证(市名+机构词)才落库
# 全部访问走代理(dps/隧道), s 留痕「SERP线索+title严格验证」。
import json, os, re, sys, tempfile, urllib.parse
from urllib.parse import urlparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "util"))
sys.path.insert(0, os.path.join(ROOT, "data"))
from site_contract import base as city_base, five_key, five_name, upsert_registry
TREE_F = os.path.join(ROOT, "data", "tree.json")
REG_F = os.path.join(ROOT, "data", "site_registry.json")
STATE_F = os.path.join(ROOT, "data", "p204_state.json")
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"

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

import threading
_serp_lock = threading.Lock()
def serp_fetch(q):
    """百度 SERP: 隧道 IP 被百度拦截(227字节验证页), 必须走 dps 私密代理;
    http_client 单例非线程安全 → 全局锁串行（SERP 请求量小, 可接受）"""
    with _serp_lock:
        from http_client import get_client
        try:
            return get_client().fetch_text(f"https://www.baidu.com/s?wd={q}&rn=10", timeout=15)
        except Exception:
            return None
from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, ".env"))
_TUNNEL = os.environ.get("TUNNEL_PROXY", "")
_tl = threading.local()

def fetch(u, timeout=15):
    """每线程独立 requests+隧道代理（http_client 单例非线程安全, 16 并发
    共享会状态污染全失败）"""
    try:
        import requests, urllib3
        urllib3.disable_warnings()
        if not hasattr(_tl, "sess"):
            s = requests.Session()
            if _TUNNEL:
                s.proxies = {"http": _TUNNEL, "https": _TUNNEL}
            s.headers["User-Agent"] = UA
            s.headers["Connection"] = "close"   # 隧道切换 IP 关键
            _tl.sess = s
        r = _tl.sess.get(u, timeout=timeout, verify=False)
        if r.status_code != 200 or not r.text or len(r.text) < 300:
            return None
        try:
            r.encoding = r.apparent_encoding
        except Exception:
            pass
        return r.text
    except Exception:
        return None

def title_of(h):
    m = re.search(r"<title[^>]*>(.*?)</title>", h or "", re.S | re.I)
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else ""

ORG = {"市人大": ("人大", ("人民代表大会常务委员会", "人民代表大会", "人大"), r"(rd|renda|spc)"),
       "市政协": ("政协", ("政协委员会", "政协"), r"zx"),
       "市中级人民法院": ("法院", ("中级人民法院", "人民法院", "法院"), r"(court|fy|zy)"),
       "市人民检察院": ("检察院", ("人民检察院", "检察院"), r"(jcy|jc|jiancha)"),
       "市监委": ("监委", ("监察委员会", "纪委监委", "监委"), r"(jjw|jjjc|jcj|jiwei|lz|lj|lx|ql|qf|qinfeng|cdi|di|12388|subsite|jj|jc)")}
NEWS_PATH = re.compile(r"/(news|content|article|detail|info|tzgg|art|columns|html)[/._]|/\d{6}/", re.I)

def main():
    t = json.load(open(TREE_F, encoding="utf-8"))
    st = {"done": {}}
    if os.path.exists(STATE_F):
        try:
            st = json.load(open(STATE_F, encoding="utf-8"))
        except Exception:
            pass
    blk = next((g for g in t.get("ks", []) if g.get("n", "").startswith("省级")), None)
    reg = json.load(open(REG_F, encoding="utf-8"))
    # 省级域名黑名单: 省门户 + 省并列机关(人大/政协/检察院/纪委/法院)——SERP 常返回其新闻页
    PORTAL_DOMS = set()
    for p in (blk.get("ks") or []):
        pu = (p.get("u") or "")
        if pu:
            PORTAL_DOMS.add(urlparse(pu).netloc.lower())
        for jg in (p.get("ks") or []):
            if jg.get("c") == "并列机关":
                for o2 in (jg.get("ks") or []):
                    if (o2.get("u") or "").strip():
                        PORTAL_DOMS.add(urlparse(o2["u"]).netloc.lower())
    filled = 0
    tasks = []
    for p in (blk.get("ks") or []):
        pn = p.get("n", "")
        if "兵团" in pn:
            continue
        for c in (p.get("ks") or []):
            if c.get("c") not in ("地级市人民政府", "市辖区（地级行政区划）"):
                continue
            for jg in (c.get("ks") or []):
                if jg.get("c") != "并列机关":
                    continue
                for o in (jg.get("ks") or []):
                    if o.get("n") in ORG and not (o.get("u") or "").strip():
                        tasks.append((pn, c, o))
    print("缺口任务:", len(tasks))
    from concurrent.futures import ThreadPoolExecutor
    pending = [x for x in tasks if not st["done"].get(f"{x[0]}|{x[1].get('n')}|{x[2].get('n')}")]
    if os.environ.get("P204_LIMIT"):
        pending = pending[:int(os.environ["P204_LIMIT"])]
    print("本轮待跑:", len(pending))
    def work(item):
        pn, c, o = item
        key = f"{pn}|{c.get('n')}|{o.get('n')}"
        city = c.get("n", "")
        cn = city_base(city)
        okw, ows, ofeat = ORG[o.get("n")]
        got = False
        lvl = None
        # 渠道2: 市门户导航
        port = c.get("u") or ""
        if port:
            h = fetch(port)
            if h:
                host_portal = urlparse(port).netloc
                for m in re.finditer(r'href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', h, re.S):
                    u, raw = m.group(1), m.group(2)
                    txt = re.sub(r"<[^>]+>", "", raw)
                    txt = re.sub(r"[\s　]+", "", txt)
                    if not any(w in txt for w in ows):
                        continue
                    if u.startswith("//"):
                        u = "https:" + u
                    elif u.startswith("/"):
                        u = "https://" + host_portal + u
                    if NEWS_PATH.search(u) or host_portal in u:
                        continue
                    if cn in txt or okw in txt:
                        # title 验证
                        th = fetch(u)
                        tt = title_of(th) if th else ""
                        if tt and (re.search(r"(^|[^一-鿿])" + re.escape(cn), tt) or okw in tt):
                            o["u"] = u
                            o["s"] = f"来源:市门户({port})导航链接 HTML 提取+title验证"
                            got = True
                            lvl = "L2"
                            break
        # 渠道3: 百度 SERP 兜底
        if not got:
            q = urllib.parse.quote(f"{city}{o.get('n')[1:]}")
            sh = serp_fetch(q)
            if sh:
                # 百度 SERP mu 属性=结果真实 URL（跳转链不可直接 fetch, 用 mu）
                cands = []
                BAD_DOM = {"cppcc.gov.cn", "www.gov.cn", "npc.gov.cn", "people.com.cn",
                          "ccdi.gov.cn", "spp.gov.cn", "chinacourt.org",
                          "court.gov.cn", "sdcourt.gov.cn", "baike.baidu.com",
                          "hainanzx.gov.cn", "nxzx.gov.cn", "hljzx.gov.cn", "ynzx.gov.cn",
                          "gzrd.gov.cn", "shanxizx.gov.cn", "jlrd.gov.cn", "xzrd.gov.cn"}
                BAD_SUB = ("elink.chinacourt.cn",)
                for u in re.findall(r'mu="(https?://[^"]+)"', sh):
                    if "baidu.com" in u or "baike" in u:
                        continue
                    dom = urlparse(u).netloc.lower()
                    if dom in BAD_DOM or any(dom.endswith("." + d) for d in BAD_SUB):
                        continue
                    if dom in PORTAL_DOMS and "/subsite/" not in u:
                        continue   # 省级机关域名: 根域拒, /subsite/ 市级频道放行
                    # 12388 省级频道: 仅监委收(市纪委监委频道=官方入口), 其他系统不收
                    if ".12388.gov.cn" in dom and o.get("n") != "市监委":
                        continue
                    if ".gov.cn" in dom or "chinacourt" in dom:
                        cands.append(u)
                    if len(cands) >= 5:
                        break
                city_dom = urlparse(port).netloc.lower() if port else ""
                for u in cands:
                    udom = urlparse(u).netloc.lower()
                    if city_dom and udom == city_dom:
                        continue   # 市门户自身域名(新闻/栏目页)不是机构官网
                    if not re.search(ofeat, udom):
                        continue   # 域名无机构特征(rd/zx/jcy/jjjc/court) → 新闻/门户页
                    th = fetch(u)
                    if not th:
                        continue
                    tt = title_of(th)
                    if NEWS_PATH.search(u):
                        continue
                    if any(w in tt for w in ows) and re.search(r"(^|[^一-鿿])" + re.escape(cn), tt):
                        o["u"] = u
                        o["s"] = "来源:SERP线索+title严格验证(市名边界+机构词双验)"
                        got = True
                        lvl = "L3"
                        break
        if got:
            upsert_registry(reg, five_key(city, o["n"]), o["u"],
                            name=five_name(city, o["n"]),
                            source_level=lvl or "L3", source=o.get("s", ""),
                            locations=["块"])
        return key, got, o.get("u", "")
    results = []
    with ThreadPoolExecutor(16) as ex:
        results = list(ex.map(work, pending))
    for key, got, u in results:
        st["done"][key] = "hit" if got else "miss"
        if got:
            filled += 1
        print(f"{key}: {'HIT '+u[:50] if got else 'miss'}")
    _atomic(st, STATE_F)
    _atomic(t, TREE_F)
    _atomic(reg, REG_F)
    print("p204 done, filled:", filled)

if __name__ == "__main__":
    main()
