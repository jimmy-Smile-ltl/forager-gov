# -*- coding: utf-8 -*-
"""P62e: 法院网「tab+section」模式提取（辽宁式：中院 tab=纯城市名，
基层在 cNN 区块与 mNN tab 按 id 对应）。

流程：渲染 8 个空省高院 → 提取 mNN tab（城市名→中院映射）与 cNN 区块基层
     → 并入 court_hierarchy.jsonl。
"""
import base64
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

from p57_court_proc_systems import COURTS  # noqa: E402

EMPTY = ["辽宁省", "黑龙江省", "江西省", "湖北省", "西藏自治区",
         "甘肃省", "宁夏回族自治区", "新疆生产建设兵团"]


def decode_elink(h):
    if "elink.chinacourt.cn" in h:
        m = re.search(r"elid=([^&\s\"']+)", h)
        if m:
            elid = m.group(1)
            if elid.startswith(("http://", "https://")):
                return elid
            try:
                return base64.urlsafe_b64decode(elid + "==").decode()
            except Exception:
                pass
    return h


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


def tab_sec_extract(html, prov, city_map):
    """tab+section 模式 → [(level, name, parent, url)]。
    city_map: {base名: (全名, level)}。"""
    rows = []
    # 标记收集：tab（mNN value=K）+ section（cNN）
    marks = []
    for m in re.finditer(r'id="m(\d+)"[^>]*value="(\d+)"[^>]*>\s*<a[^>]+href="([^"]+)"[^>]*>([^<]{1,12}?)</a>', html):
        marks.append((m.start(), "tab", int(m.group(2)),
                      re.sub(r"\s+", "", m.group(4)), m.group(3)))
    for m in re.finditer(r'id="c(\d+)"', html):
        marks.append((m.start(), "sec", int(m.group(1)), None, None))
    marks.sort()

    def map_zy(name):
        """tab 名 → (节点名, level)"""
        base = re.sub(r"(市|州|盟|地区)$", "", name)
        if base in city_map and city_map[base][1] == "市":
            return f"{city_map[base][0]}中级人民法院", "市"
        return name + "法院", "省"   # 沈铁/辽河/大连海事 等专门法院

    cur = None
    for pos, kind, idx, tname, href in marks:
        if kind == "tab":
            u = decode_elink(href)
            if not u.startswith(("http://", "https://")):
                continue
            nm, lv = map_zy(tname)
            cur = nm
            rows.append(("中院", nm, None, u))
        else:
            # section cNN：其后到下一个标记之间的 基层 anchors 归 cur
            seg = html[pos: pos + 12000]
            for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>([^<]{2,18}?(?:法院|法庭)[^<]{0,6})</a>', seg):
                t = re.sub(r"\s+", "", m.group(2))
                if len(t) > 16 or "中级" in t or "高级" in t or "中院" in t:
                    continue
                if not t.endswith(("法院", "法庭")):
                    continue
                u = decode_elink(m.group(1))
                if u.startswith(("http://", "https://")) and cur:
                    rows.append(("基层", t, cur, u))
    dedup = {}
    for lv, t, p, u in rows:
        dedup[(lv, t)] = (lv, t, p, u)
    return list(dedup.values())


def main():
    # 城市映射（8 省）
    tree = json.load(open("tree.json", encoding="utf-8"))
    prov_g = next(g for g in tree["ks"] if g["n"].startswith("省级"))
    city_map = {}
    for p in prov_g["ks"]:
        cm = {}
        for top in p.get("ks", []):
            def walk(n):
                if n.get("l") in ("市", "县", "地级区") and n.get("k") == "人民政府":
                    base = re.sub(r"(自治州|地区|盟|市|区|县)$", "", n["n"])
                    cm[base] = (n["n"], n["l"])
                for k in n.get("ks", []):
                    walk(k)
            walk(top)
        city_map[p["n"]] = cm

    merged = {}
    if os.path.exists("court_hierarchy.jsonl"):
        for l in open("court_hierarchy.jsonl", encoding="utf-8"):
            r = json.loads(l)
            merged[(r["province"], r["level"], r["name"])] = r

    proc = launch()
    try:
        from DrissionPage import ChromiumPage
        page = ChromiumPage(addr_or_opts=get_ws())
        for pname in EMPTY:
            try:
                page.get(COURTS[pname])
                time.sleep(10)
                html = page.html
                for lv, t, parent, u in tab_sec_extract(html, pname, city_map[pname]):
                    if u.startswith("//"):
                        u = "http:" + u
                    if not u.startswith(("http://", "https://")):
                        continue
                    merged[(pname, lv, t)] = {
                        "province": pname, "level": lv, "name": t,
                        "parent": parent or f"{pname}高级人民法院",
                        "url": u, "text": t, "source_url": COURTS[pname]}
                nz = sum(1 for k in merged if k[0] == pname and k[1] == "中院")
                nj = sum(1 for k in merged if k[0] == pname and k[1] == "基层")
                print(f"{pname}: tab模式 中院{nz}/基层{nj}", flush=True)
            except Exception as e:
                print(f"{pname}: 失败 {str(e)[:60]}", flush=True)
    finally:
        subprocess.run(["pkill", "-9", "-f", "remote-debugging-port=9334"])
        time.sleep(2)

    with open("court_hierarchy.jsonl", "w", encoding="utf-8") as f:
        for r in sorted(merged.values(), key=lambda x: (x["province"], x["level"], x["name"])):
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    n_zy = sum(1 for r in merged.values() if r["level"] == "中院")
    n_jc = sum(1 for r in merged.values() if r["level"] == "基层")
    print(f"p62e 完成：中院 {n_zy}，基层 {n_jc}")


if __name__ == "__main__":
    main()
