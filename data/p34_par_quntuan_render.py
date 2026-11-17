# -*- coding: utf-8 -*-
"""P34: 省级群团链接浏览器渲染补采（周末收尾阶段用）。

省门户首页 footer 的群团链接多为 JS 渲染，静态抓取命中为 0。
本脚本：自启独立 CloakBrowser(9334)+DrissionPage 渲染 31 省门户
→ 渲染后 HTML 交给 p33 复用生成（回填 tree 群团组成员 u + 规则）。
用完 SIGKILL 清理浏览器并复验。
"""
import json
import os
import shutil
import subprocess
import sys
import time

sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开")
sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开/util")
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))

SNAP = "/tmp/quntuan_html"


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
    proc = launch()
    try:
        from DrissionPage import ChromiumPage
        page = ChromiumPage(addr_or_opts=get_ws())

        tree = json.load(open("tree.json", encoding="utf-8"))
        prov_g = next(g for g in tree["ks"] if g["n"].startswith("省级"))
        targets = [(p["n"], p.get("u", "")) for p in prov_g["ks"] if p.get("u")]
        os.makedirs(SNAP, exist_ok=True)

        rendered = {}
        for pname, portal in targets:
            try:
                page.get(portal)
                time.sleep(8)
                html = page.html
                if html and len(html) > 20000:
                    rendered[pname] = html
                    with open(f"{SNAP}/{pname}.html", "w", encoding="utf-8") as f:
                        f.write(html)
                    print(f"{pname}: 渲染 OK（{len(html)} 字符）", flush=True)
                else:
                    print(f"{pname}: 渲染异常（{len(html) if html else 0} 字符）", flush=True)
            except Exception as e:
                print(f"{pname}: 渲染失败 {str(e)[:60]}", flush=True)
            time.sleep(2)

        if not rendered:
            print("p34: 无任何渲染成功，中止（不覆盖现有数据）")
            return

        # 交给 p33 复用生成（回填群团组成员 u + 组/成员规则）
        import p33_gen_prov_quntuan as p33
        p33.main(html_override=rendered)
    finally:
        subprocess.run(["pkill", "-9", "-f", "remote-debugging-port=9334"])
        time.sleep(2)
        left = subprocess.run(["ps", "aux"], capture_output=True, text=True).stdout
        n = sum(1 for l in left.splitlines()
                if "remote-debugging-port=9334" in l and "grep" not in l)
        print(f"p34 浏览器清理复验: 残留 {n} 个实例")


if __name__ == "__main__":
    main()
