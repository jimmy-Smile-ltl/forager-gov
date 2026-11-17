# -*- coding: utf-8 -*-
"""P95: 政协市级挂载（政协系统条模块 + 老系统回填）。仿 p78。"""
import json
import re

MUNICIPAL = {"北京市", "天津市", "上海市", "重庆市"}

def find_lv(prov_g, pname, nm):
    p = next(x for x in prov_g["ks"] if x["n"] == pname)
    for top in p.get("ks", []):
        def walk(n):
            if n.get("k") in ("人民政府", "功能区") and n["n"] == nm \
                    and n.get("l") in ("市", "县", "地级区"):
                return n["l"]
            for k in n.get("ks", []):
                r = walk(k)
                if r:
                    return r
        r = walk(top)
        if r:
            return r
    return "市"

def main():
    rows = [json.loads(l) for l in open("rd_zx.jsonl", encoding="utf-8")]
    tree = json.load(open("tree.json", encoding="utf-8"))
    rules = json.load(open("extraction_rules.json", encoding="utf-8"))
    prov_g = next(g for g in tree["ks"] if g["n"].startswith("省级"))
    tiao = next(g for g in tree["ks"] if g["n"] == "条（垂直管理系统）")

    zx_sys = next(g for g in tiao["ks"] if g["n"].startswith("政协系统"))
    gy = next(x for x in zx_sys["ks"] if x["n"].startswith("省级政协"))

    by_prov = {}
    for r in rows:
        by_prov.setdefault(r["province"], []).append(r)

    added = filled = 0
    for pnode in gy["ks"]:
        pname = pnode["n"].replace("政协", "")
        if pname not in by_prov:
            continue
        existing = {k["n"] for k in pnode.get("ks", [])}
        for r in by_prov[pname]:
            lv = find_lv(prov_g, pname, r["name"])
            nm = f"{r['name']}政协"
            if nm in existing:
                for k in pnode.get("ks", []):
                    if k["n"] == nm:
                        if r["url"]:
                            if not k.get("u"):
                                k["u"] = r["url"]
                        else:
                            k["u"] = ""
                # 已存在也回填老系统
                p = next(x for x in prov_g["ks"] if x["n"] == pname)
                for top in p.get("ks", []):
                    def wfill(n):
                        if n.get("l") == lv and n["n"] == r["name"] \
                                and n.get("k") in ("人民政府", "功能区"):
                            par = next((g for g in n.get("ks", [])
                                        if g.get("c") == "并列机关"), None)
                            if par:
                                m = next((x for x in par.get("ks", [])
                                          if "政协" in x["n"]), None)
                                if m:
                                    m["u"] = r["url"]
                                    return True
                        for k in n.get("ks", []):
                            if wfill(k):
                                return True
                        return False
                    if wfill(top):
                        break
                continue
            pnode.setdefault("ks", []).append(
                {"n": nm, "l": lv, "k": "政协系统", "c": "政协系统",
                 "u": r["url"], "x": "", "s": "", "m": ""})
            existing.add(nm)
            added += 1
            p = next(x for x in prov_g["ks"] if x["n"] == pname)
            for top in p.get("ks", []):
                def wfill(n):
                    if n.get("l") == lv and n["n"] == r["name"] \
                            and n.get("k") in ("人民政府", "功能区"):
                        par = next((g for g in n.get("ks", [])
                                    if g.get("c") == "并列机关"), None)
                        if par:
                            m = next((x for x in par.get("ks", [])
                                      if "政协" in x["n"]), None)
                            if m:
                                m["u"] = r["url"]
                                return True
                    for k in n.get("ks", []):
                        if wfill(k):
                            return True
                    return False
                if wfill(top):
                    break

    json.dump(tree, open("tree.json", "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    print(f"p95 完成：政协系统市级/区级挂载 {added}")

if __name__ == "__main__":
    main()
