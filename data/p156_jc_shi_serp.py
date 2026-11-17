# -*- coding: utf-8 -*-
"""P156: 97 个地级市检察院缺口——SERP 线索 + 官方页面 title 验证。"""
import json
import re
import subprocess
import time

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")

tree = json.load(open("tree.json", encoding="utf-8"))
tiao = next(g for g in tree["ks"] if g["n"].startswith("条"))
jc = next(g for g in tiao["ks"] if g["n"].startswith("检察院系统"))
prov_jc = next(g for g in jc["ks"] if "省级检察院" in g["n"])
MUNI = {"北京市", "天津市", "上海市", "重庆市"}
missing = []
for p in prov_jc["ks"]:
    pn = p["n"].replace("检察院", "")
    if pn in MUNI:
        continue
    for s in p.get("ks", []):
        if not s.get("u") and s.get("l") == "市":
            missing.append((pn, s["n"]))
print(f"缺口: {len(missing)}")

def serp(q):
    try:
        r = subprocess.run(["curl", "-s", "--compressed", "--max-time", "12",
                            "-A", UA, "https://www.baidu.com/s?wd=" + q],
                           capture_output=True, timeout=15)
        t = r.stdout.decode("utf-8", errors="replace")
        return re.findall(r'mu="([^"]+)"', t)
    except Exception:
        return []

results = {}
for pn, sn in missing:
    core = re.sub(r"(人民检察院|检察院)$", "", sn)
    core = re.sub(r"(自治州|市|盟|地区)$", "", core)
    q = f"{core}人民检察院"
    cands = serp(q)
    hit = None
    for u in cands[:7]:
        if not u or not u.startswith("http") or "baidu" in u or "baike" in u or "weibo" in u:
            continue
        try:
            r2 = subprocess.run(["curl", "-s", "--compressed", "-L", "--max-time", "9",
                                 "-A", UA, u], capture_output=True, timeout=13)
            raw = r2.stdout
            tt = None
            for enc in ("utf-8", "gb18030"):
                try:
                    tt = raw.decode(enc)
                    break
                except UnicodeDecodeError:
                    continue
            if tt is None:
                tt = raw.decode("utf-8", errors="replace")
            m = re.search(r"<title>([^<]*)</title>", tt)
            title = m.group(1).strip() if m else ""
            if core in title and "检察" in title and "jcy" in u:
                hit = u
                break
        except Exception:
            pass
        time.sleep(0.35)
    if hit:
        results[f"{pn}|{sn}"] = hit
        print(f"✓ {pn} {core}: {hit}", flush=True)
    time.sleep(0.9)

json.dump(results, open("/tmp/p156_results.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=0)
print(f"\np156 完成: {len(results)}/{len(missing)}")
