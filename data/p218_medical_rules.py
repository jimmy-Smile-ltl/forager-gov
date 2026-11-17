#!/usr/bin/env python
# p218 医疗系统提取规则落盘（2026-11-17 用户问「提取逻辑/提取规则怎么处理」）
# 药监模式: 系统级一条规则（键=系统名），method 分级如实注明各渠道来源,
# SERP 兜底如实标注「线索+官网 title 严格验证」——非「搜索引擎采信」。
# depts 列中央+省级成员（市级 419 节点不进 depts, 与药监 34 成员同体量）。
import json, os, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RULES_F = os.path.join(ROOT, "data", "extraction_rules.json")
TREE_F = os.path.join(ROOT, "data", "tree.json")


def _atomic(obj, path):
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
    with os.fdopen(fd, "w") as f:
        json.dump(obj, f, ensure_ascii=False)
    os.replace(tmp, path)


def main():
    rules = json.load(open(RULES_F, encoding="utf-8"))
    t = json.load(open(TREE_F, encoding="utf-8"))

    def find(node, name):
        if node.get("n") == name:
            return node
        for ch in node.get("ks") or []:
            r = find(ch, name)
            if r:
                return r
        return None

    med = find(t, "医疗系统（卫生健康）")
    if not med:
        print("医疗系统未找到")
        return
    depts = []
    for ch in med.get("ks") or []:
        if ch.get("ks"):
            depts.extend({"n": c.get("n"), "u": c.get("u", ""), "o": i}
                         for i, c in enumerate(ch["ks"]))
        else:
            depts.append({"n": ch.get("n"), "u": ch.get("u", ""), "o": len(depts)})
    key = "医疗系统（卫生健康）"
    rules[key] = {
        "portal": "https://www.nhc.gov.cn/",
        "method": (
            "医疗系统=卫健委体系（块管为主、条块结合，各级卫健委为本级政府组成部门，"
            "上级仅业务指导，非垂直管理）。URL 来源分级："
            "①块树/registry 存量（市门户部门导航 L2，title 已验证）；"
            "②省卫健委官网「地市卫健委」栏目页真实 HTML 提取（L1）；"
            "③市政府门户部门导航（L2）；"
            "④百度 SERP 线索 + 官网 title 严格验证（市名+机构词双验，L3 兜底）——"
            "SERP 仅作发现线索，须回官网验证后落库（s 留痕「SERP线索+title严格验证」）；"
            "⑤省级疾控中心为卫健委直属事业单位、官网无省级导航，按用户指示"
            "SERP 搜索 + title 筛选采集（域名含 cdc 或 gov.cn）。"
            "医院项目 whc_cities.jsonl PASS 导入（title 复验）。"
            "2026-11-17 全量 URL 正确性检验（p214）后治理（p215）："
            "SERP 命中若为门户根址/文章页/他部门页面一律清空列名（宁缺毋滥），"
            "深路径先试根址 title 验证、机构子站首页（title=机构全名）方可保留；"
            "最终市级卫健委 209/419、省疾控 24/31，mismatch 0。"
        ),
        "sources": ["https://www.nhc.gov.cn/", "https://www.natcm.gov.cn/",
                    "https://www.ndcpa.gov.cn/", "https://www.chinacdc.cn/"],
        "code": (
            '# -*- coding: utf-8 -*-\n'
            '"""医疗系统（卫生健康）提取规则。\n'
            '方法：国家卫健委(+委管国家局 中医药局/疾控局 + 中国疾控中心) → '
            '省级卫健委(32) → 市级卫健委(419 城市级节点) + 省级疾控中心(31)。\n'
            '渠道：存量(市门户导航 L2) / 省卫健委官网市级区块+地市栏目页(L1) / '
            '市门户导航(L2) / SERP 线索+官网 title 双验(L3 兜底) / '
            '疾控 SERP 搜索+title 筛选(用户指示)。\n'
            '纪律：SERP 不直接采信——s 留痕「SERP线索+title严格验证」；禁域名猜测。\n'
            '"""\n'
        ),
        "depts": depts,
    }
    _atomic(rules, RULES_F)
    print(f"规则已写入: {key} (depts {len(depts)})")


if __name__ == "__main__":
    main()
