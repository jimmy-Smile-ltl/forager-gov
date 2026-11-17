# -*- coding: utf-8 -*-
"""P96: CDP 渲染 13 省纪委监委官网。"""
import os, re, shutil, subprocess, sys, time
sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开")
sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开/util")

TARGETS = [
    ("北京市", "http://www.bjsupervision.gov.cn"),
    ("辽宁省", "http://www.lnsjjjc.gov.cn"),
    ("上海市", "https://www.shjjjc.gov.cn"),
    ("浙江省", "http://www.zjsjw.gov.cn"),
    ("福建省", "http://www.fjcdi.gov.cn"),
    ("江西省", "http://www.jxdi.gov.cn"),
    ("山东省", "http://www.sdjj.gov.cn"),
    ("河南省", "http://www.hnsjct.gov.cn/"),
    ("重庆市", "http://jjc.cq.gov.cn"),
    ("四川省", "http://www.scjc.gov.cn"),
    ("云南省", "http://www.ynjjjc.gov.cn"),
    ("陕西省", "http://www.qinfeng.gov.cn"),
    ("青海省", "http://www.qinghai.gov.cn/zmhd/system/20"),
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
            fn = f"/tmp/jw2_{pn}.html"
            open(fn, "w", encoding="utf-8").write(html)
            print(f"{pn}: {len(html)} 字节", flush=True)
        except Exception as e:
            print(f"{pn}: 失败 {str(e)[:50]}", flush=True)
finally:
    subprocess.run(["pkill", "-9", "-f", "remote-debugging-port=9334"])
    time.sleep(2)
print("p96 render 完成")
