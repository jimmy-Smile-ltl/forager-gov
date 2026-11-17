# -*- coding: utf-8 -*-
"""幂等修复: 青海省监委错配（qinghai.gov.cn 新闻文章页 → qhjc.gov.cn）。
2026-11-13 用户指正。loop 轮结束 dump 可能覆盖, 每轮结束后重跑本脚本。
用法: cd data && uv run python fix_qinghai_jw.py
"""
import json, os
TREE_F = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tree.json")
t = json.load(open(TREE_F, encoding="utf-8"))
fixed = False
def walk(n):
    global fixed
    if n.get("n") == "省监委" and n.get("p1") == "青海省":
        if n.get("u") != "http://www.qhjc.gov.cn":
            n["u"] = "http://www.qhjc.gov.cn"
            n["s"] = "来源：中央纪委国家监委官网「地方纪委监委」名录（青海错配修正：原挂 qinghai.gov.cn 新闻文章页）"
            n["verified_at"] = "2026-11-13"
            n["status"] = "ok"
            fixed = True
            print("修复青海省监委 ->", n["u"])
        else:
            print("青海省监委已正确, 跳过")
    for c in n.get("ks", []):
        walk(c)
walk(t)
if fixed:
    json.dump(t, open(TREE_F, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
