# -*- coding: utf-8 -*-
"""P190: 树状图可视化数据生成——块树重组为思维导图结构:
每个区划节点 → [人民政府(→内设部门), 并列机关(→人大/政协/监委/
法院/检察院/党委/群团), 下级区划(递归)]。输出精简 JSON。"""
import json, os

tree = json.load(open("tree.json", encoding="utf-8"))

def t_of(n, nn):
    if "人大" in nn: return "rd"
    if "政协" in nn: return "zx"
    if "监委" in nn or "监察" in nn: return "jw"
    if "法院" in nn: return "fy"
    if "检察" in nn: return "jcy"
    if "委（党委" in nn or nn.endswith("委") and "省委" in nn or "县委" in nn or "市委" in nn: return "party"
    if "党委" in nn or nn in ("中共中央（党中央）",): return "party"
    if "群团" in n.get("k", "") or n.get("c") == "群团组织": return "qt"
    if n.get("c") and "人民政府" in n.get("c", ""): return "gov"
    if n.get("k") in ("厅局", "部门") or "部门" in n.get("k", ""): return "dept"
    return "group"

def build(node, depth):
    """重组一个区划节点。"""
    n, u = node["n"], node.get("u", "")
    out = {"n": n, "u": u, "t": t_of(node, n)}
    depts, binglie, quntuan, subgov = [], [], [], []
    for k in node.get("ks", []):
        kn, kc, kk = k.get("n", ""), k.get("c", ""), k.get("k", "")
        if kk == "分组" and ("部门" in kn or "厅局" in kn or "直属" in kn or "内设" in kn):
            for d in k.get("ks", []):
                depts.append({"n": d["n"], "u": d.get("u", ""), "t": "dept"})
        elif kk == "分组" and ("并列" in kn):
            for d in k.get("ks", []):
                binglie.append({"n": d["n"], "u": d.get("u", ""),
                                "t": t_of(d, d["n"])})
        elif kc == "群团组织" or "群团" in kn:
            if k.get("ks"):
                for d in k.get("ks", []):
                    quntuan.append({"n": d["n"], "u": d.get("u", ""), "t": "qt"})
            else:
                quntuan.append({"n": kn, "u": k.get("u", ""), "t": "qt"})
        elif kc and "人民政府" in kc and k.get("ks"):
            subgov.append(build(k, depth + 1))
        elif kc and "人民政府" in kc and not k.get("ks"):
            subgov.append({"n": kn, "u": k.get("u", ""), "t": "gov"})
    ks = []
    # 1) 人民政府 → 内设部门
    gov_ks = depts
    ks.append({"n": "人民政府", "u": u, "t": "govhome",
               "ks": gov_ks} if gov_ks else None)
    ks = [x for x in ks if x]
    if not ks:  # 无内设部门时人民政府节点只挂门户
        ks.append({"n": "人民政府", "u": u, "t": "govhome", "ks": []})
    # 2) 并列机关
    bl = binglie + quntuan
    if bl:
        ks.append({"n": "并列机关", "u": "", "t": "binglie", "ks": bl})
    # 3) 下级区划
    ks.extend(subgov)
    out["ks"] = ks
    return out

root = {"n": tree["n"], "u": "", "t": "root", "ks": []}
for g in tree["ks"]:
    gn = g["n"]
    if gn.startswith("省级"):
        provs = []
        for p in g["ks"]:
            provs.append(build(p, 1))
        root["ks"].append({"n": "地方（32 省级）", "t": "block", "ks": provs})
    elif gn.startswith("中央"):
        # 中央: 国务院(→部门) + 并列机关 + 党中央
        kids = []
        for k in g["ks"]:
            kn = k["n"]
            if "国务院" in kn:
                gov = {"n": "国务院（中央人民政府）", "u": k.get("u", ""),
                       "t": "govhome", "ks": []}
                for sub in k.get("ks", []):
                    if sub.get("k") == "分组":
                        for d in sub.get("ks", []):
                            gov["ks"].append({"n": d["n"], "u": d.get("u", ""), "t": "dept"})
                    else:
                        gov["ks"].append({"n": sub["n"], "u": sub.get("u", ""),
                                          "t": t_of(sub, sub["n"])})
                kids.append(gov)
            elif "中共中央" in kn:
                kids.append({"n": kn, "u": k.get("u", ""), "t": "party", "ks": []})
            else:
                kids.append({"n": kn, "u": k.get("u", ""), "t": t_of(k, kn),
                             "ks": [{"n": d["n"], "u": d.get("u", ""), "t": t_of(d, d["n"])}
                                    for d in k.get("ks", [])] if k.get("ks") else []})
        root["ks"].append({"n": "中央", "t": "block", "ks": kids})
    else:
        # 港澳台/条——港澳台纳入, 条跳过（有独立模块）
        if gn.startswith("港澳台"):
            root["ks"].append({"n": gn, "t": "block",
                               "ks": [{"n": k["n"], "u": k.get("u", ""),
                                       "t": "gov" if "人民政府" in k.get("c","") or k.get("k")=="人民政府" else "group"}
                                      for k in g.get("ks", [])]})

out_f = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "..", "viz_tree_data.js")
import io
s = json.dumps(root, ensure_ascii=False, separators=(",", ":"))
with open(out_f, "w", encoding="utf-8") as f:
    f.write("window.__TREE__=" + s + ";")
print(f"viz_tree_data.js: {len(s)/1024:.0f} KB")
# 统计
def cnt(n):
    c = 1
    for k in n.get("ks", []): c += cnt(k)
    return c
print("总节点:", cnt(root))
