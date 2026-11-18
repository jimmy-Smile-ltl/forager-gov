"""p240b：文章/详情页 URL 处置 —— 能根化的根化，根页也过不了身份校验的清空。

p240 全量核查把「文章/新闻/详情页路径」列为 suspect（只报告不清除）。这类链接
按项目口径**不是机构官网入口**（文章页必须拒），但多数是「本机构站点上的一篇
文章」——把根页抓下来重判：根页身份通过 → 换成根页；不通过 → 留空列名。

用法：
    uv run python p240b_article_fix.py            # 只出方案
    uv run python p240b_article_fix.py --apply    # 落库（先备份）
"""
import argparse
import json
import os
import shutil
import datetime
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

import p240_full_url_verify as p240


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    tree = json.load(open(p240.TREE_F, encoding="utf-8"))
    p240.collect_all_places(tree)
    recs = p240.collect_records(tree)
    p240.build_prov_hosts(recs)
    p240.build_city_hosts(recs)

    report = json.load(open(p240.REPORT_F, encoding="utf-8"))
    arts = [r for r in report["rows"] if r["reason"] == "文章/详情页路径"]
    print(f"文章/详情页记录 {len(arts)} 条，唯一 URL {len({r['u'] for r in arts})}")

    by_root = defaultdict(list)
    for r in arts:
        p = urlparse(r["u"])
        by_root[f"{p.scheme}://{p.netloc}/"].append(r)

    roots = list(by_root)
    print(f"待复判根页 {len(roots)} 个", flush=True)
    done = {}
    with ThreadPoolExecutor(p240.CONC) as ex:
        for res in ex.map(p240.fetch_one, roots):
            done[res["u"]] = res

    # 根页对每条记录单独判身份（同一根页可能对应不同机构节点）
    fix = {}
    for root, rows in by_root.items():
        res = done.get(root)
        for r in rows:
            if not res:
                fix[r["u"]] = ("", f"根页未抓到（{root}）")
                continue
            rec = {"u": root, "name": r["name"], "k": r.get("k") or "",
                   "c": r.get("c") or "", "path": r["path"], "lv": r.get("lv") or [],
                   "prov": r["prov"], "tree": r["tree"]}
            v, why = p240.judge(rec, res)
            if v in ("ok", "ok_neutral", "waf"):
                fix[r["u"]] = (root, f"根化自文章页（{v}）")
            else:
                fix[r["u"]] = ("", f"根页亦不合格（{v}: {why}）")

    n_root = sum(1 for v in fix.values() if v[0])
    print(f"方案：根化 {n_root} 条，清空 {len(fix) - n_root} 条")
    for u, (new, why) in list(fix.items())[:8]:
        print(f"  {u[:64]}\n     → {new or '（清空）'}  {why}")

    json.dump({u: v[0] for u, v in fix.items()},
              open(os.path.join(p240.BASE_DIR, "p240b_article_fix.json"), "w",
                   encoding="utf-8"), ensure_ascii=False, indent=1)
    if not args.apply:
        print("（未 --apply，未改数据）")
        return

    d = os.path.join(p240.ROOT, "backups", p240.TODAY)
    os.makedirs(d, exist_ok=True)
    ts = datetime.datetime.now().strftime("%H%M%S")
    for f in ("tree.json", "site_registry.json"):
        shutil.copy2(os.path.join(p240.BASE_DIR, f),
                     os.path.join(d, f"{f.split('.')[0]}_before_p240b_{ts}.json"))

    # 按 路径+名称+旧URL 精确落到节点，避免误改同 URL 的其他节点
    bad = defaultdict(list)
    for r in arts:
        bad[(r["tree"], tuple(r["path"]))].append(r)
    n_clear = n_root = 0
    cleared = set()

    def walk(n, path, kind):
        nonlocal n_clear, n_root
        u = (n.get("u") or "").strip()
        if u and u in fix:
            for r in bad.get((kind, tuple(path)), []):
                if r["name"] == (n.get("n") or "").strip() and r["u"] == u:
                    new, why = fix[u]
                    cleared.add(u)
                    if new:
                        n["u"] = new
                        n_root += 1
                    else:
                        n["u"] = ""
                        n_clear += 1
                    n["s"] = ((n.get("s") or "") + f" | p240b 文章页处置: {why}").strip(" |")
                    break
        for c in n.get("ks") or []:
            walk(c, path + [(n.get("n") or "").strip()], kind)

    for g in tree["ks"]:
        kind = "tiao" if (g.get("l") == "根" or (g.get("n") or "").startswith("条")) else "blk"
        walk(g, [], kind)
    json.dump(tree, open(p240.TREE_F, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    alive = set()

    def collect(n):
        u = (n.get("u") or "").strip()
        if u:
            alive.add(u)
        for c in n.get("ks") or []:
            collect(c)
    for g in tree["ks"]:
        collect(g)

    reg = json.load(open(p240.REG_F, encoding="utf-8"))
    reg_hit = 0
    for k, v in reg.items():
        u = (v.get("u") or "").strip()
        if u in fix and u not in alive:
            new, why = fix[u]
            v["u"] = new
            v["status"] = "rooted" if new else "cleared"
            v["verified_at"] = p240.TODAY
            v["note"] = (v.get("note") or "") + f" | p240b 文章页处置: {why}"
            reg_hit += 1
    json.dump(reg, open(p240.REG_F, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    print(f"落库：根化 {n_root} 个节点、清空 {n_clear} 个；registry {reg_hit} 条")
    print(f"备份: {d}")


if __name__ == "__main__":
    main()
