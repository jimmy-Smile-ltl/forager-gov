# -*- coding: utf-8 -*-
"""P86: 江苏市级人大（jsrd.gov.cn 首页「dis」区块，真实 HTML 验证）。"""
import json
import re

t = open("/tmp/jsrd.html", encoding="utf-8", errors="replace").read()
# 南京人大网 锚点定位区块
p = t.find("南京人大网")
seg = t[max(0, p - 300):p + 3000]
d = {}
for u, txt in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>\s*([^<]+?)\s*</a>', seg):
    txt2 = txt.strip()
    if "人大网" in txt2:
        d[txt2] = u
print("江苏下拉提取:", len(d), "项")
CITY2CORE = {"南京": "南京市", "无锡": "无锡市", "徐州": "徐州市",
             "常州": "常州市", "苏州": "苏州市", "南通": "南通市",
             "连云港": "连云港市", "淮安": "淮安市", "盐城": "盐城市",
             "扬州": "扬州市", "镇江": "镇江市", "泰州": "泰州市",
             "宿迁": "宿迁市"}
rows = []
for k, u in d.items():
    core = re.sub(r"人大网$", "", k)
    if core in CITY2CORE:
        rows.append({"province": "江苏省", "name": CITY2CORE[core],
                     "url": u, "listed": bool(u)})
for r in rows:
    print(f"  {r['name']} -> {r['url']}")

old = [json.loads(l) for l in open("rd_shi.jsonl", encoding="utf-8")]
old = [r for r in old if r["province"] != "江苏省"]
with open("rd_shi.jsonl", "w", encoding="utf-8") as f:
    for r in old + rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
print(f"p86 完成：江苏 {len(rows)} 条，rd_shi.jsonl 共 {len(old) + len(rows)} 条")
