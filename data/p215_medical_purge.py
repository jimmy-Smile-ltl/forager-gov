#!/usr/bin/env python
# p215 医疗系统 URL 污染治理（2026-11-17 用户指令「检验医疗系统的url正确性」收尾）
# 背景: p214 全量复验 + 深路径根址探测发现 29 个深路径 URL 中 26 个是
#   门户文章页/公告页/他部门页面（财政局/民政局/市场监管局/纪委监委/
#   依申请公开平台/政务服务网等），另有 12 个门户根址 mismatch。
# 规则（用户红线: 机构 URL 必须是官网/权威入口, 宁缺毋滥不许猜）:
#   1) 深路径 → 机构子站首页(标题=机构全名)保留; 否则根址 title 验证通过
#      则根化; 都不过 → 清空（列名）
#   2) 根址 → title 机构验证; 中性/空 title(JS 壳)保留; 不符 → 清空
#   3) waf(412/521 防护) 保留（来源权威, 仅当前无法 title 验证）
#   4) 同步 p213_state 与 site_registry（防 p198_loop 下一轮重新采回污染 URL）
# 用法: BROWSER_TIERS=off uv run python p215_medical_purge.py
import importlib.util
import json
import os
import re
import sys
from urllib.parse import urlparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
TREE_F = os.path.join(DATA, "tree.json")
STATE_F = os.path.join(DATA, "p213_state.json")
REG_F = os.path.join(DATA, "site_registry.json")
TODAY = "2026-11-17"

spec = importlib.util.spec_from_file_location("p205", os.path.join(DATA, "p213_medical_system.py"))
p205 = importlib.util.module_from_spec(spec)
sys.modules["p205"] = p205
spec.loader.exec_module(p205)


def atomic(obj, path):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def resolve_cdc(pn, u):
    """疾控节点复验: 规则同 p205 CDC 采集段（子站首页保留/根化/拒绝文章页）"""
    pbase = p205.base(pn)

    def ok(tt):
        if not tt:
            return False
        t1 = p205._clean_title(tt)
        if re.search(r"(招聘|公示|拟聘|医院|学院|学校|采购|考试|年度报告)", t1):
            return False
        if pbase not in t1:
            return False
        return ("疾病预防控制中心" in t1) or ("疾控中心" in t1)

    p = urlparse(u)
    if not p205._dns_ok(p.netloc):
        return None
    tt = p205.title_of(p205.fetch(u))
    if not tt:
        return u  # JS 壳/抓取失败存疑保留
    if p.path not in ("", "/"):
        root = f"{p.scheme}://{p.netloc}/"
        rt = p205.title_of(p205.fetch(root))
        if ok(rt):
            return p205.norm_host(root)
        if p205.is_org_home_deep(pn + "疾病预防控制中心", u, tt):
            return p205.norm_host(u)
        return None
    return p205.norm_host(u) if ok(tt) else None


def main():
    t = json.load(open(TREE_F, encoding="utf-8"))
    st = json.load(open(STATE_F, encoding="utf-8")) if os.path.exists(STATE_F) else {"prov": {}, "city": {}, "cdc": {}}
    reg = json.load(open(REG_F, encoding="utf-8")) if os.path.exists(REG_F) else {}

    med = p205.find(t, "医疗系统（卫生健康）")
    if not med:
        print("医疗系统未找到")
        return
    prov_grp = next(g for g in med["ks"] if g["n"].startswith("省级卫生健康委员会"))
    cdc_grp = next(g for g in med["ks"] if g["n"].startswith("省级疾控中心"))
    prov_names = [p["n"] for p in prov_grp["ks"]]
    prov_bases = [p205.base(p) for p in prov_names]

    cleared, rooted, kept, waf_kept = [], [], [], []
    changed_reg = {}

    def update_reg(cat, name, old_u, new_u):
        nb = p205.base(name)
        for k, v in reg.items():
            rcat, rname = k.split("|", 1)
            if rcat != cat or p205.base(rname) != nb:
                continue
            if (v.get("u") or "") != old_u:
                continue
            v["u"] = new_u or ""
            v["verified_at"] = TODAY
            if not new_u:
                v["status"] = "cleared"
            changed_reg[k] = new_u or ""
            return

    tasks = []  # (kind, pn, cnode, cn, cbase, collide, u)
    for pnode in prov_grp["ks"]:
        pn = pnode["n"][:-len("卫生健康委员会")]
        if pnode["n"].startswith("新疆生产建设兵团"):
            continue
        for cnode in pnode.get("ks", []):
            u = (cnode.get("u") or "").strip()
            if not u:
                continue
            cn = cnode["n"]
            cb = p205.base(cn)
            collide = len(cb) >= 2 and any(cb in pb for pb in prov_bases)
            tasks.append(("city", pn, cnode, cn, cb, collide, u))
    for cnode in cdc_grp.get("ks", []):
        u = (cnode.get("u") or "").strip()
        if not u:
            continue
        pn = cnode["n"][:-len("疾病预防控制中心")]
        tasks.append(("cdc", pn, cnode, cnode["n"], "", False, u))

    from concurrent.futures import ThreadPoolExecutor

    def work(x):
        kind, pn, cnode, cn, cb, collide, u = x
        if kind == "city":
            return p205.resolve_city_url(cn, cb, u, strict=collide)
        return resolve_cdc(pn, u)

    with ThreadPoolExecutor(12) as ex:
        results = list(ex.map(work, tasks))

    for (kind, pn, cnode, cn, cb, collide, old_u), new_u in zip(tasks, results):
        if new_u == old_u:
            kept.append((cn, old_u))
            continue
        cnode["u"] = new_u or ""
        if new_u:
            rooted.append((cn, old_u, new_u))
            cnode["s"] = (cnode.get("s") or "") + "｜2026-11-17 根化"
        else:
            cleared.append((cn, old_u))
            cnode["s"] = ""
            note = "原URL为省卫健委直属单位文章页" if kind == "cdc" else "原URL为门户文章页/他机构页面"
            cnode["m"] = (cnode.get("m") + "｜" if cnode.get("m") else "") + \
                f"{note}，按红线列名（2026-11-17 URL 正确性检验）"
        if kind == "city":
            update_reg("市级政府部门", cn, old_u, new_u)
            st["city"][f"{pn}|{cn[:-len('卫生健康委员会')]}"] = new_u or "miss"
        else:
            update_reg("疾控中心", cn, old_u, new_u)
            st.setdefault("cdc", {})[pn] = new_u or "miss"

    # waf 存疑项列出来（保留不判错）
    report_f = os.path.join(DATA, "medical_url_check_report.json")
    if os.path.exists(report_f):
        rep = json.load(open(report_f, encoding="utf-8"))
        waf_kept = [(x["n"], x["u"]) for x in rep["results"] if x["verdict"] == "waf"]

    atomic(t, TREE_F)
    atomic(st, STATE_F)
    atomic(reg, REG_F)

    print(f"根化 {len(rooted)}:")
    for n, o, u in rooted:
        print(f"  🔗 {n} | {o[:60]} → {u}")
    print(f"\n清空列名 {len(cleared)}:")
    for n, u in cleared:
        print(f"  ❌ {n} | {u[:70]}")
    print(f"\n保留 {len(kept)} / WAF 存疑保留 {len(waf_kept)}")
    for n, u in waf_kept:
        print(f"  🛡 {n} | {u[:60]}")
    print(f"\nregistry 更新 {len(changed_reg)} 条")


if __name__ == "__main__":
    main()
