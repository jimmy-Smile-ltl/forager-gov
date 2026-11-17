# -*- coding: utf-8 -*-
"""P38: 群团「待核」URL 浏览器渲染验证（p37 的 JS 渲染补充）。

对 verify=uncertain/uncertain_repick 的行：DrissionPage 渲染 → 取渲染后标题+正文
→ 按 p37 的 judge 逻辑重判：通过→render_pass；确凿错误→清空回列名；
仍无证据→保持 uncertain。
用完 SIGKILL 清理 9334 并复验。
"""
import json
import re
import shutil
import subprocess
import sys
import time

sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开")
sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开/util")
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))

from p37_verify_titles import SLOT_KW, WRONG_RE  # noqa: E402


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
    rows = [json.loads(l) for l in open("quntuan_baidu.jsonl", encoding="utf-8")]
    todo = [r for r in rows if r.get("url") and r["verify"].startswith("uncertain")]
    print(f"待渲染验证: {len(todo)} 条", flush=True)
    if not todo:
        return

    proc = launch()
    try:
        from DrissionPage import ChromiumPage
        page = ChromiumPage(addr_or_opts=get_ws())
        changed = 0
        for i, r in enumerate(todo):
            kw = re.compile(SLOT_KW[r["slot"]])
            try:
                page.get(r["url"])
                time.sleep(6)
                title = page.title or ""
                body = page.run_js("return document.body ? "
                                   "document.body.innerText.slice(0,3000) : ''")
                text = title + " " + body
                if kw.search(text):
                    r["verify"] = "render_pass"
                    changed += 1
                elif WRONG_RE.search(text):
                    r["verify"] = "render_fail"
                    r["url"] = ""
                    changed += 1
                else:
                    r["verify"] = "uncertain"   # 仍无证据
                print(f"  {i+1}/{len(todo)} {r['province']} {r['slot']} "
                      f"-> {r['verify']}", flush=True)
            except Exception as e:
                print(f"  {i+1}/{len(todo)} {r['province']} {r['slot']} "
                      f"渲染失败 {str(e)[:40]}", flush=True)
        print(f"渲染验证完成，变更 {changed} 条", flush=True)
    finally:
        subprocess.run(["pkill", "-9", "-f", "remote-debugging-port=9334"])
        time.sleep(2)
        left = subprocess.run(["ps", "aux"], capture_output=True, text=True).stdout
        n = sum(1 for l in left.splitlines()
                if "remote-debugging-port=9334" in l and "grep" not in l)
        print(f"浏览器清理复验: 残留 {n} 个实例", flush=True)

    with open("quntuan_baidu.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    st = json.load(open("quntuan_baidu_state.json", encoding="utf-8"))
    st["rows"] = rows
    st["applied"] = False
    json.dump(st, open("quntuan_baidu_state.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=0)
    hit = sum(1 for r in rows if r["url"])
    print(f"p38 完成：现命中 {hit}")


if __name__ == "__main__":
    main()
