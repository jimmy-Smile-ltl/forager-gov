# -*- coding: utf-8 -*-
"""P88 probe: dump 安徽点击后 tab 区 + 浙江点击后折叠区 DOM。"""
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

    page.get("http://www.ahrd.gov.cn/")
    time.sleep(9)
    box = page.ele('css:div.itemBox')
    tabs = box.eles('css:div.tabItem')
    tabs[0].click(by_js=True)
    time.sleep(2)
    # dump tabBox 及周边 DOM
    js = "(document.querySelector('.tabBox')||document.body).parentElement.innerHTML"
    html = page.run_js(js, as_expr=True)
    open("/tmp/ah_clicked.html", "w", encoding="utf-8").write(html)
    print("安徽点击后 tabBox 父容器:", len(html), "字节", flush=True)

    page.get("https://www.zjrd.gov.cn/")
    time.sleep(9)
    el = page.ele('xpath://span[@title="市县人大"]')
    el.click(by_js=True)
    time.sleep(2)
    js2 = """() => {
        const items = document.querySelectorAll('.item_list .item');
        let out = '';
        for (const it of items) out += it.innerHTML.slice(0, 3000) + '\\n---ITEM---\\n';
        return out.slice(0, 12000);
    }"""
    html2 = page.run_js(js2, as_expr=True)
    open("/tmp/zj_clicked.html", "w", encoding="utf-8").write(html2)
    print("浙江点击后 item_list:", len(html2), "字节", flush=True)

finally:
    subprocess.run(["pkill", "-9", "-f", "remote-debugging-port=9334"])
    time.sleep(2)
print("probe 完成")
