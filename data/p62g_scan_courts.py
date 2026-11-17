# -*- coding: utf-8 -*-
"""P62g: 通用站内扫描——高院首页全部站内链接逐个探测，找含「中院」≥3 的
列表页 → parse_seq 顺序解析并入。"""
import base64
import json
import os
import re
import subprocess
import sys
import time
from urllib.parse import urljoin

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from p57_court_proc_systems import COURTS  # noqa: E402

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
REST = ["江西省", "湖北省", "西藏自治区", "甘肃省", "宁夏回族自治区",
        "新疆生产建设兵团"]


def decode_elink(h):
    if "elink.chinacourt.cn" in h:
        m = re.search(r"elid=([^&\s\"']+)", h)
        if m:
            elid = m.group(1)
            if elid.startswith(("http://", "https://")):
                return elid
            try:
                return base64.urlsafe_b64decode(elid + "==").decode()
            except Exception:
                pass
    return h


def fetch(u):
    try:
        r = subprocess.run(["curl", "-s", "-L", "--max-time", "18", "-A", UA, u],
                           capture_output=True, timeout=22)
        raw = r.stdout
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            return raw.decode("gb18030", errors="replace")
    except Exception:
        return ""


def parse_seq(html):
    rows = []
    cur = None
    for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>([^<]{2,28}?)</a>', html):
        t = re.sub(r"\s+", "", m.group(2))
        u = decode_elink(m.group(1))
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


def main():
    merged = {}
    if os.path.exists("court_hierarchy.jsonl"):
        for l in open("court_hierarchy.jsonl", encoding="utf-8"):
            r = json.loads(l)
            merged[(r["province"], r["level"], r["name"])] = r

    for pname in REST:
        home = fetch(COURTS[pname])
        if not home:
            print(f"{pname}: 首页失败", flush=True)
            continue
        base = COURTS[pname]
        host = re.search(r"https?://([^/]+)", base).group(1)
        cands = set()
        for m in re.finditer(r'(?:href|src)="([^"]+)"', home):
            h = m.group(1)
            if h.startswith("//"):
                h = "http:" + h
            if h.startswith("http"):
                if host in h and re.search(r"\.(s?html?|php|jsp|aspx?)$", h):
                    cands.add(h.split("#")[0])
            elif h.startswith("/"):
                if re.search(r"\.(s?html?|php|jsp|aspx?)$", h):
                    cands.add(urljoin(base, h))
        cands = sorted(cands)[:25]
        got = 0
        for c in cands:
            html = fetch(c)
            if not html or html.count("中院") < 3:
                continue
            for lv, t, parent, u in parse_seq(html):
                merged[(pname, lv, t)] = {
                    "province": pname, "level": lv, "name": t,
                    "parent": parent or f"{pname}高级人民法院",
                    "url": u, "text": t, "source_url": c}
            got = sum(1 for k in merged if k[0] == pname and k[1] == "中院")
            if got:
                break
        print(f"{pname}: 扫描 {len(cands)} 链接，中院命中 {got}", flush=True)
        time.sleep(0.5)

    with open("court_hierarchy.jsonl", "w", encoding="utf-8") as f:
        for r in sorted(merged.values(), key=lambda x: (x["province"], x["level"], x["name"])):
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    n_zy = sum(1 for r in merged.values() if r["level"] == "中院")
    n_jc = sum(1 for r in merged.values() if r["level"] == "基层")
    print(f"p62g 完成：中院 {n_zy}，基层 {n_jc}")


if __name__ == "__main__":
    main()
