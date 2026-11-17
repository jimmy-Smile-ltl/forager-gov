# -*- coding: utf-8 -*-
"""P200 功能区官网补全（2026-11-16 用户指令: 85 个功能区名字有但无 URL,
官网理应存在——排查市门户「园区/开发区」区块提取逻辑）。

独立实现（不 import p195）: 枚举功能区缺口 → 市门户提取（园区关键词
窗口+全页）→ 基底名匹配（锚文本常省市名前缀, 如「火炬高技术产业开发
区」vs 节点「威海火炬…」）→ title 验证 → 落库。"""
import sys, os, re, json
from urllib.parse import urlparse, urljoin

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BASE)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "util"))
sys.path.insert(0, BASE)
from site_contract import upsert_registry
TREE_F = os.path.join(BASE, "tree.json")
REG_F = os.path.join(BASE, "site_registry.json")
STATE_F = os.path.join(BASE, "p200_state.json")

FUNC_KW = ('开发区','高新区','经开区','园区','示范区','新区','试验区','保税区',
           '功能区','管理区','新城','合作区','经济区','化工园区','产业园','工业区','物流','风景','食品区')
NAV_KW = re.compile(r"(园区|开发区|经济区|管理区|功能区|示范区|新区|区县|县区|网站导航|网站地图|友情链接|相关链接|网站群|站群)")
SUF_STRIP = ("高新技术产业开发区","经济技术开发区","经济开发区","工业园区","产业园","产业园区","示范区","管理区","合作区","新区","新城","功能区","食品区","风景名胜区","工业区")
TAG_RE = re.compile(r"<[^>]+>")


def _links(html):
    out, i, L = [], 0, len(html)
    while True:
        i = html.find("<a", i)
        if i < 0: break
        j = html.find(">", i + 2)
        if j < 0: break
        if j - i > 2000:
            i = j + 1; continue
        tag = html[i + 2:j]
        m = re.search(r"""href\s*=\s*["']([^"']+)["']""", tag)
        if m:
            k = html.find("</a", j)
            txt = re.sub(r"[\s　]+", "", TAG_RE.sub("", html[j + 1:k if k > j else j + 2500]))
            out.append((m.group(1), txt))
        i = j + 1
    return out


def clean(t):
    return re.sub(r"[\s　]+", "", TAG_RE.sub("", t or ""))


def base(nm):
    t = nm or ""
    for _ in range(8):
        t0 = t
        t = re.sub(r"(自治州|自治县|自治旗|地区|盟|市|县|区|旗|管委会|管理委员会)$", "", t)
        for s in SUF_STRIP:
            if t.endswith(s):
                t = t[:-len(s)]
                break
        if t == t0:
            break
    return t


def _fetch(u):
    from smart_fetch import smart_fetch
    try:
        h, m = smart_fetch(u)
        return (h if h and len(h) > 500 else None, m)
    except Exception as e:
        return (None, f"exc:{type(e).__name__}")


def load_state():
    try:
        return json.load(open(STATE_F, encoding="utf-8"))
    except Exception:
        return {"done": {}, "tried": {}}


def save_state(st):
    json.dump(st, open(STATE_F, "w", encoding="utf-8"), ensure_ascii=False, indent=0)


def main():
    tree = json.load(open(TREE_F, encoding="utf-8"))
    portals = {}
    funcs = []

    def walk(n):
        if n.get("k") == "人民政府" and n.get("c") in ("地级市人民政府", "市辖区（地级行政区划）") and n.get("u"):
            portals[(n.get("p1", ""), n.get("n", ""))] = n["u"]
        if n.get("k") == "人民政府" and n.get("c") == "县级人民政府" and not n.get("u"):
            nm = n.get("n", "")
            if any(k in nm for k in FUNC_KW):
                funcs.append((n.get("p1", ""), n.get("p2", ""), nm, n))
        for c in n.get("ks", []):
            walk(c)
    walk(tree)
    st = load_state()
    reg = json.load(open(REG_F, encoding="utf-8"))
    # 防错配: 同 URL 已用于其他节点则不再匹配（威海临港误配 eweihai 教训）
    used_urls = {u for u in st.get("done", {}).values()}
    print(f"功能区缺口 {len(funcs)} | 市门户 {len(portals)}")
    filled = 0
    for p1, p2, nm, cnode in funcs:
        key = f"{p1}|{p2}|{nm}"
        if key in st["done"] or key in st["tried"]:
            continue
        pu = portals.get((p1, p2))
        if not pu:
            st["tried"][key] = "no_portal"
            continue
        html, m = _fetch(pu)
        if not html:
            st["tried"][key] = f"fetch[{m}]"
            if len(st["tried"]) % 10 == 0:
                save_state(st)
            continue
        nb = base(nm)
        pages = []
        for href, txt in _links(html):
            t = txt.strip()
            if t and len(t) <= 12 and NAV_KW.search(t):
                u2 = urljoin(pu, href.strip())
                if u2 != pu and u2 not in pages:
                    pages.append(u2)
                if len(pages) >= 4:
                    break
        cand = None
        for href, txt in _links(html):
            t = txt.strip()
            if not t or len(t) > 22 or len(t) < 3:
                continue
            if not any(k in t for k in ("开发", "园区", "示范", "管理区", "新区", "经开", "高新", "合作", "新城", "保税", "物流", "工业")):
                continue
            u = urljoin(pu, href.strip())
            net = urlparse(u).netloc.lower()
            if not net or "gov.cn" not in net or "zwfw" in net or net == urlparse(pu).netloc.lower():
                continue
            cb = base(t)
            if nb and cb and (nb == cb or nb.endswith(cb) or cb.endswith(nb)):
                if u in used_urls:
                    continue
                cand = (t, u)
                break
        if not cand:
            # 子页 BFS: 网站地图/园区导航页
            for pg in pages[:3]:
                ph, pm = _fetch(pg)
                if not ph:
                    continue
                for href, txt in _links(ph):
                    t2 = txt.strip()
                    if not t2 or len(t2) > 22 or len(t2) < 3:
                        continue
                    if not any(k in t2 for k in ("开发", "园区", "示范", "管理区", "新区", "经开", "高新", "合作", "新城", "保税", "物流", "工业")):
                        continue
                    u2 = urljoin(pg, href.strip())
                    net2 = urlparse(u2).netloc.lower()
                    if not net2 or "gov.cn" not in net2 or "zwfw" in net2 or net2 == urlparse(pu).netloc.lower():
                        continue
                    cb2 = base(t2)
                    if nb and cb2 and (nb == cb2 or nb.endswith(cb2) or cb2.endswith(nb)):
                        if u2 in used_urls:
                            continue
                        cand = (t2, u2)
                        break
                if cand:
                    break
        if not cand:
            st["tried"][key] = "no_cand"
            if len(st["tried"]) % 10 == 0:
                save_state(st)
            continue
        t, u = cand
        # title 验证
        hh, mm = _fetch(u)
        ok = False
        if hh:
            mtt = re.search(r"<title[^>]*>(.*?)</title>", hh, re.S | re.I)
            title = re.sub(r"\s+", " ", mtt.group(1)).strip() if mtt else ""
            core = base(t) or nb
            if core and core in title:
                ok = True
            elif nb and nb in title:
                ok = True
        if not ok:
            st["tried"][key] = "verify_fail"
            continue
        cnode["u"] = u
        src = f"来源：{p2}政府门户园区导航 HTML 提取（title 验证）"
        cnode["s"] = src
        upsert_registry(reg, f"县级人民政府|{nm}", u, name=nm,
                        source_level="L2", source=src, locations=["块"])
        st["done"][key] = u
        used_urls.add(u)
        filled += 1
        print(f"[ok] {p1}/{p2}/{nm} -> {u}")
        save_state(st)
    if filled:
        json.dump(tree, open(TREE_F, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        json.dump(reg, open(REG_F, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    save_state(st)
    print(f"本轮落库 {filled}")


if __name__ == "__main__":
    main()
