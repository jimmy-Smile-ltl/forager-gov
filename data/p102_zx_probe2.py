# -*- coding: utf-8 -*-
"""P102: 剩余省政协交互 probe——点击后保存 HTML 离线分析。"""
import json, os, re, shutil, subprocess, sys, time
sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开")
sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开/util")

TARGETS = [
    ("江苏省", "https://www.jszx.gov.cn/", "各设区市政协"),
    ("河南省", "http://www.hnzx.gov.cn/", "省辖市政协"),
    ("河北省", "http://www.hebzx.gov.cn/", "设区市政协"),
    ("山西省", "http://www.shanxizx.gov.cn/", "各市政协"),
    ("海南省", "http://www.hainanzx.gov.cn/", "市县政协"),
    ("黑龙江省", "http://www.hljzx.gov.cn/", "市地政协"),
    ("云南省", "http://www.ynzx.gov.cn/", "州市政协"),
    ("安徽省", "http://www.ahzx.gov.cn/", "各市政协"),
    ("浙江省", "http://www.zjzx.gov.cn/", "各市政协"),
    ("新疆维吾尔自治区", "http://www.xjzx.gov.cn/", "地州市政协"),
    ("西藏自治区", "https://www.xizangzx.gov.cn/", "各地市政协"),
    ("辽宁省", "http://www.lnzx.gov.cn/", "各市政协"),
    ("宁夏回族自治区", "http://www.nxzx.gov.cn/", "各市政协"),
    ("江西省", "http://jxzx.jxnews.com.cn/", "设区市政协"),
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
    for pn, u, kw in TARGETS:
        try:
            page.get(u)
            time.sleep(8)
            # 点击 linkBtn-item 或含关键字元素（用 JS 找最接近的可点元素）
            js = ("var els=document.querySelectorAll('*');"
                  "for(const el of els){"
                  f"if(el.children.length<=2&&el.textContent&&el.textContent.trim().includes('{kw}'))"
                  "{{el.click();break;}}}")
            page.run_js(js, as_expr=True)
            time.sleep(3)
            html = page.html
            fn = f"/tmp/zx3_{pn}.html"
            open(fn, "w", encoding="utf-8").write(html)
            print(f"{pn}: {len(html)} 字节", flush=True)
        except Exception as e:
            print(f"{pn}: 失败 {str(e)[:50]}", flush=True)
finally:
    subprocess.run(["pkill", "-9", "-f", "remote-debugging-port=9334"])
    time.sleep(2)
print("p102 完成")
