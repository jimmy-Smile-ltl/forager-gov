# -*- coding: utf-8 -*-
"""P22: 把 tree.json / extraction_rules.json 拆分为模块化数据文件。

输出 data_js/：
  manifest.js          根结构 + 各模块桩(stub) + 预计算统计 + 文件映射（记录各 JSON 逻辑关系）
  modules/central.js   中央板块（党中央/国务院/并列机关/海关）
  modules/<省>.js      每省一个（并列机关+厅局+市州+区县，省名拼音做文件名）
  modules/gat.js       港澳台板块
  rules/<省>.js        每省提取规则（含 Python 代码，按需加载）

加载约定：每个模块文件执行 window.__M["<key>"] = {节点JSON}；
manifest.js 执行 window.__MANIFEST__ = {...}。
"""
import subprocess, sys
try:
    subprocess.run([sys.executable, "backup_now.py"], capture_output=True,
                   timeout=30, cwd=__import__("os").path.dirname(__import__("os").path.abspath(__file__)))
except Exception:
    pass  # 备份失败不阻断主流程

import json
import re
import os
from urllib.parse import urlparse

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data_js")


def prov_py(name):
    s = re.sub(r"(省|市|特别行政区)$", "", name)
    s = re.sub(r"(壮族|回族|维吾尔)?自治区$", "", s)
    s = re.sub(r"[（）()·、]", "_", s)
    return s


def stats_of(node):
    e = ok = warn = miss = 0

    def walk(n):
        nonlocal e, ok, warn, miss
        if not n.get("ks") or n.get("k") != "分组":
            e += 1
            if n.get("x"):
                ok += 1
            elif n.get("u"):
                warn += 1
            else:
                miss += 1
        for k in n.get("ks", []):
            walk(k)
    walk(node)
    return {"e": e, "ok": ok, "warn": warn, "miss": miss}


def main():
    tree = json.load(open("tree.json", encoding="utf-8"))
    rules = json.load(open("extraction_rules.json", encoding="utf-8"))
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(os.path.join(OUT, "modules"), exist_ok=True)
    os.makedirs(os.path.join(OUT, "rules"), exist_ok=True)

    # 顶层分组
    central_g = next(g for g in tree["ks"] if g["n"].startswith("中央"))
    prov_g = next(g for g in tree["ks"] if g["n"].startswith("省级"))
    gat_g = next(g for g in tree["ks"] if g["n"].startswith("港澳台"))
    extra_gs = [g for g in tree["ks"]
                if g not in (central_g, prov_g, gat_g)]   # 工会系统/条（垂直管理系统）等

    # ---- 模块文件 ----
    def write_module(key, node, fname):
        node = dict(node)
        with open(os.path.join(OUT, fname), "w", encoding="utf-8") as f:
            f.write("window.__M=window.__M||{};window.__M[%s]=%s;\n"
                    % (json.dumps(key, ensure_ascii=False),
                       json.dumps(node, ensure_ascii=False, separators=(",", ":"))))

    write_module("central", central_g, "modules/central.js")
    write_module("gat", gat_g, "modules/gat.js")
    for g in extra_gs:
        write_module(g["n"], g, "modules/%s.js" % prov_py(g["n"]))

    prov_stubs = []
    for pnode in prov_g["ks"]:
        key = pnode["n"]
        fname = "modules/%s.js" % prov_py(key)
        write_module(key, pnode, fname)
        prov_stubs.append({
            "n": pnode["n"], "l": pnode.get("l", "省"), "k": pnode.get("k", "人民政府"),
            "c": pnode.get("c", ""), "cd": pnode.get("cd", ""),
            "u": pnode.get("u", ""), "x": pnode.get("x", ""),
            "s": pnode.get("s", ""), "m": pnode.get("m", ""),
            "file": fname, "_key": key, "_stats": stats_of(pnode),
        })

    # ---- 规则模块 ----
    rules_files = {}
    for pname, r in rules.items():
        fname = "rules/%s.js" % prov_py(pname)
        with open(os.path.join(OUT, fname), "w", encoding="utf-8") as f:
            f.write("window.__R=window.__R||{};window.__R[%s]=%s;\n"
                    % (json.dumps(pname, ensure_ascii=False),
                       json.dumps(r, ensure_ascii=False, separators=(",", ":"))))
        rules_files[pname] = fname

    # ---- 统计 ----
    per = {}
    all_e = all_ok = all_warn = 0
    LEVELS = ["中央", "省", "市", "地级区", "县", "特别行政区", "港澳台"]
    for lv in LEVELS:
        s = {"e": 0, "ok": 0, "warn": 0, "miss": 0}
        # 中央/港澳台：直接算；省级：由各省 stub 汇总（省本体在 stub，厅局/市县在模块）
        def add(node, lv_name):
            nonlocal all_e, all_ok, all_warn
            if not node.get("ks") or node.get("k") != "分组":
                if node.get("l") == lv_name:
                    s["e"] += 1
                    if node.get("x"):
                        s["ok"] += 1
                    elif node.get("u"):
                        s["warn"] += 1
                    else:
                        s["miss"] += 1
                if node.get("l") == lv_name:
                    all_e += 1
                    if node.get("x"):
                        all_ok += 1
                    elif node.get("u"):
                        all_warn += 1
            for k in node.get("ks", []):
                add(k, lv_name)
        for g in (central_g, gat_g):
            add(g, lv)
        # 省级模块统计（含省本体）
        for stub in prov_stubs:
            node = next(n for n in prov_g["ks"] if n["n"] == stub["n"])
            add(node, lv)
        per[lv] = s

    extra_stubs = [{
        "n": g["n"], "l": g.get("l", "根"), "k": g.get("k", "分组"),
        "c": g.get("c", ""), "file": "modules/%s.js" % prov_py(g["n"]),
        "_key": g["n"], "_stats": stats_of(g),
    } for g in extra_gs]

    root = {
        "n": tree["n"], "l": tree["l"], "k": tree["k"], "c": tree.get("c", ""),
        "ks": [
            {**{k: central_g.get(k, "") for k in ("n", "l", "k", "c")}, "file": "modules/central.js",
             "_key": "central", "_stats": stats_of(central_g)},
            {**{k: prov_g.get(k, "") for k in ("n", "l", "k", "c")}, "ks": prov_stubs,
             "_stats": stats_of(prov_g)},
            {**{k: gat_g.get(k, "") for k in ("n", "l", "k", "c")}, "file": "modules/gat.js",
             "_key": "gat", "_stats": stats_of(gat_g)},
            *extra_stubs,
        ],
    }
    manifest = {
        "version": "2026-10-30",
        "root": root,
        "total": {"e": all_e, "ok": all_ok, "warn": all_warn},
        "perLevel": per,
        "modules": {"central": "modules/central.js", "gat": "modules/gat.js",
                    **{s["n"]: s["file"] for s in prov_stubs},
                    **{s["n"]: s["file"] for s in extra_stubs}},
        "rulesFiles": rules_files,
        "desc": "中国政府信息公开名录模块化数据。modules/<key>.js 为树节点模块；"
                "rules/<省>.js 为提取规则；manifest 记录根结构与各文件逻辑关系。",
    }
    with open(os.path.join(OUT, "manifest.js"), "w", encoding="utf-8") as f:
        f.write("window.__MANIFEST__=%s;\n" % json.dumps(manifest, ensure_ascii=False, separators=(",", ":")))

    sizes = {}
    for dirpath, _dirs, files in os.walk(OUT):
        for fn in files:
            p = os.path.join(dirpath, fn)
            sizes[os.path.relpath(p, OUT)] = os.path.getsize(p)
    big = sorted(sizes.items(), key=lambda x: -x[1])[:6]
    
    print("data_js 生成完成", [(k, f"{v//1024}KB") for k, v in big])


# ===== 数据质量统计（质量面板数据源）=====
def gen_quality():
    import json as _json
    tree = _json.load(open("tree.json", encoding="utf-8"))
    reg = _json.load(open("site_registry.json", encoding="utf-8")) if _json.load else {}
    tiao = next(g for g in tree["ks"] if g["n"].startswith("条"))
    rows = []
    for g in tiao["ks"]:
        cnt = [0, 0, 0]
        def walk(x):
            cnt[0] += 1
            if x.get("u"): cnt[1] += 1
            if x.get("x"): cnt[2] += 1
            for k in x.get("ks", []): walk(k)
        walk(g)
        n, u, x = cnt
        rows.append({"name": g["n"], "nodes": n, "urls": u, "xxgk": x,
                     "coverage": round(u / n * 100, 1) if n else 0})
    from collections import Counter
    lvl = Counter(v.get("source_level", "L4") for v in reg.values() if v.get("u"))
    st = Counter(v.get("status", "unknown") for v in reg.values() if v.get("u"))
    # xxgk 全局统计：有官网叶子的专栏覆盖
    xx_all = [0, 0]
    def w2(x):
        if x.get("u") and not x.get("ks"):
            xx_all[0] += 1
            if x.get("x"): xx_all[1] += 1
        for k in x.get("ks", []): w2(k)
    w2(tree)
    # URL 缺失率（省/市/县 × 系统，p221）——同时刷新 data/URL_STATS.md
    url_stats = None
    try:
        from p221_url_stats import build_and_write as _build_url_stats
        url_stats = _build_url_stats(tree)
    except Exception as e:
        print(f"[警告] URL 缺失率统计失败(不阻断管线): {e}")
    q = {"systems": rows, "source_level": dict(lvl), "status": dict(st),
         "registry_total": len(reg),
         "xxgk": {"leaves_with_url": xx_all[0], "with_column": xx_all[1],
                  "coverage": round(xx_all[1] / xx_all[0] * 100, 1) if xx_all[0] else 0},
         "url_stats": url_stats}
    with open("../data_js/quality.js", "w", encoding="utf-8") as f:
        f.write("window.__QUALITY__=" + _json.dumps(q, ensure_ascii=False) + ";")
    print(f"质量统计已生成: {len(rows)} 系统")
gen_quality()

# 可视化数据（块/条双视图）——每次重建自动刷新, 兼容数据更新
try:
    from gen_viz import gen_viz
    gen_viz()
except Exception as e:
    print(f"[警告] 可视化数据生成失败(不阻断管线): {e}")


if __name__ == "__main__":
    main()
