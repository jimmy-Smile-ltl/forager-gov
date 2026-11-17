# -*- coding: utf-8 -*-
"""P141: 安徽政协专项——tab 点击提取市县政协链接。

p94 曾误用安徽人大 JS（hefeirenda.cn），数据已清，重采政协官网
ahzx.gov.cn 的市县政协 tab。
"""
import os, re, shutil, subprocess, sys, time
sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开")
sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开/util")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def launch():
    shutil.rmtree("/tmp/xxgk_rs_profile", ignore_errors=True)
    from util.browser_lifecycle import PROJECT_CHROME
    return subprocess.Popen([PROJECT_CHROME, "--headless=new",
                             "--remote-debugging-port=9343",
                             "--user-data-dir=/tmp/xxgk_rs_profile",
                             "--no-sandbox", "--disable-gpu", "--no-first-run",
                             "about:blank"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def get_ws():
    import httpx
    for _ in range(30):
        try:
            r = httpx.get("http://127.0.0.1:9343/json/version", timeout=3)
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
    page.get("http://www.ahzx.gov.cn/")
    time.sleep(9)
    # 点击「市县政协」相关 tab
    tabs = page.eles('css:div.tabItem')
    print(f"安徽 tabItem: {len(tabs)}", flush=True)
    hits = {}
    for i in range(len(tabs)):
        try:
            tabs[i].click(by_js=True)
            time.sleep(1.2)
            html = page.html
            for u, txt in re.findall(
                    r'<a[^>]+href="([^"]+)"[^>]*>\s*([^<]{2,24}?)\s*</a>', html):
                t2 = txt.strip()
                if re.search(r'(政协|zhengxie|szx)', t2) and u.startswith("http") \
                        and "ahzx.gov.cn" not in u:
                    hits.setdefault(t2, u)
        except Exception as e:
            print(f"tab{i} 失败: {str(e)[:35]}", flush=True)
    print(f"安徽政协命中: {len(hits)}", flush=True)
    for k, v in hits.items():
        print(f"  {k} -> {v}", flush=True)
finally:
    subprocess.run(["pkill", "-9", "-f", "remote-debugging-port=9343"])
    time.sleep(2)
print("p141 完成")
