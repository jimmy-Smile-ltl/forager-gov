# -*- coding: utf-8 -*-
"""P70: 检察院市级院提取 v3 —— gzip 解压 + 「XX市院/分院」文本模式 +
湖南地图模式（map-hd 市 + map-bd 市院/基层院列表）。

通用：anchor 文本匹配 纯市名 / {base}市院 / {base}分院 / 含分院铁检
湖南：hn.jcy.gov.cn 地图区块 link_box_XX：map-hd=市名；
      map-bd 内 title=「XX市人民检察院」（市院，列表第一项）
      +「XX区/县人民检察院」（基层，szylj 介绍页 URL）
输出合并进 jc_shi.jsonl（市级）+ jc_hierarchy.jsonl（基层）。
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


def extract_shi(html, city_names, special_pat):
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
        else:
            # {base}市院 / {base}分院 / {base}地区院
            for full in city_names:
                base = re.sub(r"(自治州|地区|盟|市)$", "", full)
                if len(base) >= 2 and t in (base + "市院", base + "分院",
                                            base + "地区院"):
                    out[full] = u
                    break
    return out


def hn_map_extract(html):
    """湖南地图模式 → (市级院列表, 基层院列表)。"""
    shi, jc = {}, {}
    for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*title="([^"]+)"', html):
        t = re.sub(r"\s+", "", m.group(2))
        u = m.group(1)
        if not t.endswith("人民检察院") or not u.startswith(("http://", "https://")):
            continue
        core = re.sub(r"人民检察院$", "", t)
        if re.search(r"(市|州)人民检察院$", t) and len(core) <= 10:
            shi[core] = u
        elif re.search(r"(区|县|市)人民检察院$", t):
            jc[core] = u
    return shi, jc


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

    shi_rows = []
    for l in open("jc_shi.jsonl", encoding="utf-8"):
        shi_rows.append(json.loads(l))
    have = {(r["province"], r["name"]) for r in shi_rows}

    # 湖南地图
    html = fetch("http://www.hn.jcy.gov.cn/")
    if html:
        s, j = hn_map_extract(html)
        print(f"湖南地图: 市院 {len(s)} / 基层 {len(j)}")
        for core, u in s.items():
            nm = core + ("市" if core in city_sets["湖南省"] else "") + "检察院"
            base = core + ("市" if core.endswith(("市", "州")) else "市")
            nm = core + "检察院" if (core.endswith(("市", "州")) or
                                     core in city_sets["湖南省"]) else core + "市检察院"
            if ("湖南省", nm) not in have:
                shi_rows.append({"province": "湖南省", "name": nm, "url": u,
                                 "source": "map"})
                have.add(("湖南省", nm))
        jc_rows = [json.loads(l) for l in open("jc_hierarchy.jsonl", encoding="utf-8")] \
            if os.path.exists("jc_hierarchy.jsonl") else []
        jc_have = {(r["province"], r["name"]) for r in jc_rows}
        for core, u in j.items():
            nm = core + "人民检察院"
            if ("湖南省", nm) not in jc_have:
                jc_rows.append({"province": "湖南省", "level": "基层",
                                "name": nm, "parent": "湖南省检察院", "url": u,
                                "text": nm, "source_url": "hn map"})
        with open("jc_hierarchy.jsonl", "w", encoding="utf-8") as f:
            for r in jc_rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # 通用重跑（gzip + 市院模式）
    proc = launch()
    try:
        from DrissionPage import ChromiumPage
        page = ChromiumPage(addr_or_opts=get_ws())
        for pname, u in sorted(prov_jc.items()):
            hits = extract_shi(fetch(u), city_sets[pname], special_pat)
            if not hits:
                try:
                    page.get(u)
                    time.sleep(7)
                    hits = extract_shi(page.html, city_sets[pname], special_pat)
                except Exception:
                    hits = {}
            added = 0
            for t, hu in hits.items():
                if (pname, t) in have:
                    continue
                shi_rows.append({"province": pname, "name": t, "url": hu,
                                 "source": "v3"})
                have.add((pname, t))
                added += 1
            if added:
                print(f"{pname}: +{added}", flush=True)
    finally:
        subprocess.run(["pkill", "-9", "-f", "remote-debugging-port=9334"])
        time.sleep(2)

    with open("jc_shi.jsonl", "w", encoding="utf-8") as f:
        for r in shi_rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    from collections import Counter
    print("p70 完成：市级", dict(Counter(r["province"] for r in shi_rows)))


if __name__ == "__main__":
    main()
