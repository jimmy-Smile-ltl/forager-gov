# -*- coding: utf-8 -*-
"""P20 v2: 官网原始顺序采集（按与已有厅局清单匹配度选容器，URL 优先匹配）。"""
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
    depts = [json.loads(l) for l in open("prov_depts.jsonl", encoding="utf-8")]
    url_to_dept = {}
    host_to_dept = {}
    for r in depts:
        if not r.get("portal_url"):
            continue
        u = r["portal_url"].rstrip("/")
        url_to_dept.setdefault(u, r)
        h = urlparse(u).netloc.lower().replace("www.", "")
        host_to_dept.setdefault(h, r)

    order_map = {}
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
            containers = page.run_js("""
              const boxes = [];
              const seen = new Set();
              const spans = [...document.querySelectorAll('span,div,h3')].filter(
                el => /(部门网站|委办局|厅局网站|政府部门|组成部门|直属机构|政府机构)/.test(el.innerText||'') && el.innerText.length < 30);
              for (const s of spans) {
                let box = s.parentElement;
                for (let i=0;i<4 && box;i++){
                  const as = box.querySelectorAll('a');
                  if (as.length >= 8 && !seen.has(box)) {
                    seen.add(box);
                    boxes.push([...as].map((a,idx) =>
                      [(a.title||a.innerText||'').trim().replace(/\\s+/g,''), a.href, idx]));
                    break;
                  }
                  box = box.parentElement;
                }
              }
              return boxes;
            """)
        except Exception:
            containers = []
        best, best_score = None, -1
        for clist in containers:
            score = 0
            for name, href, idx in clist:
                u = href.rstrip("/")
                if u in url_to_dept or urlparse(href).netloc.lower().replace("www.", "") in host_to_dept:
                    score += 1
            if score > best_score:
                best, best_score = clist, score
        if best:
            for name, href, idx in best:
                u = href.rstrip("/")
                r = url_to_dept.get(u) or host_to_dept.get(urlparse(href).netloc.lower().replace("www.", ""))
                if r and idx < r.get("order", 999):
                    order_map[id(r)] = idx
        print(f"{pname}: 容器{len(containers)} 最优匹配 {best_score}", flush=True)

    for r in depts:
        r["order"] = order_map.get(id(r), r.get("order", 999))
    with open("prov_depts.jsonl", "w", encoding="utf-8") as f:
        for r in depts:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    matched = sum(1 for r in depts if r.get("order", 999) < 999)
    print(f"顺序匹配: {matched}/{len(depts)}", flush=True)

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
