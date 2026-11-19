# -*- coding: utf-8 -*-
"""P255: 群团工会节点命名补全 + 提取规则键迁移（承接 p252/p253，2026-11-19 巡检）。

三件事：

一、修 p252 的规则键回归（544 条）
   p252 把省级群团槽位名改成全名后，前端的 ruleKeyOf 对省级群团成员返回
   「{省}·{节点名}」，于是「北京市·北京市总工会」——而 extraction_rules 里
   仍是旧键「北京市·省总工会」，544 个节点的「提取规则」页签全部消失。
   本脚本按「新名 = 省名 + 机构后缀」反推旧槽位名，迁移规则键、depts 名与
   代码开头 docstring 里的旧名。

二、市级/区级工会节点命名补全（179 条）
   与省级同一缺陷：块视图里是裸「市总工会」（139 个市）、「区总工会」
   （40 个地级区），列表模式单独成行时看不出是哪个市/区。改为
   「{父级名}总工会」，并迁移对应规则键「{父级名}·市总工会」→
   「{父级名}·{父级名}总工会」。registry 键本来就由父级名+总工会组成，
   改名前后同键，只需把 n 字段更新为新名。

三、5 个误分类工会节点归位
   晋城/淮安/嘉兴/潍坊/安康 的「市总工会」同时出现在「市级政府部门」名录里
   （k=政府部门）。其中 4 市本来就有群团口径的同名节点 → 名录这条是重复，
   删除并清掉它算出的错误 registry 键（「市级政府部门|江苏省总工会」——省名+
   总工会，丢市名）；淮安没有群团口径节点 → 移到市节点下（k/c=群团组织）并
   改名「淮安市总工会」。p167.full_name 的市级部门前缀问题（registry 里
   4,988 个「市级政府部门|湖北省市交通运输局」式键）另行处理。

不改 URL、不新采；幂等（已改名的节点/已迁移的键再跑即跳过）。--dry 干跑。
遗留（本次不动）：p167.full_name 对「市…局」类市级部门名会取到省级人民政府
作前缀（registry 里 4,988 个「市级政府部门|湖北省市交通运输局」式键），是
独立的数据模型问题，需要单独迁移。
"""
import json
import sys

# 与 p252 保持一致
SLOT_SUFFIX = {
    "省总工会": "总工会",
    "省妇联": "妇女联合会",
    "省科协": "科学技术协会",
    "省文联": "文学艺术界联合会",
    "省作协": "作家协会",
    "省工商联": "工商业联合会",
    "省侨联": "归国华侨联合会",
    "省台联": "台湾同胞联谊会",
    "省残联": "残疾人联合会",
    "省贸促会": "国际贸易促进委员会",
    "省红十字会": "红十字会",
    "省法学会": "法学会",
    "省记协": "新闻工作者协会",
    "省人民对外友好协会": "人民对外友好协会",
    "省计划生育协会": "计划生育协会",
    "省欧美同学会": "欧美同学会",
}


def walk(n, path=()):
    yield n, path
    for k in n.get("ks") or []:
        yield from walk(k, path + (n,))


def move_rule(rules, old_key, new_key, scope, old_name, new_name, stat):
    """旧键 → 新键：键、depts 名、代码 docstring 一起迁。"""
    if old_key == new_key or old_key not in rules:
        return False
    if new_key in rules:
        stat["conflict"].append((old_key, new_key))
        return False
    e = rules.pop(old_key)
    for d in e.get("depts") or []:
        if (d.get("n") or "") == old_name:
            d["n"] = new_name
    code = e.get("code") or ""
    old_line, new_line = f"{scope} {old_name}", f"{scope} {new_name}"
    if old_line in code:
        e["code"] = code.replace(old_line, new_line, 1)
    rules[new_key] = e
    return True


def main(dry=False):
    tree = json.load(open("tree.json", encoding="utf-8"))
    reg = json.load(open("site_registry.json", encoding="utf-8"))
    rules = json.load(open("extraction_rules.json", encoding="utf-8"))
    prov_g = next(g for g in tree["ks"] if g["n"].startswith("省级"))
    stat = {"rule_prov": 0, "rule_city": 0, "rule_gov": 0, "conflict": [],
            "node_city": 0, "node_area": 0, "moved": [], "reg_n": 0,
            "reg_new": 0, "reg_del": [], "skip": []}

    # ---- 一、省级群团规则键迁移（修 p252 回归） ----
    prov_map = []  # (省名, 旧槽位名, 新名)
    for p in prov_g["ks"]:
        pn = p["n"]
        for g in p.get("ks") or []:
            if not (g.get("n") or "").startswith("群团"):
                continue
            for c in g.get("ks") or []:
                nm = c.get("n") or ""
                if nm == f"共青团{pn}委员会":
                    prov_map.append((pn, "团省委", nm))
                    continue
                for old, suf in SLOT_SUFFIX.items():
                    if nm == f"{pn}{suf}":
                        prov_map.append((pn, old, nm))
                        break
    for pn, old, new in prov_map:
        if move_rule(rules, f"{pn}·{old}", f"{pn}·{new}", pn, old, new, stat):
            stat["rule_prov"] += 1

    # ---- 二、市/区工会节点改名 + 规则键迁移 ----
    for p in prov_g["ks"]:
        for n, path in walk(p):
            if n is p or not path:
                continue
            parent = path[-1]
            nm = n.get("n") or ""
            if n.get("k") != "群团组织" or nm not in ("市总工会", "区总工会"):
                continue
            if parent.get("l") not in ("市", "地级区"):
                stat["skip"].append(("父级非市/区", p["n"], parent.get("n"), nm))
                continue
            new = f"{parent['n']}总工会"
            if any((s.get("n") or "") == new for s in parent.get("ks") or []):
                stat["skip"].append(("同名已存在", p["n"], parent.get("n"), new))
                continue
            n["n"] = new
            stat["node_city" if nm == "市总工会" else "node_area"] += 1
            if move_rule(rules, f"{parent['n']}·{nm}", f"{parent['n']}·{new}",
                         parent["n"], nm, new, stat):
                stat["rule_city"] += 1
            e = reg.get(f"群团|{new}")
            if e is not None and e.get("n") != new:
                e["n"] = new
                stat["reg_n"] += 1

    # ---- 三、5 个误分类工会节点归位 ----
    # 先收集再改：移动节点会改动父级 ks，不能边遍历边删
    misfiled = []
    for p in prov_g["ks"]:
        for n, path in walk(p):
            if n.get("k") != "政府部门" or not path:
                continue
            parent = path[-1]
            if not (parent.get("n") or "").startswith("市级政府部门"):
                continue
            nm = n.get("n") or ""
            if nm in ("市总工会", "总工会"):
                misfiled.append((p, n, path))
    for p, n, path in misfiled:
        parent = path[-1]
        nm = n.get("n") or ""
        if len(path) < 2:
            stat["skip"].append(("找不到市节点", p["n"], nm))
            continue
        city = path[-2]
        new = f"{city['n']}总工会"
        u = (n.get("u") or "").strip()
        ukey = u.rstrip("/")
        # 多数城市本来就有群团口径的同名节点（p252 已改名），名录里的这条是重复
        twin = None
        for c in city.get("ks") or []:
            if c is n:
                continue
            cu = (c.get("u") or "").strip().rstrip("/")
            if c.get("k") == "群团组织" and (
                    (u and cu == ukey)
                    or (c.get("n") or "") in (new, "市总工会")):
                twin = c
                break
        parent["ks"].remove(n)
        if twin:
            stat["moved"].append(("重复删除", p["n"], city["n"], nm,
                                  u, "保留 " + (twin.get("n") or "")))
        else:
            n["n"] = new
            n["k"] = n["c"] = "群团组织"
            n["m"] = (n.get("m") or "") + (
                "；p255 从「市级政府部门」名录移入市级群团（总工会非政府部门）")
            # 挂到市节点首位（与其他市「市总工会」位置一致）
            city.setdefault("ks", []).insert(0, n)
            stat["moved"].append(("移入群团", p["n"], city["n"], nm, new, u))
            if move_rule(rules, f"{city['n']}·{nm}", f"{city['n']}·{new}",
                         city["n"], nm, new, stat):
                stat["rule_gov"] += 1
        # registry：保留/补建群团键，删除错误分类键
        key = f"群团|{new}"
        e = reg.get(key)
        if e is None:
            reg[key] = {"u": u, "locations": ["块"], "n": new,
                        "source_level": "L2", "source": n.get("s", ""),
                        "verified_at": "", "status": "ok"}
            stat["reg_new"] += 1
        else:
            if e.get("n") != new:
                e["n"] = new
                stat["reg_n"] += 1
            if not (e.get("u") or "").strip() and u:
                e["u"] = u
                e["status"] = "ok"
        for k in [k for k, v in list(reg.items())
                  if k.startswith("市级政府部门|")
                  and u and (v.get("u") or "").strip() == u
                  and (v.get("n") or "") in ("市总工会", "总工会")]:
            reg.pop(k)
            stat["reg_del"].append(k)
    # 顺手清掉一条明显畸形的历史键（u 指向晋城工会）
    junk = reg.get("群团|市级政府部门总工会")
    if junk and "jcszgh" in (junk.get("u") or ""):
        reg.pop("群团|市级政府部门总工会")
        stat["reg_del"].append("群团|市级政府部门总工会")

    print(f"p255 规则键：省级 {stat['rule_prov']}/544，市/区 {stat['rule_city']}/179，"
          f"误分类 {stat['rule_gov']}/4")
    print(f"  节点改名：市总工会 {stat['node_city']}，区总工会 {stat['node_area']}")
    print("  归位：", stat["moved"])
    print(f"  registry：n 更新 {stat['reg_n']}，新增 {stat['reg_new']}，"
          f"删除错误键 {len(stat['reg_del'])} {stat['reg_del']}")
    if stat["conflict"]:
        print(f"  ⚠ 目标键已存在（未合并）{len(stat['conflict'])}：{stat['conflict'][:6]}")
    if stat["skip"]:
        print(f"  跳过 {len(stat['skip'])}：{stat['skip'][:8]}")
    if dry:
        print("--dry 干跑，未写盘")
        return
    with open("tree.json", "w", encoding="utf-8") as f:
        json.dump(tree, f, ensure_ascii=False, indent=1)
        f.write("\n")
    with open("site_registry.json", "w", encoding="utf-8") as f:
        json.dump(reg, f, ensure_ascii=False, indent=1)
        f.write("\n")
    with open("extraction_rules.json", "w", encoding="utf-8") as f:
        json.dump(rules, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print("已写 tree.json / site_registry.json / extraction_rules.json")


if __name__ == "__main__":
    main(dry="--dry" in sys.argv)
