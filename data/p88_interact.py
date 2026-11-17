# -*- coding: utf-8 -*-
"""P88: 交互提取——安徽 tab、浙江折叠面板、宁夏 tab、西藏 /dxrd。"""
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

    # ===== 安徽：市县人大 tab 逐个点击 =====
    page.get("http://www.ahrd.gov.cn/")
    time.sleep(9)
    tabs = page.eles('css:div.tabItem')
    ah = {}
    for i, tab in enumerate(tabs):
        try:
            tab.click()
            time.sleep(1.2)
            html = page.html
            # 当前 tab 对应的内容区块链接
            m = re.search(r'oneTab">市县人大', html)
            seg = html[m.start():m.start()+12000] if m else html
            for u, txt in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>\s*([^<]{2,24}?)\s*</a>', seg):
                txt2 = txt.strip()
                if re.search(r'(人大|常委会)', txt2):
                    ah[txt2] = u
        except Exception as e:
            print(f"安徽 tab{i} 失败: {str(e)[:40]}")
    out["安徽省"] = ah
    print(f"安徽: {len(ah)} 链接", flush=True)

    # ===== 浙江：点击市县人大折叠 =====
    page.get("https://www.zjrd.gov.cn/")
    time.sleep(9)
    titles = page.eles('css:div.item.multipleContent .title')
    for ti in titles:
        try:
            txt = ti.text.strip()
            if "市县人大" in txt or "各地人大" in txt:
                ti.click()
                time.sleep(1.5)
        except Exception as e:
            print(f"浙江点击失败: {str(e)[:40]}")
    html = page.html
    zj = {}
    for u, txt in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>\s*([^<]{2,24}?)\s*</a>', html):
        txt2 = txt.strip()
        if re.search(r'(市人大|人大网)', txt2) and 'zjrd.gov.cn' not in u:
            zj[txt2] = u
    out["浙江省"] = zj
    print(f"浙江: {len(zj)} 链接", flush=True)

    # ===== 宁夏：点击区内重要网站 tab =====
    page.get("http://www.nxrd.gov.cn/")
    time.sleep(9)
    items = page.eles('css:div.yqlj-title .item')
    for it in items:
        try:
            if "区内" in it.text:
                it.click()
                time.sleep(1.5)
        except Exception as e:
            print(f"宁夏点击失败: {str(e)[:40]}")
    html = page.html
    nx = {}
    for u, txt in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>\s*([^<]{2,24}?)\s*</a>', html):
        txt2 = txt.strip()
        if re.search(r'(人大|政府)', txt2) and "nxrd.gov.cn" not in u:
            nx[txt2] = u
    out["宁夏回族自治区"] = nx
    print(f"宁夏: {len(nx)} 链接", flush=True)

    # ===== 西藏：/dxrd 页面 =====
    page.get("http://www.xizangrd.gov.cn/dxrd")
    time.sleep(7)
    html = page.html
    xz = {}
    for u, txt in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>\s*([^<]{2,24}?)\s*</a>', html):
        txt2 = txt.strip()
        if re.search(r'(人大|常委会)', txt2) and "xizangrd.gov.cn" not in u:
            xz[txt2] = u
    out["西藏自治区"] = xz
    print(f"西藏: {len(xz)} 链接", flush=True)

finally:
    subprocess.run(["pkill", "-9", "-f", "remote-debugging-port=9334"])
    time.sleep(2)

json.dump(out, open("/tmp/p88_out.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=0)
print("p88 完成，结果已存 /tmp/p88_out.json")
