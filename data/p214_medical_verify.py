#!/usr/bin/env python
# p214 医疗系统 URL 正确性检验（2026-11-17 用户指令「检验医疗系统的url正确性」）
# 对医疗系统子树全部 URL 并发复验:
#   ok       200 + title 含机构基底名 + 机构词
#   neutral  200 + title 中性/空（JS 壳站, 采录时已验证 → 存疑不判错）
#   mismatch 200 + title 与机构不符（错配 → 待修）
#   waf      4xx/5xx/挑战页（WAF 防护, 无法 title 验证 → 存疑）
#   dead     DNS 失败/连接错误/超时（死链 → 待修）
# 抓取: 每线程独立 curl_cffi Session(impersonate=chrome124)——p213 沉淀的五连坑教训。
import json, os, re, socket, sys, threading, tempfile
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "util"))
TREE_F = os.path.join(ROOT, "data", "tree.json")
OUT_F = os.path.join(ROOT, "data", "medical_url_check_report.json")
_tl = threading.local()

ETH = r"(哈萨克族?|维吾尔族?|柯尔克孜族?|朝鲜族?|蒙古族?|藏族?|回族?|壮族?|苗族?|黎族?|侗族?|满族?|白族?|傣族?|彝族?|哈尼族?|拉祜族?|傈僳族?|佤族?|水族?|羌族?|布依族?|仡佬族?|仫佬族?|毛南族?|瑶族?|畲族?|土家族?|锡伯族?|达斡尔族?|鄂温克族?|鄂伦春族?|赫哲族?|俄罗斯族?|塔塔尔族?|乌孜别克族?|塔吉克族?|撒拉族?|保安族?|裕固族?|东乡族?|纳西族?|景颇族?|阿昌族?|普米族?|怒族?|德昂族?|独龙族?|基诺族?|门巴族?|珞巴族?|京族?|自治)$"
ETH_RE = re.compile(ETH)
NEUTRAL = re.compile(r"^(首页|网站首页|欢迎|Welcome|index|-)?\s*$", re.I)
NEUTRAL_Q = re.compile(r"Web managerment|系统提示|建设中", re.I)  # 拉萨 jkw 类壳站标题
WAF_SIG = re.compile(r"(安全验证|访问验证|滑动验证|请输入验证码|检测到异常|WAF|challenge|Just a moment|访问过于频繁)", re.I)


def base(nm):
    t = re.sub(r"[（(][^（）)]*[）)]$", "", nm or "")
    t = re.sub(r"(疾病预防控制中心|疾控中心|卫生健康委员会|卫健委|卫生健康局|卫生计生委|卫生局)$", "", t)
    # 自治区先剥（宁夏回族自治区→宁夏）; 否则尾部「区」误剥成「宁夏自治」致 CDC 误报
    t = re.sub(r"(自治区|特别行政区)$", "", t)
    t = re.sub(r"(自治州|自治县|自治旗|地区|盟|市|县|区|旗|州)$", "", t)
    for _ in range(8):
        t2 = ETH_RE.sub("", t)
        if t2 == t or len(t2) < 2:
            break
        t = t2
    return t


def kw_of(n):
    if "疾病预防控制中心" in n or "疾控中心" in n:
        return ("疾病预防控制中心", "疾控中心")
    if "中医药" in n:
        return ("中医药管理局", "中医药")
    if "疾病预防控制局" in n:
        return ("疾病预防控制局", "疾控局")
    return ("卫生健康委员会", "卫健委", "卫生健康委", "卫生健康局", "卫生局", "卫生计生委")


def clean_title(tt):
    """重复标题取首段; 中性前缀「首页 - XXX」取后段"""
    parts = re.split(r"[—–-]", tt or "")
    if len(parts) > 1 and re.match(r"^\s*(首页|欢迎|网站首页|Home)\s*$", parts[0]):
        return parts[1].strip()
    return parts[0].strip()


def title_match(n, tt, strict=False):
    if not tt:
        return "neutral"
    tt1 = clean_title(tt)
    if NEUTRAL.match(tt1) or NEUTRAL_Q.search(tt1):
        return "neutral"
    nb = base(n)
    # 省级卫健委站 title 惯用「省卫生健康委员会」不带省名（黑龙江案例）→ 视为站点惯例 ok
    if re.match(r"^(省|自治区)卫生健康委员会$", tt1):
        return "ok"
    if strict:
        # 跨省同名基底（吉林市/吉林省、青海海南州/海南省）: 要求全称或 X州/X市
        if not any(x in tt1 for x in (n, nb + "州", nb + "市")):
            return "mismatch"
    elif not nb or nb not in tt1:
        return "mismatch"
    return "ok" if any(w in tt1 for w in kw_of(n)) else "mismatch"


def dns_ok(host):
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


def check(u, timeout=12):
    if not dns_ok(urlparse(u).netloc):
        return "dead", "DNS 失败"
    try:
        if not hasattr(_tl, "crs"):
            import curl_cffi.requests as _cr
            _tl.crs = _cr.Session(impersonate="chrome124")
        r = _tl.crs.get(u, timeout=timeout, verify=False)
        if r.status_code == 200 and r.text and len(r.text) > 200:
            return "alive", r.text
        return "waf", f"HTTP {r.status_code} ({len(r.text or '')}B)"
    except Exception as e:
        msg = str(e)
        return "dead", f"{type(e).__name__}:{msg[:60]}"


def extract_title(html):
    """按 charset 解码 title（gbk/gb18030 页 utf-8 直解会乱码, p158 教训）"""
    m = re.search(r"<title[^>]*>(.*?)</title>", html or "", re.S | re.I)
    if not m:
        return ""
    raw = m.group(1)
    cs = re.search(r'charset=["\']?([\w-]+)', html[:2000], re.I)
    enc = (cs.group(1) if cs else "").lower()
    if enc in ("gbk", "gb2312", "gb18030"):
        try:
            raw = raw.encode("latin1", "ignore").decode(enc, "ignore")
        except Exception:
            pass
    return re.sub(r"\s+", " ", raw).strip()


def main():
    t = json.load(open(TREE_F, encoding="utf-8"))

    def find(node, name):
        if node.get("n") == name:
            return node
        for ch in node.get("ks", []):
            r = find(ch, name)
            if r:
                return r
        return None

    med = find(t, "医疗系统（卫生健康）")
    if not med:
        print("医疗系统未找到")
        return
    items = []
    seen = set()
    prov_names = []
    for grp in med.get("ks", []):
        if grp.get("n", "").startswith("省级卫生健康委员会"):
            prov_names = [ch.get("n", "") for ch in grp.get("ks", [])]
    prov_bases = [base(p) for p in prov_names]

    def add(node):
        u = (node.get("u") or "").strip()
        if u and u not in seen:
            seen.add(u)
            items.append({"n": node.get("n", ""), "u": u, "path": ""})
        for ch in node.get("ks") or []:
            add(ch)

    add(med)
    print(f"待检 URL: {len(items)}")

    def work(it):
        n, u = it["n"], it["u"]
        st, info = check(u)
        if st == "alive":
            tt = extract_title(info)
            nb = base(n)
            is_cdc = ("疾病预防控制中心" in n) or ("疾控中心" in n)
            strict = (not is_cdc) and len(nb) >= 2 and any(nb in pb for pb in prov_bases)
            verdict = title_match(n, tt, strict=strict)
            it["title"] = tt[:60]
            it["verdict"] = verdict
        else:
            it["title"] = ""
            it["verdict"] = st
            it["note"] = info
        return it

    results = []
    with ThreadPoolExecutor(12) as ex:
        results = list(ex.map(work, items))
    from collections import Counter
    cnt = Counter(r["verdict"] for r in results)
    for v, c in cnt.most_common():
        print(f"  {v}: {c}")
    bad = [r for r in results if r["verdict"] in ("mismatch", "dead", "waf")]
    print(f"\n问题项 {len(bad)}（mismatch/dead/waf）:")
    for r in bad:
        print(f"  [{r['verdict']}] {r['n']} | {r['u'][:55]} | {r.get('title','')[:30]} | {r.get('note','')[:40]}")
    neutral = [r for r in results if r["verdict"] == "neutral"]
    print(f"\n中性标题（JS 壳, 存疑 {len(neutral)}）:")
    for r in neutral:
        print(f"  {r['n']} | {r['u'][:55]} | title={r.get('title','')[:25]}")
    with open(OUT_F, "w", encoding="utf-8") as f:
        json.dump({"counts": dict(cnt), "results": results}, f, ensure_ascii=False, indent=1)
    print(f"\n报告: {OUT_F}")


if __name__ == "__main__":
    main()
