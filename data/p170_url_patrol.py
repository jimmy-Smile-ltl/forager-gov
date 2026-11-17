# -*- coding: utf-8 -*-
"""P170: URL 健康巡检——全量并发验证 registry URL，写 status 字段。

ok=200+有效内容；dead=连接失败/404；maintain=维护中/反爬挑战。
断点续跑（按 key 记录）。
"""
import json
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
reg = json.load(open("site_registry.json", encoding="utf-8"))

def check(u):
    try:
        r = subprocess.run(["curl", "-s", "--compressed", "-L", "--max-time", "10",
                            "-A", UA, u], capture_output=True, timeout=13)
        raw = r.stdout
        if len(raw) < 100:
            return "dead"
        t = None
        for enc in ("utf-8", "gb18030"):
            try:
                t = raw.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        if t is None:
            t = raw.decode("utf-8", errors="replace")
        if "404" in t[:300] and len(raw) < 2000:
            return "dead"
        if re.search(r'(维护|maintenance|正在建设|Cloudflare|请稍候|Environment Checking)', t[:800]):
            return "maintain"
        return "ok"
    except Exception:
        return "dead"

items = [(k, v) for k, v in reg.items()
         if v.get("u") and v.get("status", "unknown") != "ok"]
print(f"待巡检: {len(items)} 条", flush=True)
done = 0
with ThreadPoolExecutor(max_workers=12) as ex:
    futs = {ex.submit(check, v["u"]): k for k, v in items}
    for f in as_completed(futs):
        k = futs[f]
        st = f.result()
        reg[k]["status"] = st
        reg[k]["verified_at"] = "2026-11-06"
        done += 1
        if done % 500 == 0:
            print(f"{done}/{len(items)}", flush=True)
json.dump(reg, open("site_registry.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=0)
from collections import Counter
c = Counter(v["status"] for v in reg.values() if v.get("u"))
print(f"\np170 巡检完成: {dict(c)}")
