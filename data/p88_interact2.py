# -*- coding: utf-8 -*-
"""P88v2: 交互提取——安徽 tab 内容区、浙江折叠展开、宁夏 tab。"""
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

    # ===== 安徽：滚动到市县人大 tabBox，逐市点击抓内容区 =====
    page.get("http://www.ahrd.gov.cn/")
    time.sleep(9)
    try:
        box = page.ele('css:div.itemBox')
        time.sleep(1)
        tabs = box.eles('css:div.tabItem')
        print(f"安徽 tabs: {len(tabs)}", flush=True)
        ah = {}
        # 内容区：tabBox 同级的链接容器（点击后变化的全部新链接）
        seen = set()
        for i in range(len(tabs)):
            tab = tabs[i]
            try:
                tab.click(by_js=True)
                time.sleep(1.2)
                html = page.html
                for u, txt in re.findall(
                        r'<a[^>]+href="([^"]+)"[^>]*>\s*([^<]{2,24}?)\s*</a>', html):
                    txt2 = txt.strip()
                    key = (u, txt2)
                    if re.search(r'(人大|常委会)', txt2) and key not in seen \
                            and "ahrd.gov.cn" not in u:
                        seen.add(key)
                        ah[txt2] = u
            except Exception as e:
                print(f"安徽 tab{i} 失败: {str(e)[:40]}", flush=True)
        out["安徽省"] = ah
        print(f"安徽: {len(ah)} 链接", flush=True)
    except Exception as e:
        print(f"安徽整体失败: {str(e)[:60]}", flush=True)
        out["安徽省"] = {}

    # ===== 浙江：滚动到底部点击市县人大 =====
    page.get("https://www.zjrd.gov.cn/")
    time.sleep(9)
    try:
        page.scroll.to_bottom()
        time.sleep(1.5)
        el = page.ele('xpath://span[@title="市县人大"]')el.click(by_js=True)
        time.sleep(2)
        html = page.html
        zj = {}
        for u, txt in re.findall(
                r'<a[^>]+href="([^"]+)"[^>]*>\s*([^<]{2,24}?)\s*</a>', html):
            txt2 = txt.strip()
            if re.search(r'(市人大|人大网)', txt2) and "zjrd.gov.cn" not in u:
                zj[txt2] = u
        out["浙江省"] = zj
        print(f"浙江: {len(zj)} 链接", flush=True)
    except Exception as e:
        print(f"浙江整体失败: {str(e)[:60]}", flush=True)
        out["浙江省"] = {}

    # ===== 宁夏：点击区内重要网站 tab 看内容 =====
    page.get("http://www.nxrd.gov.cn/")
    time.sleep(9)
    try:
        it = page.ele('xpath://div[contains(@class,"yqlj-title")]//div[contains(text(),"区内重要网站")]')it.click(by_js=True)
        time.sleep(2)
        html = page.html
        nx = {}
        for u, txt in re.findall(
                r'<a[^>]+href="([^"]+)"[^>]*>\s*([^<]{2,24}?)\s*</a>', html):
            txt2 = txt.strip()
            if re.search(r'(人大|政府)', txt2) and "nxrd.gov.cn" not in u:
                nx[txt2] = u
        out["宁夏回族自治区"] = nx
        print(f"宁夏: {len(nx)} 链接", flush=True)
    except Exception as e:
        print(f"宁夏整体失败: {str(e)[:60]}", flush=True)
        out["宁夏回族自治区"] = {}

finally:
    subprocess.run(["pkill", "-9", "-f", "remote-debugging-port=9334"])
    time.sleep(2)

json.dump(out, open("/tmp/p88_out2.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=0)
print("p88v2 完成")
