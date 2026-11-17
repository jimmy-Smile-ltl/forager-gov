# -*- coding: utf-8 -*-
"""P62h: 江西站点群专页 + 甘肃法院网群下拉 + 湖南 tab 模式。

江西：/article/webgroup.shtml（图片入口的站点群页）
甘肃：「全省法院网群」隐藏下拉（城市名直链 chinagscourt.gov.cn 子域）
     → 中院子站逐一抓「下辖法院/法院在线」基层
湖南：scrollUl tab + cNN 区块（复用 p62e 提取器）
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

from p62e_tab_courts import tab_sec_extract  # noqa: E402
from p62c_court_unified import seq_extract, get_jiceng  # noqa: E402

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")

GS_CITY = {"兰州": "兰州市", "天水": "天水市", "白银": "白银市", "武威": "武威市",
           "金昌": "金昌市", "张掖": "张掖市", "酒泉": "酒泉市",
           "嘉峪关": "嘉峪关市", "庆阳": "庆阳市", "平凉": "平凉市",
           "定西": "定西市", "陇南": "陇南市", "临夏": "临夏回族自治州",
           "甘南": "甘南藏族自治州"}


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


def main():
    merged = {}
    if os.path.exists("court_hierarchy.jsonl"):
        for l in open("court_hierarchy.jsonl", encoding="utf-8"):
            r = json.loads(l)
            merged[(r["province"], r["level"], r["name"])] = r

    # ---- 江西：站点群专页 ----
    html = fetch("https://jxgy.jxfy.gov.cn/article/webgroup.shtml")
    print("江西站点群页:", len(html))
    for lv, t, parent, u in seq_extract(html):
        if u.startswith("//"):
            u = "http:" + u
        if not u.startswith(("http://", "https://")):
            continue
        merged[("江西省", lv, t)] = {
            "province": "江西省", "level": lv, "name": t,
            "parent": parent or "江西省高级人民法院", "url": u,
            "text": t, "source_url": "webgroup.shtml"}

    # ---- 湖南：tab 模式（静态）----
    tree = json.load(open("tree.json", encoding="utf-8"))
    prov_g = next(g for g in tree["ks"] if g["n"].startswith("省级"))
    hn_cm = {}
    p_hn = next(p for p in prov_g["ks"] if p["n"] == "湖南省")
    for top in p_hn.get("ks", []):
        def walk(n):
            if n.get("l") == "市" and n.get("k") == "人民政府":
                base = re.sub(r"(自治州|地区|盟|市)$", "", n["n"])
                hn_cm[base] = (n["n"], n["l"])
            for k in n.get("ks", []):
                walk(k)
        walk(top)
    html = fetch("http://hngy.hunancourt.gov.cn/index.shtml")
    for lv, t, parent, u in tab_sec_extract(html, "湖南省", hn_cm):
        if u.startswith("//"):
            u = "http:" + u
        if not u.startswith(("http://", "https://")):
            continue
        merged[("湖南省", lv, t)] = {
            "province": "湖南省", "level": lv, "name": t,
            "parent": parent or "湖南省高级人民法院", "url": u,
            "text": t, "source_url": "hngy index"}

    # ---- 甘肃：浏览器渲染（WAF）→ 法院网群下拉 ----
    proc = launch()
    gs_zy = []
    try:
        from DrissionPage import ChromiumPage
        page = ChromiumPage(addr_or_opts=get_ws())
        page.get("https://www.chinagscourt.gov.cn/")
        time.sleep(10)
        html = page.html
        seg = html[html.find("全省法院网群"): html.find("全省法院网群") + 8000] \
            if "全省法院网群" in html else html
        for m in re.finditer(r'<a href="(https://[^"]+)"[^>]*>([^<]{1,8})</a>', seg):
            t = re.sub(r"\s+", "", m.group(2))
            u = m.group(1)
            if t in GS_CITY:
                gs_zy.append((GS_CITY[t] + "中级人民法院", u))
            elif t in ("矿区", "兰铁", "林区"):
                gs_zy.append(({"矿区": "甘肃矿区人民法院", "兰铁": "兰州铁路运输中级法院",
                               "林区": "甘肃省林区中级法院"}[t], u))
        print("甘肃中院:", len(gs_zy))
        # 甘肃中院子站 → 基层
        for nm, u in gs_zy:
            try:
                page.get(u)
                time.sleep(6)
                jc = get_jiceng(page.html)
                for t, ju in jc.items():
                    merged[("甘肃省", "基层", t)] = {
                        "province": "甘肃省", "level": "基层", "name": t,
                        "parent": nm, "url": ju, "text": t, "source_url": u}
            except Exception as e:
                print(f"  {nm}: 子站失败 {str(e)[:40]}", flush=True)
    finally:
        subprocess.run(["pkill", "-9", "-f", "remote-debugging-port=9334"])
        time.sleep(2)

    for nm, u in gs_zy:
        merged[("甘肃省", "中院", nm)] = {
            "province": "甘肃省", "level": "中院", "name": nm,
            "parent": "甘肃省高级人民法院", "url": u, "text": nm,
            "source_url": "chinagscourt 网群"}

    with open("court_hierarchy.jsonl", "w", encoding="utf-8") as f:
        for r in sorted(merged.values(), key=lambda x: (x["province"], x["level"], x["name"])):
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    for p in ("江西省", "湖南省", "甘肃省"):
        nz = sum(1 for k in merged if k[0] == p and k[1] == "中院")
        nj = sum(1 for k in merged if k[0] == p and k[1] == "基层")
        print(f"{p}: 中院 {nz} / 基层 {nj}")
    print(f"p62h 完成：总中院 {sum(1 for r in merged.values() if r['level']=='中院')}，"
          f"总基层 {sum(1 for r in merged.values() if r['level']=='基层')}")


if __name__ == "__main__":
    main()
