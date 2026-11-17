#!/usr/bin/env python
# p201 市级中级法院全量补全（2026-11-16 用户指令「补全市级中级法院」）
# 方法: 条树 fy 系统 32 高院官网首页「中院」链接区块真实 HTML 提取,
# elink 包装的 elid 参数解码为直链; 简称文本(成都市中院/阿坝州中院)与
# 块树市州全名归一匹配; 现有节点名全名化(阿坝州中院→阿坝藏族羌族自治州
# 中级人民法院), 无节点则按全名新建。专门法院(林区/铁路/海事/知产等)排除。
import json, os, re, sys, tempfile
from urllib.parse import parse_qs, urlparse, unquote

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "util"))
TREE_F = os.path.join(ROOT, "data", "tree.json")
REG_F = os.path.join(ROOT, "data", "site_registry.json")
STATE_F = os.path.join(ROOT, "data", "p201_state.json")

ETH = r"(哈萨克族?|维吾尔族?|柯尔克孜族?|蒙古族?|藏族?|回族?|壮族?|苗族?|黎族?|侗族?|满族?|白族?|傣族?|彝族?|哈尼族?|拉祜族?|傈僳族?|佤族?|水族?|羌族?|布依族?|仡佬族?|仫佬族?|毛南族?|瑶族?|畲族?|土家族?|锡伯族?|达斡尔族?|鄂温克族?|鄂伦春族?|赫哲族?|俄罗斯族?|塔塔尔族?|乌孜别克族?|塔吉克族?|朝鲜族?|撒拉族?|保安族?|裕固族?|东乡族?|纳西族?|景颇族?|阿昌族?|普米族?|怒族?|德昂族?|独龙族?|基诺族?|门巴族?|珞巴族?|京族?|自治)$"
ETH_RE_END = re.compile(ETH)
SPECIAL = re.compile(r"(林区|铁路|海事|知识产权|互联网|金融|自贸|矿区|油田|垦区|农垦|兵团|第一|第二|第三|第四|第五|第六|第七|第八|第九|第十|第十二|第十三)")

def base(nm):
    """机构名→基底市州名: 剥法院后缀+行政区后缀+民族修饰(尾缀锚定+单字保护)"""
    t = re.sub(r"(市|州|盟|地区)?中级人民法院$", "", nm or "")
    t = re.sub(r"(市|州|盟|地区)?中院$", "", t)
    t = re.sub(r"人民法院$", "", t)
    t = re.sub(r"[（(][^（）)]*[）)]$", "", t)
    t = re.sub(r"(自治州|自治县|自治旗|地区|盟|市|县|区|旗|州)$", "", t)
    for _ in range(8):
        t2 = ETH_RE_END.sub("", t)
        if t2 == t or len(t2) < 2:
            break
        t = t2
    return t

def _atomic(obj, path):
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=os.path.basename(path) + ".", suffix=".tmp")
    with os.fdopen(fd, "w") as f:
        json.dump(obj, f, ensure_ascii=False)
    os.replace(tmp, path)

def load_tree():
    return json.load(open(TREE_F, encoding="utf-8"))

def find(n, name):
    if n.get("n") == name:
        return n
    for k in n.get("ks") or []:
        r = find(k, name)
        if r:
            return r
    return None

def dec(u):
    """elink 包装 → elid 直链（URL 编码或 base64 两形态）; 协议相对 → https"""
    if "elid=" in u:
        q = parse_qs(urlparse(u.replace("//elink", "https://elink")).query)
        e = q.get("elid", [""])[0]
        try:
            d = unquote(e)
            if not d.startswith("http") and re.fullmatch(r"[A-Za-z0-9+/=]+", e):
                import base64
                d = base64.b64decode(e + "===").decode("utf-8", errors="ignore")
            u = d
        except Exception:
            pass
    if u.startswith("//"):
        u = "https:" + u
    if "://" not in u:
        return None
    return u

def main():
    t = load_tree()
    st = {"done": {}}
    if os.path.exists(STATE_F):
        try:
            st = json.load(open(STATE_F, encoding="utf-8"))
        except Exception:
            pass
    # 块树市州全名索引: 基底 → 全名
    city_full = {}
    def w(n):
        if n.get("k") == "人民政府" and n.get("c") in ("地级市人民政府", "地级区划", "自治州人民政府") and n.get("n"):
            city_full.setdefault(base(n["n"]), n["n"])
        for k in n.get("ks") or []:
            w(k)
    w(t)
    g = find(t, "高级人民法院（32）")
    if not g:
        print("高级人民法院分组未找到")
        return
    added = 0
    for hn in (g.get("ks") or []):
        hu = hn.get("u") or ""
        if "兵团" in hn.get("n", "") or not hu:
            continue
        if st["done"].get(hn["n"]):
            continue
        from smart_fetch import smart_fetch
        try:
            h, m = smart_fetch(hu)
        except Exception as e:
            st["done"][hn["n"]] = f"fetch-exc:{type(e).__name__}"
            _atomic(st, STATE_F)
            continue
        if not h or len(h) < 500:
            st["done"][hn["n"]] = f"fetch-fail:{m}"
            _atomic(st, STATE_F)
            continue
        # 提取 <a href>...</a> 全标签段（兼容 <span>包裹文本 形态: 清远/吉林类）
        cands = []
        for m in re.finditer(r'href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', h, re.S):
            u, raw = m.group(1), m.group(2)
            txt = re.sub(r"<[^>]+>", "", raw)
            txt = re.sub(r"[\s　]+", "", txt)
            if len(txt) < 2 or len(txt) > 40:
                continue
            if not re.search(r"中院|中级", txt):
                continue
            # 新闻标题形态过滤（高院首页新闻列表「XX中院召开…」类不是名录链接）
            if re.search(r"[｜|:：]|\.\.|法官|礼赞|原创|办实事|整顿|MV|“|”|案例|通报|召开|举办", txt):
                continue
            if not txt.endswith(("中院", "中级人民法院")):
                continue
            real = dec(u)
            if not real:
                continue
            cands.append((txt, real))
        # 去重(按直链)
        seen = set()
        ded = []
        for txt, real in cands:
            if real in seen:
                continue
            seen.add(real)
            ded.append((txt, real))
        kids = {base(k.get("n")): k for k in (hn.get("ks") or [])}
        changed = 0
        for txt, real in ded:
            if SPECIAL.search(txt):
                continue
            b = base(txt)
            if not b:
                continue
            node = kids.get(b)
            if node:
                if not node.get("u"):
                    node["u"] = real
                    node["s"] = f"来源:{hn['n']}官网首页中院区块 HTML 提取"
                    changed += 1
                # 全名化: 阿坝州中院 → 阿坝藏族羌族自治州中级人民法院
                full = city_full.get(b)
                if full and node.get("n") != full + "中级人民法院":
                    node["n"] = full + "中级人民法院"
                    changed += 1
                continue
            # 新增节点
            full = city_full.get(b)
            if not full:
                continue
            kids[b] = {"n": full + "中级人民法院", "l": "市", "k": "中级人民法院",
                       "c": "中级人民法院", "p1": hn["n"], "u": real,
                       "s": f"来源:{hn['n']}官网首页中院区块 HTML 提取"}
            hn.setdefault("ks", []).append(kids[b])
            added += 1
            changed += 1
        # registry 同步
        reg = json.load(open(REG_F, encoding="utf-8"))
        for k in (hn.get("ks") or []):
            if k.get("u"):
                reg[f"法院|{k['n']}"] = {"u": k["u"], "n": k["n"], "locations": ["块", "条"],
                                        "source_level": "L1", "verified_at": "2026-11-16", "status": "ok", "snapshot": ""}
        _atomic(reg, REG_F)
        st["done"][hn["n"]] = f"ok:{changed}chg"
        _atomic(st, STATE_F)
        _atomic(t, TREE_F)
        print(f"{hn['n']}: 候选{len(ded)} 变更{changed} 新增{added} 累计")
    print("p201 done, added total:", added)

if __name__ == "__main__":
    main()
