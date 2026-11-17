# -*- coding: utf-8 -*-
"""P92: CDP 渲染无命中省政协首页。"""
import json, os, re, shutil, subprocess, sys, time
sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开")
sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开/util")

TARGETS = [
    "云南省", "内蒙古自治区", "吉林省", "天津市", "宁夏回族自治区", "安徽省",
    "山东省", "江苏省", "江西省", "河北省", "河南省", "浙江省", "海南省",
    "湖南省", "甘肃省", "新疆维吾尔自治区", "西藏自治区", "陕西省",
    "贵州省", "辽宁省", "黑龙江省",
]

provs = json.load(open("/tmp/zx_prov.json", encoding="utf-8"))

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
    for pn in TARGETS:
        u = provs.get(pn)
        if not u:
            print(f"{pn}: 无URL", flush=True)
            continue
        try:
            page.get(u)
            time.sleep(8)
            html = page.html
            fn = f"/tmp/zx2_{pn}.html"
            open(fn, "w", encoding="utf-8").write(html)
            print(f"{pn}: {len(html)} 字节", flush=True)
        except Exception as e:
            print(f"{pn}: 失败 {str(e)[:50]}", flush=True)
finally:
    subprocess.run(["pkill", "-9", "-f", "remote-debugging-port=9334"])
    time.sleep(2)
print("p92 render 完成")
