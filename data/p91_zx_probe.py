# -*- coding: utf-8 -*-
"""P91: 批量静态抓 31 省政协官网首页。"""
import json, subprocess

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
provs = json.load(open("/tmp/zx_prov.json", encoding="utf-8"))
for pn, u in provs.items():
    if not u:
        print(f"{pn}: (无URL)")
        continue
    fn = f"/tmp/zx_{pn}.html"
    try:
        r = subprocess.run(["curl", "-s", "--compressed", "-L", "--max-time", "18",
                            "-A", UA, u, "-o", fn], capture_output=True, timeout=25)
        import os
        sz = os.path.getsize(fn)
        print(f"{pn}: {sz} 字节")
    except Exception as e:
        print(f"{pn}: 失败 {str(e)[:50]}")
