# -*- coding: utf-8 -*-
"""P166: 渲染 6 总局「机构设置」栏目页——按用户方法论找下级组织权威名录。"""
import os, re, shutil, subprocess, sys, time
sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开")
sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开/util")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import save_snap

TARGETS = [
    ("矿山", "https://www.chinamine-safety.gov.cn/", "机构设置"),
    ("矿山机构", "https://www.chinamine-safety.gov.cn/zfxxgk/fdzdgknr/jgsz/", "机构设置"),
    ("粮储", "https://www.lswz.gov.cn/html/jggk/index.shtml", "机构设置"),
    ("审计", "https://www.audit.gov.cn/n10/n16/index.html", "机构设置"),
    ("海事", "https://www.msa.gov.cn/", "机构"),
    ("林草", "http://www.forestry.gov.cn/pcjg.jhtml", "派出机构"),
    ("统计", "https://www.stats.gov.cn/", "机构"),
]

def launch():
    shutil.rmtree("/tmp/xxgk_rs_profile", ignore_errors=True)
    from util.browser_lifecycle import PROJECT_CHROME
    return subprocess.Popen([PROJECT_CHROME, "--headless=new",
                             "--remote-debugging-port=9347",
                             "--user-data-dir=/tmp/xxgk_rs_profile",
                             "--no-sandbox", "--disable-gpu", "--no-first-run",
                             "about:blank"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def get_ws():
    import httpx
    for _ in range(30):
        try:
            r = httpx.get("http://127.0.0.1:9347/json/version", timeout=3)
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
            time.sleep(9)
            html = page.html
            save_snap("other", "中央", f"{pn}总局", "jigou", html)
            print(f"{pn}: {len(html)} 字节", flush=True)
            hits = {}
            for uu, txt in re.findall(
                    r'<a[^>]+href="([^"]+)"[^>]*>\s*([^<]{3,34}?)\s*</a>', html):
                t2 = txt.strip()
                if re.search(r'(管理局|监管局|海事局|专员办|审计厅|调查总队|矿山安全监察局|储备局)', t2) \
                        and uu.startswith("http"):
                    hits.setdefault(t2, uu)
            for k, v in list(hits.items())[:20]:
                print(f"   {k} -> {v[:60]}", flush=True)
        except Exception as e:
            print(f"{pn}: 失败 {str(e)[:40]}", flush=True)
finally:
    subprocess.run(["pkill", "-9", "-f", "remote-debugging-port=9347"])
    time.sleep(2)
print("p166 完成")
