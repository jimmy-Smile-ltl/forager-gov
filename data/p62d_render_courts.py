# -*- coding: utf-8 -*-
"""P62d: 缺失省高院/中院浏览器渲染补采（JS 渲染导航）。

目标：辽宁/黑龙江/上海/江西/山东/湖北/西藏/甘肃/宁夏/兵团 10 个高院
     + 河南(20)/湖南(1) 中院页（基层 0）。
渲染后 DOM 跑 seq_extract（同 p62c），并入 court_hierarchy.jsonl。
"""
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

from p57_court_proc_systems import COURTS  # noqa: E402
from p62c_court_unified import seq_extract, get_jiceng  # noqa: E402

EMPTY = ["辽宁省", "黑龙江省", "上海市", "江西省", "山东省", "湖北省",
         "西藏自治区", "甘肃省", "宁夏回族自治区", "新疆生产建设兵团"]


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


def main():
    merged = {}
    if os.path.exists("court_hierarchy.jsonl"):
        for l in open("court_hierarchy.jsonl", encoding="utf-8"):
            r = json.loads(l)
            merged[(r["province"], r["level"], r["name"])] = r

    proc = launch()
    try:
        from DrissionPage import ChromiumPage
        page = ChromiumPage(addr_or_opts=get_ws())

        # 1) 10 个空高院渲染
        for pname in EMPTY:
            gy_url = COURTS[pname]
            try:
                page.get(gy_url)
                time.sleep(10)
                html = page.html
                for lv, t, parent, u in seq_extract(html):
                    if u.startswith("//"):
                        u = "http:" + u
                    if lv == "中院" and len(t) > 14:
                        continue
                    if not u.startswith(("http://", "https://")):
                        continue
                    r = {"province": pname, "level": lv, "name": t,
                         "parent": parent or f"{pname}高级人民法院",
                         "url": u, "text": t, "source_url": gy_url}
                    merged[(pname, lv, t)] = r
                nz = sum(1 for x in merged if x[0] == pname and x[1] == "中院")
                print(f"{pname}: 渲染后 中院 {nz}", flush=True)
            except Exception as e:
                print(f"{pname}: 渲染失败 {str(e)[:50]}", flush=True)

        # 2) 河南/湖南 中院页渲染 → 基层
        zy_todo = [r for r in merged.values() if r["level"] == "中院"
                   and r["province"] in ("河南省", "湖南省")]
        for i, r in enumerate(zy_todo):
            try:
                u = r["url"]
                if u.startswith("//"):
                    u = "http:" + u
                page.get(u)
                time.sleep(8)
                jc = get_jiceng(page.html)
                for t, u in jc.items():
                    merged[(r["province"], "基层", t)] = {
                        "province": r["province"], "level": "基层", "name": t,
                        "parent": r["name"], "url": u, "text": t,
                        "source_url": r["url"]}
                if (i + 1) % 5 == 0:
                    print(f"  中院渲染 {i+1}/{len(zy_todo)}", flush=True)
            except Exception as e:
                print(f"  {r['name']}: 失败 {str(e)[:40]}", flush=True)
    finally:
        subprocess.run(["pkill", "-9", "-f", "remote-debugging-port=9334"])
        time.sleep(2)

    # 清洗：名称过长的中院（新闻标题误入）
    for k in [k for k in merged if k[1] == "中院" and len(k[2]) > 14]:
        del merged[k]
    with open("court_hierarchy.jsonl", "w", encoding="utf-8") as f:
        for r in sorted(merged.values(), key=lambda x: (x["province"], x["level"], x["name"])):
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    n_zy = sum(1 for r in merged.values() if r["level"] == "中院")
    n_jc = sum(1 for r in merged.values() if r["level"] == "基层")
    print(f"p62d 完成：中院 {n_zy}，基层 {n_jc}")


if __name__ == "__main__":
    main()
