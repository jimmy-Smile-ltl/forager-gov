# -*- coding: utf-8 -*-
"""修复县级门户 URL 同名串号（2026-11-18）。

问题：tree.json 里 7 组同名区县共用同一门户 URL（如杭州西湖区与南昌西湖区
都写 xhq.nc.gov.cn），必有一方错。经**上级市政府门户的区县导航**（合规权威渠道）
逐条核对，确认 7 个县的 URL 张冠李戴，2 个县暂未找到权威来源（留空待补）。

本脚本只改三处：tree.json 节点 u/s/m、site_registry.json 的 u；zzjg_county.json
的错采记录由 p248 另行剔除（需先停采集进程）。
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
TREE = os.path.join(HERE, "tree.json")
REG = os.path.join(HERE, "site_registry.json")
SRC = "上级市政府门户-区县导航（2026-11-18 同名串号核对）"

# (省, 市, 县) → 正确 URL（"" = 暂无权威来源，留空待补）
FIX = {
    ("内蒙古自治区", "呼和浩特市", "新城区"): "http://www.xinchengqu.gov.cn/",
    ("湖北省", "武汉市", "青山区"): "https://www.qingshan.gov.cn/",
    ("吉林省", "辽源市", "西安区"): "https://www.lyxa.gov.cn/",
    ("山东省", "济南市", "市中区"): "http://www.shizhong.gov.cn/",
    ("山东省", "枣庄市", "市中区"): "http://www.zzszq.gov.cn/",
    ("四川省", "内江市", "市中区"): "https://www.neijiangshizhongqu.gov.cn/",
    ("甘肃省", "兰州市", "城关区"): "https://www.lzcgq.gov.cn/",
    ("广东省", "深圳市", "南山区"): "",
    ("浙江省", "杭州市", "西湖区"): "",
}
OLD_NOTE = "同名串号（原 URL 属他市同名区，2026-11-18 上级市门户导航核对后修正）"
CLEAR_NOTE = "同名串号（原 URL 属他市同名区），权威来源待补"


def main():
    tree = json.load(open(TREE, encoding="utf-8"))
    changed = []
    todo = set(FIX)

    def walk(n, path):
        p = path + [n.get("n", "")]
        if (n.get("k") == "人民政府" and n.get("l") == "县" and len(p) >= 3):
            k = (p[-3], p[-2], n.get("n"))
            if k in todo:
                new = FIX[k]
                old = n.get("u", "")
                n["u"] = new
                n["s"] = SRC
                n["m"] = (CLEAR_NOTE if not new else OLD_NOTE)
                changed.append((k, old, new))
                todo.discard(k)
        for c in n.get("ks") or []:
            walk(c, p)

    walk(tree, [])
    if todo:
        print("!! 未匹配到节点:", todo)
    json.dump(tree, open(TREE, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"tree.json 已更新 {len(changed)} 个县级节点：")
    for k, o, n in changed:
        print(f"   {k[0]}{k[1]}{k[2]}: {o}  ->  {n or '(留空待补)'}")

    # registry 同步（只改 u 与被改节点的来源）
    reg = json.load(open(REG, encoding="utf-8"))
    n_reg = 0
    for k, o, new in changed:
        prov, city, name = k
        hits = [rk for rk in reg
                if rk.startswith("县级人民政府|")
                and rk.split("|", 1)[1] in (name, prov + name, city + name)
                and (reg[rk].get("u") or "").strip().rstrip("/").lower()
                == (o or "").strip().rstrip("/").lower()]
        for rk in hits:
            reg[rk]["u"] = new
            reg[rk]["s"] = SRC
            reg[rk]["verified_at"] = "2026-11-18"
            n_reg += 1
    json.dump(reg, open(REG, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"site_registry.json 已更新 {n_reg} 条")


if __name__ == "__main__":
    main()
