# -*- coding: utf-8 -*-
"""P254: 群团 URL 树/注册表冲突复核（2026-11-19 数据巡检）。

p252 改名时发现：群团叶子「tree 里挂的」和「registry 里存的」有 12 条跨主域冲突，
其中若干是明显错挂（山西省台联 → zjtmtl.org.cn 浙江台联、湖南省作协 → zjzj.org
浙江作家、黑龙江省工商联 → acfic.org.cn 全国工商联、云南/宁夏作协 → chinawriter
文章页）。两处都会展示给用户，必须收敛成同一权威 URL。

做法（不猜域名、不做 SERP，只复验已知候选）：
  1. 收集 tree 与 registry URL 跨主域的群团叶子；
  2. 两个候选都用 smart_fetch 取真实标题（重试 2 次，空标题视为不可判）；
  3. 标题判定：必须同时含机构核心词 + 本省名，且 URL 不是新闻/文章路径；
  4. 裁决：
       tree 通过、registry 不通过 → registry 改挂 tree（以展示层为准）
       registry 通过、tree 不通过 → tree 改挂 registry，s 留痕
       都通过 → registry 改挂 tree（同站收敛）
       都不可判/都不通过 → 不动，列「待人工」
     ——单侧「不通过」不足以下结论（标题可能只是「XX网」），故只有一真一假才改。

干跑加 --dry。
"""
import datetime
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

from p223_county_5sys_fill import NEWS_PATH, NEWS_QUERY, page_title

TODAY = datetime.date.today().isoformat()
DRY = "--dry" in sys.argv

CORE = [
    ("台湾同胞联谊会", ("台湾同胞联谊会", "台联")),
    ("作家协会", ("作家协会", "作家网", "作协", "作家")),
    ("工商业联合会", ("工商业联合会", "工商联", "总商会")),
    ("科学技术协会", ("科学技术协会", "科协")),
    ("归国华侨联合会", ("归国华侨联合会", "侨联")),
    ("残疾人联合会", ("残疾人联合会", "残联")),
    ("红十字会", ("红十字会", "红会")),
    ("法学会", ("法学会",)),
    ("新闻工作者协会", ("新闻工作者协会", "记协")),
    ("文学艺术界联合会", ("文学艺术界联合会", "文联")),
    ("欧美同学会", ("欧美同学会", "留学人员")),
    ("计划生育协会", ("计划生育协会", "计生协")),
    ("国际贸易促进委员会", ("国际贸易促进委员会", "贸促会", "CCPIT")),
    ("人民对外友好协会", ("人民对外友好协会", "对外友好协会", "友协")),
    ("总工会", ("总工会",)),
    ("共青团", ("共青团", "团省委", "团委")),
    ("妇女联合会", ("妇女联合会", "妇联")),
]
PROV_SUF = ("维吾尔自治区", "壮族自治区", "回族自治区", "自治区", "省", "市")


def prov_base(nm):
    for suf in PROV_SUF:
        if nm.endswith(suf) and len(nm) > len(suf) + 1:
            return nm[: -len(suf)]
    return nm


def cores_of(nm):
    for k, ws in CORE:
        if k in nm:
            return ws
    return ()


def judge(name, prov, u):
    """→ (True 通过 / False 不通过 / None 不可判, 说明, title)"""
    if NEWS_PATH.search(u) or NEWS_QUERY.search(u):
        return False, "新闻/文章路径", ""
    t = page_title(u)
    if not t:
        return None, "title空", ""
    ws = cores_of(name)
    pb = prov_base(prov)
    core_ok = any(w in t for w in ws) if ws else None
    prov_ok = (pb in t) or (prov in t)
    if core_ok is None:
        return None, "无核心词表", t
    if core_ok and prov_ok:
        return True, "ok", t
    if not core_ok:
        return False, "标题无机构核心词", t
    return False, "标题无本省名", t


def host(u):
    h = (urlparse((u or "").strip()).netloc or "").lower()
    return h[4:] if h.startswith("www.") else h


def walk(n):
    yield n
    for k in n.get("ks") or []:
        yield from walk(k)


def main():
    tree = json.load(open("tree.json", encoding="utf-8"))
    reg = json.load(open("site_registry.json", encoding="utf-8"))
    prov_g = next(g for g in tree["ks"] if g["n"].startswith("省级"))

    tasks = []
    for p in prov_g["ks"]:
        for g in p.get("ks") or []:
            if not (g.get("n") or "").startswith("群团"):
                continue
            for c in g.get("ks") or []:
                u = (c.get("u") or "").strip()
                e = reg.get(f"群团|{c.get('n')}")
                if not u or not e:
                    continue
                ru = (e.get("u") or "").strip()
                if ru and host(u) != host(ru):
                    tasks.append({"node": c, "prov": p["n"], "key": f"群团|{c['n']}",
                                  "tree_u": u, "reg_u": ru, "name": c["n"]})
    print(f"p254 跨主域冲突 {len(tasks)} 条")

    def probe(t):
        t["tree"] = judge(t["name"], t["prov"], t["tree_u"])
        t["reg"] = judge(t["name"], t["prov"], t["reg_u"])
        return t

    with ThreadPoolExecutor(3) as ex:
        tasks = list(ex.map(probe, tasks))

    fixed_reg = fixed_tree = merged = manual = 0
    for t in tasks:
        (tok, tnote, ttitle), (rok, rnote, rtitle) = t["tree"], t["reg"]
        print(f"  {t['prov']}｜{t['name']}")
        print(f"    tree {t['tree_u'][:66]} → {tok}:{tnote}｜{ttitle[:34]}")
        print(f"    reg  {t['reg_u'][:66]} → {rok}:{rnote}｜{rtitle[:34]}")
        e = reg[t["key"]]
        if tok and not rok:
            if not DRY:
                e["u"] = t["tree_u"]
                e["status"] = "ok"
                e["verified_at"] = TODAY
                e["source"] = "p254 树/registy 冲突复核：标题验证通过（树为准）"
            fixed_reg += 1
        elif rok and not tok:
            if not DRY:
                old = t["tree_u"]
                t["node"]["u"] = t["reg_u"]
                t["node"]["s"] = (f"来源:p254 冲突复核改写（注册表标题验证通过，"
                                  f"原挂 {old[:44]}）")
                e["verified_at"] = TODAY
                e["status"] = "ok"
            fixed_tree += 1
        elif tok and rok:
            if not DRY:
                e["u"] = t["tree_u"]
                e["status"] = "ok"
                e["verified_at"] = TODAY
            merged += 1
        else:
            manual += 1
            print("    → 待人工（不满足单侧通过，保持原样）")

    print(f"p254 结论：registry 改挂树 {fixed_reg}，树改挂 registry {fixed_tree}，"
          f"同站收敛 {merged}，待人工 {manual}")
    if DRY:
        print("--dry 干跑，未写盘")
        return
    if fixed_reg or fixed_tree or merged:
        with open("tree.json", "w", encoding="utf-8") as f:
            json.dump(tree, f, ensure_ascii=False, indent=1)
            f.write("\n")
        with open("site_registry.json", "w", encoding="utf-8") as f:
            json.dump(reg, f, ensure_ascii=False, indent=1)
            f.write("\n")
        print("已写 tree.json / site_registry.json")


if __name__ == "__main__":
    main()
