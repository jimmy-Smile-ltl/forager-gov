# -*- coding: utf-8 -*-
"""P154: 17 缺口省省检察院官网 CDP 渲染提取市级院导航。"""
import json, os, re, shutil, subprocess, sys, time
sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开")
sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开/util")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import save_snap

need = json.load(open("/tmp/jc_prov_need.json", encoding="utf-8"))
jobs = [(pn, u) for pn, u in need.items() if u]

def launch():
    shutil.rmtree("/tmp/xxgk_rs_profile", ignore_errors=True)
    from util.browser_lifecycle import PROJECT_CHROME
    return subprocess.Popen([PROJECT_CHROME, "--headless=new",
                             "--remote-debugging-port=9344",
                             "--user-data-dir=/tmp/xxgk_rs_profile",
                             "--no-sandbox", "--disable-gpu", "--no-first-run",
                             "about:blank"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def get_ws():
    import httpx
    for _ in range(30):
        try:
            r = httpx.get("http://127.0.0.1:9344/json/version", timeout=3)
            if r.status_code == 200:
                return r.json()["webSocketDebuggerUrl"]
        except Exception:
            pass
        time.sleep(1)
    raise RuntimeError("CDP 未就绪")

proc = launch()
results = {}
try:
    from DrissionPage import ChromiumPage
    page = ChromiumPage(addr_or_opts=get_ws())
    for pn, u in jobs:
        try:
            page.get(u)
            time.sleep(8)
            html = page.html
            save_snap("jiancha", pn, f"{pn}检察院", "home_shi", html)
            hits = {}
            for uu, txt in re.findall(
                    r'<a[^>]+href="([^"]+)"[^>]*>\s*([^<]{3,30}?)\s*</a>', html):
                t2 = txt.strip()
                if re.search(r'(人民检察院|检察)', t2) and uu.startswith("http") \
                        and "jcy" in uu:
                    m = re.match(r'^(.+?)(?:市|自治州|盟|地区)?(?:人民检察院|检察院)$', t2)
                    if m:
                        hits.setdefault(m.group(1), uu)
            results[pn] = hits
            print(f"{pn}: {len(hits)} 市级链接", flush=True)
            for k, v in list(hits.items())[:14]:
                print(f"   {k} -> {v[:60]}", flush=True)
        except Exception as e:
            print(f"{pn}: 失败 {str(e)[:40]}", flush=True)
            results[pn] = {}
finally:
    subprocess.run(["pkill", "-9", "-f", "remote-debugging-port=9344"])
    time.sleep(2)

json.dump(results, open("/tmp/jc_prov_hits2.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=0)
print(f"p154 完成: {sum(len(v) for v in results.values())} 条")
