# -*- coding: utf-8 -*-
"""P169: 注册表升级为主数据（source_level/verified_at/status/snapshot）。"""
import json
import re

reg = json.load(open("site_registry.json", encoding="utf-8"))
rules = json.load(open("extraction_rules.json", encoding="utf-8"))

# 来源等级推断：从规则 method 留痕
def infer_level(n, u):
    """L1 官网名录/L2 门户导航/L3 SERP验证/L4 未知。"""
    # 找相关规则的 method
    for rk, r in rules.items():
        m = r.get("method", "")
        if "SERP" in m or "搜索" in m or "bing" in m.lower():
            return "L3"
        if "名录" in m or "权威" in m or "机构页" in m or "机构设置" in m:
            return "L1"
        if "导航" in m or "区块" in m or "footer" in m or "首页" in m:
            return "L2"
    return "L4"

for k, v in reg.items():
    if "source_level" not in v:
        v["source_level"] = infer_level(k, v.get("u", ""))
    if "verified_at" not in v:
        v["verified_at"] = ""
    if "status" not in v:
        v["status"] = "unknown"
    if "snapshot" not in v:
        v["snapshot"] = ""

json.dump(reg, open("site_registry.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=0)
from collections import Counter
c = Counter(v["source_level"] for v in reg.values())
print(f"注册表升级: {len(reg)} 条")
print("来源等级分布:", dict(c))
