# -*- coding: utf-8 -*-
"""P142: 安徽 16 市政协——SERP 线索 + 官方页面 title 验证。"""
import json
import re
import subprocess
import time

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")

CITIES = ["合肥", "芜湖", "蚌埠", "淮南", "马鞍山", "淮北", "铜陵", "安庆",
          "黄山", "滁州", "阜阳", "宿州", "六安", "亳州", "池州", "宣城"]

def serp(q):
    try:
        r = subprocess.run(["curl", "-s", "--compressed", "--max-time", "12",
                            "-A", UA, "https://www.baidu.com/s?wd=" + q],
                           capture_output=True, timeout=15)
        t = r.stdout.decode("utf-8", errors="replace")
        return re.findall(r'mu="([^"]+)"', t)
    except Exception:
        return []

def verify(u, core):
    try:
        r = subprocess.run(["curl", "-s", "--compressed", "-L", "--max-time", "10",
                            "-A", UA, u], capture_output=True, timeout=14)
        raw = r.stdout
        t = None
        for enc in ("utf-8", "gb18030"):
            try:
                t = raw.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        if t is None:
            t = raw.decode("utf-8", errors="replace")
        m = re.search(r"<title>([^<]*)</title>", t)
        title = m.group(1).strip() if m else ""
        return (core in title and "政协" in title) or \
               (core in title and "政府" in title and "政协" in title)
    except Exception:
        return False

results = {}
for city in CITIES:
    cands = serp(f"{city}市政协")
    hit = None
    for u in cands[:6]:
        if not u or not u.startswith("http") or "baidu" in u or "baike" in u:
            continue
        # 政协 title 或 政府域名下政协频道
        try:
            r = subprocess.run(["curl", "-s", "--compressed", "-L", "--max-time", "10",
                                "-A", UA, u], capture_output=True, timeout=14)
            raw = r.stdout
            t = None
            for enc in ("utf-8", "gb18030"):
                try:
                    t = raw.decode(enc)
                    break
                except UnicodeDecodeError:
                    continue
            if t is None:
                t = raw.decode("utf-8", errors="replace")
            m = re.search(r"<title>([^<]*)</title>", t)
            title = m.group(1).strip() if m else ""
            if city in title and "政协" in title:
                hit = u
                print(f"✓ {city}市政协: {u} ({title[:30]})", flush=True)
                break
        except Exception:
            pass
        time.sleep(0.5)
    results[city] = hit or ""
    time.sleep(1.2)

json.dump(results, open("/tmp/p142_ah.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=0)
print(f"\np142 完成: {sum(1 for v in results.values() if v)}/16")
