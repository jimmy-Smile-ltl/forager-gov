# -*- coding: utf-8 -*-
"""P133: 37 个市缺口——SERP 线索 + 官方页面 title 验证（合规链路）。

浙江 8 / 湖北 9 / 广东 16 / 海南 4。每市搜索「XX市人民政府」，
候选回官方页面验证 title 身份后落库。
"""
import json
import re
import subprocess
import time

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")

MISSING = [
    ("浙江省", "杭州市"), ("浙江省", "宁波市"), ("浙江省", "温州市"),
    ("浙江省", "嘉兴市"), ("浙江省", "湖州市"), ("浙江省", "金华市"),
    ("浙江省", "舟山市"), ("浙江省", "丽水市"),
    ("湖北省", "武汉市"), ("湖北省", "黄石市"), ("湖北省", "十堰市"),
    ("湖北省", "宜昌市"), ("湖北省", "荆门市"), ("湖北省", "孝感市"),
    ("湖北省", "荆州市"), ("湖北省", "咸宁市"), ("湖北省", "随州市"),
    ("广东省", "广州市"), ("广东省", "深圳市"), ("广东省", "珠海市"),
    ("广东省", "汕头市"), ("广东省", "佛山市"), ("广东省", "江门市"),
    ("广东省", "湛江市"), ("广东省", "茂名市"), ("广东省", "肇庆市"),
    ("广东省", "惠州市"), ("广东省", "汕尾市"), ("广东省", "河源市"),
    ("广东省", "阳江市"), ("广东省", "东莞市"), ("广东省", "潮州市"),
    ("广东省", "揭阳市"), ("广东省", "云浮市"),
    ("海南省", "海口市"), ("海南省", "三亚市"), ("海南省", "儋州市"),
]

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
        return core in title and "政府" in title
    except Exception:
        return False

results = {}
for prov, city in MISSING:
    core = city.replace("市", "")
    key = f"{prov}|{city}"
    cands = serp(f"{city}人民政府")
    hit = None
    for u in cands[:8]:
        if not u or not u.startswith("http") or "baidu" in u or "baike" in u:
            continue
        if verify(u, core):
            hit = u
            print(f"✓ {city}: {u}", flush=True)
            break
        time.sleep(0.5)
    if not hit:
        print(f"✗ {city}: 未命中", flush=True)
    results[key] = hit or ""
    time.sleep(1.2)

json.dump(results, open("/tmp/p133_results.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=0)
print(f"\np133 完成: {sum(1 for v in results.values() if v)}/{len(MISSING)}")
