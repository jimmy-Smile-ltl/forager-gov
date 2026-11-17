# -*- coding: utf-8 -*-
"""P112: 12309 检察地图探测（CDP 渲染 + 网络监听找 API）。"""
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
    # 12309 检察地图可能路径
    for u in ("https://www.12309.gov.cn/12309/jcdt/",
              "https://www.12309.gov.cn/12309/ditu/",
              "https://www.12309.gov.cn/"):
        try:
            page.get(u)
            time.sleep(8)
            html = page.html
            print(f"{u}: {len(html)} 字节", flush=True)
            # 找地图/名录相关链接
            seen = set()
            for uu, txt in re.findall(
                    r'<a[^>]+href="([^"]+)"[^>]*>\s*([^<]{2,26}?)\s*</a>', html):
                t2 = txt.strip()
                if re.search(r'(地图|ditu|dt/)', t2 + uu) and (uu, t2) not in seen:
                    seen.add((uu, t2))
                    print(f"   {t2} -> {uu[:80]}", flush=True)
            if "jcdt" in u:
                open("/tmp/s12309_jcdt.html", "w", encoding="utf-8").write(html)
                break
        except Exception as e:
            print(f"{u}: {str(e)[:50]}", flush=True)
finally:
    subprocess.run(["pkill", "-9", "-f", "remote-debugging-port=9334"])
    time.sleep(2)
print("p112 完成")
