# -*- coding: utf-8 -*-
"""P157: 人大县级节点建设 + 市人大官网县级导航扫描（宜宾模式）。

1. 建县级人大节点（挂市级人大节点下，u="" 列名）
2. 批量扫有 URL 的市人大官网，提取「XX县人大」导航（宜宾官网底部
   高县人大/珙县人大/屏山县人大 模式）
"""
import json, os, re, subprocess, time

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")

tree = json.load(open("tree.json", encoding="utf-8"))
prov = next(g for g in tree["ks"] if g["n"].startswith("省级"))
tiao = next(g for g in tree["ks"] if g["n"].startswith("条"))
rd = next(g for g in tiao["ks"] if g["n"].startswith("人大系统"))
gy = next(x for x in rd["ks"] if x["n"].startswith("省级人大"))

# 县级名单（树里 l=县 的县名 → 所属市）
county_city = {}
for p in prov["ks"]:
    pn = p["n"]
    for top in p.get("ks", []):
        def walk(n, city):
            if n.get("l") == "市" and n.get("k") == "人民政府":
                city = n["n"]
            if n.get("l") == "县" and n.get("k") == "人民政府":
                county_city[(pn, n["n"])] = city
            for k in n.get("ks", []):
                walk(k, city)
        walk(top, None)

# 建县级人大节点
added = 0
for p in gy["ks"]:
    pname = p["n"].replace("人大", "")
    for shi in p.get("ks", []):
        shi_core = re.sub(r"人大$", "", shi["n"])
        existing = {k["n"] for k in shi.get("ks", [])}
        for (pn, cn), city in county_city.items():
            if pn != pname or city != shi_core:
                continue
            nm = f"{cn}人大"
            if nm in existing:
                continue
            shi.setdefault("ks", []).append(
                {"n": nm, "l": "县", "k": "人大系统", "c": "人大系统",
                 "u": "", "x": "", "s": "", "m": ""})
            existing.add(nm)
            added += 1
json.dump(tree, open("tree.json", "w", encoding="utf-8"),
          ensure_ascii=False, separators=(",", ":"))
print(f"县级人大节点: +{added}")

# 扫描市人大官网（有 URL 的市级人大节点）
STATE_F = "rd_xian_state.json"
state = json.load(open(STATE_F, encoding="utf-8")) if os.path.exists(STATE_F) \
    else {"done": [], "rows": []}
done = set(state["done"])
rows = state["rows"]
jobs = []
for p in gy["ks"]:
    pname = p["n"].replace("人大", "")
    for shi in p.get("ks", []):
        if shi.get("u"):
            counties = [k["n"].replace("人大", "") for k in shi.get("ks", [])]
            key = f"{pname}|{shi['n']}"
            if key not in done:
                jobs.append((pname, shi["n"], shi["u"], counties))
print(f"扫描任务: {len(jobs)} 市人大官网", flush=True)

def fetch(u):
    try:
        r = subprocess.run(["curl", "-s", "--compressed", "-L", "--max-time", "12",
                            "-A", UA, u], capture_output=True, timeout=16)
        raw = r.stdout
        for enc in ("utf-8", "gb18030"):
            try:
                return raw.decode(enc)
            except UnicodeDecodeError:
                continue
        return raw.decode("utf-8", errors="replace")
    except Exception:
        return ""

for i, (pname, shiname, shiurl, counties) in enumerate(jobs):
    key = f"{pname}|{shiname}"
    try:
        html = fetch(shiurl)
        hits = {}
        if html:
            for u, txt in re.findall(
                    r'<a[^>]+href="([^"]+)"[^>]*>\s*([^<]{3,24}?)\s*</a>', html):
                t2 = txt.strip()
                m = re.match(r'^(.*?[区县旗市])人大(?:常委会|网站|网)?$', t2)
                if m and u.startswith("http"):
                    core = m.group(1)
                    for cn in counties:
                        cn_core = re.sub(r'(自治县|区|县|旗|市)$', '', cn)
                        if core == cn or core == cn_core:
                            hits[cn] = u
                            break
        rows.append({"province": pname, "shi": shiname, "hits": hits})
        done.add(key)
        state["done"] = sorted(done)
        state["rows"] = rows
        json.dump(state, open(STATE_F, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=0)
        if i % 30 == 0:
            print(f"{i}/{len(jobs)} {shiname}: {len(hits)} 县人大", flush=True)
    except Exception as e:
        print(f"{shiname}: 失败 {str(e)[:35]}", flush=True)

with open("rd_xian.jsonl", "w", encoding="utf-8") as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
n_hits = sum(len(r["hits"]) for r in rows)
print(f"p157 完成: {n_hits} 条县级人大")
