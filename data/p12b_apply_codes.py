# -*- coding: utf-8 -*-
"""P12b: 把民政部 6 位区划代码写回 divisions.json / city_county_final.jsonl，
并补齐民政部有而本地缺的县级实体（如白杨市等新设）。"""
import json
import re
import sys

sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))


def load_idx():
    d = json.load(open("mca_index.json", encoding="utf-8"))
    city = {tuple(k.split("|")): v for k, v in d["city"].items()}
    county = {tuple(k.split("|")): v for k, v in d["county"].items()}
    county_bp = {tuple(k.split("|")): v for k, v in d["county_by_prov"].items()}
    prov = d["prov"]
    return prov, city, county, county_bp


def prov_short(full):
    s = re.sub(r"(省|市|特别行政区)$", "", full)
    return re.sub(r"(壮族|回族|维吾尔)?自治区$", "", s)


def main():
    prov_i, city_i, county_i, county_bp = load_idx()
    divs = json.load(open("divisions.json", encoding="utf-8"))
    cc = [json.loads(l) for l in open("city_county_final.jsonl", encoding="utf-8")]

    fixed, added = 0, []

    # ---- divisions.json ----
    for d in divs:
        if d["level"] in ("省", "特别行政区"):
            new = prov_i.get(d["name"])
        elif d["level"] == "市":
            new = city_i.get((d["province"], d["name"]))
        else:  # 县
            new = county_i.get((d["province"], d["parent"], d["name"])) \
                or (county_bp.get((d["province"], d["name"])) or [None, None])[1]
        if new and new != d["code"]:
            d["code"] = new
            fixed += 1
    # 民政部有而 divisions 缺的县级（含直辖市辖区/兵团市）
    known = {(d["province"], d["name"]) for d in divs if d["level"] == "县"}
    known_city = {(d["province"], d["name"]) for d in divs if d["level"] == "市"}
    for (prov, name), code in sorted(city_i.items()):
        if (prov, name) in known_city or (prov, name) in known:
            continue
        # 直辖市辖区/省直辖县级（代码尾两位非00）→ 县层实体
        if code[4:6] != "00":
            divs.append({"code": code, "name": name, "level": "县",
                         "province": prov, "parent": prov,
                         "note": "省直辖" if prov not in ("北京市", "天津市", "上海市", "重庆市")
                         else "直辖市辖区"})
            added.append((prov, name, code))
    for (prov, city, name), code in sorted(county_i.items()):
        if (prov, name) in known:
            continue
        divs.append({"code": code, "name": name, "level": "县",
                     "province": prov, "parent": city, "note": ""})
        added.append((prov, name, code))

    json.dump(divs, open("divisions.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0)

    # ---- city_county_final.jsonl ----
    for r in cc:
        if r["level"] == "市":
            new = city_i.get((r["province"], r["name"]))
        else:
            new = county_i.get((r["province"], r.get("parent", ""), r["name"])) \
                or (county_bp.get((r["province"], r["name"])) or [None, None])[1]
        if new and new != r["code"]:
            r["code"] = new
            fixed += 1
    # 新增实体行（门户待解析）
    cc_codes = {r["code"] for r in cc}
    for prov, name, code in added:
        if code in cc_codes:
            continue
        lvl = "县"
        parent = prov
        for (p2, c2, n2), ccode in county_i.items():
            if ccode == code:
                parent = c2
                break
        cc.append({"code": code, "name": name, "level": lvl, "province": prov,
                   "parent": parent, "portal_url": "", "how": "民政部新增待解析"})
    with open("city_county_final.jsonl", "w", encoding="utf-8") as f:
        for r in sorted(cc, key=lambda x: x["code"]):
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"代码修正 {fixed} 处 | 新增民政部实体 {len(added)}")
    for a in added:
        print("  +", a)


if __name__ == "__main__":
    main()
