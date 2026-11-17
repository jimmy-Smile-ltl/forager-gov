# -*- coding: utf-8 -*-
"""P62b: 高院页面顺序遍历提取（天津 areamap / 北京 tit_a·tit_b 通用）。

页面锚点顺序即隶属顺序：遇「中级人民法院/中级法院/中院」锚点 → 设为当前父；
其后「XX人民法院」锚点（不含中级/高级）→ 挂当前父下。
合并进 court_hierarchy.jsonl（按 省+名+URL 去重）。
"""
import base64
import json
import re
import subprocess
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from p57_court_proc_systems import COURTS  # noqa: E402

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")


def decode_elink(h):
    if "elink.chinacourt.cn" in h:
        m = re.search(r"elid=([^&\s\"']+)", h)
        if m:
            elid = m.group(1)
            if elid.startswith(("http://", "https://")):
                return elid                      # 明文 URL
            try:
                return base64.urlsafe_b64decode(elid + "==").decode()
            except Exception:
                pass
    return h


def fetch(url):
    try:
        r = subprocess.run(["curl", "-s", "-L", "--max-time", "20", "-A", UA, url],
                           capture_output=True, text=True, timeout=25)
        return r.stdout or ""
    except Exception:
        return ""


def seq_extract(html):
    """顺序遍历 → [(level, name, parent_name, url)]；含 option 下拉通道。"""
    rows = []
    cur_zy = None
    pat = re.compile(r'<a[^>]+href="([^"]+)"[^>]*>([^<]{2,24}?)</a>')
    for m in pat.finditer(html):
        t = re.sub(r"\s+", "", m.group(2))
        u = decode_elink(m.group(1))
        if not t or not u.startswith(("http://", "https://")):
            continue
        if "中级" in t or t.endswith("中院") and len(t) <= 20:
            cur_zy = t
            rows.append(("中院", t, None, u))
        elif t.endswith("人民法院") and "高级" not in t and len(t) <= 22:
            if cur_zy:
                rows.append(("基层", t, cur_zy, u))
    # option 下拉通道（中院，容忍 value ="..." 空格写法）
    for m in re.finditer(r'<option[^>]*value\s*=\s*"([^"]+)"[^>]*>([^<]{2,24}?)</option>', html):
        t = re.sub(r"\s+", "", m.group(2))
        if not t or ("中院" not in t and "中级" not in t) or len(t) > 20:
            continue
        u = decode_elink(m.group(1))
        if u.startswith(("http://", "https://")):
            rows.append(("中院", t, None, u))
    # 去重：同文本保留最后一个 URL
    dedup = {}
    for lv, t, p, u in rows:
        dedup[(t)] = (lv, t, p, u)
    return list(dedup.values())


def main():
    merged = {json.dumps(r, ensure_ascii=False) for r in
              [json.loads(l) for l in open("court_hierarchy.jsonl", encoding="utf-8")]}
    added_zy = added_jc = 0
    for pname, gy_url in sorted(COURTS.items()):
        html = fetch(gy_url)
        if not html:
            print(f"{pname}: 抓取失败", flush=True)
            continue
        rows = seq_extract(html)
        for lv, t, parent, u in rows:
            r = {"province": pname, "level": lv, "name": t,
                 "parent": parent or f"{pname}高级人民法院",
                 "url": u, "text": t, "source_url": gy_url}
            s = json.dumps(r, ensure_ascii=False)
            if s not in merged:
                merged.add(s)
                if lv == "中院":
                    added_zy += 1
                else:
                    added_jc += 1
        nz = sum(1 for r in rows if r[0] == "中院")
        nj = sum(1 for r in rows if r[0] == "基层")
        print(f"{pname}: 新增视角 中院 {nz} / 基层 {nj}", flush=True)

    with open("court_hierarchy.jsonl", "w", encoding="utf-8") as f:
        for s in sorted(merged):
            f.write(s + "\n")
    print(f"p62b 完成：新并入 中院 {added_zy}，基层 {added_jc}")


if __name__ == "__main__":
    main()
