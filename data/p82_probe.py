# -*- coding: utf-8 -*-
"""P82 探测：dump 福建/陕西/黑龙江/辽宁/重庆 人大页面渲染后 HTML 供结构分析。"""
import json, os, re, shutil, subprocess, sys, time

sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开")
sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开/util")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

TARGETS = [
    ("福建省", "https://szrd.fjrd.gov.cn/"),
    ("陕西省", "https://www.sxrd.gov.cn/#/index"),
    ("黑龙江省", "https://www.hljrd.gov.cn/"),
    ("辽宁省", "http://www.lnrd.gov.cn/"),
    ("重庆市", "https://www.cqrd.gov.cn/"),
]

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
    for pn, u in TARGETS:
        try:
            page.get(u)
            time.sleep(9)
            html = page.html
            fn = f"p82_{pn}.html"
            open(fn, "w", encoding="utf-8").write(html)
            print(f"{pn}: {len(html)} 字节 -> {fn}", flush=True)
        except Exception as e:
            print(f"{pn}: 失败 {str(e)[:60]}", flush=True)
finally:
    subprocess.run(["pkill", "-9", "-f", "remote-debugging-port=9334"])
    time.sleep(2)
print("p82 probe 完成")
