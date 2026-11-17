# -*- coding: utf-8 -*-
"""P88v4: 真实点击交互（scroll.to_see + click）。"""
import json, os, re, shutil, subprocess, sys, time
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

out = {}
proc = launch()
try:
    from DrissionPage import ChromiumPage
    page = ChromiumPage(addr_or_opts=get_ws())

    # ===== 安徽 =====
    page.get("http://www.ahrd.gov.cn/")
    time.sleep(9)
    ah = {}
    try:
        page.scroll.to_bottom()
        time.sleep(1.5)
        tabs = page.eles('css:div.itemBox div.tabItem')
        print(f"安徽 tabs: {len(tabs)}", flush=True)
        for i in range(len(tabs)):
            try:
                t = tabs[i]
                page.scroll.to_see(t)
                time.sleep(0.4)
                t.click()
                time.sleep(1.5)
                for u, txt in re.findall(
                        r'<a[^>]+href="([^"]+)"[^>]*>\s*([^<]{2,24}?)\s*</a>',
                        page.html):
                    t2 = txt.strip()
                    if re.search(r'(人大|常委会)', t2) and "ahrd.gov.cn" not in u:
                        ah[t2] = u
            except Exception as e:
                print(f"安徽 tab{i} 失败: {str(e)[:40]}", flush=True)
    except Exception as e:
        print(f"安徽整体失败: {str(e)[:60]}", flush=True)
    out["安徽省"] = ah
    print(f"安徽: {len(ah)} 链接 {list(ah.items())[:6]}", flush=True)

    # ===== 浙江 =====
    page.get("https://www.zjrd.gov.cn/")
    time.sleep(9)
    zj = {}
    try:
        page.scroll.to_bottom()
        time.sleep(1.5)
        el = page.ele('xpath://span[@title="市县人大"]')
        page.scroll.to_see(el)
        time.sleep(0.4)
        el.click()
        time.sleep(2)
        for u, txt in re.findall(
                r'<a[^>]+href="([^"]+)"[^>]*>\s*([^<]{2,24}?)\s*</a>', page.html):
            t2 = txt.strip()
            if re.search(r'(市人大|人大网)', t2) and "zjrd.gov.cn" not in u:
                zj[t2] = u
    except Exception as e:
        print(f"浙江整体失败: {str(e)[:60]}", flush=True)
    out["浙江省"] = zj
    print(f"浙江: {len(zj)} 链接 {list(zj.items())[:6]}", flush=True)

    # ===== 宁夏 =====
    page.get("http://www.nxrd.gov.cn/")
    time.sleep(9)
    nx = {}
    try:
        page.scroll.to_bottom()
        time.sleep(1.5)
        it = page.ele('xpath://div[contains(@class,"yqlj-title")]//div[contains(text(),"区内重要网站")]')
        page.scroll.to_see(it)
        time.sleep(0.4)
        it.click()
        time.sleep(2)
        for u, txt in re.findall(
                r'<a[^>]+href="([^"]+)"[^>]*>\s*([^<]{2,24}?)\s*</a>', page.html):
            t2 = txt.strip()
            if re.search(r'(人大|政府)', t2) and "nxrd.gov.cn" not in u:
                nx[t2] = u
    except Exception as e:
        print(f"宁夏整体失败: {str(e)[:60]}", flush=True)
    out["宁夏回族自治区"] = nx
    print(f"宁夏: {len(nx)} 链接 {list(nx.items())[:6]}", flush=True)

finally:
    subprocess.run(["pkill", "-9", "-f", "remote-debugging-port=9334"])
    time.sleep(2)

json.dump(out, open("/tmp/p88_out4.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=0)
print("p88v4 完成")
