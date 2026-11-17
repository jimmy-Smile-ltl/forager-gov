# -*- coding: utf-8 -*-
"""P64: 检察院系统细化 —— 省检察院官网渲染 + 站内扫描找市级院列表页；
市级院官网抓「下辖检察院」基层院。

先跑探测阶段：对 20 个有 URL 的省检察院官网渲染，全站扫描含
「市检察院/基层检察院/检察机关」≥3 的页面，输出候选列表页 URL。
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


def main():
    tree = json.load(open("tree.json", encoding="utf-8"))
    prov_g = next(g for g in tree["ks"] if g["n"].startswith("省级"))
    prov_jc = {}
    for p in prov_g["ks"]:
        par = next((k for k in p.get("ks", []) if k.get("c") == "并列机关"), None)
        if not par:
            continue
        m = next((x for x in par.get("ks", []) if "检察院" in x["n"]), None)
        if m and m.get("u"):
            prov_jc[p["n"]] = m["u"]

    out = {}
    proc = launch()
    try:
        from DrissionPage import ChromiumPage
        page = ChromiumPage(addr_or_opts=get_ws())
        for pname, u in sorted(prov_jc.items()):
            try:
                page.get(u)
                time.sleep(8)
                html = page.html
                host = re.search(r"https?://([^/]+)", u).group(1)
                cands = set()
                for m in re.finditer(r'href="([^"]+)"', html):
                    h = m.group(1)
                    if h.startswith("//"):
                        h = "http:" + h
                    if h.startswith("http"):
                        if host in h:
                            cands.add(h.split("#")[0])
                    elif h.startswith("/"):
                        from urllib.parse import urljoin
                        cands.add(urljoin(u, h))
                hits = []
                for c in sorted(cands)[:20]:
                    try:
                        page.get(c)
                        time.sleep(3)
                        h2 = page.html
                        n = h2.count("检察院")
                        if n >= 8:
                            hits.append((c, n))
                    except Exception:
                        pass
                out[pname] = hits
                print(f"{pname}: 候选列表页 {len(hits)}", flush=True)
                for c, n in hits[:5]:
                    print(f"    {c[:70]} (检察院×{n})", flush=True)
            except Exception as e:
                print(f"{pname}: 失败 {str(e)[:50]}", flush=True)
    finally:
        subprocess.run(["pkill", "-9", "-f", "remote-debugging-port=9334"])
        time.sleep(2)
    json.dump(out, open("jc_list_pages.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=0)
    print("p64a 探测完成")


if __name__ == "__main__":
    main()
