# -*- coding: utf-8 -*-
"""P122: CDP 渲染 7 省政府门户，提取市导航补 14 缺口。"""
import os, re, shutil, subprocess, sys, time
sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开")
sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开/util")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import save_snap

TARGETS = [
    ("吉林省", "http://www.jl.gov.cn/"),
    ("安徽省", "https://www.ah.gov.cn/"),
    ("湖北省", "http://www.hubei.gov.cn/"),
    ("湖南省", "http://www.hunan.gov.cn/"),
    ("广东省", "http://www.gd.gov.cn/"),
    ("贵州省", "http://www.guizhou.gov.cn/"),
    ("青海省", "http://www.qinghai.gov.cn/"),
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
    for pn, u in TARGETS:
        try:
            page.get(u)
            time.sleep(9)
            html = page.html
            save_snap("shixian", pn, f"{pn}政府门户", "home", html)
            print(f"{pn}: {len(html)} 字节", flush=True)
        except Exception as e:
            print(f"{pn}: 失败 {str(e)[:50]}", flush=True)
finally:
    subprocess.run(["pkill", "-9", "-f", "remote-debugging-port=9340"])
    time.sleep(2)
print("p122 完成")
