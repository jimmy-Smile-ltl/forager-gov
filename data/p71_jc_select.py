# -*- coding: utf-8 -*-
"""P71: 检察院「省内链接」select 下拉模式提取（江西式）。

模式：<select name="--XX市院--"> 下拉框：第一个 http option = 市级院，
      后续 options = 该市区县院/专门院（文本 XX区院/XX县院/XX地区院/
      铁路运输检察院）；南铁分院/派出院 select = 专门检察院。
对 32 省重跑（静态 gzip + 渲染兜底）。
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


def fetch(u):
    try:
        r = subprocess.run(["curl", "-s", "--compressed", "-L", "--max-time", "18",
                            "-A", UA, u], capture_output=True, timeout=22)
        raw = r.stdout
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            return raw.decode("gb18030", errors="replace")
    except Exception:
        return ""


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


def select_extract(html):
    """select 模式 → (市级 {名: URL}, 基层 {名: URL}, 专门 {名: URL})。"""
    shi, jc, spec = {}, {}, {}
    for m in re.finditer(r'<select[^>]*name="--([^"]+)--"[^>]*>(.*?)</select>', html, re.S):
        grp = m.group(1)
        body = m.group(2)
        opts = re.findall(r'<option[^>]*value="(https?://[^"]+)"[^>]*>\s*([^<]{2,24}?)\s*</option>', body)
        if not opts:
            continue
        if "分院" in grp or "派出" in grp:
            for u, t in opts:
                spec[re.sub(r"\s+", "", t)] = u
            continue
        for i, (u, t) in enumerate(opts):
            t = re.sub(r"\s+", "", t)
            if i == 0:
                shi[t] = u
            else:
                jc[t] = u
    return shi, jc, spec


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

    shi_rows = [json.loads(l) for l in open("jc_shi.jsonl", encoding="utf-8")]
    have_shi = {(r["province"], r["name"]) for r in shi_rows}
    jc_rows = [json.loads(l) for l in open("jc_hierarchy.jsonl", encoding="utf-8")]
    have_jc = {(r["province"], r["name"]) for r in jc_rows}

    proc = launch()
    try:
        from DrissionPage import ChromiumPage
        page = ChromiumPage(addr_or_opts=get_ws())
        for pname, u in sorted(prov_jc.items()):
            html = fetch(u)
            s, j, sp = select_extract(html)
            if not s and not j:
                try:
                    page.get(u)
                    time.sleep(7)
                    s, j, sp = select_extract(page.html)
                except Exception:
                    s, j, sp = {}, {}, {}
            n_add = 0
            for t, hu in s.items():
                if (pname, t) not in have_shi:
                    shi_rows.append({"province": pname, "name": t, "url": hu,
                                     "source": "select"})
                    have_shi.add((pname, t))
                    n_add += 1
            for t, hu in {**j, **sp}.items():
                if (pname, t) not in have_jc:
                    jc_rows.append({"province": pname, "level": "基层",
                                    "name": t, "parent": pname, "url": hu,
                                    "text": t, "source_url": u})
                    have_jc.add((pname, t))
            if n_add:
                print(f"{pname}: 市级 +{n_add}，基层累计 {len(jc_rows)}", flush=True)
    finally:
        subprocess.run(["pkill", "-9", "-f", "remote-debugging-port=9334"])
        time.sleep(2)

    with open("jc_shi.jsonl", "w", encoding="utf-8") as f:
        for r in shi_rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open("jc_hierarchy.jsonl", "w", encoding="utf-8") as f:
        for r in jc_rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"p71 完成：市级 {len(shi_rows)}，基层 {len(jc_rows)}")


if __name__ == "__main__":
    main()
