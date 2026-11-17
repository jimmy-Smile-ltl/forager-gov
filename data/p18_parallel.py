# -*- coding: utf-8 -*-
"""P18: 省级并列机关（人大/政协/监委/法院/检察院）门户 URL 采集。

从 31 省门户渲染后首页 footer 提取；省委多数无独立公开门户 → 列名。
输出 prov_parallel.jsonl
"""
import json
import re
import shutil
import subprocess
import sys
import time
from urllib.parse import urlparse

sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开")
sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开/util")
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))

CAT_RE = re.compile(r"(人大|政协|监委|监察委|纪委|法院|检察院|检察)")
EXCLUDE = re.compile(r"(最高|全国|新闻|报告|会议|要闻|工作)")


def main():
    shutil.rmtree("/tmp/xxgk_rs_profile", ignore_errors=True)
    from util.browser_lifecycle import PROJECT_CHROME
    proc = subprocess.Popen([PROJECT_CHROME, "--headless=new", "--remote-debugging-port=9334",
                             "--user-data-dir=/tmp/xxgk_rs_profile", "--no-sandbox", "--disable-gpu",
                             "--no-first-run", "about:blank"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    import httpx
    ws = None
    for _ in range(30):
        try:
            r = httpx.get("http://127.0.0.1:9334/json/version", timeout=3)
            if r.status_code == 200:
                ws = r.json()["webSocketDebuggerUrl"]
                break
        except Exception:
            pass
        time.sleep(1)
    from DrissionPage import ChromiumPage
    page = ChromiumPage(addr_or_opts=ws)

    provs = [json.loads(l) for l in open("province.jsonl", encoding="utf-8")]
    rows = []
    for p in provs:
        pname = p["name"]
        if pname == "新疆生产建设兵团":
            continue
        try:
            page.get(p["portal_url"])
            time.sleep(7)
        except Exception:
            print(f"{pname}: 加载失败", flush=True)
            continue
        try:
            links = page.run_js("""
              return [...document.querySelectorAll('a')].map(a => [
                (a.title||a.innerText||'').trim().replace(/\\s+/g,'').slice(0,24), a.href]);
            """)
        except Exception:
            links = []
        seen = set()
        for text, href in links:
            if not href.startswith(("http", "https")) or ".gov.cn" not in href:
                continue
            if not CAT_RE.search(text) or EXCLUDE.search(text):
                continue
            key = text
            if key in seen:
                continue
            seen.add(key)
            cat = "人大" if "人大" in text else "政协" if "政协" in text else \
                  "监委" if ("监委" in text or "纪委" in text) else \
                  "法院" if "法院" in text else "检察院"
            rows.append({"province": pname, "category": cat, "name": text,
                         "portal_url": href.rstrip("/")})
        print(f"{pname}: {len(seen)} 个并列机关链接", flush=True)

    with open("prov_parallel.jsonl", "w", encoding="utf-8") as f:
        for r in sorted(rows, key=lambda x: (x["province"], x["category"])):
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"总计 {len(rows)} 行", flush=True)

    try:
        page.quit()
    except Exception:
        pass
    time.sleep(2)
    subprocess.run(["pkill", "-9", "-f", "user-data-dir=/tmp/xxgk_rs_profile"])
    time.sleep(3)
    left = subprocess.run(["pgrep", "-f", "user-data-dir=/tmp/xxgk_rs_profile"],
                          capture_output=True, text=True).stdout.strip()
    print("残留:", left if left else "无", flush=True)


if __name__ == "__main__":
    main()
