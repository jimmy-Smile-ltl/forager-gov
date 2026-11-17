# -*- coding: utf-8 -*-
"""P132: 渲染浙江/湖北/广东/海南导航页补 37 市。"""
import os, re, shutil, subprocess, sys, time
sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开")
sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开/util")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import save_snap

TARGETS = [
    ("浙江省", "https://www.zj.gov.cn/col/col1591801/index.html"),
    ("湖北省", "https://www.hubei.gov.cn/2019/zqdh/szwz/"),
    ("广东省", "https://www.gd.gov.cn/yw/sqs/index.html"),
    ("海南省", "https://www.hainan.gov.cn/"),
]

def launch():
    shutil.rmtree("/tmp/xxgk_rs_profile", ignore_errors=True)
    from util.browser_lifecycle import PROJECT_CHROME
    return subprocess.Popen([PROJECT_CHROME, "--headless=new",
                             "--remote-debugging-port=9341",
                             "--user-data-dir=/tmp/xxgk_rs_profile",
                             "--no-sandbox", "--disable-gpu", "--no-first-run",
                             "about:blank"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def get_ws():
    import httpx
    for _ in range(30):
        try:
            r = httpx.get("http://127.0.0.1:9341/json/version", timeout=3)
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
            save_snap("shixian", pn, f"{pn}导航页", "nav", html)
            print(f"{pn}: {len(html)} 字节", flush=True)
            seen = {}
            for uu, txt in re.findall(
                    r'<a[^>]+href="([^"]+)"[^>]*>\s*([^<]{2,24}?)\s*</a>', html):
                t2 = txt.strip()
                if re.search(r'(市|州|林区)$', t2) and uu.startswith("http") \
                        and ".gov.cn" in uu:
                    seen.setdefault(t2, uu)
            for k, v in list(seen.items())[:24]:
                print(f"   {k} -> {v[:60]}", flush=True)
        except Exception as e:
            print(f"{pn}: 失败 {str(e)[:50]}", flush=True)
finally:
    subprocess.run(["pkill", "-9", "-f", "remote-debugging-port=9341"])
    time.sleep(2)
print("p132 完成")
