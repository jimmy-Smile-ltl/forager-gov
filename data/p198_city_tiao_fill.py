# -*- coding: utf-8 -*-
"""P198 五系统市级补全循环（周末任务 A 核心脚本, 2026-11-13 用户指令）。

一级一级往下走: 省级已全覆盖(2026-11-13 对齐), 本脚本补市级人大/政协/检察/纪委。
渠道（禁搜索引擎红线, 仅官方页面 HTML）:
  1. 市政府门户首页/渲染 → 「政协」「人大」「纪委监委」导航区块
     （广州 gzzx 模式: 市政府门户有本级人大/政协链接, p178 实证）
  2. 省政协/省人大官网市级导航（三轮已穷尽的省跳过, 缺口省重试）
落库: 条树市级节点 u 回填 + 块树市级并列机关回填 + registry 同源登记。
单写者: 与 p195 loop 错峰运行（p195 轮内 2 小时写一次树, 本脚本轮间启动）。
用法: cd data && uv run python p198_city_tiao_fill.py
"""
import sys, os, re, json, time, subprocess
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
sys.path.insert(0, BASE)
from site_contract import five_key, five_name, parse_five, upsert_registry

TREE_F = os.path.join(BASE, "tree.json")
REG_F = os.path.join(BASE, "site_registry.json")
STATE_F = os.path.join(BASE, "p198_state.json")

# 类型 → 门户导航关键词（锚文本匹配窗）
TYPE_KW = {
    "zx": ("政协",),
    "rd": ("人大",),
    "jw": ("纪委监委", "纪委"),
    "jcy": ("检察院", "检察"),
}
# title 验证关键词（市名 + 后缀, 与 smart_fetch 拿到的 title 匹配）
SUF = {
    "zx": ("政协", "政治协商"),
    "rd": ("人大", "人民代表"),
    "jw": ("纪委监委", "纪委", "监察"),
    "jcy": ("检察院", "检察"),
}
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


def find_root(n):
    return n if n.get("n") == "条（垂直管理系统）" else next(
        (r for c in n.get("ks", []) if (r := find_root(c))), None)


def city_portal_map(tree):
    """块树: (p1,p2) -> 市级政府门户 u（c=地级市人民政府 或 市辖区）"""
    m = {}
    def w(n):
        if n.get("k") == "人民政府" and n.get("c") in ("地级市人民政府", "市辖区（地级行政区划）"):
            if n.get("u"):
                m[(n.get("p1", ""), n.get("n", ""))] = n["u"]
        for c in n.get("ks", []):
            w(c)
    w(tree)
    return m


def enumerate_gaps(tree, root):
    """条树五系统市级缺口: [(type, p1, 市名, 条树节点)]"""
    out = []
    for sys_ in root.get("ks", []):
        nm = sys_.get("n", "")
        ty = None
        if "人大" in nm and "政协" not in nm: ty = "rd"
        elif "政协" in nm: ty = "zx"
        elif "检察" in nm: ty = "jcy"
        elif "纪委" in nm: ty = "jw"
        if not ty:
            continue
        for lvl in sys_.get("ks", []):
            if "省级" not in lvl.get("n", ""):
                continue
            for p in lvl.get("ks", []):
                p1 = p.get("n", "").replace("人大", "").replace("政协", "").replace("纪委监委", "")
                for c in p.get("ks", []):
                    if not c.get("u"):
                        out.append((ty, p1, c.get("n", ""), c))
    return out


def _fetch(u):
    from smart_fetch import smart_fetch
    try:
        h, m = smart_fetch(u)
        return (h if h and len(h) > 500 else None, m)
    except Exception as e:
        return (None, f"exc:{type(e).__name__}")


def find_candidates(html, base, ty):
    """门户 HTML → 政协/人大/纪委/检察 候选链接（跨域, 排除门户自身与政务网）。

    双通道: ①NAV_KW 标题窗口（政协/人大/纪委监委/网站导航/友情链接附近 8KB,
    锚文本放宽为裸地名 2-8 字）②全页锚文本含系统关键词。"""
    cands = []
    host = urlparse(base).netloc.lower()
    NAV_KW = re.compile(r"(人大|政协|纪委监委|纪检|监察|检察院|网站导航|网站地图|友情链接|相关链接|地方网站|政府网站|站群)")
    BARE_RE = re.compile(r"^[一-鿿]{2,8}$")
    seen = set()

    def push(t, u):
        net = urlparse(u).netloc.lower()
        if not net or "gov.cn" not in net or net == host or "zwfw" in net:
            return
        if u not in seen:
            seen.add(u)
            cands.append((t, u))

    for m in NAV_KW.finditer(html):
        win = html[m.start(): m.start() + 8000]
        for href, txt in _links(win):
            t = clean(txt)
            if not t or len(t) > 20:
                continue
            if any(k in t for k in TYPE_KW[ty]) or BARE_RE.match(t):
                push(t, urljoin(base, href.strip()))
    for href, txt in _links(html):
        t = clean(txt)
        if not t or len(t) > 20:
            continue
        if any(k in t for k in TYPE_KW[ty]):
            push(t, urljoin(base, href.strip()))
    return cands


def render_pass(url):
    """渲染门户拿 DOM（隐藏层/tab 形态, 如大连 divTop03）——子进程隔离"""
    try:
        r = subprocess.run(
            [sys.executable, os.path.join(BASE, "p195_render_one.py"), url],
            capture_output=True, text=True, timeout=120, cwd=ROOT)
        if r.returncode == 0 and len(r.stdout or "") > 500:
            return r.stdout
    except Exception:
        pass
    return None


def verify_city(ty, city_base, u):
    """title 验证: title 须含 市名基底 + 系统关键词"""
    h, m = _fetch(u)
    if not h:
        return None
    mm = re.search(r"<title[^>]*>(.*?)</title>", h, re.S | re.I)
    title = re.sub(r"\s+", " ", mm.group(1)).strip() if mm else ""
    if city_base not in title:
        return None
    if not any(k in title for k in SUF[ty]):
        return None
    return title[:40]


def main():
    tree = load_tree()
    reg = json.load(open(REG_F, encoding="utf-8"))
    root = find_root(tree)
    portals = city_portal_map(tree)
    gaps = enumerate_gaps(tree, root)
    st = load_state()
    # 2026-11-14: fetch 类失败每轮重试（代理撞窗口/站点恢复）, 确认无渠道
    # 的 no_cand/verify_fail 保留不重试
    _retry = [k for k, v in st.get("tried", {}).items()
              if str(v).startswith("fetch") or "timeout" in str(v) or "exc" in str(v)]
    for _k in _retry:
        del st["tried"][_k]
    if _retry:
        print(f"重试 {len(_retry)} 个 fetch 失败缺口")
    # 重放 state done: p195 loop 的整树 dump 可能覆盖本脚本已落库的 u, 每轮
    # 开始时把 done 记录重写回树（最终一致: state 持久 + 幂等重放）
    replay = 0
    for key, u in st.get("done", {}).items():
        ty, p1, cname = key.split("|", 2)
        for sys_ in root.get("ks", []):
            nm = sys_.get("n", "")
            tname = {"rd": "人大", "zx": "政协", "jcy": "检察", "jw": "纪委"}.get(ty)
            if not tname or tname not in nm or ("人大" in nm and "政协" in nm and ty != "rd"):
                continue
            for lvl in sys_.get("ks", []):
                if "省级" not in lvl.get("n", ""):
                    continue
                for p in lvl.get("ks", []):
                    if p.get("n", "").replace("人大", "").replace("政协", "").replace("纪委监委", "") != p1:
                        continue
                    for c in p.get("ks", []):
                        if c.get("n") == cname and c.get("u") != u:
                            c["u"] = u
                            c["s"] = c.get("s") or "来源：p198 市级补全（重放）"
                            replay += 1
                            pf = parse_five(cname)
                            if pf:
                                upsert_registry(reg, five_key(*pf), u,
                                                name=five_name(*pf),
                                                source_level="L2",
                                                source=c["s"], locations=["条"])
    if replay:
        print(f"重放恢复 {replay} 处")
    print(f"市级缺口 {len(gaps)}, 市门户映射 {len(portals)}")
    filled = 0
    for ty, p1, cname, cnode in gaps:
        key = f"{ty}|{p1}|{cname}"
        if key in st["done"] or key in st["tried"]:
            continue
        # 市名基底（剥「政协」等后缀）
        base = cname.replace("政协", "").replace("人大", "")
        if ty == "jw":
            base = base.replace("纪委", "").replace("监委", "").replace("监察", "")
        if ty == "jcy":
            base = base.replace("检察院", "").replace("检察", "")
        # 市门户 key: (p1, 市名)——市名可能是「XX市」或「XX自治州/盟/地区」
        pk = None
        for (pp, pn), u in portals.items():
            if pp == p1 and (base.startswith(pn) or pn.startswith(base)):
                pk = (pp, pn)
                break
        if not pk:
            st["tried"][key] = "no_portal"
            if len(st["tried"]) % 20 == 0:
                save_state(st)
            continue
        html, m = _fetch(portals[pk])
        if not html:
            st["tried"][key] = f"fetch[{m}]"
            if len(st["tried"]) % 20 == 0:
                save_state(st)
            continue
        cands = find_candidates(html, portals[pk], ty)
        if not cands and os.environ.get("P198_RENDER") == "1":
            # 渲染通道: 隐藏层/tab 形态（大连 divTop03 类）——限速开关,
            # 首轮默认关闭(静态+导航页先跑完全量), 后续轮 P198_RENDER=1 深挖
            rh = render_pass(portals[pk])
            if rh:
                cands = find_candidates(rh, portals[pk], ty)
        if not cands:
            st["tried"][key] = "no_cand"
            if len(st["tried"]) % 20 == 0:
                save_state(st)
            continue
        got = None
        for t, u in cands[:6]:
            v = verify_city(ty, base, u)
            if v:
                got = (u, v)
                break
        if not got:
            st["tried"][key] = "verify_fail"
            if len(st["tried"]) % 20 == 0:
                save_state(st)
                print(f"...进度: done={len(st['done'])} tried={len(st['tried'])}")
            continue
        u, vtitle = got
        cnode["u"] = u
        src = f"来源：{base}政府门户导航 HTML 提取（title 验证: {vtitle}）"
        cnode["s"] = src
        st["done"][key] = u
        filled += 1
        pf = parse_five(cname)
        if pf:
            upsert_registry(reg, five_key(*pf), u, name=five_name(*pf),
                            source_level="L2", source=src, locations=["条"])
        print(f"[ok] {ty} {p1}/{cname} -> {u}")
    if filled:
        _atomic_dump(tree, TREE_F)
    if filled or replay:
        _atomic_dump(reg, REG_F)
    save_state(st)
    print(f"本轮落库 {filled}")


if __name__ == "__main__":
    main()
