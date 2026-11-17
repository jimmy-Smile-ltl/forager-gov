import json
from common import save_snap
tree = json.load(open("tree.json", encoding="utf-8"))
gat = next(g for g in tree["ks"] if "港澳台" in g["n"])
EXTRA = [
    ("中央人民政府驻香港特别行政区联络办公室", "http://www.locpg.gov.cn/"),
    ("中央人民政府驻澳门特别行政区联络办公室", "http://www.zlb.gov.cn/"),
]
existing = {g["n"] for g in gat["ks"]}
added = 0
for nm, u in EXTRA:
    if nm not in existing:
        gat["ks"].append({"n": nm, "l": "港澳台", "k": "驻港澳机构",
                          "c": "驻港澳机构", "u": u, "x": "", "s": "", "m": ""})
        added += 1
json.dump(tree, open("tree.json", "w", encoding="utf-8"),
          ensure_ascii=False, separators=(",", ":"))
print(f"中联办补 {added}")
for fn, pg in [("/tmp/gov_部门.html", "bumen"), ("/tmp/gov_港澳.html", "gangaoz"),
               ("/tmp/gov_驻外.html", "zhuwai"), ("/tmp/gov_zzjg.html", "zzjg"),
               ("/tmp/gov_difang2.html", "difang")]:
    try:
        t = open(fn, encoding="utf-8", errors="replace").read()
        save_snap("shixian", "中央", "中国政府网", pg, t)
    except Exception as e:
        print(f"{fn}: {e}")
print("快照已存")
