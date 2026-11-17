# -*- coding: utf-8 -*-
"""P62: 法院系统三级层级爬取（真实 HTML 提取，合规）。

链路：32 省高院官网（最高法官网「全国法院」权威 URL）→「全省中级人民法院」
     下拉/链接（elink.chinacourt.cn base64 编码需解码）→ 各中院官网
     「下辖法院」区块 → 基层法院（区县法院）。
输出 court_hierarchy.jsonl: {province, level(高院/中院/基层), name, parent, url}
断点续跑 court_hierarchy_state.json。
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
STATE_F = "court_hierarchy_state.json"
OUT_F = "court_hierarchy.jsonl"


def decode_elink(h):
    if "elink.chinacourt.cn" in h:
        m = re.search(r"elid=([A-Za-z0-9+/=]+)", h)
        if m:
            try:
                return base64.b64decode(m.group(1) + "==").decode()
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


def get_zhongyuan(html):
    """省高院首页 → 中院链接 {名称: URL}（含全称「XX中级人民法院」）。"""
    out = {}
    for m in re.finditer(r'<option value="([^"]+)"[^>]*>([^<]{2,20}?(?:中院|中级)[^<]{0,10})</option>', html):
        t = re.sub(r"\s+", "", m.group(2))
        if t and ("中院" in t or "中级" in t):
            out[t] = decode_elink(m.group(1))
    for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>([^<]{0,26}?(?:中院|中级人民法院|中级法院)[^<]{0,8})</a>', html):
        t = re.sub(r"\s+", "", m.group(2))
        if t and ("中院" in t or "中级" in t) and len(t) <= 20:
            u = decode_elink(m.group(1))
            # 后出现的（areamap 区块）优先覆盖旧平台 chinacourt.gov.cn 链接
            out[t] = u
    return out


def get_jiceng_on_gy(html):
    """天津/北京模式：高院页面 .jcy 区块内基层法院（全称，无「中级」）。"""
    out = {}
    for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>([^<]{4,22}?人民法院[^<]{0,4})</a>', html):
        t = re.sub(r"\s+", "", m.group(2))
        if not t or "中级" in t or "高级" in t or len(t) > 20:
            continue
        u = decode_elink(m.group(1))
        if t not in out or "chinacourt.gov.cn" not in u:
            out[t] = u
    return out


def get_jiceng(html):
    """中院官网 → 基层法院链接。"""
    out = {}
    i = html.find("下辖法院")
    seg = html[i:i + 8000] if i > 0 else html
    for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>([^<]{2,18}?(?:法院|法庭)[^<]{0,6})</a>', seg):
        t = re.sub(r"\s+", "", m.group(2))
        if not t or "中院" in t or "高院" in t or len(t) > 16:
            continue
        if t.endswith(("法院", "法庭")):
            out[t] = decode_elink(m.group(1))
    return out


def main():
    state = json.load(open(STATE_F, encoding="utf-8")) \
        if os.path.exists(STATE_F) else {}
    done_gy = set(state.get("done_gy", []))
    done_zy = set(state.get("done_zy", []))
    rows = state.get("rows", [])

    # ---- 1. 高院 → 中院 ----
    for pname, gy_url in sorted(COURTS.items()):
        if pname in done_gy:
            continue
        html = fetch(gy_url)
        zy = get_zhongyuan(html)
        print(f"{pname}: 高院 {len(zy)} 个中院", flush=True)
        for t, u in zy.items():
            rows.append({"province": pname, "level": "中院", "name": t,
                         "parent": f"{pname}高级人民法院", "url": u,
                         "text": t, "source_url": gy_url})
        done_gy.add(pname)
        state["done_gy"] = sorted(done_gy)
        state["rows"] = rows
        json.dump(state, open(STATE_F, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=0)
        time.sleep(0.5)

    # ---- 2. 中院 → 基层 ----
    zy_rows = [r for r in rows if r["level"] == "中院"]
    todo = [r for r in zy_rows if r["url"] not in done_zy]
    print(f"中院爬取 {len(todo)} 个", flush=True)

    def work(r):
        html = fetch(r["url"])
        return r, get_jiceng(html)

    with ThreadPoolExecutor(12) as ex:
        for i, (r, jc) in enumerate(ex.map(work, todo)):
            for t, u in jc.items():
                rows.append({"province": r["province"], "level": "基层", "name": t,
                             "parent": r["name"], "url": u, "text": t,
                             "source_url": r["url"]})
            done_zy.add(r["url"])
            if (i + 1) % 50 == 0:
                state["done_zy"] = sorted(done_zy)
                state["rows"] = rows
                json.dump(state, open(STATE_F, "w", encoding="utf-8"),
                          ensure_ascii=False, indent=0)
                print(f"  进度 {i+1}/{len(todo)}，基层累计 "
                      f"{sum(1 for x in rows if x['level'] == '基层')}", flush=True)

    state["done_zy"] = sorted(done_zy)
    state["rows"] = rows
    json.dump(state, open(STATE_F, "w", encoding="utf-8"),
              ensure_ascii=False, indent=0)
    with open(OUT_F, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    n_zy = sum(1 for r in rows if r["level"] == "中院")
    n_jc = sum(1 for r in rows if r["level"] == "基层")
    print(f"p62 完成：中院 {n_zy}，基层 {n_jc}")


if __name__ == "__main__":
    main()
