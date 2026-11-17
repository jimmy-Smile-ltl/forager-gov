# -*- coding: utf-8 -*-
"""P67: 省检察院官网「市州分院」区块提取市级检察院（纯市名 anchor 模式）。

对 32 省级单位：静态抓取 + 浏览器渲染兜底 → 全页找 anchor 文本精确等于
tree 市/州/盟名（或 base 名）且 href 为 http 链接 → 市级检察院。
专门检察院（铁路运输分院/分院）文本含 分院/铁检 → 同样收录。
输出 jc_shi.jsonl；断点续跑 jc_shi_state.json。
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
STATE_F = "jc_shi_state.json"
OUT_F = "jc_shi.jsonl"


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


def extract_shi(html, city_names, special_pat):
    """全页提取：文本=市名 或 含分院/铁检 → {名: URL}。"""
    out = {}
    for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>\s*([^<]{2,24}?)\s*</a>', html):
        t = re.sub(r"\s+", "", m.group(2))
        u = m.group(1)
        if not u.startswith(("http://", "https://")) or len(t) > 24:
            continue
        if t in city_names:
            out[t] = u
        elif special_pat.search(t):
            out[t] = u
    return out


def main():
    tree = json.load(open("tree.json", encoding="utf-8"))
    prov_g = next(g for g in tree["ks"] if g["n"].startswith("省级"))
    special_pat = re.compile(r"(分院|铁检|铁路运输检察)")

    prov_jc = {}
    for p in prov_g["ks"]:
        par = next((k for k in p.get("ks", []) if k.get("c") == "并列机关"), None)
        if not par:
            continue
        m = next((x for x in par.get("ks", []) if "检察院" in x["n"]), None)
        if m and m.get("u"):
            prov_jc[p["n"]] = m["u"]

    # 各省市名集合
    city_sets = {}
    for p in prov_g["ks"]:
        names = set()
        for top in p.get("ks", []):
            def walk(n):
                if n.get("l") == "市" and n.get("k") == "人民政府":
                    names.add(n["n"])
                    names.add(re.sub(r"(自治州|地区|盟|市)$", "", n["n"]))
                for k in n.get("ks", []):
                    walk(k)
            walk(top)
        city_sets[p["n"]] = names

    state = json.load(open(STATE_F, encoding="utf-8")) \
        if os.path.exists(STATE_F) else {}
    done = set(state.get("done", []))
    rows = state.get("rows", [])

    # 静态先跑
    for pname, u in sorted(prov_jc.items()):
        if pname in done:
            continue
        hits = extract_shi(fetch(u), city_sets[pname], special_pat)
        if hits:
            for t, hu in hits.items():
                rows.append({"province": pname, "name": t, "url": hu,
                             "source": "static"})
            done.add(pname)
            state["done"] = sorted(done)
            state["rows"] = rows
            json.dump(state, open(STATE_F, "w", encoding="utf-8"),
                      ensure_ascii=False, indent=0)
            print(f"{pname}: {len(hits)} 个市级院（静态）", flush=True)

    # 渲染兜底
    proc = launch()
    try:
        from DrissionPage import ChromiumPage
        page = ChromiumPage(addr_or_opts=get_ws())
        for pname, u in sorted(prov_jc.items()):
            if pname in done:
                continue
            try:
                page.get(u)
                time.sleep(8)
                hits = extract_shi(page.html, city_sets[pname], special_pat)
                for t, hu in hits.items():
                    rows.append({"province": pname, "name": t, "url": hu,
                                 "source": "render"})
                done.add(pname)
                state["done"] = sorted(done)
                state["rows"] = rows
                json.dump(state, open(STATE_F, "w", encoding="utf-8"),
                          ensure_ascii=False, indent=0)
                print(f"{pname}: {len(hits)} 个市级院（渲染）", flush=True)
            except Exception as e:
                print(f"{pname}: 失败 {str(e)[:40]}", flush=True)
                done.add(pname)
    finally:
        subprocess.run(["pkill", "-9", "-f", "remote-debugging-port=9334"])
        time.sleep(2)

    with open(OUT_F, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    from collections import Counter
    print("p67 完成：", dict(Counter(r["province"] for r in rows)))


if __name__ == "__main__":
    main()
