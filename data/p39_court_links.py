# -*- coding: utf-8 -*-
"""P39: 县级法院/检察院门户补全（用户终止条件核心）。

阶段A：SERP 补齐 32 省级单位的省高院（court）与省检察院（jcy）门户 URL。
阶段B：smart_fetch 省级法检门户首页 → 提取辖区 中院/基层院 链接
      （链接文本与 tree 市县名做后缀匹配）→ 回填市/县 并列机关成员 u + 规则 depts。
断点续跑：p39_state.json；结果：court_links.jsonl。
"""
import json
import os
import re
import sys
import time
from urllib.parse import urlparse

sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开")
sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开/util")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from p35_baidu_quntuan import bd_search, head_ok  # noqa: E402

# 法院/检察院域名为 .gov.cn（p35 的 DOMAIN_RE 不含 gov.cn，需独立定义）
COURT_DOMAIN_RE = re.compile(r"[a-z0-9][a-z0-9-]*\.(?:gov\.cn|org\.cn|org|net)\b")
# 独立黑名单：只滤页面噪声与中央法检（不含泛 gov.cn 杀招）
COURT_NOISE = re.compile(r"(baidu|zhihu|sogou|sina|sohu|qq\.|163\.|126\.net|weibo|"
                         r"w3\.org|schema\.org|xmlns|openid|google|microsoft|"
                         r"baike|wikipedia|people\.|news\.cn|xinhuanet|cctv|"
                         r"(^|\.)court\.gov\.cn|(^|\.)spp\.gov\.cn|(^|\.)12309|"
                         r"npc\.gov|cppcc|^(www\.)?gov\.cn$|gov\.cn/guoqing)")

STATE_F = "p39_state.json"
OUT_F = "court_links.jsonl"
UA_STR = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")

# 省级法检门户搜索模板
COURT_QUERY = "{full}高级人民法院官网"
JCY_QUERY = "{full}人民检察院官网"


def short_of(full):
    for suf in ("维吾尔自治区", "壮族自治区", "回族自治区", "自治区", "省", "市"):
        if full.endswith(suf):
            return full[: -len(suf)]
    return full


def sf(url):
    try:
        from util.smart_fetch import smart_fetch
        html, _ = smart_fetch(url, timeout=20)
        return html
    except Exception:
        return None


def load_tree():
    tree = json.load(open("tree.json", encoding="utf-8"))
    prov_g = next(g for g in tree["ks"] if g["n"].startswith("省级"))
    return tree, prov_g


def phase_a():
    """补齐省高院/省检察院门户 URL（SERP + 验证）。"""
    tree, prov_g = load_tree()
    state = {}
    if os.path.exists(STATE_F):
        state = json.load(open(STATE_F, encoding="utf-8"))
    todo = []
    for p in prov_g["ks"]:
        par = next((k for k in p.get("ks", []) if k.get("c") == "并列机关"), None)
        if not par:
            continue
        for m in par.get("ks", []):
            if "法院" in m["n"] and not m.get("u"):
                todo.append((p["n"], "court", COURT_QUERY.format(full=p["n"])))
            if "检察院" in m["n"] and not m.get("u"):
                todo.append((p["n"], "jcy", JCY_QUERY.format(full=p["n"])))
    print(f"阶段A：需补 {len(todo)} 个省级法检门户", flush=True)
    for pname, kind, q in todo:
        html = bd_search(q)
        found = ""
        if html:
            for d in dict.fromkeys(COURT_DOMAIN_RE.findall(html)):
                if COURT_NOISE.search(d):
                    continue
                url = head_ok(d)
                if not url:
                    continue
                # 标题校验：含 法院/检察/司法 且（含省名 或 域名带 court/fy/jcy）
                try:
                    import requests as _rq
                    rr = _rq.get(url, headers={"User-Agent": UA_STR}, timeout=12,
                                 verify=False)
                    raw = rr.content
                    m = re.search(rb'charset=["\']?\s*([a-zA-Z0-9_-]+)', raw[:2000])
                    enc = m.group(1).decode("ascii", "ignore") if m else \
                        (rr.encoding or "")
                    if "gb" in enc.lower() or "iso-8859-1" in enc.lower() or not enc:
                        txt = raw.decode("gb18030", errors="replace")
                    else:
                        txt = raw.decode("utf-8", errors="replace")
                    tm = re.search(r"<title[^>]*>(.*?)</title>", txt, re.S | re.I)
                    title = tm.group(1) if tm else ""
                    if not re.search(r"法院|检察|司法", title):
                        continue
                    short = re.sub(r"(维吾尔|壮族|回族)?自治区$|省$|市$", "", pname)
                    if not (short in title or
                            re.search(r"court|fy|jcy|justice", url)):
                        continue
                except Exception:
                    continue
                found = url
                break
        if found:
            for p in prov_g["ks"]:
                if p["n"] != pname:
                    continue
                par = next(k for k in p.get("ks", []) if k.get("c") == "并列机关")
                for m in par.get("ks", []):
                    if (kind == "court" and "法院" in m["n"]) or \
                       (kind == "jcy" and "检察院" in m["n"]):
                        m["u"] = found
            state.setdefault("phase_a", {})[f"{pname}|{kind}"] = found
            print(f"  {pname} {kind} -> {found}", flush=True)
        else:
            state.setdefault("phase_a", {})[f"{pname}|{kind}"] = ""
            print(f"  {pname} {kind} -> 未找到", flush=True)
        time.sleep(2.5)
    json.dump(tree, open("tree.json", "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    json.dump(state, open(STATE_F, "w", encoding="utf-8"),
              ensure_ascii=False, indent=0)


def phase_b(limit=100000):
    """省级法检门户首页 → 基层院链接提取回填。"""
    tree, prov_g = load_tree()
    state = json.load(open(STATE_F, encoding="utf-8")) if os.path.exists(STATE_F) else {}
    done = set(state.get("phase_b_done", []))
    rows = state.get("court_rows", [])
    seen = {(r["province"], r["name"], r["kind"]) for r in rows}

    # 省市县名索引（长名优先做后缀匹配）
    for p in prov_g["ks"]:
        par = next((k for k in p.get("ks", []) if k.get("c") == "并列机关"), None)
        if not par:
            continue
        fy = next((m for m in par.get("ks", []) if "法院" in m["n"]), None)
        jc = next((m for m in par.get("ks", []) if "检察院" in m["n"]), None)
        if not (fy and fy.get("u")):
            continue
        key = p["n"]
        if key in done:
            continue
        names = [(p["n"], "省", p.get("cd", ""))]   # 高院自身
        def walk(n):
            if n.get("l") in ("市", "县", "地级区") and n.get("k") == "人民政府":
                names.append((n["n"], n.get("l", ""), n.get("cd", "")))
            for k in n.get("ks", []):
                walk(k)
        walk(p)
        portals = [("court", fy["u"])]
        if jc and jc.get("u"):
            portals.append(("jcy", jc["u"]))
        for kind, portal in portals:
            html = sf(portal)
            if not html:
                continue
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "lxml")
            for a in soup.find_all("a"):
                text = re.sub(r"\s+", "", (a.get("title") or a.get_text(" ", strip=True)).strip())
                href = a.get("href") or ""
                if not text or not href.startswith(("http://", "https://")):
                    continue
                if ("法院" not in text and "检察院" not in text and "检察" not in text) \
                        or len(text) > 24:
                    continue
                if not urlparse(href).netloc.lower().endswith(".gov.cn"):
                    continue
                # 去尾取核：屏山县人民法院→屏山县；成都市中级人民法院→成都市
                core = re.sub(r"(高级|中级|基层)?人民法院.*$|(高级|中级|基层)?人民检察院.*$",
                              "", text)
                if not core:
                    continue
                hits = [t for t in names if t[1] in ("市", "县", "地级区") and core == t[0]]
                if not hits:
                    hits = [t for t in names if t[1] in ("市", "县", "地级区")
                            and core.endswith(t[0]) and len(core) - len(t[0]) <= 2]
                if not hits:
                    continue
                n, lv, cd = max(hits, key=lambda t: len(t[0]))
                if (p["n"], n, kind) in seen:
                    continue
                seen.add((p["n"], n, kind))
                rows.append({"province": p["n"], "level": lv, "name": n,
                             "cd": cd, "kind": kind, "org_name": text, "url": href})
        done.add(key)
        state["phase_b_done"] = sorted(done)
        state["court_rows"] = rows
        json.dump(state, open(STATE_F, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=0)
        print(f"  {key}: 累计 {len(rows)} 条法检链接", flush=True)

    with open(OUT_F, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    # 回填 tree + rules
    by_key = {}
    for r in rows:
        k = (r["province"], r["cd"] if r["level"] in ("县", "地级区") else r["name"])
        by_key.setdefault(k, {})[r["kind"]] = r["url"]

    rules = json.load(open("extraction_rules.json", encoding="utf-8"))
    filled = 0
    for p in prov_g["ks"]:
        def walk(n):
            nonlocal filled
            if n.get("k") == "人民政府" and n.get("l") in ("市", "县", "地级区"):
                k = (p["n"], n.get("cd", "") if n.get("l") in ("县", "地级区") else n["n"])
                if k in by_key:
                    par = next((g for g in n.get("ks", []) if g.get("c") == "并列机关"), None)
                    if par:
                        for m in par.get("ks", []):
                            kind = "court" if "法院" in m["n"] else ("jcy" if "检察院" in m["n"] else "")
                            if kind and kind in by_key[k]:
                                m["u"] = by_key[k][kind]
                                filled += 1
                    # 规则 depts 同步（县键=cd；市键=市名·并列机关组名）
                    rkeys = []
                    if n.get("l") in ("县", "地级区") and n.get("cd"):
                        rkeys.append(n["cd"])
                    rkeys += [f"{n['n']}·{g['n']}" for g in n.get("ks", [])
                              if g.get("c") == "并列机关"]
                    for rkey in rkeys:
                        if rkey in rules:
                            for d in rules[rkey]["depts"]:
                                kind = "court" if "法院" in d["n"] else ("jcy" if "检察院" in d["n"] else "")
                                if kind and kind in by_key[k]:
                                    d["u"] = by_key[k][kind]
            for k in n.get("ks", []):
                walk(k)
        walk(p)
    json.dump(tree, open("tree.json", "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    json.dump(rules, open("extraction_rules.json", "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    print(f"阶段B完成：{len(rows)} 条链接，回填 {filled} 个成员")


if __name__ == "__main__":
    if "--b" in sys.argv:
        phase_b()
    else:
        phase_a()
        phase_b()
