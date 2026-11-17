# -*- coding: utf-8 -*-
"""P151: 289 市院官网静态扫描——找「下辖/区县检察院」导航。

用户路径：省检察院→市检察院→区县检察院。真实 HTML 提取，零猜测。
静态轮：curl 首页提取「XX区/县人民检察院」链接。断点续跑。
"""
import json, os, re, subprocess, time

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")

tree = json.load(open("tree.json", encoding="utf-8"))
tiao = next(g for g in tree["ks"] if g["n"].startswith("条"))
jc = next(g for g in tiao["ks"] if g["n"].startswith("检察院系统"))
prov_jc = next(g for g in jc["ks"] if "省级检察院" in g["n"])

jobs = []
for p in prov_jc["ks"]:
    pn = p["n"].replace("检察院", "")
    for s in p.get("ks", []):
        if s.get("u"):
            # 该市下县级名（基层节点名单）
            counties = [k["n"].replace("人民检察院", "") for k in s.get("ks", [])]
            jobs.append((pn, s["n"], s["u"], counties))

STATE_F = "jc_shi_scan_state.json"
state = json.load(open(STATE_F, encoding="utf-8")) if os.path.exists(STATE_F) \
    else {"done": [], "rows": []}
done = set(state["done"])
rows = state["rows"]
jobs = [j for j in jobs if f"{j[0]}|{j[1]}" not in done]
print(f"待扫描: {len(jobs)} 市院", flush=True)

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

for i, (pn, shiname, shiurl, counties) in enumerate(jobs):
    key = f"{pn}|{shiname}"
    try:
        html = fetch(shiurl)
        hits = {}
        if html:
            # 「XX区/县人民检察院」锚点
            for u, txt in re.findall(
                    r'<a[^>]+href="([^"]+)"[^>]*>\s*([^<]{3,24}?)\s*</a>', html):
                t2 = txt.strip()
                m = re.match(r'^(.*?[区县旗市])人民检察院$', t2)
                if m and u.startswith("http"):
                    core = m.group(1)
                    for cn in counties:
                        cn_core = re.sub(r'(自治县|区|县|旗|市)$', '', cn)
                        if core == cn or core == cn_core:
                            hits[cn] = u
                            break
        rows.append({"province": pn, "shi": shiname, "hits": hits})
        done.add(key)
        state["done"] = sorted(done)
        state["rows"] = rows
        json.dump(state, open(STATE_F, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=0)
        if i % 20 == 0:
            print(f"{i}/{len(jobs)} {shiname}: {len(hits)} 基层", flush=True)
    except Exception as e:
        print(f"{shiname}: 失败 {str(e)[:40]}", flush=True)

with open("jc_shi_scan.jsonl", "w", encoding="utf-8") as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
n_hits = sum(len(r["hits"]) for r in rows)
print(f"p151 静态轮完成: {n_hits} 条基层，done {len(done)}")
