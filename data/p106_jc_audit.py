# -*- coding: utf-8 -*-
"""P106: 市级检察院 URL 审计——连通性 + title 身份验证。"""
import json
import re
import subprocess

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")

tree = json.load(open("tree.json", encoding="utf-8"))
tiao = next(g for g in tree["ks"] if g["n"].startswith("条"))
jc = next(g for g in tiao["ks"] if g["n"].startswith("检察院系统"))
prov_jc = next(g for g in jc["ks"] if "省级检察院" in g["n"])

def check(u):
    try:
        r = subprocess.run(["curl", "-s", "-o", "/tmp/jc_audit.html", "-w", "%{http_code}",
                            "--compressed", "-L", "--max-time", "12", "-A", UA, u],
                           capture_output=True, timeout=16)
        code = r.stdout.decode().strip()
        try:
            t = open("/tmp/jc_audit.html", encoding="utf-8").read()
        except UnicodeDecodeError:
            t = open("/tmp/jc_audit.html", encoding="gb18030", errors="replace").read()
        title = re.search(r'<title>([^<]*)</title>', t)
        title = title.group(1).strip() if title else ""
        return code, title
    except Exception as e:
        return "ERR", str(e)[:40]

bad = []
n = 0
for p in prov_jc["ks"]:
    for shi in p.get("ks", []):
        u = shi.get("u", "")
        if not u:
            continue
        n += 1
        code, title = check(u)
        ok = code == "200" and ("检察院" in title or "检察" in title)
        if not ok:
            bad.append((p["n"], shi["n"], u, code, title[:40]))
print(f"审计 {n} 个市级院 URL")
print(f"异常 {len(bad)} 个:")
for pn, sn, u, code, title in bad:
    print(f"  [{code}] {pn} {sn}: {u[:50]} title={title}")
json.dump([{"prov": b[0], "shi": b[1], "url": b[2], "code": b[3], "title": b[4]}
           for b in bad], open("/tmp/jc_bad.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=0)
