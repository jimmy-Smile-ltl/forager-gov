# -*- coding: utf-8 -*-
"""P50b: 工会市/区级数据严格化。

1. union_city2.jsonl 过滤：label 必须匹配 ^(.{1,12}?)(总)?工会(网站|首页)?$
   （新闻标题如「中卫市总工会走访慰问困难职工09-15」剔除）
2. 清理 p50 误入的模块节点/老系统子节点/规则（按被剔除 URL）
3. 重放干净数据（复用 p50 逻辑）
"""
import json
import re
import subprocess

PAT = re.compile(r"^(.{1,12}?)(总)?工会(网站|首页)?$")


def valid(r):
    label = (r["label"] or "").strip()
    label = re.sub(r"^(.{2,10}?)\1$", r"\1", label)   # 名称翻倍归一（合肥市总工会合肥市总工会）
    city = r["city"]
    base = re.sub(r"(自治州|地区|盟|市|区|县)$", "", city)
    if r["level"] == "区":
        # 直辖市辖区：链接文本通常就是纯区名
        return label == city or label == base or \
            (label == city + "总工会" or label == base + "总工会")
    # 市级：纯市名 或 市名+总工会/工会（网站/首页 后缀容忍）
    if label == city or label == base:
        return True
    m = PAT.match(label)
    if not m:
        return False
    core = m.group(1)
    return core == city or core == base or \
        core == re.sub(r"市$", "", base) or core.endswith("州")


def clean_rows():
    rows = [json.loads(l) for l in open("union_city2.jsonl", encoding="utf-8")]
    good, bad = [], []
    for r in rows:
        if valid(r):
            good.append(r)
        else:
            bad.append(r)
    with open("union_city2.jsonl", "w", encoding="utf-8") as f:
        for r in good:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return good, bad


def cleanup(bad):
    bad_urls = {r["url"] for r in bad}
    tree = json.load(open("tree.json", encoding="utf-8"))
    rules = json.load(open("extraction_rules.json", encoding="utf-8"))
    prov_g = next(g for g in tree["ks"] if g["n"].startswith("省级"))
    removed = 0

    # 模块内：名称不合规的节点删除
    tiao = next(g for g in tree["ks"] if g["n"] == "条（垂直管理系统）")
    union = next(g for g in tiao["ks"] if g["n"].startswith("工会系统"))
    acftu = next(g for g in union["ks"] if g["n"] == "中华全国总工会")
    pgrp = next(g for g in acftu["ks"] if g["n"].startswith("省级工会"))
    for pnode in pgrp["ks"]:
        kids = pnode.get("ks", [])
        pnode["ks"] = [k for k in kids if k.get("u") not in bad_urls]
        removed += len(kids) - len(pnode["ks"])

    # 老系统：URL 命中坏 URL 的 市/区总工会 子节点删除
    def walk(n):
        nonlocal removed
        for k in list(n.get("ks", [])):
            if k["n"] in ("市总工会", "区总工会") and k.get("u") in bad_urls:
                n["ks"].remove(k)
                removed += 1
                rk = f"{n['n']}·{k['n']}"
                rules.pop(rk, None)
            else:
                walk(k)
    for p in prov_g["ks"]:
        walk(p)
    # 模块节点坏 URL（上一轮已按坏 URL 集合清理）
    for pnode in pgrp["ks"]:
        pnode["ks"] = [k for k in pnode.get("ks", []) if k.get("u") not in bad_urls]

    json.dump(tree, open("tree.json", "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    json.dump(rules, open("extraction_rules.json", "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    print(f"p50b 清理：剔除 {len(bad)} 条坏数据，移除 {removed} 个节点")


if __name__ == "__main__":
    good, bad = clean_rows()
    print(f"干净 {len(good)} 条，剔除 {len(bad)} 条")
    for r in bad[:8]:
        print(f"  剔除: {r['province']} {r['city']} | {r['label'][:30]}")
    cleanup(bad)
    subprocess.run(["/Users/jimmy/projectBaidu/.venv/bin/python", "p50_apply_union2.py"])
