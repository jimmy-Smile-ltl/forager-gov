# -*- coding: utf-8 -*-
"""市级/县级「政府部门」聚合节点（列表模式 + 树模式共用）。

用户指令（2026-11-18）：「网页前端 列表模式 树模式 都需要添加 市政府部门
县政府部门 两个节点 分别展示政府部门 list」。

数据来源（只读，不落主数据）：
  zzjg_pages.json   —— 省/市门户的「组织机构 / 部门」栏目（p246）
  zzjg_county.json  —— 县级门户的「组织机构 / 部门」栏目（p248）

产出结构（两级分组，叶子 = 部门/机构栏目链接）：
  市政府部门 → 省 → 市 → {机构设置, 直属单位, 事业单位, 直属企业, 公积金, 高校}
  县政府部门 → 省 → 市 → 县 → {…同上}

节点 schema 与 tree.json 一致 {n,l,k,c,u,s,m,ks}；叶子 l="部门"、k="部门"，
不参与区划统计（地图/覆盖率只认 k=人民政府|区划），也不会污染省/市/县计数。
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))

CITY_F = os.path.join(HERE, "zzjg_pages.json")
COUNTY_F = os.path.join(HERE, "zzjg_county.json")
DEPTS_F = os.path.join(HERE, "county_depts.json")   # p250 部门名录
TREE_F = os.path.join(HERE, "tree.json")

KIND_ORDER = ["机构设置", "内设机构", "直属单位", "事业单位",
              "直属企业", "公积金", "高校"]
LEVEL_BASE = {"省": "省", "市": "市"}


def _load(path):
    try:
        return json.load(open(path, encoding="utf-8"))
    except Exception:
        return {}


def _leaf(kind, u, src="", level="市"):
    # l 必须落在前端 LEVELS 里，否则默认层级筛选会把叶子过滤掉（2026-11-18 实测）
    n = {"n": kind, "l": level, "k": "部门", "u": u or "", "c": "部门"}
    if src:
        n["s"] = src
    return n


def _city_prov_map():
    """市名 → 所属省名（zzjg_pages 记录里没有 prov 字段，用树的主干补）。"""
    try:
        tree = json.load(open(TREE_F, encoding="utf-8"))
    except Exception:
        return {}
    out = {}

    def walk(n, prov):
        for k in n.get("ks") or []:
            if k.get("k") == "人民政府" and k.get("l") == "市":
                out.setdefault(k.get("n", ""), prov)
            walk(k, prov if n.get("l") == "省" and n.get("k") == "人民政府" else prov)

    pg = next((g for g in tree.get("ks") or [] if g.get("n", "").startswith("省级")), None)
    for p in (pg or {}).get("ks") or []:
        walk(p, p.get("n", ""))
    return out


def _city_tree():
    """市政府部门：省 → 市 → 栏目。"""
    data = _load(CITY_F)
    pmap = _city_prov_map()
    provs = {}
    for key, rec in sorted(data.items()):
        try:
            lv, name = key.split("|", 1)
        except ValueError:
            continue
        links = sorted((rec.get("links") or []),
                       key=lambda l: (KIND_ORDER.index(l["kind"])
                                      if l.get("kind") in KIND_ORDER else 99))
        links = [l for l in links if l.get("u")]
        if not links:
            continue
        prov = rec.get("prov") or (name if lv == "省" else pmap.get(name, ""))
        node = {"n": name, "l": "市" if lv == "市" else "省", "k": "分组",
                "c": "部门", "u": rec.get("u") or "",
                "ks": [_leaf(l.get("kind") or "机构设置", l["u"], l.get("src", ""),
                             "省" if lv == "省" else "市")
                       for l in links]}
        if lv == "省":
            node["n"] = name + "（省级）"
        provs.setdefault(prov or "中央/未分省", []).append(node)
    kids = [{"n": p, "l": "省", "k": "分组", "c": "部门", "ks": ns}
            for p, ns in sorted(provs.items(), key=lambda kv: kv[0])]
    return {"n": "市政府部门", "l": "根", "k": "分组", "c": "部门", "ks": kids}


def _county_tree():
    """县政府部门：省 → 市 → 县 → 部门。

    2026-11-19：县级优先用 p250 抽出的**部门名录**（county_depts.json）做叶子——
    用户口径「政府信息公开 → 法定主动公开内容 → 组织机构」「删去机构职能几个字
    就是我要的内容」「采完分页、清洗、去重」。没有名录的县回退到栏目链接。
    """
    data = _load(COUNTY_F)
    depts_all = _load(DEPTS_F)
    provs = {}
    n_dept_nodes = 0
    for key, rec in sorted(data.items()):
        parts = key.split("|")
        if len(parts) < 4:
            continue
        _lv, prov, city, name = parts[0], parts[1], parts[2], parts[3]
        drec = depts_all.get(key) or {}
        depts = [d for d in (drec.get("depts") or []) if d.get("n") and d.get("u")]
        if len(depts) >= 3:
            # c 保持「部门」与既有叶子一致（前端按 c 分组）；细分类型放 dt
            ks = [{"n": d["n"], "l": "县", "k": "部门", "c": "部门",
                   "dt": d.get("c") or "gov", "u": d["u"]} for d in depts]
            n_dept_nodes += len(ks)
        else:
            links = sorted((rec.get("links") or []),
                           key=lambda l: (KIND_ORDER.index(l["kind"])
                                          if l.get("kind") in KIND_ORDER else 99))
            links = [l for l in links if l.get("u")]
            if not links:
                continue
            ks = [_leaf(l.get("kind") or "机构设置", l["u"], l.get("src", ""), "县")
                  for l in links]
        node = {"n": name, "l": "县", "k": "分组", "c": "部门",
                "u": (drec.get("u") if len(depts) >= 3 else rec.get("u")) or "",
                "ks": ks}
        provs.setdefault(prov, {}).setdefault(city, []).append(node)
    if n_dept_nodes:
        print(f"  县政府部门叶子：{n_dept_nodes} 个部门名录条目（p250）")
    kids = []
    for p, cities in sorted(provs.items(), key=lambda kv: kv[0]):
        cks = [{"n": c, "l": "市", "k": "分组", "c": "部门",
                "ks": sorted(ns, key=lambda x: x["n"])}
               for c, ns in sorted(cities.items(), key=lambda kv: kv[0])]
        kids.append({"n": p, "l": "省", "k": "分组", "c": "部门", "ks": cks})
    return {"n": "县政府部门", "l": "根", "k": "分组", "c": "部门", "ks": kids}


def tree_groups():
    """给 tree.json / p22 用的两个顶层分组（l=根，p22 会自动拆成模块）。"""
    out = []
    for g in (_city_tree(), _county_tree()):
        if g.get("ks"):
            out.append(g)
    return out


def block_groups():
    """给 gen_viz 块视图用的两个分组（t=block 壳，叶子 t=dept）。"""
    def conv(n):
        t = "block" if n.get("k") == "分组" else "dept"
        o = {"n": n["n"], "u": n.get("u", ""), "t": t}
        for f in ("l", "k", "c", "s", "m", "dt"):
            if n.get(f):
                o[f] = n[f]
        if n.get("ks"):
            o["ks"] = [conv(k) for k in n["ks"]]
        return o

    return [conv(g) for g in tree_groups()]


if __name__ == "__main__":
    for g in tree_groups():
        cnt = 0

        def walk(n, d=0):
            global cnt
            cnt += 1
            for k in n.get("ks") or []:
                walk(k, d + 1)
        walk(g)
        print(g["n"], "节点", cnt)
