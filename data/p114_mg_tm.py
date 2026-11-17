# -*- coding: utf-8 -*-
"""P114: CDP 渲染民革/台盟官网找省级组织导航。"""
import os, re, shutil, subprocess, sys, time
sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开")
sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开/util")

def launch():
    shutil.rmtree("/tmp/xxgk_rs_profile", ignore_errors=True)
    from util.browser_lifecycle import PROJECT_CHROME
    return subprocess.Popen([PROJECT_CHROME, "--headless=new",
                             "--remote-debugging-port=9336",
                             "--user-data-dir=/tmp/xxgk_rs_profile",
                             "--no-sandbox", "--disable-gpu", "--no-first-run",
                             "about:blank"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def get_ws():
    import httpx
    for _ in range(30):
        try:
            r = httpx.get("http://127.0.0.1:9336/json/version", timeout=3)
            if r.status_code == 200:
                return r.json()["webSocketDebuggerUrl"]
        except Exception:
            pass
        time.sleep(1)
    raise RuntimeError("CDP 未就绪")

proc = launch()
try:
    from DrissionPage import ChromiumPage
    page = ChromiumPage(addr_or_opts=get_ws())
    for pn, u in [("民革", "http://www.minge.gov.cn/"),
                  ("台盟", "http://www.taimeng.gov.cn/")]:
        try:
            page.get(u)
            time.sleep(9)
            html = page.html
            open(f"/tmp/dp2_{pn}.html", "w", encoding="utf-8").write(html)
            print(f"{pn}: {len(html)} 字节", flush=True)
            hits = {}
            for uu, tt, txt in re.findall(
                    r'<a[^>]+href="([^"]+)"[^>]*\s*(?:title="([^"]+)")?>([^<]*)</a>', html):
                name = (tt or txt).strip()
                if re.search(r'(省委会|省委|市委会)$', name) and uu.startswith("http"):
                    hits.setdefault(name, uu)
            for k, v in list(hits.items())[:20]:
                print(f"   {k} -> {v[:60]}", flush=True)
        except Exception as e:
            print(f"{pn}: 失败 {str(e)[:50]}", flush=True)
finally:
    subprocess.run(["pkill", "-9", "-f", "remote-debugging-port=9336"])
    time.sleep(2)
print("p114 完成")
