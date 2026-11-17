# -*- coding: utf-8 -*-
"""P62c: 法院层级统一爬取（整合 p62/p62b，修复 option 空格写法与明文 elid）。

1) 32 高院首页：<option>（容忍 value ="..." 空格写法）+ <a> 顺序遍历
   （遇中院设父，后续基层归其下，天津/北京 areamap 模式）
2) 全部中院官网：全页扫描「法院在线/下辖法院」基层链接
3) 合并进 court_hierarchy.jsonl（按 省+层级+名 去重，URL 后出现者优先）
断点续跑 court_crawl_state.json。
"""
import base64
import json
import os
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from p57_court_proc_systems import COURTS  # noqa: E402

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
STATE_F = "court_crawl_state.json"
OUT_F = "court_hierarchy.jsonl"


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


def fetch(url):
    try:
        r = subprocess.run(["curl", "-s", "-L", "--max-time", "20", "-A", UA, url],
                           capture_output=True, text=True, timeout=25)
        return r.stdout or ""
    except Exception:
        return ""


def seq_extract(html):
    """顺序遍历（a 通道 + option 通道）→ [(level, name, parent, url)]"""
    rows = []
    cur_zy = None
    for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>\s*([^<]{2,30}?)\s*</a>', html):
        t = re.sub(r"\s+", "", m.group(2))
        u = decode_elink(m.group(1))
        if not t or not u.startswith(("http://", "https://")):
            continue
        if ("中级" in t or t.endswith("中院")) and len(t) <= 20:
            cur_zy = t
            rows.append(("中院", t, None, u))
        elif t.endswith("人民法院") and "高级" not in t and len(t) <= 22:
            if cur_zy:
                rows.append(("基层", t, cur_zy, u))
    for m in re.finditer(r'<option[^>]*value\s*=\s*"([^"]+)"[^>]*>\s*([^<]{2,30}?)\s*</option>', html):
        t = re.sub(r"\s+", "", m.group(2))
        if not t or ("中院" not in t and "中级" not in t) or len(t) > 20:
            continue
        u = decode_elink(m.group(1))
        if u.startswith(("http://", "https://")):
            rows.append(("中院", t, None, u))
    dedup = {}
    for lv, t, p, u in rows:
        dedup[t] = (lv, t, p, u)
    return list(dedup.values())


def get_jiceng(html):
    """中院页全页扫描基层法院（法院在线/下辖法院等区块）。"""
    out = {}
    for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>([^<]{2,18}?(?:法院|法庭)[^<]{0,6})</a>', html):
        t = re.sub(r"\s+", "", m.group(2))
        if not t or len(t) > 16:
            continue
        if "中级" in t or "高级" in t or "中院" in t:
            continue
        if t.endswith(("法院", "法庭")):
            u = decode_elink(m.group(1))
            if u.startswith(("http://", "https://")):
                out[t] = u
    return out


def main():
    state = json.load(open(STATE_F, encoding="utf-8")) \
        if os.path.exists(STATE_F) else {}
    done_gy = set(state.get("done_gy", []))
    done_zy = set(state.get("done_zy", []))
    merged = {}
    if os.path.exists(OUT_F):
        for l in open(OUT_F, encoding="utf-8"):
            r = json.loads(l)
            merged[(r["province"], r["level"], r["name"])] = r

    # ---- 1) 高院页 ----
    for pname, gy_url in sorted(COURTS.items()):
        if pname in done_gy:
            continue
        html = fetch(gy_url)
        nz = nj = 0
        for lv, t, parent, u in seq_extract(html):
            r = {"province": pname, "level": lv, "name": t,
                 "parent": parent or f"{pname}高级人民法院",
                 "url": u, "text": t, "source_url": gy_url}
            merged[(pname, lv, t)] = r
            nz += lv == "中院"
            nj += lv == "基层"
        print(f"{pname}: 高院页 中院{nz}/基层{nj}", flush=True)
        done_gy.add(pname)
        state["done_gy"] = sorted(done_gy)
        json.dump(state, open(STATE_F, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=0)
        time.sleep(0.5)

    # ---- 2) 中院页 ----
    zy_rows = [r for r in merged.values() if r["level"] == "中院"]
    todo = [r for r in zy_rows if r["url"] not in done_zy]
    print(f"中院页爬取 {len(todo)} 个", flush=True)

    def work(r):
        return r, get_jiceng(fetch(r["url"]))

    with ThreadPoolExecutor(12) as ex:
        for i, (r, jc) in enumerate(ex.map(work, todo)):
            for t, u in jc.items():
                merged[(r["province"], "基层", t)] = {
                    "province": r["province"], "level": "基层", "name": t,
                    "parent": r["name"], "url": u, "text": t,
                    "source_url": r["url"]}
            done_zy.add(r["url"])
            if (i + 1) % 50 == 0:
                state["done_zy"] = sorted(done_zy)
                json.dump(state, open(STATE_F, "w", encoding="utf-8"),
                          ensure_ascii=False, indent=0)
                print(f"  进度 {i+1}/{len(todo)}", flush=True)

    state["done_zy"] = sorted(done_zy)
    json.dump(state, open(STATE_F, "w", encoding="utf-8"),
              ensure_ascii=False, indent=0)
    with open(OUT_F, "w", encoding="utf-8") as f:
        for r in sorted(merged.values(), key=lambda x: (x["province"], x["level"], x["name"])):
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    n_zy = sum(1 for r in merged.values() if r["level"] == "中院")
    n_jc = sum(1 for r in merged.values() if r["level"] == "基层")
    print(f"p62c 完成：中院 {n_zy}，基层 {n_jc}")


if __name__ == "__main__":
    main()
