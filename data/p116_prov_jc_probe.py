# -*- coding: utf-8 -*-
"""P116: 逐省渲染省检察院官网，探测基层院导航（湖南 szylj 模式）。

31 省渲染 + 快照存 snapshots/jiancha/<省>/<省检察院>/home.html
（按体系设计 7.5 快照约定）。提取：
1) 市州院频道栏目链接（szylj/xx 模式）
2) 渲染后页面基层检察院链接（XX区/县人民检察院）
断点续跑 jc_jc3_state.json。
"""
import json, os, re, shutil, subprocess, sys, time
sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开")
sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开/util")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import save_snap

STATE_F = "jc_jc3_state.json"
state = json.load(open(STATE_F, encoding="utf-8")) if os.path.exists(STATE_F) \
    else {"done": [], "rows": []}
done = set(state["done"])
rows = state["rows"]

provs = json.load(open("/tmp/prov_jc_urls.json", encoding="utf-8"))
jobs = [(pn, u) for pn, u in provs.items() if u and pn not in done]

tree = json.load(open("tree.json", encoding="utf-8"))
prov_g = next(g for g in tree["ks"] if g["n"].startswith("省级"))
counties_by_prov = {}
for p in prov_g["ks"]:
    counties = {}
    for top in p.get("ks", []):
        def walk(n):
            if n.get("l") == "县" and n.get("k") == "人民政府":
                counties[n["n"]] = re.sub(r"(自治县|区|县|市)$", "", n["n"])
            for k in n.get("ks", []):
                walk(k)
        walk(top)
    counties_by_prov[p["n"]] = counties

def launch():
    shutil.rmtree("/tmp/xxgk_rs_profile", ignore_errors=True)
    from util.browser_lifecycle import PROJECT_CHROME
    return subprocess.Popen([PROJECT_CHROME, "--headless=new",
                             "--remote-debugging-port=9337",
                             "--user-data-dir=/tmp/xxgk_rs_profile",
                             "--no-sandbox", "--disable-gpu", "--no-first-run",
                             "about:blank"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def get_ws():
    import httpx
    for _ in range(30):
        try:
            r = httpx.get("http://127.0.0.1:9337/json/version", timeout=3)
            if r.status_code == 200:
                return r.json()["webSocketDebuggerUrl"]
        except Exception:
            pass
        time.sleep(1)
    raise RuntimeError("CDP 未就绪")

print(f"待渲染: {len(jobs)} 省", flush=True)
proc = launch()
try:
    from DrissionPage import ChromiumPage
    page = ChromiumPage(addr_or_opts=get_ws())
    for i, (pn, u) in enumerate(jobs):
        try:
            page.get(u)
            time.sleep(8)
            html = page.html
            save_snap("jiancha", pn, f"{pn}检察院", "home", html)
            counties = counties_by_prov.get(pn, {})
            # 1) szylj 模式频道链接
            channels = set()
            for uu in re.findall(r'href="([^"]+)"', html):
                if re.search(r'(szylj|shizhouyuan|jcydf|dfjcy)/[a-z]{1,4}/?', uu, re.I):
                    channels.add(uu)
            # 2) 基层院链接
            hits = {}
            for uu, txt in re.findall(
                    r'<a[^>]+href="([^"]+)"[^>]*>\s*([^<]{3,24}?)\s*</a>', html):
                t2 = txt.strip()
                if re.search(r'人民检察院$', t2) and uu.startswith("http"):
                    core = re.sub(r'人民检察院$', '', t2)
                    core_b = re.sub(r'(自治县|区|县|市)$', '', core)
                    for cn, base in counties.items():
                        if core == cn or core_b == base or core == base:
                            hits[cn] = uu
                            break
            rows.append({"province": pn, "channels": sorted(channels),
                         "hits": hits})
            done.add(pn)
            state["done"] = sorted(done)
            state["rows"] = rows
            json.dump(state, open(STATE_F, "w", encoding="utf-8"),
                      ensure_ascii=False, indent=0)
            print(f"{pn}: 频道 {len(channels)} 个，基层命中 {len(hits)}", flush=True)
        except Exception as e:
            print(f"{pn}: 失败 {str(e)[:40]}", flush=True)
finally:
    subprocess.run(["pkill", "-9", "-f", "remote-debugging-port=9337"])
    time.sleep(2)

with open("jc_jc3.jsonl", "w", encoding="utf-8") as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
print(f"p116 完成: {len(rows)} 省，done {len(done)}")
