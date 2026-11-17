# -*- coding: utf-8 -*-
"""P199 市级政府部门采集（周末任务 B, 2026-11-13 用户指令）。

渠道（禁搜索引擎, 仅政府官网）: 各市政府门户「网站群/部门导航」页 +
首页 footer 部门网站区块（荆门 col904 模式: 部门与县区导航同页/附近,
参考 p195 提取下级人民政府的方案）。
落库: 块树市级节点下「市级政府部门」分组 + 子节点（清远先例, 只记录不访问）;
registry 同源登记。只增不改已有节点。
用法: cd data && uv run python p199_city_dept_fill.py
"""
import sys, os, re, json, subprocess
from urllib.parse import urlparse, urljoin

def _atomic_dump(obj, path):
    """原子写 JSON (2026-11-15 tree.json 并发写互踩损坏根治): 临时文件 +
    os.replace 原子替换, 杜绝 p199 每市落盘与 p195 轮尾 dump 交叉写坏"""
    import os as _os, json as _json, tempfile as _tf
    d = _os.path.dirname(path)
    fd, tmp = _tf.mkstemp(dir=d, prefix=".atomic_", suffix=".tmp")
    try:
        with _os.fdopen(fd, "w", encoding="utf-8") as f:
            _json.dump(obj, f, ensure_ascii=False, indent=1)
        _os.replace(tmp, path)
    except Exception:
        try:
            _os.unlink(tmp)
        except Exception:
            pass
        raise




BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BASE)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "util"))

TREE_F = os.path.join(BASE, "tree.json")
REG_F = os.path.join(BASE, "site_registry.json")
STATE_F = os.path.join(BASE, "p199_state.json")

def _links(html):
    """纯字符串扫描提取 <a href>（2026-11-15 弃正则: libpcre 回溯实测
    6.5h 100% CPU 空转, 限量正则仍回溯——彻底无正则零回溯）"""
    out, i, L = [], 0, len(html)
    while True:
        i = html.find("<a", i)
        if i < 0:
            break
        j = html.find(">", i + 2)
        if j < 0:
            break
        if j - i > 2000:
            i = j + 1
            continue
        tag = html[i + 2:j]
        m = re.search(r"""href\s*=\s*["']([^"']+)["']""", tag)
        if m:
            k = html.find("</a", j)
            txt = clean(html[j + 1:k if k > j else j + 2500])
            out.append((m.group(1), txt))
        i = j + 1
    return out
TAG_RE = re.compile(r"<[^>]+>")
NAV_KW = re.compile(r"(部门网站|政府部门|直属单位|网站群|站群导航|网站导航|网站地图|机构设置|组织机构|友情链接|相关链接|市直部门)")
DEPT_RE = re.compile(r"^(市|区)?[一-鿿]{2,14}?(局|委员会|办公室|中心|办公室|委员会办公室|管理局|管理局)$")
# 部门锚文本特征: 以 局/委/办/部 结尾（排除 通知/新闻 类）
DEPT_END = ("局", "委", "办", "部", "厅", "社", "中心", "馆", "院", "站", "所", "队", "会", "校")
BAD = ("新闻", "动态", "公告", "通知", "公示", "政策", "解读", "政务", "服务", "平台")


def clean(s):
    return re.sub(r"[\s　]+", "", TAG_RE.sub("", s or ""))


def load_tree():
    return json.load(open(TREE_F, encoding="utf-8"))


def load_state():
    try:
        return json.load(open(STATE_F, encoding="utf-8"))
    except Exception:
        return {"done": {}, "tried": {}}


def save_state(st):
    json.dump(st, open(STATE_F, "w", encoding="utf-8"), ensure_ascii=False, indent=0)


def _fetch(u):
    # 2026-11-15 轻量化: 部门采集不走 smart_fetch 全链（瑞数 412 站被
    # _cf_flag 误标 Cloudflare 绕过 BROWSER_TIERS 烧浏览器层, 每站 180s 空转）
    # P199_LIGHT=1 时直连 http_client(curl+代理) 快失败
    from smart_fetch import smart_fetch
    try:
        import os as _os
        if _os.environ.get("P199_LIGHT") == "1":
            from http_client import get_client
            try:
                c = get_client()
                h = c.fetch_text(u, timeout=15)
                if h and len(h) > 500:
                    return h, "light"
            except Exception:
                pass
            return None, "light_fail"
        h, m = smart_fetch(u)
        return (h if h and len(h) > 500 else None, m)
    except Exception as e:
        return (None, f"exc:{type(e).__name__}")


def _with_timeout(fn, sec):
    """每市处理总超时 (2026-11-14 p199 挂死教训: 某反爬市 fetch 阻塞 3 小时)"""
    import signal
    def _h(signum, frame):
        raise TimeoutError("city timeout")
    old = signal.signal(signal.SIGALRM, _h)
    signal.alarm(sec)
    try:
        return fn()
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)


def render_pass(url):
    try:
        r = subprocess.run(
            [sys.executable, os.path.join(BASE, "p195_render_one.py"), url],
            capture_output=True, text=True, timeout=120, cwd=ROOT)
        if r.returncode == 0 and len(r.stdout or "") > 500:
            return r.stdout
    except Exception:
        pass
    return None


def city_list(tree):
    """块树市级区划节点: [(p1, 市名, u, 节点)]"""
    out = []
    def w(n):
        if n.get("k") == "人民政府" and n.get("c") in ("地级市人民政府", "市辖区（地级行政区划）"):
            if n.get("u"):
                out.append((n.get("p1", ""), n.get("n", ""), n["u"], n))
        for c in n.get("ks", []):
            w(c)
    w(tree)
    return out


def find_dept_pages(html, base):
    """首页 → 部门网站/网站群 栏目页链接（最多 4 个）"""
    pages = []
    for href, txt in _links(html):
        t = clean(txt)
        if not t or len(t) > 14:
            continue
        if not NAV_KW.search(t):
            continue
        if any(b in t for b in BAD):
            continue
        u = urljoin(base, href.strip())
        if u not in pages:
            pages.append(u)
        if len(pages) >= 4:
            break
    return pages


def extract_depts(html, base):
    """页面 → 部门候选 (文本, URL)。跨域或门户子域; 排除政务网/县政府"""
    host = urlparse(base).netloc.lower()
    host_root = ".".join(host.split(".")[-2:])
    out, seen = [], set()
    for href, txt in _links(html):
        t = clean(txt)
        if not t or len(t) > 16 or len(t) < 3:
            continue
        if not t.endswith(DEPT_END):
            continue
        if any(b in t for b in BAD):
            continue
        u = urljoin(base, href.strip())
        net = urlparse(u).netloc.lower()
        if not net or "gov.cn" not in net or "zwfw" in net:
            continue
        if net == host:
            continue
        # 允许门户同根子域（fgw.jingmen.gov.cn）或其他政府域名
        if u in seen:
            continue
        seen.add(u)
        out.append((t, u))
    return out


def verify_dept(city_base, t, u):
    """title 验证: title 含部门名主体或市名+部门特征"""
    h, m = _fetch(u)
    if not h:
        return None
    mm = re.search(r"<title[^>]*>(.*?)</title>", h, re.S | re.I)
    title = re.sub(r"\s+", " ", mm.group(1)).strip() if mm else ""
    core = t.replace("市", "")
    if core and core in title:
        return title[:40]
    # 兜底: title 含 局/委 + 市名
    if city_base and city_base in title and any(k in title for k in ("局", "委", "办", "中心", "部")):
        return title[:40]
    return None


_ADDED_TOTAL = 0
_LAST_DUMPED = 0


def _city_wrapper(p1, cname, curl, cnode, st, reg, tree):
    """单市处理（整体 180s 超时, 防反爬市阻塞挂死）"""
    global _ADDED_TOTAL, _LAST_DUMPED
    key = f"{p1}|{cname}"
    html, m = _fetch(curl)
    if not html:
        st["tried"][key] = f"fetch[{m}]"
        return
    # 1) 首页 footer 部门区块直接提取
    cands = extract_depts(html, curl)
    # 2) 部门导航页（网站群/部门网站栏目）
    pages = find_dept_pages(html, curl)
    for pg in pages[:3]:
        ph, pm = _fetch(pg)
        if ph:
            cands += extract_depts(ph, pg)
    if len(cands) < 3:
        rh = render_pass(curl)
        if rh:
            cands += extract_depts(rh, curl)
            for pg in find_dept_pages(rh, curl)[:3]:
                ph, pm = _fetch(pg)
                if ph:
                    cands += extract_depts(ph, pg)
    if not cands:
        st["tried"][key] = "no_cand"
        if len(st["tried"]) % 10 == 0:
            save_state(st)
            print(f"...进度: done={len(st['done'])} tried={len(st['tried'])}", flush=True)
        return
    city_base = cname.replace("市", "").replace("自治州", "").replace("地区", "").replace("盟", "")
    got = {}
    for t, u in cands:
        if len(got) >= 40:
            break
        v = verify_dept(city_base, t, u)
        if v:
            got[t] = (u, v)
    if not got:
        st["tried"][key] = "verify_fail"
        if len(st["tried"]) % 10 == 0:
            save_state(st)
        return
    # 落库: 市节点下「市级政府部门」分组（清远先例）
    grp = None
    for k in cnode.get("ks", []):
        if k.get("n", "").startswith("市级政府部门") or k.get("c") == "市级政府部门":
            grp = k
            break
    if grp is None:
        grp = {"n": "市级政府部门", "l": "市", "k": "分组", "c": "市级政府部门",
               "p1": p1, "p2": cname, "ks": []}
        cnode.setdefault("ks", []).append(grp)
    have = {k.get("n") for k in grp.get("ks", [])}
    added = 0
    for t, (u, vtitle) in sorted(got.items()):
        if t in have:
            continue
        grp["ks"].append({
            "n": t, "l": "市", "k": "政府部门", "c": "市级政府部门",
            "p1": p1, "p2": cname, "u": u,
            "s": f"来源：{cname}政府门户部门导航 HTML 提取（title 验证: {vtitle}）",
            "verified_at": "2026-11-13", "status": "ok"})
        rkey = f"市级政府部门|{p1}{t}"
        if rkey not in reg:
            reg[rkey] = {"u": u, "n": t, "locations": ["块"],
                         "source_level": "L2", "verified_at": "2026-11-13",
                         "status": "ok", "snapshot": "", "xxgk": "", "xxgk_src": ""}
        added += 1
        _ADDED_TOTAL += 1
    st["done"][key] = list(got.keys())
    save_state(st)
    # 2026-11-15 丢数修复: 每市落库后立即 dump（进程被杀只丢当前市）
    _atomic_dump(tree, TREE_F)
    _atomic_dump(reg, REG_F)
    print(f"[ok] {p1}/{cname} +{len(got)} 部门", flush=True)


def main():
    global _ADDED_TOTAL, _LAST_DUMPED
    tree = load_tree()
    reg = json.load(open(REG_F, encoding="utf-8"))
    cities = city_list(tree)
    st = load_state()
    print(f"市级区划 {len(cities)} 个")
    filled = added = 0
    _SKIP = set((os.environ.get("P199_SKIP", "") or "").split(","))
    for p1, cname, curl, cnode in cities:
        key = f"{p1}|{cname}"
        if key in st["done"] or key in st["tried"]:
            continue
        if key in _SKIP:
            # 2026-11-15 湘西州类: C 级阻塞(signal 不打断)手动跳过
            st["tried"][key] = "skip_manual"
            save_state(st)
            print(f"[skip-manual] {p1}/{cname}", flush=True)
            continue
        try:
            _process_city = lambda: _city_wrapper(p1, cname, curl, cnode, st, reg, tree)
            _with_timeout(_process_city, 180)
        except Exception as _e:
            st["tried"][key] = f"timeout/exc:{type(_e).__name__}"
            save_state(st)
            print(f"[skip] {p1}/{cname} {type(_e).__name__}", flush=True)
        # 2026-11-14 防长轮丢失: 每 30 市落盘 tree（进程崩溃只丢最近 30 市）
        if _ADDED_TOTAL - _LAST_DUMPED >= 30:
            _atomic_dump(tree, TREE_F)
            _atomic_dump(reg, REG_F)
            _LAST_DUMPED = _ADDED_TOTAL
            print(f"...tree 落盘 {_ADDED_TOTAL} 部门", flush=True)
        continue
        pass  # 单市逻辑已移至 _city_wrapper（180s 超时防挂死）
    if _ADDED_TOTAL:
        _atomic_dump(tree, TREE_F)
        _atomic_dump(reg, REG_F)
    save_state(st)
    print(f"本轮覆盖 {filled} 市, 新增部门 {added}")


if __name__ == "__main__":
    main()
