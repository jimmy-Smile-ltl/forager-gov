# -*- coding: utf-8 -*-
"""P62j: 最后四省补全（西藏/兵团站点群页、湖北 API 列表页、宁夏官方群区块）。"""
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from p62c_court_unified import seq_extract  # noqa: E402

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")


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


def nx_extract(html):
    """宁夏「官方网站群」区块：市名设父（中院），其后区县（基层）跟随。"""
    i = html.find("官方网站群")
    seg = html[i:i + 15000] if i > 0 else html
    rows = []
    cur = None
    for m in re.finditer(r'<a href="([^"]+)"[^>]*title="([^"]+)"', seg):
        u = m.group(1)
        t = re.sub(r"\s+", "", m.group(2))
        if not u.startswith(("http://", "https://")):
            continue
        if t.endswith("市") or "铁路" in t:
            cur = t
            if t.endswith("市"):
                rows.append(("中院", t + "中级人民法院", None, u))
            else:
                rows.append(("中院", t, None, u))
        else:
            nm = t + ("人民法院" if not t.endswith("法院") else "")
            rows.append(("基层", nm, cur, u))
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

    jobs = [
        ("西藏自治区", "http://xzgy.xzcourt.gov.cn/article/webgroup.shtml", "seq"),
        ("新疆生产建设兵团", "http://btfy.btcourt.gov.cn/article/webgroup.shtml", "seq"),
        ("湖北省", "https://www.hbfy.gov.cn/DocManage/getDocsByFolder?folderNo=03", "seq"),
        ("宁夏回族自治区", "https://www.nxfy.gov.cn/", "nx"),
    ]
    for pname, u, mode in jobs:
        html = fetch(u)
        print(f"{pname}: {len(html)} 字节")
        if mode == "seq":
            for lv, t, parent, url in seq_extract(html):
                if url.startswith("//"):
                    url = "http:" + url
                if not url.startswith(("http://", "https://")):
                    continue
                if lv == "中院" and len(t) > 20:
                    continue
                merged[(pname, lv, t)] = {
                    "province": pname, "level": lv, "name": t,
                    "parent": parent or f"{pname}高级人民法院",
                    "url": url, "text": t, "source_url": u}
        else:
            for lv, t, parent, url in nx_extract(html):
                merged[(pname, lv, t)] = {
                    "province": pname, "level": lv, "name": t,
                    "parent": parent or f"{pname}高级人民法院",
                    "url": url, "text": t, "source_url": u}
        nz = sum(1 for k in merged if k[0] == pname and k[1] == "中院")
        nj = sum(1 for k in merged if k[0] == pname and k[1] == "基层")
        print(f"  → 中院 {nz} / 基层 {nj}")

    with open("court_hierarchy.jsonl", "w", encoding="utf-8") as f:
        for r in sorted(merged.values(), key=lambda x: (x["province"], x["level"], x["name"])):
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"p62j 完成：中院 {sum(1 for r in merged.values() if r['level']=='中院')}，"
          f"基层 {sum(1 for r in merged.values() if r['level']=='基层')}")


if __name__ == "__main__":
    main()
