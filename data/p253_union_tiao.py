# -*- coding: utf-8 -*-
"""P253: 重建条视图「工会系统」垂直结构（2026-11-19 数据巡检）。

问题：p45 曾生成根级模块「工会系统（中华全国总工会）」（全总 + 省级工会 + 市级工会），
但当前 tree.json 根只有 中央/省级/港澳台/条 四组，模块内容丢失，条 › 群团组织系统 下
只剩一个空占位「工会系统」——而组名写着「妇联·共青团·工会」。前端 CROSS_MAP 仍按
旧名「工会系统（中华全国总工会）」跳转，块视图点「中华全国总工会」→条视图是空节点
（jumpToTiao 找不到目标，静默不动）。

重建（数据全部取自现有 tree，不新采）：
  工会系统（32）                 [条]
    中华全国总工会               [中央›群团组织（21）的同名节点 u]
    省级工会（32）               [块›省级›群团组织（17）里 {省名}总工会]
      {省名}总工会
        {市名}市总工会          [块›市政府下「市总工会」子节点，142 个有官网]

幂等：每次运行先清空该组子节点再重建；registry 只补 n 字段与 locations，不改 URL。
"""
import json
import sys

TGT = "工会系统（32）"


def walk(n):
    yield n
    for k in n.get("ks") or []:
        yield from walk(k)


def leaf(nm, lv, u, s="", m=""):
    return {"n": nm, "l": lv, "k": "工会系统", "c": "工会系统",
            "u": u, "x": "", "s": s, "m": m}


def main(dry=False):
    tree = json.load(open("tree.json", encoding="utf-8"))
    prov_g = next(g for g in tree["ks"] if g["n"].startswith("省级"))
    central = next(g for g in tree["ks"] if g["n"].startswith("中央"))
    tiao = next(g for g in tree["ks"] if g["n"].startswith("条"))
    qt = next(g for g in tiao["ks"] if g["n"].startswith("群团"))

    # 全总（中央 群团组织（21）下的同名节点）
    acftu = None
    for g in central.get("ks") or []:
        for n in walk(g):
            if n.get("n") == "中华全国总工会":
                acftu = dict(n)
                break
    if not acftu or not acftu.get("u"):
        print("!! 中央树里找不到带 URL 的中华全国总工会，中止")
        return

    # 省级 + 市级工会（块视图）
    prov_rows = []
    for p in prov_g["ks"]:
        union = None
        for g in p.get("ks") or []:
            if not (g.get("n") or "").startswith("群团"):
                continue
            for c in g.get("ks") or []:
                if c.get("n") == f"{p['n']}总工会":
                    union = c
        cities = []
        for top in p.get("ks") or []:
            for n in walk(top):
                for c in n.get("ks") or []:
                    # p255 起块视图市级工会已改为全名「{市名}总工会」，兼容旧裸名；
                    # 只取市级父节点（l=市），区级工会（p255 改名的「{区名}总工会」，
                    # 父级 l=地级区）不进「市级工会」层
                    cn = c.get("n") or ""
                    if (n.get("l") == "市"
                            and cn in ("市总工会", f"{n.get('n')}总工会")
                            and c.get("u")):
                        cities.append(leaf(f"{n['n']}总工会", "市", c["u"],
                                           c.get("s", "")))
        city_nodes = sorted({c["n"]: c for c in cities}.values(),
                            key=lambda x: x["n"])
        node = leaf(f"{p['n']}总工会", "省",
                    (union or {}).get("u", ""), (union or {}).get("s", ""))
        if city_nodes:
            node["ks"] = city_nodes
        prov_rows.append(node)

    grp = {"n": f"省级工会（{sum(1 for p in prov_rows if p['u'])}）",
           "l": "条", "k": "分组", "c": "工会系统", "u": "", "x": "", "s": "", "m": "",
           "ks": prov_rows}
    new = {"n": TGT, "l": "条", "k": "分组", "c": "工会系统", "u": "", "x": "", "s": "",
           "m": "全总 + 省级工会（%d/32）+ 市级工会 %d 个；块视图市政府下同名节点同源"
                % (sum(1 for p in prov_rows if p["u"]),
                   sum(len(p.get("ks") or []) for p in prov_rows)),
           "ks": [leaf("中华全国总工会", "中央", acftu["u"], acftu.get("s", "")), grp]}

    old = [g for g in qt.get("ks") or [] if (g.get("n") or "").startswith("工会系统")]
    if old:
        i = qt["ks"].index(old[0])
        qt["ks"][i] = new
        for extra in old[1:]:
            qt["ks"].remove(extra)
    else:
        qt["ks"].append(new)
    print(f"p253 工会系统重建：省级 {sum(1 for p in prov_rows if p['u'])}/32，"
          f"市级 {sum(len(p.get('ks') or []) for p in prov_rows)}")

    # registry：补 n 字段 / locations（不改 URL）
    reg = json.load(open("site_registry.json", encoding="utf-8"))
    reg_hit = reg_new = 0
    for n in walk(new):
        if n.get("ks") or not n.get("u"):
            continue
        key = f"群团|{n['n']}"
        e = reg.get(key)
        if e is None:
            reg[key] = {"u": n["u"], "locations": ["块", "条"], "n": n["n"],
                        "source_level": "L2", "source": n.get("s", ""),
                        "verified_at": "", "status": "ok"}
            reg_new += 1
            continue
        if e.get("n") != n["n"]:
            e["n"] = n["n"]
            reg_hit += 1
        locs = e.setdefault("locations", [])
        if "条" not in locs:
            locs.append("条")
    print(f"  registry: n 更新 {reg_hit}，新增 {reg_new}")

    if dry:
        print("--dry 干跑，未写盘")
        return
    with open("tree.json", "w", encoding="utf-8") as f:
        json.dump(tree, f, ensure_ascii=False, indent=1)
        f.write("\n")
    with open("site_registry.json", "w", encoding="utf-8") as f:
        json.dump(reg, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print("已写 tree.json / site_registry.json")


if __name__ == "__main__":
    main(dry="--dry" in sys.argv)
