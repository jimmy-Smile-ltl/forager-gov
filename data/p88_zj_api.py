# -*- coding: utf-8 -*-
"""P88z: 浙江 XHR 监听抓市县人大数据 API。"""
import json, os, re, shutil, subprocess, sys, time
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
    page.listen.start("")   # 监听全部请求
    page.get("https://www.zjrd.gov.cn/")
    time.sleep(12)
    packets = page.listen.wait(5, timeout=3)
    print(f"捕获 {len(packets)} 个请求", flush=True)
    for p in packets:
        try:
            u = str(p.url)
            body = str(p.response.body)[:400]
            if re.search(r'(rd|renda|link)', body, re.I) and ('json' in u or 'link' in u.lower()):
                print("==", u[:100])
                print(body[:600])
        except Exception:
            pass
finally:
    subprocess.run(["pkill", "-9", "-f", "remote-debugging-port=9334"])
    time.sleep(2)
print("done")
