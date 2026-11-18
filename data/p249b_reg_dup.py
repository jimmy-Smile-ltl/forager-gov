# -*- coding: utf-8 -*-
"""补齐同名区县的 registry 条目（p249 的配套，2026-11-18）。

registry 里同名区县只有一条无省名前缀的 key（`县级人民政府|青山区`），
p249 修正门户 URL 时会把另一市的同名区覆盖掉。这里按「URL 对齐」原则补齐：
组内每个县若在 registry 里找不到自己的 URL，就建带省名（同省重名用市名）的条目。
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
REG = os.path.join(HERE, "site_registry.json")
TREE = os.path.join(HERE, "tree.json")
SRC = "上级市政府门户-区县导航（2026-11-18 同名串号核对）"


def norm(u):
    return (u or "").strip().rstrip("/").lower()


def main():
    tree = json.load(open(TREE, encoding="utf-8"))
    reg = json.load(open(REG, encoding="utf-8"))
    GROUPS = {}
    NAMES = {"新城区", "青山区", "西安区", "南山区", "西湖区", "市中区", "城关区"}

    def walk(n, path):
        p = path + [n.get("n", "")]
        if (n.get("k") == "人民政府" and n.get("l") == "县" and len(p) >= 3
                and n.get("n") in NAMES):
            GROUPS.setdefault(n["n"], []).append(
                (p[-3], p[-2], n["n"], n.get("u") or ""))
        for c in n.get("ks") or []:
            walk(c, p)
    walk(tree, [])

    known = {norm(v.get("u")): k for k, v in reg.items()
             if k.startswith("县级人民政府|") and v.get("u")}
    added, fixed = [], []
    for name, rows in GROUPS.items():
        for prov, city, nm, u in rows:
            if not u:
                continue
            if norm(u) in known:
                continue
            for key in (f"县级人民政府|{prov}{nm}", f"县级人民政府|{city}{nm}"):
                if key not in reg or norm(reg[key].get("u")) == norm(u):
                    reg[key] = dict(u=u, n=nm, locations=["块"], source_level="L1",
                                    verified_at="2026-11-18", status="unknown", s=SRC)
                    added.append((key, u))
                    known[norm(u)] = key
                    break
    # 被 p249 清空的两条恢复成原本所属（清空前分别是鹤岗南山/南昌西湖）
    for key, u in (("县级人民政府|南山区", "https://www.hgns.gov.cn/"),
                   ("县级人民政府|西湖区", "http://xhq.nc.gov.cn/")):
        if key in reg and not (reg[key].get("u") or "").strip():
            reg[key]["u"] = u
            reg[key]["s"] = SRC
            reg[key]["verified_at"] = "2026-11-18"
            fixed.append((key, u))

    json.dump(reg, open(REG, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"新增 {len(added)} 条，恢复 {len(fixed)} 条：")
    for k, u in added + fixed:
        print(f"   {k:26s} {u}")


if __name__ == "__main__":
    main()
