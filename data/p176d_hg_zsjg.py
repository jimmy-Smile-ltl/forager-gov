# -*- coding: utf-8 -*-
"""P176d: 海关总署「直属机构」页（42 直属海关名录）独立撞窗口。"""
import os, sys, time
sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开")
sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开/util")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import save_snap
from smart_fetch import smart_fetch

URL = "http://www.customs.gov.cn/customs/zsgk93/5726493/5726495/index.html"
for attempt in range(8):
    t0 = time.time()
    html, m = smart_fetch(URL, timeout=25)
    print(f"轮{attempt+1}: {m} {len(html)}B ({time.time()-t0:.0f}s)", flush=True)
    if html and len(html) > 5000:
        save_snap("other", "中央", "海关总署", "zsjg", html)
        print("✓ 直属机构页已存快照", flush=True)
        sys.exit(0)
    time.sleep(45)
print("P176d: 8 轮未过", flush=True)
