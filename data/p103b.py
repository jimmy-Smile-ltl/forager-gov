# -*- coding: utf-8 -*-
"""P103b: 江苏点击后 dump links 容器 HTML。"""
import os, re, shutil, subprocess, sys, time
sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开")
sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开/util")

def launch():
    shutil.rmtree("/tmp/xxgk_rs_profile", ignore_errors=True)
    from util.browser_lifecycle import PROJECT_CHROME
    return subprocess.Popen([PROJECT_CHROME, "--headless=new",
                             "--remote-debugging-port=9334",
                             "--user-data-dir=/tmp/xxgk_rs_profile",
                             "--no-sandbox", "--disable-gpu", "--no-first-run",
                             "about:blank"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def get_ws():
    import httpx
    for _ in range(30):
        try:
            r = httpx.get("http://127.0.0.1:9334/json/version", timeout=3)
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
    page.get("https://www.jszx.gov.cn/")
    time.sleep(9)
    spans = page.eles('css:span.linkBtn-item')
    for sp in spans:
        if "各设区市政协" in sp.text:
            sp.click()
            time.sleep(3)
            break
    # dump links 容器
    html = page.run_js(
        "(()=>{const d=document.querySelector('div.links');return d?d.outerHTML.slice(0,12000):'no .links'})()",
        as_expr=True)
    print(html[:12000] if html else "(空)")
finally:
    subprocess.run(["pkill", "-9", "-f", "remote-debugging-port=9334"])
    time.sleep(2)
print()
print("p103b 完成")
