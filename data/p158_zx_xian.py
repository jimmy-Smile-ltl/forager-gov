# -*- coding: utf-8 -*-
"""P158: 政协县级节点建设 + 市政协官网县级导航扫描。"""
import json, re, subprocess, time

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
tree = json.load(open("tree.json", encoding="utf-8"))
prov = next(g for g in tree["ks"] if g["n"].startswith("省级"))
tiao = next(g for g in tree["ks"] if g["n"].startswith("条"))
zx = next(g for g in tiao["ks"] if g["n"].startswith("政协系统"))
gy = next(x for x in zx["ks"] if x["n"].startswith("省级政协"))

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

added = 0
for p in gy["ks"]:
    pname = p["n"].replace("政协", "")
    for shi in p.get("ks", []):
        shi_core = re.sub(r"政协$", "", shi["n"])
        existing = {k["n"] for k in shi.get("ks", [])}
        for (pn, cn), city in county_city.items():
            if pn != pname or city != shi_core:
                continue
            nm = f"{cn}政协"
            if nm in existing:
                continue
            shi.setdefault("ks", []).append(
                {"n": nm, "l": "县", "k": "政协系统", "c": "政协系统",
                 "u": "", "x": "", "s": "", "m": ""})
            existing.add(nm)
            added += 1
json.dump(tree, open("tree.json", "w", encoding="utf-8"),
          ensure_ascii=False, separators=(",", ":"))
print(f"县级政协节点: +{added}")

STATE_F = "zx_xian_state.json"
state = json.load(open(STATE_F, encoding="utf-8")) if __import__("os").path.exists(STATE_F) \
    else {"done": [], "rows": []}
done = set(state["done"])
rows = state["rows"]
jobs = []
for p in gy["ks"]:
    pname = p["n"].replace("政协", "")
    for shi in p.get("ks", []):
        if shi.get("u"):
            counties = [k["n"].replace("政协", "") for k in shi.get("ks", [])]
            key = f"{pname}|{shi['n']}"
            if key not in done:
                jobs.append((pname, shi["n"], shi["u"], counties))
print(f"扫描任务: {len(jobs)} 市政协官网", flush=True)

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
                m = re.match(r'^(.*?[区县旗市])政协(?:委员会|网站|网)?$', t2)
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
        if i % 40 == 0:
            print(f"{i}/{len(jobs)} {shiname}: {len(hits)} 县政协", flush=True)
    except Exception as e:
        print(f"{shiname}: 失败 {str(e)[:35]}", flush=True)

with open("zx_xian.jsonl", "w", encoding="utf-8") as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
n_hits = sum(len(r["hits"]) for r in rows)
print(f"p158 完成: {n_hits} 条县级政协")
