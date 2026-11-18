"""p244 —— URL 形态修复：`https:https://…` 重复协议头（阳泉法院 5 站）。

来源：山西法院网 elink 解码时把内层完整 URL 直接拼在外层 `https:` 后面，
落库成 `https:https://yqcqfy.shanxify.gov.cn`——浏览器打不开、p240/p243
抓取全失败（当时按「无证据」放过），但站点本身是好的。

做法：
  1. 全树 + registry 扫描 `^https?:(https?://)` 形态；
  2. 去掉重复协议头，用 p241 的 verify() 按节点自己的身份复核
     （title 含地区/机构，或省级平台子站口径），复核不过的不改；
  3. --apply 落库（写前备份 tree/registry），tree 与 registry 同步修。

用法（在 data/ 目录）：
    uv run python p244_url_form_fix.py            # 只出报告
    uv run python p244_url_form_fix.py --apply    # 修正落库
"""
import datetime
import json
import os
import re
import shutil
import sys

import p240_full_url_verify as V
import p241_wrong_url_backfill as P

DATA = os.path.dirname(os.path.abspath(__file__))
TREE_F = os.path.join(DATA, "tree.json")
REG_F = os.path.join(DATA, "site_registry.json")
TODAY = datetime.date.today().isoformat()
APPLY = "--apply" in sys.argv

DUP_PROTO = re.compile(r"^(https?:)(https?://)", re.I)


def fix(u):
    """`https:https://x` → `https://x`；多层也只剥到一层合法。"""
    u = (u or "").strip()
    while True:
        m = DUP_PROTO.match(u)
        if not m:
            return u
        u = m.group(2) + u[m.end():]


def targets(tree):
    out = []

    def walk(n, path, lv, prov, kind):
        name = (n.get("n") or "").strip()
        myprov = prov
        if n.get("l") == "省" and name:
            p = V.place_of(name)
            if p and V.is_real_prov(p[0]):
                myprov = p[0]
        u = (n.get("u") or "").strip()
        if name and DUP_PROTO.match(u):
            out.append({"node": n, "name": name, "k": n.get("k") or "",
                        "c": n.get("c") or "", "path": list(path),
                        "lv": list(lv), "prov": myprov, "tree": kind,
                        "u": u, "s": n.get("s") or ""})
        for c in n.get("ks") or []:
            walk(c, path + [name], lv + [n.get("l") or ""], myprov, kind)

    for g in tree["ks"]:
        kind = "tiao" if (g.get("l") == "根"
                          or (g.get("n") or "").startswith("条")) else "blk"
        walk(g, [], [], "", kind)
    return out


def main():
    tree = json.load(open(TREE_F, encoding="utf-8"))
    reg = json.load(open(REG_F, encoding="utf-8"))
    V.collect_all_places(tree)
    P.build_dup_counties()
    P.build_url_owners(tree)

    todo = targets(tree)
    print(f"p244 重复协议头 URL: {len(todo)} 节点")
    ok_rows = []
    fail = []
    for t in todo:
        nu = fix(t["u"])
        ok, note, fu = P.verify(t, nu, official=True, nav=True)
        if ok:
            ok_rows.append((t, fu, note))
            print(f"  ✓ {t['name']} @ {'/'.join(t['path'][-2:])}\n"
                  f"      {t['u'][:34]}… -> {fu[:70]}  ({note})")
        else:
            fail.append((t, nu, note))

    # 条树简称（阳泉城区法院 / 阳泉矿区法院）与块树「城区/矿区 → 县人民法院」
    # 是同一机构：修正后的 URL 若已由块视图节点通过复核，条视图直接跟随。
    def ident(t):
        return ((t["prov"] or ""), P.base_norm(P.rec_of(t, "")),
                P.fam2(t["name"]))

    passed = {}
    for t, fu, _ in ok_rows:
        passed.setdefault(fu.rstrip("/").lower(), set()).add(ident(t))
    still = []
    for t, nu, note in fail:
        owners = passed.get(nu.rstrip("/").lower()) or set()
        if ident(t) in owners:
            ok_rows.append((t, nu, "条块同机构(块视图已验证同 URL)"))
            print(f"  ✓ {t['name']} @ {'/'.join(t['path'][-2:])}  "
                  f"条块同机构跟随 -> {nu[:70]}")
        else:
            still.append((t, nu, note))
            print(f"  ✗ {t['name']} @ {'/'.join(t['path'][-2:])} 修正后仍不过: "
                  f"{note}  -> {nu[:70]}")
    print(f"\n可修 {len(ok_rows)} / {len(todo)}")

    nfix = nreg = 0
    if APPLY and ok_rows:
        d = os.path.join(P.ROOT, "backups", TODAY)
        os.makedirs(d, exist_ok=True)
        ts = datetime.datetime.now().strftime("%H%M%S")
        shutil.copy2(TREE_F, os.path.join(d, f"tree_before_p244_{ts}.json"))
        shutil.copy2(REG_F, os.path.join(d, f"registry_before_p244_{ts}.json"))
        for t, fu, note in ok_rows:
            t["node"]["u"] = fu
            t["node"]["s"] = ((t["node"].get("s") or "")
                              + f" | p244 重复协议头修复({note})").strip(" |")
            nfix += 1
        for k, v in reg.items():
            old = (v.get("u") or "").strip()
            if not DUP_PROTO.match(old):
                continue
            nu = fix(old)
            # registry 条目按 URL 归属判断：该 URL 已出现在树里就跟着改
            if any(fu.strip("/") == nu.strip("/") for _, fu, _ in ok_rows
                   ) or nu in {fix(x["u"]) for x in todo}:
                v["u"] = nu
                v["verified_at"] = TODAY
                v["status"] = "ok"
                v["source"] = ((v.get("source") or "")
                               + f" | p244 重复协议头修复({TODAY})").strip(" |")
                nreg += 1
        P._atomic(tree, TREE_F)
        P._atomic(reg, REG_F)
        print(f"落库: 节点 {nfix} / registry {nreg}")
    elif not APPLY:
        print("（dry-run，未写库；加 --apply 落库）")


if __name__ == "__main__":
    main()
