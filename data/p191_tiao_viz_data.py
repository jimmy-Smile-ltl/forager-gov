# -*- coding: utf-8 -*-
"""P191: 条视图（垂直系统）可视化数据——15 系统子树。
法检人大政协纪委 5 系统从块树重组省→市→县全层级
（节点名带地名归一化: 石家庄市+县人民检察院→石家庄市人民检察院）;
其余系统取条树原结构。"""
import json, os

tree = json.load(open("tree.json", encoding="utf-8"))
blk = next(g for g in tree["ks"] if g["n"].startswith("省级"))
tiao = next(g for g in tree["ks"] if g["n"].startswith("条"))

def t_of(nn):
    if "人大" in nn: return "rd"
    if "政协" in nn: return "zx"
    if "监委" in nn or "监察" in nn: return "jw"
    if "法院" in nn: return "fy"
    if "检察" in nn: return "jcy"
    return "dept"

# ── 5 大系统从块树重组 ──────────────────────
# 中央根
CENTRAL = {
  "rd":  ("全国人民代表大会", "http://www.npc.gov.cn/"),
  "zx":  ("中国人民政治协商会议全国委员会", "http://www.cppcc.gov.cn/"),
  "jw":  ("国家监察委员会", ""),
  "fy":  ("最高人民法院", "https://www.court.gov.cn/"),
  "jcy": ("最高人民检察院", "https://www.spp.gov.cn/"),
}
def prov_node_of(p, cat):
    for jg in p.get("ks", []):
        if jg.get("k") != "分组":
            continue
        for o in jg.get("ks", []):
            nn = o.get("n", "")
            if cat == "rd" and nn == "省人大": return o
            if cat == "zx" and nn == "省政协": return o
            if cat == "jw" and nn == "省监委": return o
            if cat == "fy" and "法院" in nn: return o
            if cat == "jcy" and "检察" in nn: return o
    return None
def city_node_of(c, cat):
    for jg in c.get("ks", []):
        if jg.get("k") != "分组":
            continue
        for o in jg.get("ks", []):
            nn = o.get("n", "")
            if cat == "rd" and nn == "县人大": return o
            if cat == "zx" and nn == "县政协": return o
            if cat == "jw" and nn == "县监委": return o
            if cat == "fy" and nn == "县人民法院": return o
            if cat == "jcy" and nn == "县人民检察院": return o
    return None
def rename(cat, prefix, nn):
    base = {"rd": "人大", "zx": "政协", "jw": "监委",
            "fy": "人民法院", "jcy": "人民检察院"}[cat]
    return prefix + base

def build_5sys(cat):
    rootn, rootu = CENTRAL[cat]
    root = {"n": rootn, "u": rootu, "t": t_of(rootn), "ks": []}
    for p in blk["ks"]:
        po = prov_node_of(p, cat)
        pnode = {"n": p["n"] + t_of("x" + {"rd":"人大","zx":"政协","jw":"监委","fy":"法院","jcy":"检察院"}[cat]).replace("rd",""),
                 "u": po.get("u", "") if po else "",
                 "t": t_of(rootn), "ks": []}
        pname = p["n"]
        # 省下各市
        for c in p.get("ks", []):
            if c.get("c") not in ("地级市人民政府", "市辖区（地级行政区划）"):
                continue
            co = city_node_of(c, cat)
            cnode = {"n": rename(cat, c["n"], "县人民检察院"),
                     "u": co.get("u", "") if co else "",
                     "t": t_of(rootn), "ks": []}
            # 市下各县
            for x in c.get("ks", []):
                if x.get("c") != "县级人民政府":
                    continue
                xo = city_node_of(x, cat)
                if xo is None:
                    continue
                cnode["ks"].append({
                    "n": rename(cat, x["n"], "县人民检察院"),
                    "u": xo.get("u", ""),
                    "t": t_of(rootn)})
            pnode["ks"].append(cnode)
        root["ks"].append(pnode)
    return root

FIVE = [build_5sys(cat) for cat in ("rd", "zx", "fy", "jcy", "jw")]

# ── 条树其他系统原样（精简） ────────────────
def slim(n, t=None):
    out = {"n": n["n"], "u": n.get("u", ""), "t": t or t_of(n.get("n", ""))}
    if n.get("ks"):
        out["ks"] = [slim(k) for k in n["ks"]]
    return out
others = [slim(g) for g in tiao["ks"]
          if not any(s in g["n"] for s in ("人大", "政协", "法院", "检察", "纪委"))]

root = {"n": "垂直管理系统（条）", "u": "", "t": "root", "ks": FIVE + others}
out_f = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "..", "viz_tiao_data.js")
s = json.dumps(root, ensure_ascii=False, separators=(",", ":"))
open(out_f, "w", encoding="utf-8").write("window.__TIAO__=" + s + ";")
print(f"viz_tiao_data.js: {len(s)/1024:.0f} KB")
def cnt(n):
    c = 1
    for k in n.get("ks", []): c += cnt(k)
    return c
print("条视图节点:", cnt(root))
# 抽查检察院
jcy = FIVE[3]
print("检察院系统:", jcy["n"], "→", len(jcy["ks"]), "省级")
hbei = [p for p in jcy["ks"] if p["n"].startswith("河北")][0]
print("河北省检察院 →", len(hbei["ks"]), "市")
sjz = [c for c in hbei["ks"] if "石家庄" in c["n"]][0]
print("石家庄:", sjz["n"], sjz["u"], "→", len(sjz["ks"]), "县")
print("  样例:", sjz["ks"][0]["n"], sjz["ks"][0]["u"][:40])
