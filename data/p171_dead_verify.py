# -*- coding: utf-8 -*-
"""P171: dead 抽样 CDP 复核（防 curl 误杀反爬站点）。"""
import json, os, re, shutil, subprocess, sys, time
sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开")
sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开/util")

picks = json.load(open("/tmp/dead_sample.json", encoding="utf-8"))

def launch():
    shutil.rmtree("/tmp/xxgk_rs_profile", ignore_errors=True)
    from util.browser_lifecycle import PROJECT_CHROME
    return subprocess.Popen([PROJECT_CHROME, "--headless=new",
                             "--remote-debugging-port=9348",
                             "--user-data-dir=/tmp/xxgk_rs_profile",
                             "--no-sandbox", "--disable-gpu", "--no-first-run",
                             "about:blank"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def get_ws():
    import httpx
    for _ in range(30):
        try:
            r = httpx.get("http://127.0.0.1:9348/json/version", timeout=3)
            if r.status_code == 200:
                return r.json()["webSocketDebuggerUrl"]
        except Exception:
            pass
        time.sleep(1)
    raise RuntimeError("CDP 未就绪")

proc = launch()
alive = []
try:
    from DrissionPage import ChromiumPage
    page = ChromiumPage(addr_or_opts=get_ws())
    for k, u in picks:
        try:
            page.get(u)
            time.sleep(7)
            title = page.title
            size = len(page.html)
            is_alive = len(title) > 0 and size > 500
            print(f"{'✓活' if is_alive else '✗死'} {k}: title={title[:35]} size={size}", flush=True)
            if is_alive:
                alive.append((k, u))
        except Exception as e:
            print(f"✗死 {k}: {str(e)[:35]}", flush=True)
finally:
    subprocess.run(["pkill", "-9", "-f", "remote-debugging-port=9348"])
    time.sleep(2)
print(f"\np171 完成: {len(alive)}/{len(picks)} 是误杀（实际存活）")
