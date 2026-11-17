# -*- coding: utf-8 -*-
"""P194: 凉山州 17 县市政府门户补全 + 条→块法检同步。

背景（2026-11-11 用户指正）：lsz.gov.cn 官网区县导航有木里县（官网锚文本
用简称「木里县」，树节点全名「木里藏族自治县」——简称/全名匹配不佳的典型）。
块树凉山 17 县市中 8 个门户 u 为空（西昌/会理/木里/宁南/金阳/昭觉/甘洛/美姑）。

来源：https://www.lsz.gov.cn/ 首页 inkboxlist 区县导航区块真实 HTML（17 链接
全量提取），逐条 smart_fetch title 验证后落库。条系统凉山法院/检察叶子 URL
同步回填块树「并列机关→县人民法院/县人民检察院」（空才填）。
"""
import sys, os, re, json, datetime

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, "util"))
from smart_fetch import smart_fetch

os.chdir(BASE)
tree = json.load(open("data/tree.json", encoding="utf-8"))
reg = json.load(open("data/site_registry.json", encoding="utf-8"))
today = datetime.date.today().strftime("%Y-%m-%d")

# ── 1. 官方门户区县导航真实 HTML 提取 ──
html, method = smart_fetch("https://www.lsz.gov.cn/")
assert html, "lsz.gov.cn 获取失败"
TARGET = {"西昌市": "西昌市", "会理市": "会理市", "德昌县": "德昌县",
          "会东县": "会东县", "宁南县": "宁南县", "普格县": "普格县",
          "布拖县": "布拖县", "昭觉县": "昭觉县", "金阳县": "金阳县",
          "雷波县": "雷波县", "美姑县": "美姑县", "甘洛县": "甘洛县",
          "越西县": "越西县", "喜德县": "喜德县", "冕宁县": "冕宁县",
          "盐源县": "盐源县", "木里县": "木里藏族自治县"}   # 官网简称 → 树全名
links = {}
for a in re.finditer(r'<a href="(https?://www\.[a-z]+\.gov\.cn/?[^"]*)"[^>]*>\s*([^<]{2,10}?)\s*</a>', html):
    nm = a.group(2).strip()
    if nm in TARGET:
        links[TARGET[nm]] = a.group(1).strip().rstrip("/")
assert len(links) == 17, f"仅提取 {len(links)}/17: {sorted(links)}"

# ── 2. title 验证 ──
def verify(name, u):
    try:
        h, m = smart_fetch(u)
        if not h:
            return False, "无响应"
        t = (re.search(r"<title>(.*?)</title>", h, re.S) or [None, ""])[1] if False else ""
        m2 = re.search(r"<title>(.*?)</title>", h, re.S | re.I)
        t = m2.group(1).strip() if m2 else ""
        base = name.replace("藏族自治县", "").replace("彝族自治州", "")
        ok = bool(t) and ("政府" in t or base[:2] in t or "凉山" in t or "县" in t or "市" in t)
        return ok, t[:30]
    except Exception as e:
        return False, str(e)[:30]

# ── 3. 块树回填 ──
def find_node(n, name):
    if n.get("n") == name:
        return n
    for k in n.get("ks", []) or []:
        r = find_node(k, name)
        if r:
            return r
    return None

ls = find_node(tree, "凉山彝族自治州")
assert ls, "树中无凉山彝族自治州节点"
METHOD = "来源：凉山州政府门户(lsz.gov.cn)区县导航 HTML 提取（title 验证）"
filled, verified = 0, 0
for x in ls["ks"]:
    if x.get("k") != "人民政府":
        continue
    nm = x["n"]
    u = links.get(nm)
    if not u:
        print(f"  ⚠ 官网导航无 {nm}")
        continue
    ok, t = verify(nm, u)
    if not ok:
        print(f"  ⚠ {nm} title 验证不过: {t}")
        continue
    verified += 1
    if not x.get("u"):
        x["u"] = u
        x["s"] = METHOD
        filled += 1
        print(f"  ✓ {nm} → {u}")
print(f"title 验证通过 {verified}/17, 块树回填 {filled} 个")

# ── 4. 注册表 ──
reg_filled = 0
for x in ls["ks"]:
    if x.get("k") != "人民政府" or not x.get("u"):
        continue
    key = f"县级人民政府|{x['n']}"
    if key in reg and reg[key].get("u"):
        continue
    reg[key] = {"u": x["u"], "n": x["n"], "locations": ["块"],
                "source_level": "L2", "verified_at": today,
                "status": "ok", "snapshot": "", "xxgk": "", "xxgk_src": ""}
    reg_filled += 1
print(f"registry 新增 {reg_filled} 条")

# ── 5. 条→块 法院/检察同步（凉山 17 县）──
def walk_all(n):
    yield n
    for k in n.get("ks", []):
        yield from walk_all(k)

ETH_PY = re.compile(
    r"(哈萨克族?|维吾尔族?|柯尔克孜族?|蒙古族?|藏族?|回族?|壮族?|苗族?|黎族?|侗族?|满族?|白族?|傣族?|彝族?|哈尼族?|拉祜族?|傈僳族?|佤族?|水族?|羌族?|布依族?|仡佬族?|仫佬族?|毛南族?|瑶族?|畲族?|土家族?|锡伯族?|达斡尔族?|鄂温克族?|鄂伦春族?|赫哲族?|俄罗斯族?|塔塔尔族?|乌孜别克族?|塔吉克族?|撒拉族?|保安族?|裕固族?|东乡族?|纳西族?|景颇族?|阿昌族?|普米族?|怒族?|德昂族?|独龙族?|基诺族?|门巴族?|珞巴族?|京族?|自治)$")

def base(nm):
    t = re.sub(r"(自治州|自治县|自治旗|地区|盟|市|县|区|旗)$", "", nm or "")
    for _ in range(8):
        t2 = ETH_PY.sub("", t)
        if t2 == t:
            break
        t = t2
    return t

tiao_orgs = {}
for n in walk_all(tree):
    nm = n.get("n", "")
    if not n.get("u") or n.get("ks"):
        continue
    if "法院" in nm and ("县" in nm or "市" in nm):
        tiao_orgs.setdefault(("fy", base(re.sub(r"(人民法院|法院)$", "", nm))), n["u"])
    if "检察" in nm and ("县" in nm or "市" in nm):
        tiao_orgs.setdefault(("jcy", base(re.sub(r"(人民检察院|检察院)$", "", nm))), n["u"])

synced = 0
for x in ls["ks"]:
    if x.get("k") != "人民政府":
        continue
    b = base(x["n"])
    for g in x.get("ks", []) or []:
        if g.get("k") != "分组" or "并列" not in g.get("n", ""):
            continue
        for o in g.get("ks", []) or []:
            if o.get("u"):
                continue
            if "人民法院" in o.get("n", "") and ("fy", b) in tiao_orgs:
                o["u"] = tiao_orgs[("fy", b)]
                o["s"] = "来源：法院系统条树同步（p194）"
                synced += 1
            elif "人民检察院" in o.get("n", "") and ("jcy", b) in tiao_orgs:
                o["u"] = tiao_orgs[("jcy", b)]
                o["s"] = "来源：检察院系统条树同步（p194）"
                synced += 1
print(f"条→块 法检同步 {synced} 个")

json.dump(tree, open("data/tree.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
json.dump(reg, open("data/site_registry.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=0)
print("P194 done")
