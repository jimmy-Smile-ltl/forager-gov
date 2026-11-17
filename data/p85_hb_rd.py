# -*- coding: utf-8 -*-
"""P85: 河北市级人大（hbrd.gov.cn 首页 select 下拉，真实 HTML）。"""
import json
import re

t = open("/tmp/hbrd.html", encoding="utf-8", errors="replace").read()
# 市级人大下拉：含「石家庄人大」选项的 select
d = {}
for sel in re.findall(r'<select[^>]*>(.*?)</select>', t, re.S):
    opts = re.findall(r'<option[^>]*value="([^"]*)"[^>]*>\s*([^<]+?)\s*</option>', sel)
    if any("石家庄人大" in x[1] for x in opts):
        for v, txt in opts:
            txt2 = txt.strip()
            if "人大" in txt2 and "各地人大" not in txt2:
                d[txt2] = v if v and v != "#" else ""
print("下拉提取:", len(d), "项")
for k, v in d.items():
    print(f"  {k} -> {v or '(无官网)'}")

# 河北数据：11 市 + 辛集/定州（省直管县级市，官方下拉与市级并列）
rows = []
CITY2CORE = {"石家庄人大": "石家庄市", "承德人大": "承德市", "张家口人大": "张家口市",
             "秦皇岛人大": "秦皇岛市", "唐山人大": "唐山市", "廊坊人大": "廊坊市",
             "保定人大": "保定市", "沧州人大": "沧州市", "衡水人大": "衡水市",
             "邢台人大": "邢台市", "邯郸人大": "邯郸市", "辛集人大": "辛集市",
             "定州人大": "定州市"}
for k, nm in CITY2CORE.items():
    rows.append({"province": "河北省", "name": nm, "url": d.get(k, ""),
                 "listed": bool(d.get(k))})

old = [json.loads(l) for l in open("rd_shi.jsonl", encoding="utf-8")]
old = [r for r in old if r["province"] != "河北省"]
with open("rd_shi.jsonl", "w", encoding="utf-8") as f:
    for r in old + rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
print(f"p85 完成：河北 {len(rows)} 条（{sum(1 for r in rows if r['listed'])} 有官网），"
      f"rd_shi.jsonl 共 {len(old) + len(rows)} 条")
