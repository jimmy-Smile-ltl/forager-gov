# -*- coding: utf-8 -*-
"""P117: CDP 渲染海关/金融监管/移民官网找省级机构名录。"""
import os, re, shutil, subprocess, sys, time
sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开")
sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开/util")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import save_snap

TARGETS = [
    ("海关", "http://www.customs.gov.cn/"),
    ("金融监管", "https://www.nfra.gov.cn/"),
    ("移民", "https://www.nia.gov.cn/"),
]

def launch():
    shutil.rmtree("/tmp/xxgk_rs_profile", ignore_errors=True)
    from util.browser_lifecycle import PROJECT_CHROME
    return subprocess.Popen([PROJECT_CHROME, "--headless=new",
                             "--remote-debugging-port=9338",
                             "--user-data-dir=/tmp/xxgk_rs_profile",
                             "--no-sandbox", "--disable-gpu", "--no-first-run",
                             "about:blank"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def get_ws():
    import httpx
    for _ in range(30):
        try:
            r = httpx.get("http://127.0.0.1:9338/json/version", timeout=3)
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
            time.sleep(10)
            html = page.html
            save_snap("other", "中央", f"{pn}总局", "home", html)
            print(f"{pn}: {len(html)} 字节", flush=True)
            # 省级机构链接（海关直属海关/金融监管派出机构/移民边检总站）
            seen = {}
            for uu, txt in re.findall(
                    r'<a[^>]+href="([^"]+)"[^>]*>\s*([^<]{2,28}?)\s*</a>', html):
                t2 = txt.strip()
                if re.search(r'(海关|监管局|总站|分局)$', t2) and uu.startswith("http"):
                    seen.setdefault(t2, uu)
            for k, v in list(seen.items())[:20]:
                print(f"   {k} -> {v[:65]}", flush=True)
        except Exception as e:
            print(f"{pn}: 失败 {str(e)[:50]}", flush=True)
finally:
    subprocess.run(["pkill", "-9", "-f", "remote-debugging-port=9338"])
    time.sleep(2)
print("p117 完成")
