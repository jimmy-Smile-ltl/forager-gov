# -*- coding: utf-8 -*-
"""P62i: 湖南渲染 tab 模式 + 江西中院子站基层爬取。"""
import json
import os
import re
import shutil
import subprocess
import sys
import time

sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开")
sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开/util")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from p62e_tab_courts import tab_sec_extract  # noqa: E402
from p62c_court_unified import get_jiceng  # noqa: E402

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")


def launch():
    shutil.rmtree("/tmp/xxgk_rs_profile", ignore_errors=True)
    from util.browser_lifecycle import PROJECT_CHROME
    return subprocess.Popen([PROJECT_CHROME, "--headless=new",
                             "--remote-debugging-port=9334",
                             "--user-data-dir=/tmp/xxgk_rs_profile",
                             "--no-sandbox", "--disable-gpu", "--no-first-run",
                             "about:blank"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def get_ws():
    import httpx
    for _ in range(30):
        try:
            r = httpx.get("http://127.0.0.1:9334/json/version", timeout=3)
            if r.status_code == 200:
                return r.json()["webSocketDebuggerUrl"]
        except Exception:
            pass
        time.sleep(1)
    raise RuntimeError("CDP 未就绪")


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


def main():
    merged = {}
    if os.path.exists("court_hierarchy.jsonl"):
        for l in open("court_hierarchy.jsonl", encoding="utf-8"):
            r = json.loads(l)
            merged[(r["province"], r["level"], r["name"])] = r

    # 湖南城市映射
    tree = json.load(open("tree.json", encoding="utf-8"))
    prov_g = next(g for g in tree["ks"] if g["n"].startswith("省级"))
    hn_cm = {}
    for top in next(p for p in prov_g["ks"] if p["n"] == "湖南省").get("ks", []):
        def walk(n):
            if n.get("l") == "市" and n.get("k") == "人民政府":
                base = re.sub(r"(自治州|地区|盟|市)$", "", n["n"])
                hn_cm[base] = (n["n"], n["l"])
            for k in n.get("ks", []):
                walk(k)
        walk(top)

    proc = launch()
    try:
        from DrissionPage import ChromiumPage
        page = ChromiumPage(addr_or_opts=get_ws())
        # 湖南渲染
        page.get("http://hngy.hunancourt.gov.cn/index.shtml")
        time.sleep(10)
        for lv, t, parent, u in tab_sec_extract(page.html, "湖南省", hn_cm):
            if u.startswith("//"):
                u = "http:" + u
            if not u.startswith(("http://", "https://")):
                continue
            merged[("湖南省", lv, t)] = {
                "province": "湖南省", "level": lv, "name": t,
                "parent": parent or "湖南省高级人民法院", "url": u,
                "text": t, "source_url": "hngy render"}
        nz = sum(1 for k in merged if k[0] == "湖南省" and k[1] == "中院")
        nj = sum(1 for k in merged if k[0] == "湖南省" and k[1] == "基层")
        print(f"湖南渲染: 中院{nz}/基层{nj}", flush=True)

        # 江西中院子站 → 基层
        jx_zy = [r for r in merged.values()
                 if r["province"] == "江西省" and r["level"] == "中院"]
        for r in jx_zy:
            try:
                page.get(r["url"])
                time.sleep(6)
                jc = get_jiceng(page.html)
                for t, u in jc.items():
                    merged[("江西省", "基层", t)] = {
                        "province": "江西省", "level": "基层", "name": t,
                        "parent": r["name"], "url": u, "text": t,
                        "source_url": r["url"]}
            except Exception as e:
                print(f"  {r['name']}: 失败 {str(e)[:40]}", flush=True)
        nj = sum(1 for k in merged if k[0] == "江西省" and k[1] == "基层")
        print(f"江西基层: {nj}", flush=True)
    finally:
        subprocess.run(["pkill", "-9", "-f", "remote-debugging-port=9334"])
        time.sleep(2)

    with open("court_hierarchy.jsonl", "w", encoding="utf-8") as f:
        for r in sorted(merged.values(), key=lambda x: (x["province"], x["level"], x["name"])):
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"p62i 完成：中院 {sum(1 for r in merged.values() if r['level']=='中院')}，"
          f"基层 {sum(1 for r in merged.values() if r['level']=='基层')}")


if __name__ == "__main__":
    main()
