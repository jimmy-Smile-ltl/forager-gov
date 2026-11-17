# -*- coding: utf-8 -*-
"""P103: 江苏真实点击 linkBtn-item 抓市级政协。"""
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
    page.get("https://www.jszx.gov.cn/")
    time.sleep(9)
    # 找 linkBtn-item 中含「各设区市政协」的 span，真实点击父级
    spans = page.eles('css:span.linkBtn-item')
    print(f"linkBtn-item 数: {len(spans)}")
    for sp in spans:
        if "各设区市政协" in sp.text:
            sp.click()
            time.sleep(3)
            break
    html = page.html
    # links 容器内容
    seg = html[html.find("各设区市政协"):]
    seg = seg[:8000]
    for u, txt in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>\s*([^<]{2,16}?)\s*</a>', seg):
        t2 = txt.strip()
        if u.startswith("http"):
            print(f"  {t2} -> {u[:70]}")
finally:
    subprocess.run(["pkill", "-9", "-f", "remote-debugging-port=9334"])
    time.sleep(2)
print("p103 完成")
