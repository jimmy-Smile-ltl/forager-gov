# -*- coding: utf-8 -*-
"""P16: 浏览器渲染版厅局重采 —— 从渲染后首页的「部门网站」容器整体提取。

容器判定：span/div 文本匹配 (部门网站|委办局|厅局网站|政府部门|组成部门)，
取其容器内全部 .gov.cn 链接；兜底：全页宽松部门名链接。
自启独立 CloakBrowser(9334)+DrissionPage，用完 SIGKILL 复验。
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

from p13_reattribute import detect_province  # noqa: E402

LOOSE_NAME = re.compile(r"^(省|市|自治区)?[^，。|、（）]{1,12}?(委员会|办公厅|办公室|厅|局|委|办|中心|管委会|执法队|总队)$")
BAD_TAIL = re.compile(r"(区|县|市|州|盟|旗|苏木)$")
CENTRAL_PREFIX = re.compile(r"^(国家|国务院|中央|中国|全国)")
CONTAINER_TXT = re.compile(r"(部门网站|委办局|厅局网站|政府部门|组成部门|直属机构网站|市政府机构)")


def launch():
    shutil.rmtree("/tmp/xxgk_rs_profile", ignore_errors=True)
    from util.browser_lifecycle import PROJECT_CHROME
    return subprocess.Popen([PROJECT_CHROME, "--headless=new", "--remote-debugging-port=9334",
                             "--user-data-dir=/tmp/xxgk_rs_profile", "--no-sandbox", "--disable-gpu",
                             "--no-first-run", "about:blank"],
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
    proc = launch()
    from DrissionPage import ChromiumPage
    page = ChromiumPage(addr_or_opts=get_ws())

    provs = [json.loads(l) for l in open("province.jsonl", encoding="utf-8")]
    depts = [json.loads(l) for l in open("prov_depts.jsonl", encoding="utf-8")]
    existing_urls = {r["portal_url"].rstrip("/") for r in depts if r.get("portal_url")}
    existing_hosts = {urlparse(r["portal_url"]).netloc.lower().replace("www.", "")
                      for r in depts if r.get("portal_url")}

    def dept_count(pname):
        return sum(1 for r in depts if r["province"] == pname)

    # 目标：厅局数 < 34 的省
    targets = [p for p in provs if p["name"] != "新疆生产建设兵团"
               and dept_count(p["name"]) < 34]

    for p in targets:
        pname, portal = p["name"], p["portal_url"]
        try:
            page.get(portal)
            time.sleep(7)
        except Exception as e:
            print(f"{pname}: 加载失败 {str(e)[:50]}", flush=True)
            continue
        # 容器提取
        try:
            hits = page.run_js(f"""
              const out = new Set();
              const spans = [...document.querySelectorAll('span,div,h3')].filter(
                el => /(部门网站|委办局|厅局网站|政府部门|组成部门|直属机构|政府机构)/.test(el.innerText||'') && el.innerText.length < 30);
              for (const s of spans) {{
                let box = s.parentElement;
                for (let i=0;i<4 && box;i++){{
                  const as = box.querySelectorAll('a');
                  if (as.length >= 8) {{
                    as.forEach(a => {{
                      if (a.href && a.href.includes('.gov.cn'))
                        out.add(JSON.stringify([(a.title||a.innerText||'').trim().replace(/\\s+/g,''), a.href]));
                    }});
                    break;
                  }}
                  box = box.parentElement;
                }}
              }}
              return [...out];
            """)
        except Exception:
            hits = []
        # 兜底：全页宽松链接
        try:
            all_links = page.run_js("""
              return [...document.querySelectorAll('a')].map(a => [(a.title||a.innerText||'').trim().replace(/\\s+/g,''), a.href]);
            """)
        except Exception:
            all_links = []
        for text, href in all_links:
            if (text and LOOSE_NAME.match(text) and not BAD_TAIL.search(text)
                    and not CENTRAL_PREFIX.match(text) and href.startswith(("http", "https"))):
                hits.append([text, href])

        added = 0
        seen = set()
        for item in hits:
            try:
                name, href = json.loads(item)
            except Exception:
                continue
            u = href.rstrip("/")
            if not u.startswith("http") or not ".gov.cn" in urlparse(u).netloc:
                continue
            if u in existing_urls or urlparse(u).netloc.lower().replace("www.", "") in existing_hosts:
                continue
            det = detect_province(u)
            if det and det != pname:
                continue
            if CENTRAL_PREFIX.match(name) or BAD_TAIL.search(name) or not name:
                continue
            if (pname, u) in seen:
                continue
            seen.add((pname, u))
            depts.append({"name": name, "province": pname,
                          "category": "省政府组成部门/直属机构", "portal_url": u})
            existing_urls.add(u)
            existing_hosts.add(urlparse(u).netloc.lower().replace("www.", ""))
            added += 1
        print(f"{pname}: +{added} → 共 {dept_count(pname)}", flush=True)

    with open("prov_depts.jsonl", "w", encoding="utf-8") as f:
        for r in sorted(depts, key=lambda x: (x["province"], x["name"])):
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"厅局总数: {len(depts)}", flush=True)

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
