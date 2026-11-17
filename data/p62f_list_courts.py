# -*- coding: utf-8 -*-
"""P62f: 法院「专页列表」模式提取（黑龙江 qsfy.php 式：全称列表，
中院在前、其基层跟后顺序排列）。

1) 已知专页：黑龙江 /public/qsfy.php
2) 其余空省：抓高院首页 footer「法院链接/全省法院/下辖法院」候选链接
   → 抓取候选页 → 含 ≥5 个「人民法院」→ 顺序解析并入。
"""
import json
import os
import re
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from p57_court_proc_systems import COURTS  # noqa: E402

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
REST = ["江西省", "湖北省", "西藏自治区", "甘肃省", "宁夏回族自治区",
        "新疆生产建设兵团"]
KNOWN_PAGE = {"黑龙江省": "http://www.hljcourt.gov.cn/public/qsfy.php"}


def fetch(u):
    try:
        r = subprocess.run(["curl", "-s", "-L", "--max-time", "20", "-A", UA, u],
                           capture_output=True, timeout=25)
        raw = r.stdout
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            return raw.decode("gb18030", errors="replace")
    except Exception:
        return ""


def parse_seq(html):
    """顺序解析全称列表 → [(level, name, parent, url)]"""
    rows = []
    cur = None
    for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>([^<]{2,28}?)</a>', html):
        t = re.sub(r"\s+", "", m.group(2))
        u = m.group(1)
        if not u.startswith(("http://", "https://")) or len(t) > 26:
            continue
        if "中级人民法院" in t or t.endswith("中级法院"):
            cur = t
            rows.append(("中院", t, None, u))
        elif t.endswith(("人民法院", "法院")) and "高级" not in t and "中级" not in t:
            if cur:
                rows.append(("基层", t, cur, u))
    dedup = {}
    for lv, t, p, u in rows:
        dedup[(lv, t)] = (lv, t, p, u)
    return list(dedup.values())


def find_list_page(html, base):
    """footer 候选：文本含(法院链接|全省法院|下辖法院)的链接"""
    cands = []
    for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>([^<]{0,24}?(?:法院链接|全省法院|下辖法院|法院导航)[^<]{0,8})</a>', html):
        h = m.group(1)
        if h.startswith("/"):
            from urllib.parse import urljoin
            h = urljoin(base, h)
        cands.append(h)
    return cands


def main():
    merged = {}
    if os.path.exists("court_hierarchy.jsonl"):
        for l in open("court_hierarchy.jsonl", encoding="utf-8"):
            r = json.loads(l)
            merged[(r["province"], r["level"], r["name"])] = r

    for pname, u in KNOWN_PAGE.items():
        html = fetch(u)
        for lv, t, parent, url in parse_seq(html):
            merged[(pname, lv, t)] = {
                "province": pname, "level": lv, "name": t,
                "parent": parent or f"{pname}高级人民法院",
                "url": url, "text": t, "source_url": u}
        nz = sum(1 for k in merged if k[0] == pname and k[1] == "中院")
        nj = sum(1 for k in merged if k[0] == pname and k[1] == "基层")
        print(f"{pname}: 专页 中院{nz}/基层{nj}", flush=True)

    for pname in REST:
        home = fetch(COURTS[pname])
        if not home:
            print(f"{pname}: 首页抓取失败", flush=True)
            continue
        cands = find_list_page(home, COURTS[pname])
        got = 0
        for c in cands[:5]:
            html = fetch(c)
            if html.count("人民法院") < 5:
                continue
            for lv, t, parent, url in parse_seq(html):
                merged[(pname, lv, t)] = {
                    "province": pname, "level": lv, "name": t,
                    "parent": parent or f"{pname}高级人民法院",
                    "url": url, "text": t, "source_url": c}
            got = sum(1 for k in merged if k[0] == pname and k[1] == "中院")
            if got:
                break
        print(f"{pname}: 专页命中 中院{got}", flush=True)
        time.sleep(0.5)

    with open("court_hierarchy.jsonl", "w", encoding="utf-8") as f:
        for r in sorted(merged.values(), key=lambda x: (x["province"], x["level"], x["name"])):
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    n_zy = sum(1 for r in merged.values() if r["level"] == "中院")
    n_jc = sum(1 for r in merged.values() if r["level"] == "基层")
    print(f"p62f 完成：中院 {n_zy}，基层 {n_jc}")


if __name__ == "__main__":
    main()
