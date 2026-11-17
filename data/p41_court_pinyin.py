# -*- coding: utf-8 -*-
"""P41: 法院门户拼音域名探测回填（中院/基层院）。

模式：www.{拼音}court.gov.cn（武汉/浙江/广东成立）、www.{拼音}fy.gov.cn、
     www.{拼音}zy.gov.cn（中院缩写）。
方法：333 市 × 3 模式 + 2980 县 × 2 模式 GET 探测 → 标题含「法院」+地名验证
     → 回填 tree 并列机关成员 + 规则 depts。
运行：uv run --with pypinyin python p41_court_pinyin.py
断点续跑：p41_state.json。
"""
import json
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from p40_jcy_pinyin import pinyin_of, PY_EXCEPT, STRIP_RE  # noqa: E402

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
STATE_F = "p41_state.json"

CITY_PATTERNS = ["{py}court.gov.cn", "{py}fy.gov.cn", "{py}zy.gov.cn"]
COUNTY_PATTERNS = ["{py}court.gov.cn", "{py}fy.gov.cn"]


def probe(domain):
    for scheme in ("https", "http"):
        u = f"{scheme}://www.{domain}/"
        try:
            r = subprocess.run(["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
                                "-L", "--max-time", "6", "-A", UA, u],
                               capture_output=True, text=True, timeout=10)
            code = r.stdout.strip()
            if code and code != "000":
                return True, u
        except Exception:
            pass
    return False, ""


def title_check(url, name):
    try:
        import requests
        r = requests.get(url, headers={"User-Agent": UA}, timeout=12, verify=False)
        raw = r.content[:60000]
        m = re.search(rb'charset=["\']?\s*([a-zA-Z0-9_-]+)', raw[:2000])
        enc = (m.group(1).decode("ascii", "ignore") if m else (r.encoding or "")).lower()
        txt = raw.decode("gb18030", errors="replace") if (
            "gb" in enc or "iso-8859-1" in enc or not enc) \
            else raw.decode("utf-8", errors="replace")
        if "法院" not in txt[:20000]:
            return False
        short = re.sub(r"(维吾尔|壮族|回族)?(自治州|自治县|地区|盟|市|区|县|旗)$", "", name)
        return short in txt[:20000]
    except Exception:
        return False


def main():
    tree = json.load(open("tree.json", encoding="utf-8"))
    prov_g = next(g for g in tree["ks"] if g["n"].startswith("省级"))
    targets = []
    for p in prov_g["ks"]:
        for top in p.get("ks", []):
            def walk(n):
                if n.get("l") in ("市", "县", "地级区") and n.get("k") == "人民政府" \
                        and n.get("cd"):
                    targets.append({"province": p["n"], "name": n["n"],
                                    "cd": n["cd"], "level": n["l"]})
                for k in n.get("ks", []):
                    walk(k)
            walk(top)

    state = {}
    if os.path.exists(STATE_F):
        state = json.load(open(STATE_F, encoding="utf-8"))
    done = set(state.get("done", []))
    hits = state.get("hits", [])
    todo = [t for t in targets if t["cd"] not in done]
    print(f"p41 本轮 {len(todo)} 个市县（累计命中 {len(hits)}）", flush=True)

    def work(t):
        py = pinyin_of(t["name"])
        pats = CITY_PATTERNS if t["level"] == "市" else COUNTY_PATTERNS
        for pat in pats:
            ok, url = probe(pat.format(py=py))
            if ok:
                conf = title_check(url, t["name"])
                if conf:
                    return t, url
        return t, ""

    with ThreadPoolExecutor(16) as ex:
        for i, (t, url) in enumerate(ex.map(work, todo)):
            if url:
                hits.append({"province": t["province"], "name": t["name"],
                             "cd": t["cd"], "level": t["level"], "url": url})
            done.add(t["cd"])
            if (i + 1) % 300 == 0:
                state["done"] = sorted(done)
                state["hits"] = hits
                json.dump(state, open(STATE_F, "w", encoding="utf-8"),
                          ensure_ascii=False, indent=0)
                print(f"  进度 {i+1}/{len(todo)}，命中 {len(hits)}", flush=True)

    state["done"] = sorted(done)
    state["hits"] = hits
    json.dump(state, open(STATE_F, "w", encoding="utf-8"), ensure_ascii=False, indent=0)

    # 回填
    by_cd = {h["cd"]: h["url"] for h in hits}
    rules = json.load(open("extraction_rules.json", encoding="utf-8"))
    filled = 0
    for p in prov_g["ks"]:
        for top in p.get("ks", []):
            def walk(n):
                nonlocal filled
                if n.get("l") in ("市", "县", "地级区") and n.get("cd") in by_cd:
                    par = next((g for g in n.get("ks", []) if g.get("c") == "并列机关"), None)
                    if par:
                        for m in par.get("ks", []):
                            if "法院" in m["n"]:
                                m["u"] = by_cd[n["cd"]]
                                filled += 1
                    rkeys = [n["cd"]] + [f"{n['n']}·{g['n']}" for g in n.get("ks", [])
                                          if g.get("c") == "并列机关"]
                    for rkey in rkeys:
                        if rkey in rules:
                            for d in rules[rkey]["depts"]:
                                if "法院" in d["n"]:
                                    d["u"] = by_cd[n["cd"]]
                for k in n.get("ks", []):
                    walk(k)
            walk(top)
    json.dump(tree, open("tree.json", "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    json.dump(rules, open("extraction_rules.json", "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    print(f"p41 完成：命中 {len(hits)}，回填 {filled} 个成员", flush=True)


if __name__ == "__main__":
    main()
