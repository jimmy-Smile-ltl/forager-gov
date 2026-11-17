#!/usr/bin/env python
# p212 五系统 URL 修正（第三轮，2026-11-17）
# ① 替换（权威源/严格 SERP 验证）
#   合肥监委 → hfsjw.gov.cn（安徽纪检监察网首页市县导航, title=中共合肥市纪律检查委员会）
#   铜陵监委 → tljw.gov.cn（同上, title=廉田网=铜陵纪委廉政品牌站）
#   安庆监委 → aqjjjc.gov.cn（同上, title=安庆市纪检监察网站-中共安庆市纪律检查委员会）
#   太原政协 → tyzx.gov.cn（百度 SERP 线索+title严格验证: 中国人民政治协商会议太原市委员会;
#              原值 jnzx.gov.cn 是济南市政协, 张冠李戴）
# ② 清除
#   克拉玛依中院：新疆法院网（xjfy.xjcourt.gov.cn）中院导航中克拉玛依链接为 "#" 占位
#   → 无独立官网，列名
import json, os, re, shutil, time, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TREE_F = os.path.join(ROOT, "data", "tree.json")
BAK_DIR = os.path.join(ROOT, "backups", "2026-11-17")
DRY = "--dry" in sys.argv

REPLACE = [
    ("安徽省", "合肥市", "市监委", "http://www.hfsjw.gov.cn/",
     "L1|安徽纪检监察网首页市县纪委导航 HTML 提取"),
    ("安徽省", "铜陵市", "市监委", "http://www.tljw.gov.cn/",
     "L1|安徽纪检监察网首页市县纪委导航 HTML 提取"),
    ("安徽省", "安庆市", "市监委", "http://www.aqjjjc.gov.cn",
     "L1|安徽纪检监察网首页市县纪委导航 HTML 提取"),
    ("山西省", "太原市", "市政协", "http://www.tyzx.gov.cn/",
     "SERP|百度 SERP 线索+title严格验证：中国人民政治协商会议太原市委员会"),
]
CLEAR = [
    ("新疆维吾尔自治区", "克拉玛依市", "市中级人民法院",
     "2026-11-17 p212 审计清除：新疆法院网中院导航该市链接为 # 占位，无独立官网"),
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

    def node(prov, city, sysn):
        p = find(blk, prov); c = find(p, city) if p else None
        jg = next((x for x in (c or {}).get("ks", []) if x.get("c") == "并列机关"), None)
        return find(jg, sysn) if jg else None

    stats = {"replace": 0, "clear": 0, "skip": 0}
    for prov, city, sysn, u, note in REPLACE:
        o = node(prov, city, sysn)
        if not o:
            print(f"SKIP 未找到 {prov}/{city}/{sysn}"); stats["skip"] += 1; continue
        print(f"REPLACE {prov}/{city}/{sysn}\n    {(o.get('u') or '(空)')[:70]}\n -> {u}")
        o["u"] = u
        o["s"] = f"来源:{note}；2026-11-17 p212 修正"
        stats["replace"] += 1

    for prov, city, sysn, note in CLEAR:
        o = node(prov, city, sysn)
        if not o or not (o.get("u") or "").strip():
            print(f"SKIP 已空 {prov}/{city}/{sysn}"); stats["skip"] += 1; continue
        print(f"CLEAR {prov}/{city}/{sysn}: {o['u'][:70]}")
        o["u"] = ""
        o["s"] = note
        stats["clear"] += 1

    print("统计:", stats, "DRY" if DRY else "")
    if DRY:
        return
    os.makedirs(BAK_DIR, exist_ok=True)
    bak = os.path.join(BAK_DIR, f"tree_before_p212_{time.strftime('%H%M%S')}.json")
    shutil.copy2(TREE_F, bak)
    json.dump(t, open(TREE_F, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("已落库, 备份:", bak)


if __name__ == "__main__":
    main()
