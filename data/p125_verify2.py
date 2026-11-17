# -*- coding: utf-8 -*-
"""P125: 增强验证——GBK 解码 + 核心名匹配，重验剩余缺口。"""
import json
import re
import subprocess
import time

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")

# (省, 节点, 搜索词, 候选URL直接验证)
TARGETS = [
    ("安徽省", "合肥市", "合肥市人民政府", None),
    ("安徽省", "黄山市", "黄山市人民政府", None),
    ("湖北省", "襄阳市", "襄阳市人民政府", None),
    ("湖南省", "湘西土家族苗族自治州", "湘西州人民政府", None),
    ("广东省", "清远市", "清远市人民政府", None),
    ("云南省", "迪庆藏族自治州", "迪庆州人民政府", "http://www.diqing.gov.cn/"),
    ("青海省", "黄南藏族自治州", "黄南州人民政府", "http://www.huangnan.gov.cn/"),
    ("青海省", "玉树藏族自治州", "玉树州人民政府", "https://www.yushuzhou.gov.cn/"),
    ("河北省", "省教育厅", "河北省教育厅", "http://www.hee.gov.cn/"),
    ("新疆维吾尔自治区", "新疆维吾尔自治区税务局", "新疆税务局",
     "https://xinjiang.chinatax.gov.cn/"),
]

def fetch_title(u):
    try:
        r = subprocess.run(["curl", "-s", "--compressed", "-L", "--max-time", "12",
                            "-A", UA, u], capture_output=True, timeout=16)
        raw = r.stdout
        for enc in ("utf-8", "gb18030"):
            try:
                t = raw.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        else:
            t = raw.decode("utf-8", errors="replace")
        m = re.search(r"<title>([^<]*)</title>", t)
        return m.group(1).strip() if m else ""
    except Exception:
        return ""

def serp(q):
    try:
        r = subprocess.run(["curl", "-s", "--compressed", "--max-time", "12",
                            "-A", UA,
                            "https://www.baidu.com/s?wd=" + q],
                           capture_output=True, timeout=15)
        t = r.stdout.decode("utf-8", errors="replace")
        out = re.findall(r'mu="([^"]+)"', t)
        return out
    except Exception:
        return []

results = json.load(open("/tmp/p123_results.json", encoding="utf-8"))
for prov, node, query, direct in TARGETS:
    key = f"{prov}|{node}"
    if results.get(key):
        continue
    cands = [direct] if direct else serp(query)
    hit = None
    core = re.sub(r"(自治州|省|市|厅|局|发展改革委)$", "", node)
    core = core.replace("省教育厅", "教育厅").replace("税务局", "税务")
    core2 = re.sub(r"(维吾尔|壮族|回族|藏族|蒙古族|苗族|土家族|布依族|傣族|景颇族|彝族自治)?州$", "", core)
    for u in cands:
        if not u or not u.startswith("http") or "baidu" in u or "baike" in u:
            continue
        title = fetch_title(u)
        ok = (core2 and len(core2) >= 2 and core2 in title and
              ("政府" in title or "教育" in title or "税务" in title or "发改" in title))
        print(f"{prov} {node}: {u[:50]} title={title[:40]} {'✓' if ok else '✗'}", flush=True)
        if ok:
            hit = u
            break
        time.sleep(0.6)
    if hit:
        results[key] = hit
    time.sleep(1.2)

json.dump(results, open("/tmp/p123_results.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=0)
n_hit = sum(1 for v in results.values() if v)
print(f"\np125 完成: {n_hit}/18")
