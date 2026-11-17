# -*- coding: utf-8 -*-
"""P97: CDP 渲染 ccdi 首页 + 地方纪委监委机构页（验证码需浏览器）。"""
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
    for name, u in [("ccdi_home", "https://www.ccdi.gov.cn/"),
                    ("ccdi_difang", "https://www.ccdi.gov.cn/wzdhn/dfjjjcjg/")]:
        try:
            page.get(u)
            time.sleep(10)
            html = page.html
            open(f"/tmp/{name}.html", "w", encoding="utf-8").write(html)
            print(f"{name}: {len(html)} 字节", flush=True)
        except Exception as e:
            print(f"{name}: 失败 {str(e)[:50]}", flush=True)
finally:
    subprocess.run(["pkill", "-9", "-f", "remote-debugging-port=9334"])
    time.sleep(2)
print("p97 完成")
