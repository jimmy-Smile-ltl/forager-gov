#!/usr/bin/env python
# p211 五系统 URL 修正（第二轮，2026-11-17）
# 依据 p205 审计复验 + 省级官网导航（L1 权威源）重新定位:
#   镇江检察   → zj.jsjc.gov.cn      江苏检察网首页「市级检察院」导航
#   淮北监委   → www.hbjjjc.gov.cn   安徽纪检监察网首页「市县纪委」导航
#   六安监委   → www.lajjjc.gov.cn   同上
# 原值分别是江苏检察网专题文章页 / 淮北发改委领导简历页 / 六安人大决定文章页。
import json, os, re, shutil, time, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TREE_F = os.path.join(ROOT, "data", "tree.json")
BAK_DIR = os.path.join(ROOT, "backups", "2026-11-17")
DRY = "--dry" in sys.argv

REPLACE = [
    ("江苏省", "镇江市", "市人民检察院", "https://zj.jsjc.gov.cn",
     "L1|江苏检察网首页市级检察院导航 HTML 提取"),
    ("安徽省", "淮北市", "市监委", "http://www.hbjjjc.gov.cn/",
     "L1|安徽纪检监察网首页市县纪委导航 HTML 提取"),
    ("安徽省", "六安市", "市监委", "http://www.lajjjc.gov.cn/",
     "L1|安徽纪检监察网首页市县纪委导航 HTML 提取"),
]


def main():
    t = json.load(open(TREE_F, encoding="utf-8"))
    blk = next(g for g in t["ks"] if g.get("n", "").startswith("省级"))

    def find(n, name):
        if n.get("n") == name:
            return n
        for c in n.get("ks", []):
            r = find(c, name)
            if r:
                return r
        return None

    stats = {"replace": 0, "skip": 0}
    for prov, city, sysn, u, note in REPLACE:
        p = find(blk, prov); c = find(p, city) if p else None
        jg = next((x for x in (c or {}).get("ks", []) if x.get("c") == "并列机关"), None)
        o = find(jg, sysn) if jg else None
        if not o:
            print(f"SKIP 未找到 {prov}/{city}/{sysn}"); stats["skip"] += 1; continue
        print(f"REPLACE {prov}/{city}/{sysn}\n    {(o.get('u') or '(空)')[:70]}\n -> {u}")
        o["u"] = u
        o["s"] = f"来源:{note}；2026-11-17 p211 修正"
        stats["replace"] += 1

    print("统计:", stats, "DRY" if DRY else "")
    if DRY:
        return
    os.makedirs(BAK_DIR, exist_ok=True)
    bak = os.path.join(BAK_DIR, f"tree_before_p211_{time.strftime('%H%M%S')}.json")
    shutil.copy2(TREE_F, bak)
    json.dump(t, open(TREE_F, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("已落库, 备份:", bak)


if __name__ == "__main__":
    main()
