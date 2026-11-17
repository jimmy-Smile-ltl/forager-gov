# -*- coding: utf-8 -*-
"""P108: CDP 渲染广东/广西/湖南省检察院官网，找市级院权威导航。"""
import json, os, re, shutil, subprocess, sys, time
sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开")
sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开/util")

TARGETS = [
    ("广东", "http://www.gd.jcy.gov.cn/"),
    ("广西", "http://www.gx.jcy.gov.cn/"),
    ("湖南", "https://www.hn.jcy.gov.cn/"),
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
            open(f"/tmp/provjc_{pn}.html", "w", encoding="utf-8").write(html)
            print(f"{pn}: {len(html)} 字节", flush=True)
            # 市院链接
            seen = set()
            for uu, txt in re.findall(
                    r'<a[^>]+href="([^"]+)"[^>]*>\s*([^<]{2,26}?)\s*</a>', html):
                t2 = txt.strip()
                if re.search(r'(人民检察院|检察)', t2) and uu.startswith("http") \
                        and (uu, t2) not in seen and 'jcy.gov.cn' in uu:
                    seen.add((uu, t2))
            for uu, txt in list(seen)[:30]:
                print(f"   {txt} -> {uu[:65]}", flush=True)
        except Exception as e:
            print(f"{pn}: 失败 {str(e)[:50]}", flush=True)
finally:
    subprocess.run(["pkill", "-9", "-f", "remote-debugging-port=9334"])
    time.sleep(2)
print("p108 完成")
