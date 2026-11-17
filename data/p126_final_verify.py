# -*- coding: utf-8 -*-
"""P126: CDP 渲染终验 3 市 title（黄山/湘西/清远反爬拦 curl）。"""
import os, re, shutil, subprocess, sys, time
sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开")
sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开/util")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

TARGETS = [
    ("黄山市", "https://www.huangshan.gov.cn/"),
    ("湘西土家族苗族自治州", "https://www.xxz.gov.cn/"),
    ("清远市", "https://www.gdqy.gov.cn/"),
]

def launch():
    shutil.rmtree("/tmp/xxgk_rs_profile", ignore_errors=True)
    from util.browser_lifecycle import PROJECT_CHROME
    return subprocess.Popen([PROJECT_CHROME, "--headless=new",
                             "--remote-debugging-port=9340",
                             "--user-data-dir=/tmp/xxgk_rs_profile",
                             "--no-sandbox", "--disable-gpu", "--no-first-run",
                             "about:blank"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def get_ws():
    import httpx
    for _ in range(30):
        try:
            r = httpx.get("http://127.0.0.1:9340/json/version", timeout=3)
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
    for nm, u in TARGETS:
        try:
            page.get(u)
            time.sleep(10)
            title = page.title
            print(f"{nm}: title={title}", flush=True)
        except Exception as e:
            print(f"{nm}: 失败 {str(e)[:50]}", flush=True)
finally:
    subprocess.run(["pkill", "-9", "-f", "remote-debugging-port=9340"])
    time.sleep(2)
print("p126 完成")
