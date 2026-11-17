# -*- coding: utf-8 -*-
"""P176b: 海关总署会话内多页采集——一次挑战通过后同会话连采
首页 + 机构设置(直属海关名录) + 网站地图 + 关于我们, 避免重复挑战。"""
import json, os, re, sys, time
sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开")
sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开/util")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import save_snap

BASE = "http://www.customs.gov.cn"
PAGES = {
    "home": "/",
    "jgsz": "/customs/zsgk93/302251/index.html",   # 机构设置
    "wzdt": "/customs/zdxx/wzdt/index.html",       # 网站地图
    "gywm": "/customs/zdxx/gywm/index.html",       # 关于我们
}

def wait_real(p, url, max_wait=75):
    try:
        p.goto(url, timeout=60000, wait_until="domcontentloaded")
    except Exception as e:
        print(f"  goto异常: {str(e)[:60]}", flush=True)
        return ""
    t0 = time.time()
    while time.time() - t0 < max_wait:
        try:
            h = p.content()
        except Exception:
            time.sleep(2); continue
        if len(h) > 5000 and p.title():
            return h
        # 子页可能无"海关"字样 title — 内容充实即可
        if len(h) > 30000:
            return h
        time.sleep(2)
    return ""

from cloakbrowser import launch
for rnd in range(8):
    t0 = time.time()
    b = None
    try:
        b = launch(headless=False, humanize=True)
        p = b.new_page()
        home = wait_real(p, BASE + PAGES["home"])
        if not home:
            print(f"轮{rnd+1}: 首页挑战未过 ({time.time()-t0:.0f}s)", flush=True)
            b.close(); b = None
            time.sleep(60)
            continue
        print(f"轮{rnd+1}: ✓ 首页 {len(home)}B ({time.time()-t0:.0f}s)", flush=True)
        save_snap("other", "中央", "海关总署", "home", home)
        # 会话内连采
        for key, path in list(PAGES.items())[1:]:
            h = wait_real(p, BASE + path, max_wait=45)
            print(f"  {key}: {'✓ '+str(len(h))+'B' if h else '✗'}", flush=True)
            if h:
                save_snap("other", "中央", "海关总署", key, h)
        # 导出 cookie
        try:
            cks = p.context.cookies()
            cf = [c for c in cks if c.get("name") == "cf_clearance"]
            if cf:
                json.dump({"cf_clearance": cf[0].get("value"),
                           "domain": cf[0].get("domain"), "t": time.time()},
                          open("hg_cf_cookie.json", "w", encoding="utf-8"))
                print(f"  cf_clearance 已导出 ({len(cf[0]['value'])} 字符)", flush=True)
        except Exception as e:
            print(f"  cookie 导出失败: {str(e)[:60]}", flush=True)
        b.close()
        print("P176b 完成", flush=True)
        sys.exit(0)
    except Exception as e:
        print(f"轮{rnd+1}异常: {type(e).__name__} {str(e)[:80]}", flush=True)
        try:
            if b: b.close()
        except Exception:
            pass
        time.sleep(60)
print("P176b: 8 轮均未通过", flush=True)
