# -*- coding: utf-8 -*-
"""P107: CDP 渲染复核可疑市级检察院 URL。"""
import json, os, re, shutil, subprocess, sys, time
sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开")
sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开/util")

TARGETS = [
    ("辽宁省检察院", "朝阳检察院", "http://www.chaoyang.jcy.gov.cn/"),
    ("广东省检察院", "珠海检察院", "http://www.zhuhai.jcy.gov.cn/"),
    ("广东省检察院", "河源检察院", "https://jcy.heyuan.gov.cn/"),
    ("广东省检察院", "阳江检察院", "http://www.yjjc.gov.cn/"),
    ("广西壮族自治区检察院", "贵港市检察院", "http://www.guigang.jcy.gov.cn/"),
    ("四川省检察院", "攀枝花市检察院", "http://www.panzhihua.jcy.gov.cn/"),
    ("四川省检察院", "广元市检察院", "http://www.gyjcy.gov.cn/"),
    ("四川省检察院", "遂宁市检察院", "http://www.snjcy.gov.cn/"),
    ("四川省检察院", "达州市检察院", "http://www.scdzjcy.gov.cn/"),
    ("四川省检察院", "眉山市检察院", "http://www.msjcy.gov.cn/"),
    ("四川省检察院", "甘孜藏族自治州检察院", "http://www.gzzjcy.gov.cn/"),
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
    for pn, sn, u in TARGETS:
        try:
            page.get(u)
            time.sleep(7)
            title = page.title
            print(f"{pn} {sn}: title={title[:50]}", flush=True)
        except Exception as e:
            print(f"{pn} {sn}: 失败 {str(e)[:40]}", flush=True)
finally:
    subprocess.run(["pkill", "-9", "-f", "remote-debugging-port=9334"])
    time.sleep(2)
print("p107 完成")
