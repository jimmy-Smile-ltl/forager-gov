# -*- coding: utf-8 -*-
"""P60: 证监会派出机构 / 移民局边检总站 / 自然资源督察局 —— 浏览器渲染提取。

csrc.gov.cn 派出机构下拉、nia.gov.cn 组织机构、mnr.gov.cn 派出机构均为 JS 渲染，
CloakBrowser+DrissionPage 渲染后提取真实链接；未出现者列名（不猜域名）。
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
    targets = [
        ("csrc", "http://www.csrc.gov.cn/", r"(证监局|监管局|专员办)"),
        ("nia", "https://www.nia.gov.cn/", r"(边检总站|出入境边防)"),
        ("mnr", "http://www.mnr.gov.cn/", r"(督察局)"),
    ]
    out = {}
    proc = launch()
    try:
        from DrissionPage import ChromiumPage
        page = ChromiumPage(addr_or_opts=get_ws())
        for key, url, kw in targets:
            try:
                page.get(url)
                time.sleep(10)
                rows = page.run_js("""
                  const out = [];
                  const seen = new Set();
                  document.querySelectorAll('a, select option').forEach(a => {
                    const t = (a.getAttribute('title') || a.textContent || '').trim()
                              .replace(/\\s+/g,'');
                    const h = a.href || a.value || '';
                    const k = t + '|' + h;
                    if (t && h.startsWith('http') && !seen.has(k)) { seen.add(k); out.push([t,h]); }
                  });
                  return out;
                """)
                pat = re.compile(kw)
                hits = {}
                for t, h in rows:
                    if pat.search(t) and len(t) <= 24:
                        hits[t] = h
                out[key] = hits
                print(f"{key}: {len(hits)} 个机构", flush=True)
                for t in list(hits)[:6]:
                    print(f"   {t} -> {hits[t][:70]}", flush=True)
            except Exception as e:
                print(f"{key}: 渲染失败 {str(e)[:50]}", flush=True)
                out[key] = {}
    finally:
        subprocess.run(["pkill", "-9", "-f", "remote-debugging-port=9334"])
        time.sleep(2)
    json.dump(out, open("vertical3_render.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=0)
    print("p60 完成")


if __name__ == "__main__":
    main()
