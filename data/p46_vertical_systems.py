# -*- coding: utf-8 -*-
"""P46: 垂直管理系统（条条）机构站点采集。

系统与域名规律（实测）：
  税务：{py}.chinatax.gov.cn          —— 省级 36+兵团（市级多无独立域→列名）
  邮政：{py}.spb.gov.cn               —— 省 36 + 市 333（无 www）
  烟草：{py}.tobacco.gov.cn (http)    —— 省 36 + 市 333
  人行：{py}.pbc.gov.cn               —— 市 333（省会=省分行所在地）
  铁路：18 铁路局集团公司（无独立官网→列名，总局 china-railway.com.cn）
  金融监管：总局 nfra.gov.cn；派出机构（省局）多无独立网站→列名
  海关：42 直属海关（p23 已有 DNS 探测数据，此处复用）
命中后 curl GET + 标题关键词验证。
运行：uv run --with pypinyin python p46_vertical_systems.py
"""
import json
import os
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from p40_jcy_pinyin import pinyin_of  # noqa: E402

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
STATE_F = "vertical_state.json"
OUT_F = "vertical_systems.jsonl"

# 系统配置：key / 显示名 / 域名模板(省,市) / 标题关键词 / 层级
SYSTEMS = {
    "tax":  ("税务系统", "{py}.chinatax.gov.cn", None, "税务", "省"),
    "spb":  ("邮政系统", "{py}.spb.gov.cn", "{py}.spb.gov.cn", "邮政", "省市"),
    "tobacco": ("烟草系统", "{py}.tobacco.gov.cn", "{py}.tobacco.gov.cn", "烟草", "省市"),
    "pbc":  ("人民银行系统", None, "{py}.pbc.gov.cn", "人民银行", "市"),
}


def probe(domain, scheme):
    u = f"{scheme}://{domain}/"
    try:
        r = subprocess.run(["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
                            "-L", "--max-time", "6", "-A", UA, u],
                           capture_output=True, text=True, timeout=10)
        code = r.stdout.strip()
        return code and code != "000", u
    except Exception:
        return False, ""


def title_ok(url, kw):
    try:
        r = subprocess.run(["curl", "-s", "-L", "--max-time", "10", "-A", UA, url],
                           capture_output=True, text=True, timeout=15)
        raw = r.stdout[:60000]
        m = re.search(r"charset=[\"']?\s*([a-zA-Z0-9_-]+)", raw[:2000], re.I)
        enc = (m.group(1).lower() if m else "")
        txt = raw if not enc or "utf" in enc else raw.encode("utf-8", "ignore").decode("utf-8", "ignore")
        return kw in txt[:20000]
    except Exception:
        return False


def prov_variants(p):
    """省级域名词干变体：全拼 + 每字首字母缩写（省域惯例 gd/gz/xj）。"""
    if p == "新疆生产建设兵团":
        return ["xjbt"]
    if p == "陕西省":
        return ["shaanxi", "sx"]
    if p == "山西省":
        return ["sx", "shanxi"]
    from pypinyin import lazy_pinyin
    core = re.sub(r"(维吾尔|壮族|回族)?自治区$|省$|市$", "", p)
    full = "".join(lazy_pinyin(core))
    initials = "".join(s[0] for s in lazy_pinyin(core))
    variants = [full]
    if initials != full and initials not in variants:
        variants.append(initials)
    return variants


def load_units():
    """省级（含兵团）+ 地级市列表。"""
    tree = json.load(open("tree.json", encoding="utf-8"))
    prov_g = next(g for g in tree["ks"] if g["n"].startswith("省级"))
    provs = [p["n"] for p in prov_g["ks"]]
    cities = []
    for p in prov_g["ks"]:
        for top in p.get("ks", []):
            def walk(n):
                if n.get("l") == "市" and n.get("k") == "人民政府" and n.get("cd"):
                    cities.append({"province": p["n"], "name": n["n"]})
                for k in n.get("ks", []):
                    walk(k)
            walk(top)
    return provs, cities


def main():
    provs, cities = load_units()
    state = json.load(open(STATE_F, encoding="utf-8")) \
        if os.path.exists(STATE_F) else {}
    done = set(state.get("done", []))
    rows = state.get("rows", [])

    todo = []
    for sys_key, (sys_name, prov_tpl, city_tpl, kw, scope) in SYSTEMS.items():
        if prov_tpl:
            for p in provs:
                doms = [prov_tpl.format(py=v) for v in prov_variants(p)]
                todo.append((sys_key, p, "省", doms, kw))
        if city_tpl:
            for c in cities:
                todo.append((sys_key, c["name"], "市",
                             [city_tpl.format(py=pinyin_of(c["name"]))], kw))
    todo = [t for t in todo if "|".join(t[:3]) not in done]
    print(f"p46 本轮 {len(todo)} 组探测", flush=True)

    def work(t):
        sys_key, name, level, doms, kw = t
        for dom in doms:
            for scheme in ("https", "http"):
                ok, url = probe(dom, scheme)
                if ok:
                    return t, url
        return t, ""

    with ThreadPoolExecutor(16) as ex:
        for i, (t, url) in enumerate(ex.map(work, todo)):
            sys_key, name, level, doms, kw = t
            if url:
                rows.append({"system": sys_key, "name": name, "level": level,
                             "url": url, "verified": True})
            done.add("|".join(t[:3]))
            if (i + 1) % 200 == 0:
                state["done"] = sorted(done)
                state["rows"] = rows
                json.dump(state, open(STATE_F, "w", encoding="utf-8"),
                          ensure_ascii=False, indent=0)
                print(f"  进度 {i+1}/{len(todo)}，命中 {len(rows)}", flush=True)

    state["done"] = sorted(done)
    state["rows"] = rows
    json.dump(state, open(STATE_F, "w", encoding="utf-8"),
              ensure_ascii=False, indent=0)
    with open(OUT_F, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    from collections import Counter
    print("p46 完成：", dict(Counter(r["system"] for r in rows)), flush=True)


if __name__ == "__main__":
    main()
