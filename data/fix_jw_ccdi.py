# -*- coding: utf-8 -*-
"""幂等: 按 ccdi 官网「地方纪委监委」名录对齐省级监委 URL（块树 31 + 条树纪委 32）。
2026-11-13 用户提供权威名录 HTML。loop 轮结束 dump 可能覆盖, 每轮结束后重跑。
用法: cd data && uv run python fix_jw_ccdi.py
"""
import json, os

BASE = os.path.dirname(os.path.abspath(__file__))
TREE_F = os.path.join(BASE, "tree.json")

# ccdi.gov.cn 首页「地方纪委监委」link_list 区块（用户提供权威 HTML 提取）
CCDI = {
    "北京": "http://www.bjsupervision.gov.cn/",
    "天津": "http://www.tjjw.gov.cn/",
    "河北": "http://www.hebcdi.gov.cn/",
    "山西": "http://www.sxdi.gov.cn/",
    "内蒙古": "http://www.nmgjjjc.gov.cn/",
    "辽宁": "http://www.lnsjjjc.gov.cn/",
    "吉林": "http://ccdijl.gov.cn/",
    "黑龙江": "http://www.hljjjjc.gov.cn",
    "上海": "https://www.shjjjc.gov.cn/",
    "江苏": "https://www.jssjw.gov.cn",
    "浙江": "http://www.zjsjw.gov.cn/",
    "安徽": "http://www.ahjjjc.gov.cn/",
    "福建": "http://www.fjcdi.gov.cn/",
    "江西": "http://www.jxdi.gov.cn",
    "山东": "http://www.sdjj.gov.cn/",
    "河南": "http://www.hnsjct.gov.cn",
    "湖北": "http://www.hbjwjc.gov.cn/",
    "湖南": "http://www.sxfj.gov.cn",
    "广东": "http://www.gdjct.gd.gov.cn",
    "广西": "https://www.gxjjw.gov.cn/index.shtml",
    "海南": "http://www.hncdi.gov.cn",
    "重庆": "http://jjc.cq.gov.cn",
    "四川": "http://www.scjc.gov.cn",
    "贵州": "http://www.gzdis.gov.cn",
    "云南": "http://www.ynjjjc.gov.cn/",
    "西藏": "http://www.xzjjw.gov.cn",
    "陕西": "http://www.qinfeng.gov.cn",
    "甘肃": "http://www.gsjw.gov.cn",
    "宁夏": "http://www.nxjjjc.gov.cn/",
    "青海": "http://www.qhjc.gov.cn",
    "新疆": "http://www.xjjw.gov.cn/",
    "新疆生产建设兵团": "http://btjw.xjbt.gov.cn",
}
# 块树 p1 名 → ccdi 名录键（块树省监委节点 p1 是行政区划名）
# 按 key 长度降序匹配: 「新疆生产建设兵团」必须先于「新疆」判定
def prov_key(p1):
    for k in sorted(CCDI, key=len, reverse=True):
        if p1.startswith(k):
            return k
    return None

t = json.load(open(TREE_F, encoding="utf-8"))
changed = []

# 1) 块树省监委（31 节点, k=并列机关 n=省监委）
def walk(n):
    if n.get("n") == "省监委":
        k = prov_key(n.get("p1", ""))
        if k and n.get("u") != CCDI[k]:
            old = n.get("u", "")
            n["u"] = CCDI[k]
            n["s"] = "来源：中央纪委国家监委官网「地方纪委监委」名录（ccdi 权威对齐）"
            n["verified_at"] = "2026-11-13"
            n["status"] = "ok"
            changed.append((f"块:{n.get('p1')}:省监委", old[:60], CCDI[k]))
    for c in n.get("ks", []):
        walk(c)

walk(t)

# 2) 条树纪委省级节点
def find_root(n):
    return n if n.get("n") == "条（垂直管理系统）" else next(
        (r for c in n.get("ks", []) if (r := find_root(c))), None)

root = find_root(t)
for sys_ in (root.get("ks", []) if root else []):
    if "纪委" not in sys_.get("n", ""):
        continue
    for lvl in sys_.get("ks", []):
        if "省级" not in lvl.get("n", ""):
            continue
        for k in lvl.get("ks", []):
            pk = prov_key(k.get("n", ""))
            if pk and k.get("u") != CCDI[pk]:
                old = k.get("u", "")
                k["u"] = CCDI[pk]
                k["s"] = "来源：中央纪委国家监委官网「地方纪委监委」名录（ccdi 权威对齐）"
                k["verified_at"] = "2026-11-13"
                k["status"] = "ok"
                changed.append((f"条:{k.get('n')}", old[:60], CCDI[pk]))

if changed:
    json.dump(t, open(TREE_F, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"对齐 {len(changed)} 处:")
    for a, b, c in changed:
        print(f"  {a}: {b} -> {c}")
else:
    print("无差异, 已全部对齐")
