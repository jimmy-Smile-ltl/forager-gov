#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""p247_sitemap.py — 网站地图/站点导航渠道补采（p246 的第七通道，官方渠道）。

适用形态：p246 六阶段全灭的门户——首页没有机构类锚点、枢纽页也渲染不出机构入口，
但站内「网站地图 / 站点导航 / 全站导航」页通常把全站栏目平铺（含机构设置、部门导航）。
本脚本只走 **站内官方页面**：首页（静态/渲染）→ 网站地图锚 → 地图页锚点分类 →
候选回抓 + `page_score` 严格验证（静态不过再渲染一次，与 candrender 同款兜底）。
**不拼路径、不猜域名、不走搜索引擎**，与项目合规口径一致。

用法（在 data/ 目录，单写者：不得与 p246 同时运行）：
  PROXY_MODE=dps RS_DISABLE=1 P246_RENDER_PROXY=1 BROWSER_TIERS=off \
    uv run python p247_sitemap.py --workers 3
  ... --only "唐山市 太原市"        # 只跑指定门户
产物：并入 `zzjg_pages.json`（与 p246 同一事实源，增量并 links）。
"""
import argparse
import json
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import p246_zzjg_pages as P  # 复用获取/分类/验证/合并，保持单一判定标准

SITEMAP_KW = re.compile(r"网站地图|站点地图|网站导航|站点导航|全站导航|网站索引|网站导览")


def out_data():
    if not os.path.exists(P.OUT_F):
        return {}
    return json.load(open(P.OUT_F, encoding="utf-8"))


def missing_targets(targets, only):
    """只跑「还没有核心类别链接」的门户（与 p246 阶段跳过口径一致）。"""
    data = out_data()
    miss = []
    for t in targets:
        if only and not any(o in t["name"] for o in only):
            continue
        rec = data.get(t["key"]) or {}
        kinds = [l.get("kind") for l in rec.get("links") or []]
        if any(k in P.CORE_KINDS for k in kinds):
            continue
        miss.append(t)
    return miss


def sitemap_links(html, base_url):
    """首页 HTML → 同站「网站地图/站点导航」锚 URL 列表（最多 3 条）。"""
    out = []
    for m in re.finditer(P.ANCHOR_RE, html or ""):
        h = re.search(r"href\s*=\s*[\"']([^\"']+)[\"']", m.group(1), re.I)
        if not h:
            continue
        text = P.norm_text(m.group(2))
        if not text or len(text) > 12 or not SITEMAP_KW.search(text):
            continue
        u = urljoin(base_url, h.group(1).strip())
        if u.startswith("http") and P.same_site(u, base_url) and u not in out:
            out.append(u)
    return out[:3]


def try_sitemap(t):
    """门户 → 网站地图 → 栏目候选 → 验证。返回 (rec, err)。"""
    deadline = time.time() + P.BUDGET
    home, m0 = P.fetch_or_render(t["url"], timeout=20)
    if not home or len(home) < 1500:
        return None, f"home-{m0}-short"
    maps = sitemap_links(home, t["url"])
    if not maps:
        return None, "no-sitemap-anchor"
    tried = 0
    for su in maps:
        if time.time() > deadline:
            break
        sh, m1 = P.fetch_or_render(su, timeout=20)
        if not sh or len(sh) < 1000:
            continue
        links = []
        cands = [c for c in P.link_candidates(sh, su) if c[0] >= 4]
        # 类别优先于分数（营口教训：真正机构页评分不高但类别核心）
        cands.sort(key=lambda c: (-P.KIND_BASE.get(c[3], 0), -c[0]))
        for score, text, url, kind in cands[:6]:
            if time.time() > deadline:
                break
            tried += 1
            h2, m2 = P.fetch(url, timeout=15)
            ok, s2, title, why = P.page_score(url, h2, kind)
            if not ok and time.time() < deadline:
                # 地图页链过去常是 JS 列表页：渲染后再验一次（candrender 同款）
                h3 = P.render_page(url, wait_ms=1800, use_proxy=True)
                if h3 and len(h3) > len(h2 or ""):
                    ok, s2, title, why = P.page_score(url, h3, kind)
                    if ok:
                        m2 = "render"
            if ok:
                links.append(dict(
                    kind=kind, u=url, title=title,
                    src=(f"网站地图「{P.norm_text(su)[:30]}」候选锚「{text}」"
                         f"(打分{score}) → 验证 {why}"),
                    method=m2, score=s2))
                if len(links) >= 3:
                    break
        if links:
            rec = P.make_rec(links, method=f"sitemap/{m1}")
            if rec:
                return rec, ""
    return None, f"sitemap-no-verified (地图{len(maps)}, 候选尝试{tried})"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="", help="只跑名称包含这些词的门户")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--budget", type=float, default=None, help="每站秒数（默认同 p246）")
    args = ap.parse_args()
    if args.budget:
        P.BUDGET = args.budget

    targets = P.load_targets()
    todo = missing_targets(targets, args.only.split())
    P.log(f"== sitemap 阶段: 待处理 {len(todo)} / 总 {len(targets)}")
    lock = threading.Lock()
    hits = 0
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as ex:
        futs = {ex.submit(try_sitemap, t): t for t in todo}
        for fut in as_completed(futs):
            t = futs[fut]
            try:
                rec, err = fut.result()
            except Exception as e:
                rec, err = None, f"exc:{str(e)[:60]}"
            with lock:
                if rec:
                    hits += 1
                    P.merge_links(t["key"], rec)
                    P.log(f"[sitemap][OK] {t['key']} -> {rec['u']}  ({rec['title'][:30]})")
                else:
                    P.log(f"[sitemap][--] {t['key']} {err}")
    P.log(f"== sitemap 完成: 处理 {len(todo)}，命中 {hits}，耗时 {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
