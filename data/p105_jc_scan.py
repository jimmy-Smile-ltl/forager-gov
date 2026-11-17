# -*- coding: utf-8 -*-
"""P105: 检察院基层批量扫描——静态轮 186 个市级院官网。

提取「下辖检察院/基层检察院」区块链接，匹配树里县级节点名。
"""
import json
import os
import re
import subprocess
import time

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")

tree = json.load(open("tree.json", encoding="utf-8"))
prov_g = next(g for g in tree["ks"] if g["n"].startswith("省级"))
tiao = next(g for g in tree["ks"] if g["n"].startswith("条"))
jc = next(g for g in tiao["ks"] if g["n"].startswith("检察院系统"))
prov_jc = next(g for g in jc["ks"] if "省级检察院" in g["n"])

# 市级院 URL + 其下县级名（树里 l=县 的人民政府节点）
jobs = []
for p in prov_g["ks"]:
    pname = p["n"]
    # 县级名单
    counties = {}
    for top in p.get("ks", []):
        def walk(n):
            if n.get("l") == "县" and n.get("k") == "人民政府":
                counties[n["n"]] = ""
            for k in n.get("ks", []):
                walk(k)
        walk(top)
    pj = next((x for x in prov_jc["ks"] if x["n"].startswith(pname)), None)
    if not pj:
        continue
    for shi in pj.get("ks", []):
        if shi.get("u"):
            jobs.append((pname, shi["n"], shi["u"], counties))

print(f"任务数: {len(jobs)} 个市级院")
STATE_F = "jc_jc_state.json"
state = json.load(open(STATE_F, encoding="utf-8")) if os.path.exists(STATE_F) else {"done": [], "rows": []}
done = set(state["done"])
rows = state["rows"]

def fetch(u):
    try:
        r = subprocess.run(["curl", "-s", "--compressed", "-L", "--max-time", "12",
                            "-A", UA, u], capture_output=True, timeout=16)
        raw = r.stdout
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            try:
                return raw.decode("gb18030")
            except Exception:
                return ""
    except Exception:
        return ""

for i, (pname, shiname, shiurl, counties) in enumerate(jobs):
    key = f"{pname}|{shiname}"
    if key in done:
        continue
    try:
        html = fetch(shiurl)
        hits = {}
        if html:
            # 区块锚点：XX区/县人民检察院
            for u, txt in re.findall(
                    r'<a[^>]+href="([^"]+)"[^>]*>\s*([^<]{3,24}?)\s*</a>', html):
                t2 = txt.strip()
                if re.search(r'人民检察院$', t2) and u.startswith("http"):
                    core = re.sub(r'人民检察院$', '', t2)
                    for cn in counties:
                        base = re.sub(r'(自治县|区|县|市)$', '', cn)
                        if core == cn or core == base or core.endswith(cn[:2]) and len(core) <= len(base) + 2:
                            hits[cn] = u
                            break
            # select 下拉
            if not hits:
                for sel in re.findall(r'<select[^>]*>(.*?)</select>', html, re.S):
                    opts = re.findall(r'<option[^>]*value="([^"]*)"[^>]*>\s*([^<]+?)\s*</option>', sel)
                    for v, txt in opts:
                        if '检察院' in txt and v.startswith("http"):
                            core = re.sub(r'(人民检察院|检察院)$', '', txt.strip())
                            for cn in counties:
                                base = re.sub(r'(自治县|区|县|市)$', '', cn)
                                if core == cn or core == base:
                                    hits[cn] = v
                                    break
        for cn, u in hits.items():
            rows.append({"province": pname, "shi": shiname, "county": cn, "url": u})
        done.add(key)
        state["done"] = sorted(done)
        state["rows"] = rows
        json.dump(state, open(STATE_F, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=0)
        if i % 10 == 0:
            print(f"{i}/{len(jobs)} {shiname}: {len(hits)} 基层", flush=True)
    except Exception as e:
        print(f"{key}: 失败 {str(e)[:40]}", flush=True)

with open("jc_jc.jsonl", "w", encoding="utf-8") as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
print(f"p105 静态轮完成: {len(rows)} 条基层记录，done {len(done)}/{len(jobs)}")
