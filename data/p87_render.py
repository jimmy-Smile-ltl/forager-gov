# -*- coding: utf-8 -*-
"""P87: 批量渲染 12 省人大官网（CDP 9334），保存渲染后 HTML。"""
import os, re, shutil, subprocess, sys, time

sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开")
sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开/util")

TARGETS = [
    ("山西省", "http://www.sxpc.gov.cn/"),
    ("内蒙古自治区", "http://www.nmgrd.gov.cn/"),
    ("吉林省", "http://www.jlrd.gov.cn/"),
    ("浙江省", "http://www.zjrd.gov.cn/"),
    ("安徽省", "http://www.ahrd.gov.cn/"),
    ("山东省", "http://www.sdrd.gov.cn/"),
    ("湖北省", "http://www.hppc.gov.cn/"),
    ("西藏自治区", "http://www.xizangrd.gov.cn/"),
    ("甘肃省", "http://www.gsrdw.gov.cn/"),
    ("宁夏回族自治区", "http://www.nxrd.gov.cn/"),
    ("天津市", "http://www.tjrd.gov.cn/"),
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
            time.sleep(8)
            html = page.html
            fn = f"/tmp/p87_{pn}.html"
            open(fn, "w", encoding="utf-8").write(html)
            print(f"{pn}: {len(html)} 字节", flush=True)
        except Exception as e:
            print(f"{pn}: 失败 {str(e)[:60]}", flush=True)
finally:
    subprocess.run(["pkill", "-9", "-f", "remote-debugging-port=9334"])
    time.sleep(2)
print("p87 render 完成")
