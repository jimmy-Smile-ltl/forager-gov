# -*- coding: utf-8 -*-
"""P175h: 信息公开专栏渲染轮——JS 壳站点（curl 拿不到导航）用
CloakBrowser Chromium 渲染 DOM 提取。断点续跑。"""
import json, os, re, sys, time
sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开")
sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开/util")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from util.browser_lifecycle import PROJECT_CHROME
from DrissionPage import ChromiumPage, ChromiumOptions

STATE_F = "xxgk_render_state.json"
state = json.load(open(STATE_F, encoding="utf-8")) if os.path.exists(STATE_F) \
    else {"done": [], "found": {}}
done = set(state["done"]); found = state["found"]

tree = json.load(open("tree.json", encoding="utf-8"))
jobs = []
def walk(n):
    if n.get("u") and not n.get("ks") and not n.get("x"):
        jobs.append({"n": n["n"], "u": n["u"]})
    for k in n.get("ks", []): walk(k)
walk(tree)
# 按 u 去重，优先厅局：先跑厅局组
prov = next(g for g in tree["ks"] if g["n"].startswith("省级"))
dept_us = set()
for p in prov["ks"]:
    for top in p.get("ks", []):
        if top.get("k") == "分组" and ("部门" in top.get("n") or "厅" in top.get("n")):
            for x in top.get("ks", []):
                if x.get("u"): dept_us.add(x["u"])
seen = set()
jobs_dedup = []
for j in jobs:
    if j["u"] in seen or j["u"] in done or j["u"] in found: continue
    seen.add(j["u"])
    jobs_dedup.append(j)
jobs_dept = [j for j in jobs_dedup if j["u"] in dept_us]
jobs_rest = [j for j in jobs_dedup if j["u"] not in dept_us]
print(f"渲染轮: 厅局 {len(jobs_dept)} + 其他 {len(jobs_rest)}", flush=True)

KW = re.compile(r"(政府信息公开|政务公开|信息公开|司法公开|检务公开|法定主动公开|公开指南|xxgk|zfxxgk)")

co = ChromiumOptions()
co.set_browser_path(PROJECT_CHROME)
co.set_user_data_path("/tmp/xxgk_render_prof")
co.auto_port()
page = ChromiumPage(co)

def probe(j):
    try:
        page.get(j["u"], timeout=15, retry=0)
        time.sleep(3.5)
        t = page.html
        best = None
        for uu, txt in re.findall(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>\s*([^<]{0,30}?)\s*</a>', t):
            if KW.search(txt):
                if uu.startswith("http"):
                    best = uu; break
                elif uu.startswith("/") or uu.startswith("./"):
                    m = re.match(r"https?://[^/]+", j["u"])
                    base = m.group(0) if m else j["u"].rstrip("/")
                    best = (base + uu) if uu.startswith("/") else \
                        (j["u"].rsplit("/", 1)[0] + "/" + uu[2:]) if "./" in uu else uu
                    break
        return j, best
    except Exception as e:
        return j, None

hit = 0
for i, j in enumerate(jobs_dept):
    j, best = probe(j)
    done.add(j["u"])
    if best:
        found[j["u"]] = {"n": j["n"], "x": best}
        hit += 1
    if (i + 1) % 30 == 0:
        state["done"] = sorted(done); state["found"] = found
        json.dump(state, open(STATE_F, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
        print(f"{i+1}/{len(jobs_dept)} 命中{hit}", flush=True)
state["done"] = sorted(done); state["found"] = found
json.dump(state, open(STATE_F, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
print(f"p175h 完成: 命中 {hit}", flush=True)
