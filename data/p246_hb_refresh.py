# -*- coding: utf-8 -*-
"""重算已落库的 homeblock（首页内嵌机构名录）记录：口径升级后回填。

2026-11-18 口径升级（标题归属 + 本地性校验 + 集约化网站标签）之后，旧记录里
存在两类问题：① 分组标题取成了名录里某条链接的文字（合肥「市委老干部局」、
苏州「市委书记信箱」）；② 把国家部委/省政府部门友链区当成本地名录（伊春/
牡丹江/绥化/武汉/郴州旧记录）。本脚本按新口径逐条重抓首页、重算，命中则
更新 title/src/groups，不命中则剔除该 homeblock 链接（整条空了就删记录并
从 state.done 移除，留给后续阶段重采）。

用法：cd data && uv run python p246_hb_refresh.py
"""
import json
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import p246_zzjg_pages as P  # noqa: E402


def main():
    bak = P.OUT_F + ".bak_hbrefresh"
    shutil.copy2(P.OUT_F, bak)
    print(f"backup → {bak}", flush=True)
    data = json.load(open(P.OUT_F, encoding="utf-8"))
    state = P.load_state()

    keys = [k for k, r in data.items()
            if any(l.get("homeblock") for l in (r.get("links") or []))]
    print(f"homeblock records: {len(keys)}", flush=True)

    kept = dropped = 0
    t0 = time.time()
    for i, k in enumerate(keys, 1):
        r = data[k]
        lvl = k.split("|")[0]
        url = r.get("u") or ""
        try:
            home, hm = P.fetch_or_render(url, timeout=20)
            ok, why = P.homepage_block(home or "", lvl, url)
            if not ok and "render" not in (hm or ""):
                h2 = P.render_page(url, wait_ms=4000, use_proxy=True)
                if h2 and len(h2) > len(home or ""):
                    ok, why = P.homepage_block(h2, lvl, url)
                    if ok:
                        home, hm = h2, "render"
            groups = P._block_groups(home or "", url, level=lvl) if ok else []
        except Exception as e:
            print(f"[{i}/{len(keys)}] {k} EXC {type(e).__name__}: {e}", flush=True)
            continue
        links = r.get("links") or []
        if ok and groups:
            for l in links:
                if l.get("homeblock"):
                    l["title"] = f"{k.split('|')[1]}门户首页·内嵌机构名录"
                    l["src"] = f"门户首页内嵌机构名录（前序阶段未发现独立栏目页）→ {why}"
                    l["method"] = f"homeblock/{hm}"
                    l["n_groups"] = len(groups)
                    l["n_depts"] = sum(g["n"] for g in groups)
                    l["groups"] = groups
                    l["verified_at"] = P.TODAY
            kept += 1
            print(f"[{i}/{len(keys)}] KEEP {k} :: {why}", flush=True)
        else:
            r["links"] = [l for l in links if not l.get("homeblock")]
            dropped += 1
            print(f"[{i}/{len(keys)}] DROP {k} :: {why}", flush=True)
            if not r["links"]:
                data.pop(k, None)
                state.get("done", {}).pop(k, None)
                print(f"        → 记录整体删除，state.done 移除（待重采）", flush=True)
            else:
                r["u"] = r["links"][0].get("u", "")
                r["title"] = r["links"][0].get("title", "")
                r["src"] = r["links"][0].get("src", "")
                r["method"] = r["links"][0].get("method", "")
                r["score"] = r["links"][0].get("score", 0)
        # 每 5 条落盘一次
        if i % 5 == 0:
            json.dump(data, open(P.OUT_F, "w", encoding="utf-8"),
                      ensure_ascii=False, indent=1)
            P.save_state(state)
    json.dump(data, open(P.OUT_F, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    P.save_state(state)
    print(f"== done: 保留 {kept}，剔除 {dropped}，耗时 {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
