# -*- coding: utf-8 -*-
"""P64b: 检察院基层院提取。

1) 直辖市（京津沪渝）：市检察院官网渲染 → 区县检察院链接（子路径/独立子域）
2) 市级检察院官网（p40 已验证 300+）：抓「下辖检察院/基层检察院」区块
   → 县级检察院（文本含 区/县/市 检察院，.jcy.gov.cn 域名）
输出 jc_hierarchy.jsonl: {province, level(市/基层), name, parent, url}
断点续跑 jc_hierarchy_state.json。
"""
import json
import os
import re
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开")
sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开/util")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
STATE_F = "jc_hierarchy_state.json"
OUT_F = "jc_hierarchy.jsonl"
MUNICIPAL = {"北京市", "天津市", "上海市", "重庆市"}


def fetch(u):
    try:
        r = subprocess.run(["curl", "-s", "-L", "--max-time", "18", "-A", UA, u],
                           capture_output=True, timeout=22)
        raw = r.stdout
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            return raw.decode("gb18030", errors="replace")
    except Exception:
        return ""


def get_jiceng(html):
    """市级院页面 → 基层检察院 {名: URL}（区/县 检察院，jcy 域名）。"""
    out = {}
    for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>\s*([^<]{2,26}?)\s*</a>', html):
        t = re.sub(r"\s+", "", m.group(2))
        u = m.group(1)
        if not u.startswith(("http://", "https://")) or len(t) > 24:
            continue
        if not t.endswith("检察院"):
            continue
        if "省" in t or "最高" in t or "分院" in t:
            continue
        # 区县检察院：名称含 区/县/市/旗/自治
        if re.search(r"(区|县|旗|自治县|自治旗|市)检察院$", t):
            if ".jcy.gov.cn" in u or ".jc.gov.cn" in u:
                out[t] = u
    return out


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
    state = json.load(open(STATE_F, encoding="utf-8")) \
        if os.path.exists(STATE_F) else {}
    done = set(state.get("done", []))
    rows = state.get("rows", [])

    # ---- 直辖市：区县院 ----
    tree = json.load(open("tree.json", encoding="utf-8"))
    prov_g = next(g for g in tree["ks"] if g["n"].startswith("省级"))
    muni_urls = {}
    for p in prov_g["ks"]:
        if p["n"] not in MUNICIPAL:
            continue
        par = next((k for k in p.get("ks", []) if k.get("c") == "并列机关"), None)
        m = next((x for x in par.get("ks", []) if "检察院" in x["n"]), None)
        if m and m.get("u"):
            muni_urls[p["n"]] = m["u"]

    proc = launch()
    try:
        from DrissionPage import ChromiumPage
        page = ChromiumPage(addr_or_opts=get_ws())
        for pname, u in sorted(muni_urls.items()):
            if pname in done:
                continue
            try:
                page.get(u)
                time.sleep(9)
                html = page.html
                pat = re.compile(r'<a[^>]+href="([^"]+)"[^>]*>\s*([^<]{2,26}?(?:检察院|检察)[^<]{0,4})\s*</a>')
                seen = set()
                for m in pat.finditer(html):
                    t = re.sub(r"\s+", "", m.group(2))
                    hu = m.group(1)
                    if not hu.startswith(("http://", "https://")):
                        from urllib.parse import urljoin
                        hu = urljoin(u, hu)
                    if t in seen or len(t) > 24 or not t.endswith("检察院"):
                        continue
                    if re.search(r"(区|县)检察院$", t) and ".jcy.gov.cn" in hu:
                        seen.add(t)
                        rows.append({"province": pname, "level": "基层",
                                     "name": t, "parent": f"{pname}检察院",
                                     "url": hu, "text": t, "source_url": u})
                done.add(pname)
                state["done"] = sorted(done)
                state["rows"] = rows
                json.dump(state, open(STATE_F, "w", encoding="utf-8"),
                          ensure_ascii=False, indent=0)
                print(f"{pname}: 区县院 {len(seen)}", flush=True)
            except Exception as e:
                print(f"{pname}: 失败 {str(e)[:50]}", flush=True)
    finally:
        subprocess.run(["pkill", "-9", "-f", "remote-debugging-port=9334"])
        time.sleep(2)

    # ---- 市级院 → 基层 ----
    p40 = json.load(open("p40_state.json", encoding="utf-8"))
    shi = [h for h in p40.get("hits", [])
           if h.get("verified") and h.get("level") == "市"
           and h["province"] not in MUNICIPAL]
    todo = [h for h in shi if h["url"] not in done]
    print(f"市级院基层提取 {len(todo)} 个", flush=True)

    def work(h):
        return h, get_jiceng(fetch(h["url"]))

    with ThreadPoolExecutor(10) as ex:
        for i, (h, jc) in enumerate(ex.map(work, todo)):
            for t, u in jc.items():
                rows.append({"province": h["province"], "level": "基层",
                             "name": t, "parent": h["name"], "url": u,
                             "text": t, "source_url": h["url"]})
            done.add(h["url"])
            if (i + 1) % 50 == 0:
                state["done"] = sorted(done)
                state["rows"] = rows
                json.dump(state, open(STATE_F, "w", encoding="utf-8"),
                          ensure_ascii=False, indent=0)
                print(f"  进度 {i+1}/{len(todo)}，基层累计 "
                      f"{sum(1 for r in rows if r['level']=='基层')}", flush=True)

    state["done"] = sorted(done)
    state["rows"] = rows
    json.dump(state, open(STATE_F, "w", encoding="utf-8"),
              ensure_ascii=False, indent=0)
    with open(OUT_F, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"p64b 完成：基层 {sum(1 for r in rows if r['level']=='基层')}")


if __name__ == "__main__":
    main()
