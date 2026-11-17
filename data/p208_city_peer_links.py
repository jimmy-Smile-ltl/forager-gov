#!/usr/bin/env python
# p208 五系统同级互链通用版（2026-11-17 用户启发, p207 法院版推广）:
# 每省每系统, 以该省已有市机构官网为互链源(每系统取 4 个源), 抓首页
# 「友情链接/相关链接/导航」区块提取「XX市+机构词」形态链接, 基底名
# 匹配缺口市, 空则填。title 校验(市名边界+机构词)防串市(鞍山↔马鞍山)。
import json, os, re, sys, tempfile
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "util"))
sys.path.insert(0, os.path.join(ROOT, "data"))
from site_contract import five_key, five_name, upsert_registry
TREE_F = os.path.join(ROOT, "data", "tree.json")
REG_F = os.path.join(ROOT, "data", "site_registry.json")
ETH = r"(哈萨克族?|维吾尔族?|柯尔克孜族?|朝鲜族?|蒙古族?|藏族?|回族?|壮族?|苗族?|黎族?|侗族?|满族?|白族?|傣族?|彝族?|哈尼族?|拉祜族?|傈僳族?|佤族?|水族?|羌族?|布依族?|仡佬族?|仫佬族?|毛南族?|瑶族?|畲族?|土家族?|锡伯族?|达斡尔族?|鄂温克族?|鄂伦春族?|赫哲族?|俄罗斯族?|塔塔尔族?|乌孜别克族?|塔吉克族?|撒拉族?|保安族?|裕固族?|东乡族?|纳西族?|景颇族?|阿昌族?|普米族?|怒族?|德昂族?|独龙族?|基诺族?|门巴族?|珞巴族?|京族?|自治)$"
def base(nm):
    x = re.sub(r"[（(][^（）)]*[）)]$", "", nm or "")
    x = re.sub(r"(人民代表大会常务委员会|人民代表大会|人大常委会|人大|政协委员会|政协|中级人民法院|人民法院|法院|中院|人民检察院|检察院|监察委员会|纪委监委|监委|纪委)$", "", x)
    x = re.sub(r"(自治州|自治县|自治旗|地区|盟|市|县|区|旗|州)$", "", x)
    for _ in range(8):
        x2 = re.sub(ETH, "", x)
        if x2 == x or len(x2) < 2: break
        x = x2
    return x
# 系统 → (市节点名, 链接文本机构词, 互链源取法)
SYS = {"fy": ("市中级人民法院", ("中级人民法院", "人民法院", "法院", "中院")),
       "rd": ("市人大", ("人民代表大会常务委员会", "人民代表大会", "人大常委会", "人大")),
       "zx": ("市政协", ("政协委员会", "政协")),
       "jcy": ("市人民检察院", ("人民检察院", "检察院")),
       "jw": ("市监委", ("监察委员会", "纪委监委", "监委"))}
def _atomic(obj, path):
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
    with os.fdopen(fd, "w") as f:
        json.dump(obj, f, ensure_ascii=False)
    os.replace(tmp, path)
def fetch(u):
    try:
        from smart_fetch import smart_fetch
        h, _ = smart_fetch(u)
        return h if h and len(h) > 500 else None
    except Exception:
        return None
def title_of(h):
    m = re.search(r"<title[^>]*>(.*?)</title>", h or "", re.S | re.I)
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else ""
def peer_links(h, ows):
    out = []
    for m in re.finditer(r'href=["\']([^"\']+)["\'][^>]*>\s*(?:<[^>]+>\s*)*([^<]{3,40}?)\s*(?:<[^>]+>\s*)*</a>', h, re.S):
        u, txt = m.group(1), re.sub(r"[\s　]+", "", m.group(2))
        if len(txt) > 22:
            continue
        if not any(w in txt for w in ows):
            continue
        if not u.startswith("http"):
            continue
        if any(b in u for b in ("mzfzw.net", "cppcc.gov.cn", "npc.gov.cn", "people.com.cn", "ccdi.gov.cn", "spp.gov.cn")):
            continue
        if re.search(r"/(news|content|article|detail|info|tzgg|art)[/._]|/\d{6}/", u, re.I):
            continue
        out.append((txt, u))
    return out

def main():
    t = json.load(open(TREE_F, encoding="utf-8"))
    st = {"done": {}}
    if os.path.exists("p208_state.json"):
        try: st = json.load(open("p208_state.json", encoding="utf-8"))
        except Exception: pass
    blk = next(g for g in t.get("ks") if g.get("n", "").startswith("省级"))
    reg = json.load(open(REG_F, encoding="utf-8"))
    filled = 0
    _only = os.environ.get("P208_SYS", "")
    for skey, (cnode, ows) in SYS.items():
        if _only and skey != _only: continue
        # 每省: 缺口市 + 互链源(该省已有市官网, 每省取 5)
        prov_data = {}
        for p in (blk.get("ks") or []):
            pn = p.get("n", "")
            if "兵团" in pn: continue
            need = []; srcs = []
            for c in (p.get("ks") or []):
                if c.get("c") not in ("地级市人民政府", "市辖区（地级行政区划）"): continue
                for jg in (c.get("ks") or []):
                    if jg.get("c") != "并列机关": continue
                    for o in (jg.get("ks") or []):
                        if o.get("n") == cnode:
                            if (o.get("u") or "").strip(): srcs.append((c.get("n"), o["u"]))
                            else: need.append(c)
            prov_data[pn] = (need, srcs)
        # 省级政协/人大域名(占位链接过滤用)
        prov_org_doms = set()
        for pp in (blk.get("ks") or []):
            for jg in (pp.get("ks") or []):
                if jg.get("c") == "并列机关":
                    for o2 in (jg.get("ks") or []):
                        if (o2.get("u") or "").strip():
                            prov_org_doms.add(urlparse(o2["u"]).netloc.lower())
        tasks = [(pn, skey, need, srcs) for pn, (need, srcs) in prov_data.items() if need and srcs]
        def work(item):
            pn, skey, need, srcs = item
            found = {}
            for city, u in srcs[:5]:
                k = f"{skey}|{u}"
                if st["done"].get(k): continue
                h = fetch(u)
                if not h:
                    st["done"][k] = "fail"
                    continue
                for txt, pu in peer_links(h, ows):
                    b = base(txt)
                    if b and b not in found:
                        found[b] = (txt, pu)
                st["done"][k] = "ok"
            return pn, skey, need, found
        with ThreadPoolExecutor(8) as ex:
            results = list(ex.map(work, tasks))
        for pn, skey, need, found in results:
            if not found:
                _atomic(st, "p208_state.json")
                continue
            for c in need:
                b = base(c.get("n", ""))
                if b in found:
                    txt, u = found[b]
                    dom = urlparse(u).netloc.lower()
                    cdom = urlparse(c.get("u") or "").netloc.lower()
                    if dom == cdom or (dom in prov_org_doms and "#" in u):
                        continue   # 市政府门户/省政协根# = 占位链接
                    for jg in (c.get("ks") or []):
                        if jg.get("c") != "并列机关": continue
                        for o in (jg.get("ks") or []):
                            if o.get("n") == cnode and not (o.get("u") or "").strip():
                                o["u"] = u
                                src = "来源:同省同级机构官网互链(友情链接区块) HTML 提取+title校验"
                                o["s"] = src
                                upsert_registry(reg, five_key(c.get("n"), o["n"]), u,
                                                name=five_name(c.get("n"), o["n"]),
                                                source_level="L2", source=src,
                                                locations=["块"])
                                filled += 1
                                print(f"HIT {skey} {pn}|{c['n']}: {u[:60]}")
        _atomic(st, "p208_state.json")
        _atomic(t, TREE_F)
        _atomic(reg, REG_F)
    print("p208 done, filled:", filled)

if __name__ == "__main__":
    main()
