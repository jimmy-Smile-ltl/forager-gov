# -*- coding: utf-8 -*-
"""P176c: 海关总署子页独立撞窗口——每页各自 smart_fetch 全链
（CF 快跳 + cloakbrowser 3 重试），最多 6 次调用。"""
import json, os, sys, time
sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开")
sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开/util")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import save_snap
from smart_fetch import smart_fetch

PAGES = {
    "jgsz": "http://www.customs.gov.cn/customs/zsgk93/302251/index.html",
    "wzdt": "http://www.customs.gov.cn/customs/zdxx/wzdt/index.html",
    "gywm": "http://www.customs.gov.cn/customs/zdxx/gywm/index.html",
}

for key, url in PAGES.items():
    ok = False
    for attempt in range(6):
        t0 = time.time()
        html, m = smart_fetch(url, timeout=25)
        print(f"{key} 轮{attempt+1}: {m} {len(html)}B ({time.time()-t0:.0f}s)", flush=True)
        if html and len(html) > 5000 and "海关" in html:
            save_snap("other", "中央", "海关总署", key, html)
            print(f"  ✓ {key} 已存快照", flush=True)
            ok = True
            break
        time.sleep(45)
    if not ok:
        print(f"  ✗ {key} 6 次未过", flush=True)
print("P176c 完成", flush=True)
