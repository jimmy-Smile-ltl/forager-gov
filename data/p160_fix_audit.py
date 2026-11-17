# -*- coding: utf-8 -*-
"""P160: 抽查修复——CDP 复核 JS title 站点 + 友协挂母站列名。"""
import json, os, re, shutil, subprocess, sys, time
sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开")
sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开/util")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

TARGETS = [
    ("楚雄彝族自治州政协", "http://www.cxzzx.gov.cn"),
    ("浙江省共青团委员会", "https://www.zjyouth.org.cn/"),
]

def launch():
    shutil.rmtree("/tmp/xxgk_rs_profile", ignore_errors=True)
    from util.browser_lifecycle import PROJECT_CHROME
    return subprocess.Popen([PROJECT_CHROME, "--headless=new",
                             "--remote-debugging-port=9345",
                             "--user-data-dir=/tmp/xxgk_rs_profile",
                             "--no-sandbox", "--disable-gpu", "--no-first-run",
                             "about:blank"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def get_ws():
    import httpx
    for _ in range(30):
        try:
            r = httpx.get("http://127.0.0.1:9345/json/version", timeout=3)
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
    for nm, u in TARGETS:
        try:
            page.get(u)
            time.sleep(8)
            title = page.title
            print(f"{nm}: title={title[:50]}", flush=True)
        except Exception as e:
            print(f"{nm}: 失败 {str(e)[:40]}", flush=True)
finally:
    subprocess.run(["pkill", "-9", "-f", "remote-debugging-port=9345"])
    time.sleep(2)

# 天津友协：挂外办首页 → 列名
tree = json.load(open("tree.json", encoding="utf-8"))
tiao = next(g for g in tree["ks"] if g["n"].startswith("条"))
qt = next(g for g in tiao["ks"] if "群团" in g["n"])
fixed = 0
for g in qt["ks"]:
    for k in g.get("ks", []):
        if k.get("u") == "https://fao.tj.gov.cn/":
            print(f"列名: {k['n']}（挂天津市外办首页，非友协官网）")
            k["u"] = ""
            fixed += 1
json.dump(tree, open("tree.json", "w", encoding="utf-8"),
          ensure_ascii=False, separators=(",", ":"))
print(f"友协列名 {fixed}")
