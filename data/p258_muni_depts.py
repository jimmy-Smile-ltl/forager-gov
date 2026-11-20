# -*- coding: utf-8 -*-
"""P258: 直辖市市辖区的部门名录（复用 p250 的抽取链）。

用户口径（2026-11-20）：直辖市市辖区在「块·行政层级」里**两个列表都放**——
县政府部门按区划类型（l=县）、市政府部门按机构级别（l=地级区）。

县政府部门里其他县都挂着 30-60 条部门名录叶子（p250 产物），市辖区若只挂一个
「机构设置」栏目链接，形态明显不一致。本脚本把 p246 已采到的市辖区机构设置栏目页
喂给 p250 的抽取器，产出与县同构的名录，合并进 county_depts.json
（key 前缀 `地级区|`，与 `县|` 并存，互不覆盖）。

三个步骤：

  uv run python p258_muni_depts.py --build    # zzjg_pages.json → zzjg_muni.json
  P250_IN=... P250_OUT=... uv run python p250_county_depts.py --phase render ...
  uv run python p258_muni_depts.py --merge    # county_depts_muni.json → county_depts.json

--build 只做数据整形（不联网）；--merge 只做合并（不联网）。
"""
import argparse
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
TREE_F = os.path.join(HERE, "tree.json")
PAGES_F = os.path.join(HERE, "zzjg_pages.json")
IN_F = os.path.join(HERE, "zzjg_muni.json")
MUNI_OUT = os.path.join(HERE, "county_depts_muni.json")
DEPTS_F = os.path.join(HERE, "county_depts.json")

MUNI = ("北京市", "天津市", "上海市", "重庆市")
# 能当「部门名录入口」的栏目类别，按优先级
KIND_PREF = ["机构设置", "内设机构", "直属单位", "事业单位", "直属企业"]


def walk(n):
    yield n
    if n.get("k") == "人民政府" and n.get("l") == "地级区":
        return
    for k in n.get("ks") or []:
        yield from walk(k)


def muni_districts():
    """[(直辖市, 区名)]，来自树（口径唯一来源，与 p246/zzjg_nodes 一致）。"""
    tree = json.load(open(TREE_F, encoding="utf-8"))
    out = []
    for g in tree.get("ks") or []:
        if not g.get("n", "").startswith("省级"):
            continue
        for p in g.get("ks") or []:
            if p.get("n") not in MUNI:
                continue
            for x in walk(p):
                if x.get("k") == "人民政府" and x.get("l") == "地级区":
                    out.append((p["n"], x["n"]))
    return out


def build():
    pages = json.load(open(PAGES_F, encoding="utf-8"))
    src, skip = {}, []
    for prov, name in muni_districts():
        rec = pages.get("地级区|" + name) or {}
        links = [l for l in (rec.get("links") or []) if l.get("u")]
        pick = None
        for kind in KIND_PREF:
            pick = next((l for l in links if l.get("kind") == kind), None)
            if pick:
                break
        if not pick:
            skip.append(f"{prov}{name}")
            continue
        # 直辖市省名=市名，p250 的 county_guard 已按「省名=市名」处理
        key = f"地级区|{prov}|{prov}|{name}"
        src[key] = {"u": pick["u"],
                    "title": pick.get("title") or "",
                    "src": (pick.get("src") or "")[:160]}
    json.dump(src, open(IN_F, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    open(IN_F, "a", encoding="utf-8").write("\n")
    print(f"[build] 入口 {len(src)} 个 → {os.path.basename(IN_F)}")
    if skip:
        print(f"[build] 无部门栏目而跳过 {len(skip)} 个：{' '.join(skip)}")


def merge():
    if not os.path.exists(MUNI_OUT):
        print(f"!! 缺 {os.path.basename(MUNI_OUT)}，先跑 p250（P250_OUT 指向它）")
        return
    muni = json.load(open(MUNI_OUT, encoding="utf-8"))
    depts = json.load(open(DEPTS_F, encoding="utf-8")) if os.path.exists(DEPTS_F) else {}
    n_new = n_upd = 0
    added = []
    written = set()
    for k, v in muni.items():
        if not k.startswith("地级区|"):
            continue
        name = k.split("|")[-1]
        ds = _clean([d for d in (v.get("depts") or []) if d.get("n") and d.get("u")],
                    name)
        if len(ds) < 3:
            continue
        written.add(k)
        if k in depts:
            n_upd += 1
        else:
            n_new += 1
            added.append((k, len(ds)))
        depts[k] = {**v, "depts": ds}
    # 上一轮并进去、这轮被清洗到 <3 条的市辖区记录要撤掉，否则残留的 3 条
    # 半截名录会一直挡住「回退到栏目链接」的逻辑（红桥区实锤）
    stale = [k for k in depts if k.startswith("地级区|") and k not in written]
    for k in stale:
        depts.pop(k)
    json.dump(depts, open(DEPTS_F, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    open(DEPTS_F, "a", encoding="utf-8").write("\n")
    print(f"[merge] 新增 {n_new} 个市辖区名录，更新 {n_upd} 个；"
          f"撤回 {len(stale)} 个（清洗后不足 3 条）；"
          f"county_depts.json 共 {len(depts)} 条")
    for k, n in added:
        print(f"   + {k.split('|', 1)[1]} {n} 部门")


def _clean(ds, name=""):
    """剔掉村/居委员会、区政府自身那条——与 merge() 同一口径。"""
    return [d for d in ds
            if not d["n"].endswith(("村民委员会", "居民委员会", "村居委员会",
                                    "社区居民委员会"))
            and not (d["n"].endswith("人民政府")
                     and not d["n"].endswith(("镇人民政府", "乡人民政府")))
            and d["n"] != name]


def report():
    muni = json.load(open(MUNI_OUT, encoding="utf-8")) if os.path.exists(MUNI_OUT) else {}
    src = json.load(open(IN_F, encoding="utf-8")) if os.path.exists(IN_F) else {}
    ok = [(k, len(_clean([d for d in (v.get("depts") or [])
                          if d.get("n") and d.get("u")], k.split("|")[-1])))
          for k, v in muni.items()]
    ok = [(k, n) for k, n in ok if n >= 3]
    print(f"入口 {len(src)} · 产出 {len(ok)} · 待补 {len(src) - len(ok)}")
    for k, n in sorted(ok, key=lambda x: -x[1])[:10]:
        print(f"   {k.split('|', 1)[1]} {n}")
    okset = {k for k, _ in ok}
    miss = [k.split("|")[-1] for k in src if k not in okset]
    if miss:
        print("待补：" + " ".join(miss))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--merge", action="store_true")
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args()
    if not (a.build or a.merge or a.report):
        ap.print_help()
        return
    if a.build:
        build()
    if a.merge:
        merge()
    if a.report:
        report()


if __name__ == "__main__":
    main()
