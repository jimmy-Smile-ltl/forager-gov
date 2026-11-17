# -*- coding: utf-8 -*-
"""P123: 14 市 + 4 厅局缺口——百度 SERP 发现候选 → 官方页面 title 验证。

合规链路：SERP 仅作发现线索（不直接采信），候选 URL 必须回官方页面
HTML 验证 title 身份（权威源体系第 4 档兜底）。
"""
import json
import re
import subprocess
import time

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")

TARGETS = [
    ("吉林省", "白城市", "白城市人民政府"),
    ("安徽省", "合肥市", "合肥市人民政府"),
    ("安徽省", "黄山市", "黄山市人民政府"),
    ("湖北省", "襄阳市", "襄阳市人民政府"),
    ("湖北省", "恩施土家族苗族自治州", "恩施州人民政府"),
    ("湖南省", "湘西土家族苗族自治州", "湘西州人民政府"),
    ("广东省", "清远市", "清远市人民政府"),
    ("贵州省", "黔南布依族苗族自治州", "黔南州人民政府"),
    ("云南省", "德宏傣族景颇族自治州", "德宏州人民政府"),
    ("云南省", "迪庆藏族自治州", "迪庆州人民政府"),
    ("青海省", "黄南藏族自治州", "黄南州人民政府"),
    ("青海省", "果洛藏族自治州", "果洛州人民政府"),
    ("青海省", "玉树藏族自治州", "玉树州人民政府"),
    ("青海省", "海西蒙古族藏族自治州", "海西州人民政府"),
    ("河北省", "省教育厅", "河北省教育厅"),
    ("山西省", "山西省教育厅", "山西省教育厅"),
    ("四川省", "省发展改革委", "四川省发展和改革委员会"),
    ("新疆维吾尔自治区", "新疆维吾尔自治区税务局", "新疆税务局"),
]

def serp(q):
    """百度搜索返回候选 URL 列表。"""
    try:
        r = subprocess.run(["curl", "-s", "--compressed", "--max-time", "12",
                            "-A", UA,
                            "https://www.baidu.com/s?wd=" + q.replace(" ", "+")],
                           capture_output=True, timeout=15)
        t = r.stdout.decode("utf-8", errors="replace")
        urls = re.findall(r'href="(http[^"]+\.gov\.cn[^"]*)"', t)
        # 百度跳转链接解码
        out = []
        for m in re.finditer(r'mu="([^"]+)"', t):
            out.append(m.group(1))
        return out or urls
    except Exception:
        return []

def verify(u, expect):
    """title 验证身份。"""
    try:
        r = subprocess.run(["curl", "-s", "--compressed", "-L", "--max-time", "12",
                            "-A", UA, u], capture_output=True, timeout=16)
        t = r.stdout.decode("utf-8", errors="replace")
        m = re.search(r"<title>([^<]*)</title>", t)
        title = m.group(1).strip() if m else ""
        return expect.replace("人民政府", "") in title or expect in title, title[:50]
    except Exception:
        return False, ""

results = {}
for prov, node, query in TARGETS:
    print(f"{prov} {node}: 搜索...", flush=True)
    cands = serp(query)
    hit = None
    for u in cands[:6]:
        if not u.startswith("http"):
            continue
        ok, title = verify(u, query)
        if ok:
            hit = u
            print(f"   ✓ {u} title={title}", flush=True)
            break
        else:
            print(f"   ✗ {u[:60]} title={title}", flush=True)
        time.sleep(0.8)
    results[f"{prov}|{node}"] = hit or ""
    time.sleep(1.5)

json.dump(results, open("/tmp/p123_results.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=0)
n_hit = sum(1 for v in results.values() if v)
print(f"\np123 完成: {n_hit}/{len(TARGETS)} 命中")
