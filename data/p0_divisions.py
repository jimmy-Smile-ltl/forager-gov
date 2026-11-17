# -*- coding: utf-8 -*-
"""P0: 行政区划数据扁平化（v2）。

modood pcas-code 的「省直辖县级行政区划」伪节点在多个省下重复挂同一份
县名单（河南/湖北/海南共用 20 县），需按区划代码前缀（PPCCXX 的 PP 位）
去重并归位到正确省份。
输出: divisions.json
"""
import json

SRC = "pcas-code.json"
OUT = "divisions.json"

# 省级代码前缀 → 省名（含港澳台）
PP_MAP = {
    "11": "北京市", "12": "天津市", "13": "河北省", "14": "山西省", "15": "内蒙古自治区",
    "21": "辽宁省", "22": "吉林省", "23": "黑龙江省",
    "31": "上海市", "32": "江苏省", "33": "浙江省", "34": "安徽省", "35": "福建省",
    "36": "江西省", "37": "山东省",
    "41": "河南省", "42": "湖北省", "43": "湖南省", "44": "广东省", "45": "广西壮族自治区", "46": "海南省",
    "50": "重庆市", "51": "四川省", "52": "贵州省", "53": "云南省", "54": "西藏自治区",
    "61": "陕西省", "62": "甘肃省", "63": "青海省", "64": "宁夏回族自治区", "65": "新疆维吾尔自治区",
    "71": "台湾省", "81": "香港特别行政区", "82": "澳门特别行政区",
}


def prov_of(code: str) -> str:
    return PP_MAP.get(code[:2], "其他")


def main():
    raw = json.load(open(SRC, encoding="utf-8"))
    provs = []
    for p in raw:
        provs.append({
            "code": p["code"], "name": p["name"],
            "children": p.get("children", []),
        })
    # 港澳台手动补
    for code, name in (("810000", "香港特别行政区"), ("820000", "澳门特别行政区"),
                       ("710000", "台湾省")):
        if name not in {p["name"] for p in provs}:
            provs.append({"code": code, "name": name, "children": []})

    flat = []  # {code,name,level,province,parent,note}
    seen_codes = set()
    ZHIXIA = {"北京市", "天津市", "上海市", "重庆市"}
    for p in provs:
        pname = p["name"]
        plevel = "特别行政区" if pname.endswith("特别行政区") else "省"
        flat.append({"code": p["code"], "name": pname, "level": plevel,
                     "province": pname, "parent": "", "note": ""})
        for c in p["children"]:
            cname = c["name"]
            kids = c.get("children", [])
            if kids and ("直辖县级行政区划" in cname or "直辖县级" in cname):
                # 伪节点：子女按代码前缀归位到本省（去重）
                for x in kids:
                    if prov_of(x["code"]) != pname:
                        continue  # 其它省的重复条目，丢弃
                    if x["code"] in seen_codes:
                        continue
                    seen_codes.add(x["code"])
                    flat.append({"code": x["code"], "name": x["name"], "level": "县",
                                 "province": pname, "parent": pname, "note": "省直辖"})
            elif kids and pname in ZHIXIA and cname in ("市辖区", "县"):
                # 直辖市伪节点（市辖区/县）：区县直接挂直辖市
                for x in kids:
                    if x["code"] in seen_codes:
                        continue
                    seen_codes.add(x["code"])
                    flat.append({"code": x["code"], "name": x["name"], "level": "县",
                                 "province": pname, "parent": pname, "note": "直辖市辖区"})
            elif kids:
                flat.append({"code": c["code"], "name": cname, "level": "市",
                             "province": pname, "parent": pname, "note": ""})
                for x in kids:
                    if x["code"] in seen_codes:
                        continue
                    seen_codes.add(x["code"])
                    flat.append({"code": x["code"], "name": x["name"], "level": "县",
                                 "province": pname, "parent": cname, "note": ""})
            else:
                if c["code"] in seen_codes:
                    continue
                seen_codes.add(c["code"])
                flat.append({"code": c["code"], "name": cname, "level": "县",
                             "province": pname, "parent": pname, "note": "省直辖"})

    # 按代码去重（同名不同码保留）
    by_code = {}
    for d in flat:
        by_code[d["code"]] = d
    flat = list(by_code.values())

    json.dump(flat, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print(f"省级 {sum(1 for d in flat if d['level'] in ('省','特别行政区'))} | "
          f"地级 {sum(1 for d in flat if d['level']=='市')} | "
          f"县级 {sum(1 for d in flat if d['level']=='县')} | 总 {len(flat)}")
    # 省直辖县分布
    from collections import Counter
    c = Counter(d["province"] for d in flat if d["note"] == "省直辖")
    print("省直辖县分布:", dict(c))


if __name__ == "__main__":
    main()
