# -*- coding: utf-8 -*-
"""P120: 海关总署官网直属海关名录（非 headless 过 Cloudflare 挑战）。"""
import os, re, shutil, subprocess, sys, time
sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开")
sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开/util")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import save_snap

def launch():
    shutil.rmtree("/tmp/xxgk_rs_profile", ignore_errors=True)
    from util.browser_lifecycle import PROJECT_CHROME
    return subprocess.Popen([PROJECT_CHROME,
                             "--remote-debugging-port=9339",
                             "--user-data-dir=/tmp/xxgk_rs_profile",
                             "--no-sandbox", "--disable-gpu", "--no-first-run",
                             "--window-size=1400,900",
                             "about:blank"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def get_ws():
    import httpx
    for _ in range(30):
        try:
            r = httpx.get("http://127.0.0.1:9339/json/version", timeout=3)
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
    page.get("http://www.customs.gov.cn/")
    # 等 Cloudflare 挑战自动通过（最多 40 秒）
    for i in range(8):
        time.sleep(5)
        html = page.html
        if len(html) > 5000:
            break
        print(f"  等待挑战 {i*5}s, 当前 {len(html)} 字节", flush=True)
    html = page.html
    save_snap("other", "中央", "海关总署", "home", html)
    print(f"海关: {len(html)} 字节", flush=True)
    seen = {}
    for u, txt in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>\s*([^<]{2,22}?)\s*</a>', html):
        t2 = txt.strip()
        if re.search(r'海关$', t2) and u.startswith("http") and t2 not in seen:
            seen[t2] = u
    for k, v in list(seen.items())[:50]:
        print(f"   {k} -> {v[:70]}", flush=True)
finally:
    subprocess.run(["pkill", "-9", "-f", "remote-debugging-port=9339"])
    time.sleep(2)
print("p120 完成")
