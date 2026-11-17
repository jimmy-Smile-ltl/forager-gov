#!/usr/bin/env python
# p207 法院同级互链渠道（2026-11-17 用户启发「同省同级单位导航链接」）:
# 已有中院官网首页「友情链接/yqlj/法院导航」区块列出全省中院——权威互链。
# 对缺口省: 抓该省已有中院官网首页, 提取「XX市中级人民法院」形态链接,
# 基底名匹配块树地级市, 空则填(条树+块树+registry)。
import json, os, re, sys, tempfile
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "util"))
TREE_F = os.path.join(ROOT, "data", "tree.json")
REG_F = os.path.join(ROOT, "data", "site_registry.json")
ETH = r"(哈萨克族?|维吾尔族?|柯尔克孜族?|朝鲜族?|蒙古族?|藏族?|回族?|壮族?|苗族?|黎族?|侗族?|满族?|白族?|傣族?|彝族?|哈尼族?|拉祜族?|傈僳族?|佤族?|水族?|羌族?|布依族?|仡佬族?|仫佬族?|毛南族?|瑶族?|畲族?|土家族?|锡伯族?|达斡尔族?|鄂温克族?|鄂伦春族?|赫哲族?|俄罗斯族?|塔塔尔族?|乌孜别克族?|塔吉克族?|撒拉族?|保安族?|裕固族?|东乡族?|纳西族?|景颇族?|阿昌族?|普米族?|怒族?|德昂族?|独龙族?|基诺族?|门巴族?|珞巴族?|京族?|自治)$"
def base(nm):
    x = re.sub(r"[（(][^（）)]*[）)]$", "", nm or "")
    x = re.sub(r"(中级人民法院|人民法院|法院|中院)$", "", x)
    x = re.sub(r"(自治州|自治县|自治旗|地区|盟|市|县|区|旗|州)$", "", x)
    for _ in range(8):
        x2 = re.sub(ETH, "", x)
        if x2 == x or len(x2) < 2: break
        x = x2
    return x
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
def fetch(u):
    try:
        from smart_fetch import smart_fetch
        h, _ = smart_fetch(u)
        return h if h and len(h) > 500 else None
    except Exception:
        return None
def peer_links(h):
    out = []
    for m in re.finditer(r'href=["\'](https?://[^"\']+)["\'][^>]*>\s*(?:<[^>]+>\s*)*([^<]{4,30}?)\s*(?:<[^>]+>\s*)*</a>', h, re.S):
        u, txt = m.group(1), re.sub(r"[\s　]+", "", m.group(2))
        if re.search(r"中级人民法院$|中院$", txt) and len(txt) <= 18:
            out.append((txt, u))
    return out

def main():
    t = json.load(open(TREE_F, encoding="utf-8"))
    st = {"done": {}}
    if os.path.exists("p207_state.json"):
        try: st = json.load(open("p207_state.json", encoding="utf-8"))
        except Exception: pass
    blk = next(g for g in t.get("ks") if g.get("n", "").startswith("省级"))
    reg = json.load(open(REG_F, encoding="utf-8"))
    # 缺口省: 有中院缺口的地级市列表 + 该省已有中院官网作为互链源
    prov_need = {}
    for p in (blk.get("ks") or []):
        pn = p.get("n", "")
        if "兵团" in pn: continue
        for c in (p.get("ks") or []):
            if c.get("c") not in ("地级市人民政府", "市辖区（地级行政区划）"): continue
            for jg in (c.get("ks") or []):
                if jg.get("c") != "并列机关": continue
                for o in (jg.get("ks") or []):
                    if o.get("n") == "市中级人民法院" and not (o.get("u") or "").strip():
                        prov_need.setdefault(pn, []).append((c, o))
                    elif o.get("n") == "市中级人民法院" and (o.get("u") or "").strip():
                        prov_need.setdefault(pn + "_src", []).append(o["u"])
    filled = 0
    for pn, needs in prov_need.items():
        if pn.endswith("_src"): continue
        srcs = prov_need.get(pn + "_src", [])[:8]
        found = {}
        for s in srcs:
            if st["done"].get(s): continue
            h = fetch(s)
            if not h:
                st["done"][s] = "fail"
                _atomic(st, "p207_state.json")
                continue
            for txt, u in peer_links(h):
                b = base(txt)
                if b:
                    found[b] = (txt, u)
            st["done"][s] = f"ok:{len(found)}"
            _atomic(st, "p207_state.json")
        if not found:
            continue
        for c, o in needs:
            b = base(c.get("n", ""))
            if b in found and not (o.get("u") or "").strip():
                txt, u = found[b]
                o["u"] = u
                o["s"] = "来源:同省中院官网互链(友情链接区块) HTML 提取"
                reg[f"法院|{o['n']}|{c['n']}"] = {"u": u, "n": c["n"] + o["n"], "locations": ["块"], "source_level": "L1", "verified_at": "2026-11-17", "status": "ok", "snapshot": ""}
                filled += 1
                print(f"HIT {pn}|{c['n']}: {u}")
        _atomic(t, TREE_F)
        _atomic(reg, REG_F)
    print("p207 done, filled:", filled)

if __name__ == "__main__":
    main()
