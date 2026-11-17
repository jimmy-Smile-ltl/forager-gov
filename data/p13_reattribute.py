# -*- coding: utf-8 -*-
"""P13: 省厅局从属关系全面重检 —— 以 URL 域名结构判定所属省份。

域名全拼优先（hebei/hubei/shanxi/shaanxi 可区分），
无歧义省域子域后缀兜底（sh/tj/bj/cq/sd/sc/yn/xj/hlj/ln/jl/nmg/nx）。
"""
import json
import re
import sys
from urllib.parse import urlparse

sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))

FULL_PINYIN = [
    ("beijing", "北京"), ("tianjin", "天津"), ("shanghai", "上海"), ("chongqing", "重庆"),
    ("shaaxi", None), ("shaanxi", "陕西"), ("shanxi", "山西"),
    ("hebei", "河北"), ("hubei", "湖北"),
    ("henan", "河南"), ("hunan", "湖南"),
    ("neimenggu", "内蒙古"), ("liaoning", "辽宁"), ("jilin", "吉林"), ("heilongjiang", "黑龙江"),
    ("jiangsu", "江苏"), ("zhejiang", "浙江"), ("anhui", "安徽"), ("fujian", "福建"),
    ("jiangxi", "江西"), ("shandong", "山东"),
    ("guangdong", "广东"), ("guangxi", "广西"), ("hainan", "海南"),
    ("sichuan", "四川"), ("guizhou", "贵州"), ("yunnan", "云南"),
    ("xizang", "西藏"), ("gansu", "甘肃"), ("qinghai", "青海"),
    ("ningxia", "宁夏"), ("xinjiang", "新疆"),
]
# 无歧义短后缀（域名为 xxx.{short}.gov.cn 形态）
SHORT_SUFFIX = [
    ("bj.gov.cn", "北京"), ("tj.gov.cn", "天津"), ("sh.gov.cn", "上海"), ("cq.gov.cn", "重庆"),
    ("sd.gov.cn", "山东"), ("sc.gov.cn", "四川"), ("yn.gov.cn", "云南"), ("xj.gov.cn", "新疆"),
    ("hlj.gov.cn", "黑龙江"), ("ln.gov.cn", "辽宁"), ("jl.gov.cn", "吉林"),
    ("nmg.gov.cn", "内蒙古"), ("nx.gov.cn", "宁夏"), ("ah.gov.cn", "安徽"),
    ("fj.gov.cn", "福建"), ("jx.gov.cn", "江西"), ("ha.gov.cn", "河南"),
    ("gd.gov.cn", "广东"), ("zj.gov.cn", "浙江"),
]
# 特殊：广西 gxzf.gov.cn 子域
SPECIAL = [("gxzf.gov.cn", "广西")]


def detect_province(url):
    host = urlparse(url or "").netloc.lower().replace("www.", "")
    if not host:
        return None
    for key, prov in SPECIAL:
        if key in host:
            return prov
    for key, prov in FULL_PINYIN:
        if prov and key in host:
            return prov
    labels = host.split(".")
    if len(labels) >= 3 and labels[-1] == "cn" and labels[-2] == "gov":
        for suf, prov in SHORT_SUFFIX:
            if labels[-3] == suf.split(".")[0]:
                return prov
    return None


def main():
    depts = [json.loads(l) for l in open("prov_depts.jsonl", encoding="utf-8")]
    changes, undetected = [], 0
    for r in depts:
        u = r.get("portal_url", "")
        if not u:
            undetected += 1
            continue
        det = detect_province(u)
        if not det:
            undetected += 1
            continue
        if det != r["province"]:
            changes.append((r["province"], r["name"], det, u))
            r["province"] = det
    print(f"重归属 {len(changes)} 行 | 无URL/无法判定 {undetected} 行", flush=True)
    for old, name, new, u in changes:
        print(f"  {old} → {new}: {name} | {u[:60]}", flush=True)
    with open("prov_depts.jsonl", "w", encoding="utf-8") as f:
        for r in sorted(depts, key=lambda x: (x["province"], x["name"])):
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print("已写回", flush=True)


if __name__ == "__main__":
    main()
