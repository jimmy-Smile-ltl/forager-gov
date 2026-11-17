# -*- coding: utf-8 -*-
"""P137: 建外交系统条模块。

结构：中央外办（列名，最高机构）→ 外交部（fmprc.gov.cn）
→ 驻外使馆 267（6 洲分组）/ 驻外总领馆 90（6 洲）/ 驻外团处 15
→ 地方外办 46（32 省级 + 14 副省级市）。
来源：外交部官网「驻外机构」栏目页 + 首页「地方外办」区块真实 HTML。
"""
import json
import re

def leaf(nm, cat, u, lv):
    return {"n": nm, "l": lv, "k": cat, "c": cat, "u": u,
            "x": "", "s": "", "m": ""}

def grp(nm, cat, kids):
    return {"n": nm, "l": "条", "k": "分组", "c": cat, "u": "",
            "x": "", "s": "", "m": "", "ks": kids}

ZHOU_ORDER = ["亚洲", "非洲", "欧洲", "北美洲", "南美洲", "大洋洲"]

tree = json.load(open("tree.json", encoding="utf-8"))
rules = json.load(open("extraction_rules.json", encoding="utf-8"))
tiao = next(g for g in tree["ks"] if g["n"].startswith("条"))

# 驻外机构
zw = [json.loads(l) for l in open("wj_zwjg.jsonl", encoding="utf-8")]
BASE = "https://www.fmprc.gov.cn/web/zwjg_674741/"
def full_url(cat, u):
    if u.startswith("http"):
        return u
    if cat == "驻外使馆":
        pre = BASE + "zwsg_674743/"
    elif cat == "驻外总领馆":
        pre = BASE + "zwzlg_674757/"
    else:
        pre = BASE + "zwtc_674771/"
    z = {"亚洲": "yz_674745", "非洲": "fz_674747", "欧洲": "xo_674749",
         "北美洲": "xybf_674751", "南美洲": "dozy_674753", "大洋洲": "bmdyz_674755"}
    if cat == "驻外团处":
        return pre + u.lstrip("./")
    zid = z.get(u.split("/")[0], None)  # 相对路径第一段可能不是洲
    return pre + z.get(zhou_map.get(id(u), ""), "") + u.lstrip("./") if False else pre + u.lstrip("./")

# 更简单：按原栏目页 URL 拼接
URL_PRE = {
    ("驻外使馆", "亚洲"): BASE + "zwsg_674743/yz_674745/",
    ("驻外使馆", "非洲"): BASE + "zwsg_674743/fz_674747/",
    ("驻外使馆", "欧洲"): BASE + "zwsg_674743/xo_674749/",
    ("驻外使馆", "北美洲"): BASE + "zwsg_674743/xybf_674751/",
    ("驻外使馆", "南美洲"): BASE + "zwsg_674743/dozy_674753/",
    ("驻外使馆", "大洋洲"): BASE + "zwsg_674743/bmdyz_674755/",
    ("驻外总领馆", "亚洲"): BASE + "zwzlg_674757/yz_674759/",
    ("驻外总领馆", "非洲"): BASE + "zwzlg_674757/fz_674761/",
    ("驻外总领馆", "欧洲"): BASE + "zwzlg_674757/xo_674763/",
    ("驻外总领馆", "北美洲"): BASE + "zwzlg_674757/xybf_674765/",
    ("驻外总领馆", "南美洲"): BASE + "zwzlg_674757/dozy_674767/",
    ("驻外总领馆", "大洋洲"): BASE + "zwzlg_674757/bmdyz_674769/",
    ("驻外团处", "全部"): BASE + "zwtc_674771/",
}

sg_by_zhou = {z: [] for z in ZHOU_ORDER}
lg_by_zhou = {z: [] for z in ZHOU_ORDER}
tc = []
for r in zw:
    u = URL_PRE[(r["cat"], r["zhou"])] + r["url"].lstrip("./")
    if r["cat"] == "驻外使馆":
        sg_by_zhou[r["zhou"]].append(leaf(r["name"], "外交系统", u, "条"))
    elif r["cat"] == "驻外总领馆":
        lg_by_zhou[r["zhou"]].append(leaf(r["name"], "外交系统", u, "条"))
    else:
        tc.append(leaf(r["name"], "外交系统", u, "条"))

wjb = {"n": "中华人民共和国外交部", "l": "中央", "k": "外交系统",
       "c": "外交系统", "u": "https://www.fmprc.gov.cn/web/",
       "x": "", "s": "", "m": "", "ks": [
    grp(f"驻外使馆（{sum(len(v) for v in sg_by_zhou.values())}）", "外交系统",
        [grp(f"{z}（{len(sg_by_zhou[z])}）", "外交系统", sg_by_zhou[z])
         for z in ZHOU_ORDER]),
    grp(f"驻外总领馆（{sum(len(v) for v in lg_by_zhou.values())}）", "外交系统",
        [grp(f"{z}（{len(lg_by_zhou[z])}）", "外交系统", lg_by_zhou[z])
         for z in ZHOU_ORDER]),
    grp(f"驻外团、处（{len(tc)}）", "外交系统", tc),
]}

# 地方外办
df = json.load(open("/tmp/wj_difang.json", encoding="utf-8"))
PROV = set(["北京", "天津", "河北", "山西", "内蒙古", "辽宁", "吉林", "黑龙江",
            "上海", "江苏", "浙江", "安徽", "福建", "江西", "山东", "河南",
            "湖北", "湖南", "广东", "广西", "海南", "重庆", "四川", "贵州",
            "云南", "西藏", "陕西", "甘肃", "青海", "宁夏", "新疆", "新疆生产建设兵团"])
prov_df = []
shi_df = []
for nm, u in df.items():
    core = nm.replace("外办", "").replace("市", "").replace("省", "").replace("自治区", "")
    if any(core.startswith(p) for p in PROV) or "兵团" in nm:
        prov_df.append(leaf(nm, "外交系统", u, "省"))
    else:
        shi_df.append(leaf(nm, "外交系统", u, "市"))

sys_g = grp("外交系统（外交部体系）", "外交系统", [
    leaf("中央外事工作委员会办公室", "外交系统", "", "中央"),
    wjb,
    grp(f"地方外办（{len(prov_df) + len(shi_df)}）", "外交系统",
        prov_df + shi_df),
])
tiao["ks"] = [g for g in tiao["ks"] if "外交" not in g["n"]]
tiao["ks"].append(sys_g)

# rules
rk = sys_g["n"]
all_m = []
def walk(n):
    if not n.get("ks"):
        all_m.append(n)
        return
    if all(x.get("l") != "省" for x in n["ks"]):
        all_m.append(n)
    for k in n["ks"]:
        walk(k)
walk(sys_g)
rules[rk] = {
    "portal": "https://www.fmprc.gov.cn/web/",
    "method": ("外交系统=中央外办（最高机构，无公开官网→列名）→ 外交部 → "
               f"驻外使馆 {sum(len(v) for v in sg_by_zhou.values())} + 总领馆 "
               f"{sum(len(v) for v in lg_by_zhou.values())} + 团处 {len(tc)} "
               "（外交部官网「驻外机构」栏目页真实 HTML，按 6 洲分组）→ "
               f"地方外办 {len(df)}（外交部官网首页「地方外办」区块："
               "32 省级含兵团 + 14 副省级市外办）"),
    "sources": ["https://www.fmprc.gov.cn/web/"],
    "code": "# 驻外机构：fmprc 驻外机构栏目页；地方外办：fmprc 首页区块\n",
    "depts": [{"n": m["n"], "u": m.get("u", ""), "o": i}
              for i, m in enumerate(all_m)],
    "cities": [],
}
json.dump(tree, open("tree.json", "w", encoding="utf-8"),
          ensure_ascii=False, separators=(",", ":"))
json.dump(rules, open("extraction_rules.json", "w", encoding="utf-8"),
          ensure_ascii=False, separators=(",", ":"))
n_u = sum(1 for m in all_m if m.get("u"))
print(f"p137 完成：外交系统 {len(all_m)} 节点（{n_u} 有URL）")
