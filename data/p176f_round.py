# -*- coding: utf-8 -*-
"""P176f: 单轮——smart_fetch 打直属机构页；成功后导出会话 cookie
（若含 cf_clearance 落盘, 后续 curl 快路径直采其余页）。"""
import json, os, sys, time
sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开")
sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开/util")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import save_snap
from smart_fetch import smart_fetch

URL = "http://www.customs.gov.cn/customs/zsgk93/5726493/5726495/index.html"
t0 = time.time()
html, m = smart_fetch(URL, timeout=25)
print(f"单轮: {m} {len(html)}B ({time.time()-t0:.0f}s)", flush=True)
if html and len(html) > 5000:
    save_snap("other", "中央", "海关总署", "zsjg", html)
    print("✓ 直属机构页已存快照", flush=True)
    # 顺带同会话导出 cookie（供快路径）
    try:
        from smart_fetch import _cf_cookie_load, _cf_cookie_save, _host_of_url
        import glob
        # 尝试从最新一次会话拿 cookie: cloakbrowser 已关, 只能靠落盘机制
        d = _cf_cookie_load(_host_of_url(URL))
        if d.get("cf_clearance"):
            print("cf_clearance 已落盘", flush=True)
    except Exception as e:
        print(f"cookie 检查失败: {str(e)[:60]}", flush=True)
    sys.exit(0)
sys.exit(1)
