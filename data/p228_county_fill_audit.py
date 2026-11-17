#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""p228 县级五系统补采结果审计（2026-11-17，用户「尽可能补全」配套质检）。

p223 S1/S2/S3/S4 落库后抽查发现一类残留错采：**新闻文章页**被当成机构官网
（如「藤县监委 ← 梧州纪检监察网 /art124920.html『藤县濛江镇纪委：暖心回访…』」）。
p223 的 NEWS_PATH 已补 `art\\d+`，本脚本对**已落库**的补采条目重扫：

  A 文章/新闻路径 → 清空 u（列名），s 留痕审计结论
  B 疑似错配（URL 无机构/地名特征且 title 无县名）→ 只报告不清理
  C 统计本轮补采的 title 复验通过率

用法：
  cd data && uv run python p228_county_fill_audit.py --dry
  cd data && uv run python p228_county_fill_audit.py
"""
import datetime
import json
import os
import random
import re
import shutil
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

DATA = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(DATA)
sys.path.insert(0, DATA)
sys.path.insert(0, os.path.join(ROOT, "util"))
from p223_county_5sys_fill import (BAD_COLUMN, CHANNEL_OK, LEADER_PATH,  # noqa: E402
                                   NEWS_PATH, TITLE_BAD, page_title)
from site_contract import base as geo_base  # noqa: E402
import hashlib  # noqa: E402
import p223_county_5sys_fill as P  # noqa: E402

TREE_F = os.path.join(DATA, "tree.json")
TODAY = datetime.date.today().isoformat()
DRY = "--dry" in sys.argv
MARKS = ("辖区链接", "导航", "互链", "SERP")
ORG_NAMES = {"县人大", "县政协", "县人民法院", "县人民检察院", "县监委"}
CACHE = "/tmp/p228_cache"      # 复核是只读的：磁盘缓存让二次复核从小时级降到分钟级
_ORIG_FETCH = P.fetch


def _cached_fetch(u, timeout=15):
    """p223.fetch 的磁盘缓存包装（标题复核专用；不写任何数据）。"""
    if not u:
        return ""
    os.makedirs(CACHE, exist_ok=True)
    f = os.path.join(CACHE, hashlib.sha1(u.encode()).hexdigest() + ".html")
    if os.path.exists(f):
        try:
            h = open(f, encoding="utf-8", errors="ignore").read()
            if h:
                return h
        except OSError:
            pass
    h = _ORIG_FETCH(u, timeout=timeout) or ""
    try:
        with open(f, "w", encoding="utf-8") as fh:
            fh.write(h)
    except OSError:
        pass
    return h


P.fetch = _cached_fetch
P.fetch_cached = _cached_fetch


def walk(n, p=""):
    yield n, p
    for c in n.get("ks") or []:
        yield from walk(c, p + "/" + (n.get("n") or "")[:12])


def main():
    tree = json.load(open(TREE_F, encoding="utf-8"))
    blk = next(g for g in tree["ks"] if g["n"].startswith("省级"))

    hits, suspects = [], []
    for prov in blk["ks"]:
        for n, p in walk(prov):
            u = (n.get("u") or "").strip()
            s = n.get("s") or ""
            if not u or n.get("n") not in ORG_NAMES:
                continue
            if not any(k in s for k in MARKS):
                continue
            if "p228 审计" in s:
                continue
            if (BAD_COLUMN.search(u) or LEADER_PATH.search(u)
                    or (NEWS_PATH.search(u) and not CHANNEL_OK.search(u))):
                hits.append((n, p, u, s))

    print(f"p228 审计：待查 {len(hits)} 条疑似文章页")
    for n, p, u, s in hits[:12]:
        print(f"  DEL {p.split('/')[-2][:10]}/{n.get('n')} {u[:70]}")

    if not DRY and hits:
        d = os.path.join(ROOT, "backups", TODAY)
        os.makedirs(d, exist_ok=True)
        ts = datetime.datetime.now().strftime("%H%M%S")
        shutil.copy2(TREE_F, os.path.join(d, f"tree_before_p228_{ts}.json"))
        for n, p, u, s in hits:
            n["s"] = (f"{s}｜p228 审计: 文章/新闻页路径非机构官网，清除"
                      f"（原 {u[:60]}）")
            n["u"] = ""
        json.dump(tree, open(TREE_F, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        print(f"已清除 {len(hits)} 条并写回 tree.json")

    # D 上级机构站点 / 机构类型错配（title 复验，本轮补采全量）
    allf = []
    for prov in blk["ks"]:
        for n, p in walk(prov):
            u = (n.get("u") or "").strip()
            s = n.get("s") or ""
            if u and n.get("n") in ORG_NAMES and any(k in s for k in MARKS):
                allf.append((n, p, u))
    print(f"p228 D 轮 title 复验 {len(allf)} 条 …")
    wrong = []

    def dcheck(item):
        n, p, u = item
        t = page_title(u) or ""
        nm = n.get("n") or ""
        if not t:
            return None
        badw = TITLE_BAD.search(t.replace("政治协商会议", ""))
        if badw:
            return (item, f"业务栏目页({badw.group(1)}) title={t[:34]}")
        up = re.search(r"(中级人民|高级人民|最高人民法院|州中级|地区中级|分院)", t)
        if up:
            return (item, f"上级机构站点({up.group(1)}) title={t[:34]}")
        is_court = nm == "县人民法院"
        if is_court and "检察院" in t and "法院" not in t:
            return (item, f"机构类型错配(检察) title={t[:34]}")
        if nm == "县人民检察院" and "法院" in t and "检察院" not in t:
            return (item, f"机构类型错配(法院) title={t[:34]}")
        return None

    with ThreadPoolExecutor(8) as ex:
        for r in ex.map(dcheck, allf):
            if r:
                wrong.append(r)
                print(f"  D-WRONG {r[1][:90]}")
    if not DRY and wrong:
        d = os.path.join(ROOT, "backups", TODAY)
        os.makedirs(d, exist_ok=True)
        ts = datetime.datetime.now().strftime("%H%M%S")
        shutil.copy2(TREE_F, os.path.join(d, f"tree_before_p228d_{ts}.json"))
        for (n, p, u), why in wrong:
            n["s"] = f"{n.get('s') or ''}｜p228 审计: {why}，清除（原 {u[:60]}）"
            n["u"] = ""
        json.dump(tree, open(TREE_F, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        print(f"p228 D 已清除 {len(wrong)} 条并写回 tree.json")


    # E 全量「县名在标题内」复验（本轮起新增；只报告，不自动清）
    #    title 空=JS 壳站；中性标题=门户频道——都不算错，单列存疑
    print(f"p228 E 全量县名复验 {len(allf)} 条 …")
    susp = 0

    def echeck(item):
        n, p, u = item
        t = page_title(u) or ""
        if not t:
            return "empty", item
        # 县名在路径末段（节点名是通用「县人民法院」，不含地名）
        seg = [x for x in p.split("/") if x]
        county = seg[-1] if seg else ""
        b = geo_base(county) or county[:2]
        sibs = seg[-2:]
        nm_hit = bool(b) and (b in t or any(x[:2] in t for x in sibs if len(x) >= 2))
        return ("ok" if nm_hit else "noname"), item

    from collections import Counter
    cnt = Counter()
    seen = set()
    with ThreadPoolExecutor(8) as ex:
        for kind, item in ex.map(echeck, allf):
            cnt[kind] += 1
            if kind == "noname":
                n, p, u = item
                key = (p, u)
                if key in seen:
                    continue
                seen.add(key)
                susp += 1
                if susp <= 25:
                    print(f"  E-NONAME {p.split('/')[-2][:12]}/{n.get('n')} {u[:62]}")
    print(f"p228 E 结果: 县名相符 {cnt['ok']} / title空(JS壳) {cnt['empty']}"
          f" / 标题无县名 {cnt['noname']}")

    # C 抽样复验（title 与节点名/地名是否相符）
    nodes = []
    for prov in blk["ks"]:
        for n, p in walk(prov):
            u = (n.get("u") or "").strip()
            s = n.get("s") or ""
            if u and n.get("n") in ORG_NAMES and any(k in s for k in MARKS) \
                    and NEWS_PATH.search(u) is None:
                nodes.append((n, p, u))
    random.seed(20261117)
    sample = random.sample(nodes, min(40, len(nodes)))
    ok = bad = 0
    lock = threading.Lock()

    def check(item):
        n, p, u = item
        t = page_title(u) or ""
        seg = p.split("/")
        ctx = " ".join(seg[-3:]) + " " + (n.get("n") or "")
        b = geo_base(n.get("n") or "")
        hit = bool(t) and (b and b in t or any(x in t for x in seg[-3:] if len(x) >= 2))
        failed = (not t) or "Welcometonginx" in t
        return (hit, failed), f"{p.split('/')[-3].split('、')[0][:8]}/{seg[-2][:8]}/{n.get('n')} title={t[:34]} {u[:52]}"

    unknown = 0
    with ThreadPoolExecutor(8) as ex:
        for (hit, failed), line in ex.map(check, sample):
            if hit:
                ok += 1
            elif failed:
                unknown += 1
            else:
                bad += 1
                print("  SUSPECT", line)
    print(f"p228 抽样复验 {len(sample)} 条: title 相符 {ok}, 抓取失败 {unknown}, 可疑 {bad}")

    # F 全量按 p223 现行严格校验复验（他机构/仅市名/领导建议栏目/媒体域…）
    #   只报告默认；P228_FIX=1 才清除（明确错配类）
    from p223_county_5sys_fill import collect as _collect, title_ok as _title_ok
    from p223_county_5sys_fill import page_title as _ptitle
    _blk, _tasks = _collect(tree)
    filled = [t for t in _tasks if t["filled"]]
    CLEAR_KINDS = ("他机构页面", "仅市名无县全名", "领导/建议类栏目",
                   "文章标题", "领导之窗页", "非官网栏目页",
                   "上级机构站点", "媒体/聚合域名")
    freport, fclear = [], []

    def fcheck(t):
        u = (t["org"].get("u") or "").strip()
        if not u:
            return t, "", ""
        tt = _ptitle(u) or ""
        ok, note = _title_ok(tt, t, False)
        if not ok and note.startswith("无县名"):
            # 「无县名」只在标题出现上级地名（省/市）时才算错配——
            # 「海淀纪检监察网」「首页_古韵正声」这类只丢县名的品牌站保留
            pb = geo_base(t["prov"] or "")
            cb = geo_base(t["parent"].get("n") or "")
            if not ((pb and pb in tt) or (cb and cb in tt)):
                note = ""
        return t, tt, note

    with ThreadPoolExecutor(8) as ex:
        for t, tt, note in ex.map(fcheck, filled):
            if not note:
                continue
            freport.append((t, tt, note))
            if any(note.startswith(k) for k in CLEAR_KINDS):
                fclear.append((t, tt, note))
    from collections import Counter as _C
    kc = _C(n.split("(")[0] for _, _, n in freport)
    print(f"p228 F 复验 {len(filled)} 条：不符 {len(freport)}"
          f"（其中可清除类 {len(fclear)}） {dict(kc)}")
    for t, tt, note in freport[:30]:
        print(f"  F-{note[:22]:<22} {t['prov']}/{t['parent'].get('n')}/{t['county'].get('n')}"
              f"/{t['org_name']} {tt[:26]} {(t['org'].get('u') or '')[:56]}")
    if os.environ.get("P228_FIX") == "1" and fclear and not DRY:
        d = os.path.join(ROOT, "backups", TODAY)
        os.makedirs(d, exist_ok=True)
        ts = datetime.datetime.now().strftime("%H%M%S")
        shutil.copy2(TREE_F, os.path.join(d, f"tree_before_p228f_{ts}.json"))
        for t, tt, note in fclear:
            t["org"]["s"] = (f"{t['org'].get('s') or ''}｜p228F: {note}，清除"
                            f"（原 {(t['org'].get('u') or '')[:60]} title={tt[:30]}）")
            t["org"]["u"] = ""
        json.dump(tree, open(TREE_F, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        print(f"p228 F 已清除 {len(fclear)} 条并写回 tree.json")


if __name__ == "__main__":
    main()
