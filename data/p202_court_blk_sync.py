#!/usr/bin/env python
# p202 中院 URL 条→块同步: 条树高院组 382 中院节点的 u 回填块树各市
# 「并列机关→市中级人民法院」节点（空才填, p78 纪律），registry 同键同步。
#
# 2026-11-17 契约修复:
#   ① 条树里仍残留已审计为死的旧域（xjcourt.org / *.chinacourt.gov.cn /
#      elink 包着的同类目标, p220 判死）— 回填前必须拦截, 否则会把
#      p220 清掉的死链重新写回块树（阿勒泰中院已实际踩中一次）。
#   ② 只有真正回填时才写盘; 写盘统一 indent=1, 避免全文件格式化噪音。
#   ③ main() 入口保护, import 本模块不再执行同步。
import json, os, sys, tempfile
from urllib.parse import parse_qs, urlparse
DATA = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, DATA)
from site_contract import five_key, five_name, upsert_registry
TREE_F = os.path.join(DATA, "tree.json")
REG_F = os.path.join(DATA, "site_registry.json")


def _atomic(obj, path):
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def _dead_host(host):
    host = (host or "").lower().split(":")[0]
    return host.endswith("xjcourt.org") or host.endswith(".chinacourt.gov.cn")


def _dead_url(u):
    """p220 判死域拦截（含 elink 包裹的目标域）。"""
    u = (u or "").strip()
    if not u:
        return False
    p = urlparse(u)
    if _dead_host(p.netloc):
        return True
    for v in parse_qs(p.query).get("elid", []):
        if _dead_host(urlparse(v).netloc):
            return True
    return False


def find(n, name):
    if n.get("n") == name:
        return n
    for k in n.get("ks") or []:
        r = find(k, name)
        if r:
            return r
    return None


def main():
    t = json.load(open(TREE_F, encoding="utf-8"))
    reg = json.load(open(REG_F, encoding="utf-8"))
    g = find(t, "高级人民法院（32）")
    filled = skipped_dead = 0
    for hn in (g.get("ks") or []):
        for k in (hn.get("ks") or []):
            u = (k.get("u") or "").strip()
            if not u:
                continue
            if _dead_url(u):
                skipped_dead += 1
                continue
            city = k["n"].replace("中级人民法院", "")
            blk = find(t, city)
            if not blk:
                print("块树无区划:", city)
                continue
            for jg in (blk.get("ks") or []):
                if jg.get("c") != "并列机关":
                    continue
                for o in (jg.get("ks") or []):
                    if o.get("n") == "市中级人民法院" and not o.get("u"):
                        o["u"] = u
                        src = f"来源:{hn['n']}官网中院区块 HTML 提取"
                        o["s"] = src
                        filled += 1
                        upsert_registry(reg, five_key(city, "市中级人民法院"), u,
                                        name=five_name(city, "市中级人民法院"),
                                        source_level="L1", source=src,
                                        locations=["块", "条"])
    if filled:
        _atomic(t, TREE_F)
        _atomic(reg, REG_F)
    print("filled:", filled, "skipped_dead:", skipped_dead)


if __name__ == "__main__":
    main()
