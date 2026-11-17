# -*- coding: utf-8 -*-
"""P14: 自启独立 CloakBrowser Chromium + DrissionPage 直连，抓 山东/湖北/安徽 部门列表页。

合规要点（全局浏览器铁律）：
- 只用 PROJECT_CHROME（CloakBrowser 独立 Chromium），专用端口 9334 + 专用 profile
- 一次性会话，结束即 SIGKILL 并复验
- 不触碰 9222/9333 常驻（他人管线资源）
"""
import json
import re
import subprocess
import sys
import time
from urllib.parse import urlparse

sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
from p2_prov_depts import extract_dept_links
from p11b_fix_depts2 import is_junk, resolve_xxgk

PORT = 9334
PROFILE = "/tmp/xxgk_rs_profile"
TARGETS = {
    "山东": ["https://www.shandong.gov.cn/col/col314107/",
             "https://www.shandong.gov.cn/col/col305145/index.html"],
    "湖北": ["https://www.hubei.gov.cn/fbjd/xxgkml/jgzn/dwzz/h5.shtml"],
    "安徽": ["https://www.ah.gov.cn/jgsz/index.html",
             "https://www.ah.gov.cn/public/column/21741?type=2"],
}


def launch_chrome():
    import shutil
    shutil.rmtree(PROFILE, ignore_errors=True)
    exe = None
    sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开")
    from util.browser_lifecycle import PROJECT_CHROME
    exe = PROJECT_CHROME
    proc = subprocess.Popen(
        [exe, "--headless=new", f"--remote-debugging-port={PORT}",
         f"--user-data-dir={PROFILE}", "--no-sandbox", "--disable-gpu",
         "--no-first-run", "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return proc


def get_ws_url():
    import httpx
    for _ in range(30):
        try:
            r = httpx.get(f"http://127.0.0.1:{PORT}/json/version", timeout=3)
            if r.status_code == 200:
                return r.json()["webSocketDebuggerUrl"]
        except Exception:
            pass
        time.sleep(1)
    raise RuntimeError("CDP 未就绪")


def main():
    proc = launch_chrome()
    ws = get_ws_url()
    print("CDP ws:", ws, flush=True)

    from DrissionPage import ChromiumPage
    page = ChromiumPage(addr_or_opts=ws)

    depts = [json.loads(l) for l in open("prov_depts.jsonl", encoding="utf-8")]
    existing = {(r["province"], urlparse(r["portal_url"]).netloc.lower().replace("www.", ""))
                for r in depts if r.get("portal_url")}

    for pname, urls in TARGETS.items():
        for u in urls:
            try:
                page.get(u)
                time.sleep(6)
                html = page.html
            except Exception as e:
                print(pname, u, "ERR", str(e)[:60], flush=True)
                continue
            if not html or len(html) < 2000:
                print(pname, u, "空页面", flush=True)
                continue
            added = 0
            for t, url in extract_dept_links(html, u):
                host = urlparse(url).netloc.lower().replace("www.", "")
                if (pname, host) in existing or not host:
                    continue
                rec = {"name": t, "province": pname, "category": "省政府组成部门/直属机构",
                       "portal_url": url}
                if is_junk(rec):
                    continue
                depts.append(rec)
                existing.add((pname, host))
                added += 1
            print(pname, u[:60], "→ +", added, flush=True)
            if added >= 15:
                break

    # 新部门解析 xxgk（本脚本结束后统一跑；此处仅登记）
    with open("prov_depts.jsonl", "w", encoding="utf-8") as f:
        for r in sorted(depts, key=lambda x: (x["province"], x["name"])):
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # 清理：关页面、杀 Chromium、复验
    try:
        page.quit()
    except Exception:
        pass
    time.sleep(2)
    subprocess.run(["pkill", "-9", "-f", f"user-data-dir={PROFILE}"])
    time.sleep(3)
    left = subprocess.run(["pgrep", "-f", f"user-data-dir={PROFILE}"],
                          capture_output=True, text=True).stdout.strip()
    print("残留进程:", left if left else "无（已清理）", flush=True)


if __name__ == "__main__":
    main()
