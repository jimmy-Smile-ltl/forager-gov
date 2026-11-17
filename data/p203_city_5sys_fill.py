#!/usr/bin/env python
# p203 五系统地级市补全（2026-11-16 用户指令「人大/政协/法院/检察院/监委
# 做到地级市层面」）: 逐省从省人大/省政协/省检察院/省纪委监委官网首页
# 真实 HTML 提取市级机构链接, 基底名匹配块树地级市, 空则填「并列机关」
# 对应节点 u。法院走 p201（高院首页中院区块）已覆盖, 此处补山东/新疆类
# 首页区块不全的省（栏目页深挖另行）。禁搜索引擎, 失败下轮重试。
import json, os, re, sys, tempfile
from urllib.parse import urlparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "util"))
sys.path.insert(0, os.path.join(ROOT, "data"))
from site_contract import five_key, five_name, upsert_registry
TREE_F = os.path.join(ROOT, "data", "tree.json")
REG_F = os.path.join(ROOT, "data", "site_registry.json")
STATE_F = os.path.join(ROOT, "data", "p203_state.json")

ETH = r"(哈萨克族?|维吾尔族?|柯尔克孜族?|朝鲜族?|蒙古族?|藏族?|回族?|壮族?|苗族?|黎族?|侗族?|满族?|白族?|傣族?|彝族?|哈尼族?|拉祜族?|傈僳族?|佤族?|水族?|羌族?|布依族?|仡佬族?|仫佬族?|毛南族?|瑶族?|畲族?|土家族?|锡伯族?|达斡尔族?|鄂温克族?|鄂伦春族?|赫哲族?|俄罗斯族?|塔塔尔族?|乌孜别克族?|塔吉克族?|撒拉族?|保安族?|裕固族?|东乡族?|纳西族?|景颇族?|阿昌族?|普米族?|怒族?|德昂族?|独龙族?|基诺族?|门巴族?|珞巴族?|京族?|自治)$"
ETH_RE = re.compile(ETH)

def base(nm):
    t = re.sub(r"[（(][^（）)]*[）)]$", "", nm or "")
    t = re.sub(r"(人民代表大会常务委员会|人民代表大会|人大|政协委员会|政协|人民检察院|检察院|监察委员会|纪委监委|纪委|中级人民法院|人民法院|法院)$", "", t)
    t = re.sub(r"(自治州|自治县|自治旗|地区|盟|市|县|区|旗|州)$", "", t)
    for _ in range(8):
        t2 = ETH_RE.sub("", t)
        if t2 == t or len(t2) < 2:
            break
        t = t2
    return t

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

# 系统 → 省并列机关节点名 → 块树市并列机关节点名
SYS = [("rd", "省人大", "市人大"), ("zx", "省政协", "市政协"),
       ("jcy", "省人民检察院", "市人民检察院"), ("jw", "省监委", "市监委")]
NEWS_PATH = re.compile(r"/(news|content|article|detail|info|tzgg|通知|公示)[/._]|\.shtml$|\.htm$|\.html$", re.I)

def main():
    t = json.load(open(TREE_F, encoding="utf-8"))
    st = {"done": {}}
    if os.path.exists(STATE_F):
        try:
            st = json.load(open(STATE_F, encoding="utf-8"))
        except Exception:
            pass
    blk = next((g for g in t.get("ks", []) if g.get("n", "").startswith("省级")), None)
    if not blk:
        print("省级组未找到")
        return
    reg = json.load(open(REG_F, encoding="utf-8"))
    filled = 0
    for p in (blk.get("ks") or []):
        pn = p.get("n", "")
        if "兵团" in pn:
            continue
        # 省并列机关 u
        porj = {}
        for jg in (p.get("ks") or []):
            if jg.get("c") == "并列机关":
                for o in (jg.get("ks") or []):
                    porj[o.get("n", "")] = (o.get("u") or "").strip()
        # 市州索引: 基底 → 城市节点
        cities = {}
        for c in (p.get("ks") or []):
            if c.get("c") in ("地级市人民政府", "市辖区（地级行政区划）"):
                cities.setdefault(base(c.get("n", "")), c)
        for skey, porg, cnode in SYS:
            key = f"{pn}|{skey}"
            if st["done"].get(key):
                continue
            purl = porj.get(porg, "")
            if not purl:
                st["done"][key] = "no-prov-url"
                _atomic(st, STATE_F)
                continue
            if os.environ.get("P203_LIGHT") == "1":
                from http_client import get_client
                h, m = None, "light"
                try:
                    h = get_client().fetch_text(purl, timeout=15)
                    if h and len(h) < 500:
                        h = None
                except Exception as e:
                    m = f"light-exc:{type(e).__name__}"
            else:
                from smart_fetch import smart_fetch
                try:
                    h, m = smart_fetch(purl)
                except Exception as e:
                    h, m = None, f"exc:{type(e).__name__}"
            if not h or len(h) < 500:
                st["done"][key] = f"fail:{m}"
                _atomic(st, STATE_F)
                continue
            got = 0
            for mm in re.finditer(r'href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', h, re.S):
                u, raw = mm.group(1), mm.group(2)
                txt = re.sub(r"<[^>]+>", "", raw)
                txt = re.sub(r"[\s　]+", "", txt)
                if len(txt) < 2 or len(txt) > 24:
                    continue
                if NEWS_PATH.search(u):
                    continue
                # 文本含系统关键词且基底匹配市州
                kw = {"rd": "人大", "zx": "政协", "jcy": "检察", "jw": "纪委|监委"}[skey]
                if not re.search(kw, txt) and not re.search(r"(rd|zx|jcy|jjjc|jjw)\.", u):
                    continue
                if u.startswith("//"):
                    u = "https:" + u
                elif u.startswith("/"):
                    u = "https://" + urlparse(purl).netloc + u
                b = base(txt)
                c = cities.get(b)
                if not c:
                    continue
                for jg in (c.get("ks") or []):
                    if jg.get("c") != "并列机关":
                        continue
                    for o in (jg.get("ks") or []):
                        if o.get("n") == cnode and not (o.get("u") or "").strip():
                            o["u"] = u
                            src = f"来源:{porg}官网({purl})市级链接区块 HTML 提取"
                            o["s"] = src
                            upsert_registry(reg, five_key(c["n"], cnode), u,
                                            name=five_name(c["n"], cnode),
                                            source_level="L1", source=src,
                                            locations=["块"])
                            got += 1
                            filled += 1
            st["done"][key] = f"ok:{got}"
            _atomic(st, STATE_F)
            _atomic(t, TREE_F)
            _atomic(reg, REG_F)
            print(f"{key}: {got} 填充")
    print("p203 done, filled:", filled)

if __name__ == "__main__":
    main()
