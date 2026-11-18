"""p241b —— p241 回填结果的独立复核（新进程 = 全新抓取）。

对树里 s 带「p241」痕迹且 u 非空的节点逐条重抓，用 p241 同一套身份校验
（`p241_wrong_url_backfill.verify`，含本轮新增的政府门户负向规则）复核，
独立于回填时的内存缓存——回填说 ok 的，这里要能再过一次。

  · 硬通过：取到页面且 title/地区/机构判定全过
  · 软通过：页面取不到（WAF/封锁/IP 拦截）+ 官方页面链接 + DNS 可解析，
    按项目「封锁默认正确」口径保留，但单独列出供人工复核
  · 失败：身份不过/死域/形态违规 → --apply 清除（宁缺毋滥）

URL 取不到时先换 http/https 再试；换协议后能硬通过的，落库 URL 随之升级
（实测 佳木斯市向阳区：http 取不到、https 标题正确）。

用法（在 data/ 目录）：
    uv run python p241b_new_url_audit.py            # 只出报告
    uv run python p241b_new_url_audit.py --apply    # 清除失败项 + 协议升级（写前备份）
环境变量：P241B_WORKERS（默认 4）
"""
import datetime
import json
import os
import shutil
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit, urlunsplit

import p240_full_url_verify as V
import p241_wrong_url_backfill as P

DATA = os.path.dirname(os.path.abspath(__file__))
TREE_F = os.path.join(DATA, "tree.json")
REG_F = os.path.join(DATA, "site_registry.json")
REPORT_F = os.path.join(DATA, "p241b_audit_report.json")
TODAY = datetime.date.today().isoformat()
APPLY = "--apply" in sys.argv
WORKERS = int(os.environ.get("P241B_WORKERS", "4"))

SOFT_KW = ("页面不可取", "WAF")


def audit_targets(tree):
    """s 带 p241 痕迹、u 非空的节点（与 p240 collect_records 同口径建 path/prov）。"""
    out = []

    def walk(n, path, lv, prov, anc, kind):
        name = (n.get("n") or "").strip()
        myprov = prov
        if n.get("l") == "省" and name:
            p = V.place_of(name)
            if p and V.is_real_prov(p[0]):
                myprov = p[0]
        u = (n.get("u") or "").strip()
        s = n.get("s") or ""
        # p241 三类回填的痕迹：通用/同步写「p241」，五系统段是 p223 渠道
        # 落库的「来源:…」+ 原有的 p240 清除痕迹（历史轮次没写 p241 前缀）
        p241 = ("p241" in s
                or ("p240" in s and "来源:" in s and "p241b" not in s))
        if name and u.startswith("http") and p241:
            out.append({"node": n, "name": name, "k": n.get("k") or "",
                        "c": n.get("c") or "", "path": list(path),
                        "lv": list(lv), "prov": myprov, "anc": list(anc),
                        "tree": kind, "u": u, "s": s,
                        # SERP 来源没有官方页面背书，按严格口径复核
                        "nav": "SERP" not in s})
        for c in n.get("ks") or []:
            walk(c, path + [name], lv + [n.get("l") or ""], myprov,
                 anc + [n], kind)

    for g in tree["ks"]:
        kind = "tiao" if (g.get("l") == "根"
                          or (g.get("n") or "").startswith("条")) else "blk"
        walk(g, [], [], "", [], kind)
    return out


def swap_scheme(u):
    p = urlsplit(u)
    sch = "http" if p.scheme == "https" else "https"
    return urlunsplit((sch, p.netloc, p.path or "/", p.query, ""))


def check(t):
    """返回 {res: pass/soft/fail, u, note, upgrade, title}。"""
    u = t["u"]
    ok, note, fu = P.verify(t, u, official=True, nav=t["nav"])
    soft = ok and any(x in note for x in SOFT_KW)
    if not ok or soft:
        alt = swap_scheme(u)
        if alt != u:
            ok2, note2, fu2 = P.verify(t, alt, official=True, nav=t["nav"])
            if ok2 and not any(x in note2 for x in SOFT_KW):
                s = P.snap(fu2)
                title = (s[0].get("title") or "") if s else ""
                return {"res": "pass", "u": fu2, "note": note2,
                        "title": title,
                        "upgrade": fu2 if fu2.strip("/") != u.strip("/") else ""}
    s = P.snap(fu)
    title = (s[0].get("title") or "") if s else ""
    if ok and not soft:
        return {"res": "pass", "u": fu, "note": note, "upgrade": "", "title": title}
    if ok:
        return {"res": "soft", "u": fu, "note": note, "upgrade": "", "title": title}
    # 回填时页面上已取到过 title（s 留痕），本轮取不到属 WAF/封锁/限流——
    # 按项目「封锁默认正确」口径保留观察，不当错配清除
    if any(note.startswith(x) for x in SOFT_KW) and "title=" in t["s"]:
        return {"res": "soft", "u": fu, "title": title,
                "note": "回填时 title 已验证，本轮取不到（封锁默认正确）",
                "upgrade": ""}
    return {"res": "fail", "u": fu, "note": note, "upgrade": "", "title": title}


def reg_clear(reg, t, u):
    """按 URL + 名称匹配定位 registry 条目并清空（不给别的节点误清）。"""
    cands = [(k, v) for k, v in reg.items()
             if (v.get("u") or "").strip() == u]
    named = [(k, v) for k, v in cands
             if (v.get("n") or k.split("|")[-1]).endswith(t["name"])]
    for k, v in named:
        v["u"] = ""
        v["status"] = "cleared"
        v["verified_at"] = TODAY
        v["source"] = ((v.get("source") or "")
                       + f" | p241b 复核清除({TODAY})").strip(" |")
    return [k for k, _ in named]


def dedupe(rows, todo):
    """同一 URL 挂到不同机构（地区/系统不同）时裁决归属。

    实测 四川省金川县监委 与 甘肃省金川区监委 被回填成同一个
    jinchuanjcjjjc.gov.cn——两个机构不可能共用一个纪委站。
    标题能唯一对上某个机构时保留它、清其余；对不上就全清（宁缺毋滥）。
    同一机构的块/条双视图共用 URL 不算冲突。
    """
    by_u = defaultdict(list)
    for t, r in zip(todo, rows):
        if r["res"] in ("pass", "soft"):
            by_u[r["u"].rstrip("/").lower()].append((t, r))
    for u, items in by_u.items():
        if len(items) < 2:
            continue
        ident = {}
        for t, r in items:
            deep = V.rec_places(P.rec_of(t, ""))[2]
            ident[id(r)] = (deep, P.fam_of(t["name"]))
        if len(set(ident.values())) < 2:
            continue
        # 标题里能唯一认领的机构；标题全是中性名（「金川纪检监察网」）时
        # 再看正文——金川区的站正文写「金川区/金昌」，金川县的站写「金川县/阿坝」
        def claims(t, r):
            deep = ident[id(r)][0]
            if not deep:
                return False
            if deep in (r.get("title") or ""):
                return "title"
            s = P.snap(r["u"])
            body = (s[0].get("snippet") or "") if s else ""
            return "body" if deep in body else ""

        keeper = ""
        for basis in ("title", "body"):
            hit = {id(r): claims(t, r) == basis for t, r in items}
            if sum(hit.values()) == 1:
                keeper = next(t["name"] for t, r in items if hit[id(r)])
                hitter = {id(r) for t, r in items if hit[id(r)]}
                break
        else:
            hitter = set()
        for t, r in items:
            if keeper and id(r) in hitter:
                continue
            r["res"] = "fail"
            r["note"] = (f"同一 URL 已归属别处机构({keeper})" if keeper
                         else "同一 URL 挂多个机构("
                              + "/".join(sorted({d for d, _ in ident.values()})) + ")")


def main():
    tree = json.load(open(TREE_F, encoding="utf-8"))
    reg = json.load(open(REG_F, encoding="utf-8"))
    V.collect_all_places(tree)
    P.build_dup_counties()

    todo = audit_targets(tree)
    print(f"p241b 复核目标（s 带 p241 痕迹 + u 非空）: {len(todo)}")
    if not todo:
        return

    if APPLY:
        d = os.path.join(P.ROOT, "backups", TODAY)
        os.makedirs(d, exist_ok=True)
        ts = datetime.datetime.now().strftime("%H%M%S")
        shutil.copy2(TREE_F, os.path.join(d, f"tree_before_p241b_{ts}.json"))
        shutil.copy2(REG_F, os.path.join(d, f"registry_before_p241b_{ts}.json"))

    rows = []
    with ThreadPoolExecutor(WORKERS) as ex:
        for t, r in zip(todo, ex.map(check, todo)):
            r.update({"name": t["name"], "path": t["path"], "k": t["k"],
                      "u0": t["u"]})
            rows.append(r)
    dedupe(rows, todo)
    for t, r in zip(todo, rows):
        tag = {"pass": "✓", "soft": "?", "fail": "✗"}[r["res"]]
        where = "/".join(t["path"][-2:])
        extra = f"  [升级 {r['upgrade'][:60]}]" if r["upgrade"] else ""
        print(f"  {tag} {t['name']} @ {where} -> {r['u'][:64]}{extra}"
              f"\n      {r['note'][:90]}", flush=True)

    np = sum(1 for r in rows if r["res"] == "pass")
    ns = sum(1 for r in rows if r["res"] == "soft")
    nf = sum(1 for r in rows if r["res"] == "fail")
    print(f"\n复核: 硬通过 {np} / 软通过 {ns} / 失败 {nf}")

    cleared = upgraded = 0
    if APPLY:
        by_key = {id(t["node"]): (t, r) for t, r in zip(todo, rows)}
        for node_id, (t, r) in by_key.items():
            node = t["node"]
            if r["res"] == "fail":
                node["u"] = ""
                node["s"] = ((node.get("s") or "")
                             + f" | p241b 复核清除({r['note'][:60]})").strip(" |")
                reg_clear(reg, t, r["u0"])
                cleared += 1
            elif r["res"] == "pass" and r["upgrade"]:
                node["u"] = r["upgrade"]
                node["s"] = ((node.get("s") or "")
                             + " | p241b http/https 升级").strip(" |")
                upgraded += 1
        if cleared or upgraded:
            P._atomic(tree, TREE_F)
            P._atomic(reg, REG_F)
        print(f"落库: 清除 {cleared} / 协议升级 {upgraded}")

    P._atomic({"generated": datetime.datetime.now().isoformat(timespec="seconds"),
               "applied": APPLY, "pass": np, "soft": ns, "fail": nf,
               "rows": rows}, REPORT_F)
    print(f"报告: {REPORT_F}")


if __name__ == "__main__":
    main()
