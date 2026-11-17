# -*- coding: utf-8 -*-
"""P195 全省审计: 块树县级人民政府 URL 覆盖情况按省统计。
用法: uv run python data/p195_prov_audit.py（只读 tree.json, 可随时跑）
输出: 终端表格 + data/p195_prov_audit.json（含各省缺失清单, 供补全对照）
注意: 台湾 22 县市/港澳区议会 c 不在县级 CTYPES, 不计入本审计。"""
import json, os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TREE_F = os.path.join(BASE, "data", "tree.json")
OUT_F = os.path.join(BASE, "data", "p195_prov_audit.json")

CT = {"县级人民政府", "市辖区（地级行政区划）", "直辖市辖县（县级行政区划）",
      "省直辖县级市/县/林区", "兵团直辖县级市（自治区直辖县级市）"}


def walk(n, path):
    yield n, path
    for k in n.get("ks", []) or []:
        yield from walk(k, path + [n])


def main():
    tree = json.load(open(TREE_F, encoding="utf-8"))
    blk = [k for k in tree.get("ks", []) if "省级" in k.get("n", "")][0]
    gat = [k for k in tree.get("ks", []) if "港澳台" in k.get("n", "")][0]
    prov_roots = blk.get("ks", []) + gat.get("ks", [])
    prov_of = {}
    for pr in prov_roots:
        for n, path in walk(pr, [pr]):
            if n.get("k") == "人民政府" and n.get("c") in CT:
                prov_of.setdefault(pr.get("n"), []).append(n)
    order = ["北京市", "天津市", "上海市", "重庆市", "河北省", "山西省",
             "辽宁省", "吉林省", "黑龙江省", "江苏省", "浙江省", "安徽省",
             "福建省", "江西省", "山东省", "河南省", "湖北省", "湖南省",
             "广东省", "海南省", "四川省", "贵州省", "云南省", "陕西省",
             "甘肃省", "青海省", "内蒙古自治区", "广西壮族自治区",
             "西藏自治区", "宁夏回族自治区", "新疆维吾尔自治区",
             "新疆生产建设兵团"]
    report = {"date": "", "by_prov": []}
    for prov in order:
        nodes = prov_of.get(prov, [])
        tot = len(nodes)
        filled = sum(1 for n in nodes if n.get("u"))
        missing = [n.get("n") for n in nodes if not n.get("u")]
        pct = f"{filled/tot*100:.0f}%" if tot else "-"
        flag = "🟢" if tot and filled == tot else ("🟡" if tot and filled/tot >= 0.8 else "🔴")
        report["by_prov"].append({"prov": prov, "total": tot, "filled": filled,
                                  "missing": missing})
        line = f"{flag} {prov}: {filled}/{tot} ({pct})"
        if missing:
            line += f"  缺({len(missing)}): {'、'.join(missing)}"
        print(line)
    t = sum(r["total"] for r in report["by_prov"])
    f = sum(r["filled"] for r in report["by_prov"])
    print(f"\n合计 {f}/{t} ({f/t*100:.1f}%) 缺 {t-f}")
    json.dump(report, open(OUT_F, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"审计报告已存 {os.path.relpath(OUT_F, BASE)}")


if __name__ == "__main__":
    main()
