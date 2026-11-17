#!/usr/bin/env python
# p202 中院 URL 条→块同步: 条树高院组 382 中院节点的 u 回填块树各市
# 「并列机关→市中级人民法院」节点（空才填, p78 纪律）。
import json, os, tempfile
TREE_F = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tree.json")
def _atomic(obj, path):
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
    with os.fdopen(fd, "w") as f:
        json.dump(obj, f, ensure_ascii=False)
    os.replace(tmp, path)
t = json.load(open(TREE_F, encoding="utf-8"))
def find(n, name):
    if n.get("n") == name:
        return n
    for k in n.get("ks") or []:
        r = find(k, name)
        if r:
            return r
    return None
g = find(t, "高级人民法院（32）")
filled = 0
for hn in (g.get("ks") or []):
    prov = hn["n"].replace("高级人民法院", "")
    for k in (hn.get("ks") or []):
        u = (k.get("u") or "").strip()
        if not u:
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
                    o["s"] = f"来源:{hn['n']}官网中院区块 HTML 提取"
                    filled += 1
_atomic(t, TREE_F)
print("filled:", filled)
