# -*- coding: utf-8 -*-
"""P75: 市级/区级人大提取（省人大官网「各区人大/市县人大」区块）。

模式：区块内 <a>（纯地名/区名 anchor）+ 纯文本地名（无官网 → 列名，仍展示）；
四川特别：js/map.js 的 cityLinkMap JSON 配置（21 市州全量）。
直辖市→区人大；省→市人大。断点续跑 rd_shi_state.json。
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
MUNICIPAL = {"北京市", "天津市", "上海市", "重庆市"}
STATE_F = "rd_shi_state.json"
OUT_F = "rd_shi.jsonl"
BLOCK_RE = re.compile(r"(各区人大|区人大|市县人大|各市人大|市人大网站|地方人大)")


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


def extract(html, names):
    """区块内：链接地名 + 纯文本地名（无链接→列名）。
    names: {全名, base名} 集合。返回 {全名: url(或"")}。"""
    out = {}
    # 链接地名
    for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>\s*([^<]{2,16}?)\s*</a>', html):
        t = re.sub(r"\s+", "", m.group(2))
        u = m.group(1)
        if not u.startswith(("http://", "https://")):
            continue
        full = match_name(t, names)
        if full and full not in out:
            out[full] = u
    # 纯文本地名（区块文本中，无链接也列名）
    text = re.sub(r"<[^>]+>", "|", html)
    for nm, base in names:
        if nm not in out and (base in text or nm in text):
            out[nm] = ""
    return out


def match_name(t, names):
    t2 = re.sub(r"人大常委会$|人大$|人民代表大会常务委员会$", "", t)
    for nm, base in names:
        if t == nm or t == base or t2 == nm or t2 == base:
            return nm
    return None


def sc_mapjs(html):
    """四川 map.js：提取 cityLinkMap JSON。"""
    m = re.search(r'cityLinkMap\s*=\s*(\{.*?\})\s*;', html, re.S)
    if not m:
        return {}
    raw = m.group(1)
    pairs = re.findall(r'"([^"]+)":\s*"([^"]+)"', raw)
    return dict(pairs)


def main():
    tree = json.load(open("tree.json", encoding="utf-8"))
    prov_g = next(g for g in tree["ks"] if g["n"].startswith("省级"))
    prov_rd = {}
    for p in prov_g["ks"]:
        par = next((k for k in p.get("ks", []) if k.get("c") == "并列机关"), None)
        if not par:
            continue
        m = next((x for x in par.get("ks", []) if "人大" in x["n"]), None)
        if m and m.get("u"):
            prov_rd[p["n"]] = m["u"]

    # 各省下级地名（直辖市→区；省→市）
    name_sets = {}
    for p in prov_g["ks"]:
        lv = "地级区" if p["n"] in MUNICIPAL else "市"
        s = []
        for top in p.get("ks", []):
            def walk(n):
                if n.get("l") == lv and n.get("k") == "人民政府":
                    base = re.sub(r"(自治州|地区|盟|市|区|县)$", "", n["n"])
                    s.append((n["n"], base))
                for k in n.get("ks", []):
                    walk(k)
            walk(top)
        name_sets[p["n"]] = s

    state = json.load(open(STATE_F, encoding="utf-8")) \
        if os.path.exists(STATE_F) else {}
    done = set(state.get("done", []))
    rows = state.get("rows", [])

    # 四川特别：map.js
    if "四川省" not in done:
        html = fetch("https://www.scspc.gov.cn/js/map.js?v=7")
        cm = sc_mapjs(html)
        print(f"四川 map.js: {len(cm)} 市州")
        for nm, u in cm.items():
            if nm in name_sets["四川省"] or \
               any(b == nm for b, _ in name_sets["四川省"]):
                rows.append({"province": "四川省", "name": nm, "url": u,
                             "listed": bool(u)})
        done.add("四川省")
        state["done"] = sorted(done)
        state["rows"] = rows
        json.dump(state, open(STATE_F, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=0)

    proc = launch()
    try:
        from DrissionPage import ChromiumPage
        page = ChromiumPage(addr_or_opts=get_ws())
        for pname, u in sorted(prov_rd.items()):
            if pname in done:
                continue
            try:
                page.get(u)
                time.sleep(7)
                html = page.html
                hits = extract(html, name_sets[pname])
                if not hits:
                    # 兜底：静态
                    hits = extract(fetch(u), name_sets[pname])
                for nm, hu in hits.items():
                    rows.append({"province": pname, "name": nm, "url": hu,
                                 "listed": bool(hu)})
                done.add(pname)
                state["done"] = sorted(done)
                state["rows"] = rows
                json.dump(state, open(STATE_F, "w", encoding="utf-8"),
                          ensure_ascii=False, indent=0)
                n_listed = sum(1 for r in rows if r["province"] == pname
                               and r["listed"])
                print(f"{pname}: {len(hits)} 个（{n_listed} 有官网）", flush=True)
            except Exception as e:
                print(f"{pname}: 失败 {str(e)[:50]}", flush=True)
                done.add(pname)
    finally:
        subprocess.run(["pkill", "-9", "-f", "remote-debugging-port=9334"])
        time.sleep(2)

    state["done"] = sorted(done)
    state["rows"] = rows
    json.dump(state, open(STATE_F, "w", encoding="utf-8"),
              ensure_ascii=False, indent=0)
    with open(OUT_F, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    n_listed = sum(1 for r in rows if r["listed"])
    print(f"p75 完成：{len(rows)} 个市级人大（{n_listed} 有官网，"
          f"其余列名展示）")


if __name__ == "__main__":
    main()
