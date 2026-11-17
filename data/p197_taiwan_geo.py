# -*- coding: utf-8 -*-
"""P197: 台湾省 22 县市边界数据并入地图（一个中国原则, 简体中文）。

数据源: dkaoster/taiwan-atlas（GitHub, MIT）counties-10t.json（TopoJSON,
台湾内政部开放资料「直辖市、县市界线(TWD97经纬度)」转换, 未投影经纬度）。
下载: https://cdn.jsdelivr.net/npm/taiwan-atlas/counties-10t.json

产出: data/geo/geo_710000.js（window.__GEO_710000__ = FeatureCollection,
22 县市 features: properties {adcode, name(简体), center, centroid}）——
点击台湾省即可下钻县市图（沿用 loadProvince 管线, 县市点击直接看详情）。
"""
import sys, os, json, re, urllib.request

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
GEO = os.path.join(BASE, "data", "geo")
SRC = "https://cdn.jsdelivr.net/npm/taiwan-atlas/counties-10t.json"

# 繁体→简体（仅覆盖 22 县市名所需字符）
T2S = str.maketrans({
    "縣": "县", "臺": "台", "連": "连", "蘭": "兰", "雲": "云",
    "義": "义", "東": "东", "蓮": "莲", "屏": "屏", "園": "园",
    "門": "门", "員": "员",
})
# 名称 → 大陆统计体系风格 adcode（7101xx 起, 稳定表）
CODES = {
    "台北市": 710100, "新北市": 710200, "桃园市": 710300, "台中市": 710400,
    "台南市": 710500, "高雄市": 710600, "基隆市": 710700, "新竹市": 710800,
    "嘉义市": 710900, "新竹县": 711100, "苗栗县": 711200, "彰化县": 711300,
    "南投县": 711400, "云林县": 711500, "嘉义县": 711600, "屏东县": 711700,
    "宜兰县": 711800, "花莲县": 711900, "台东县": 712000, "澎湖县": 712100,
    "金门县": 712200, "连江县": 712300,
}


def fetch_src(path):
    if os.path.exists(path):
        return json.load(open(path, encoding="utf-8"))
    req = urllib.request.Request(SRC, headers={"User-Agent": "Mozilla/5.0"})
    data = urllib.request.urlopen(req, timeout=60).read()
    open(path, "wb").write(data)
    return json.loads(data)


def decode_topo(d):
    """TopoJSON(量化 delta 编码) → 每条 arc 的绝对经纬度坐标"""
    scale, trans = d["transform"]["scale"], d["transform"]["translate"]
    arcs = []
    for arc in d["arcs"]:
        x = y = 0
        pts = []
        for dx, dy in arc:
            x += dx
            y += dy
            pts.append([x * scale[0] + trans[0], y * scale[1] + trans[1]])
        arcs.append(pts)
    return arcs


def rings_of(geom_arcs, arcs):
    """TopoJSON geometry.arcs → GeoJSON Polygon/MultiPolygon coordinates。

    TopoJSON 语义: 环=弧序列拼接（[5,6]=弧5接弧6 的一段环, 不是双环）;
    Polygon=[环1,环2(洞)]; MultiPolygon=[[环1],[环2]]。"""
    def ring_of(idx_list):
        pts = []
        for i in idx_list:
            pts += list(arcs[i]) if i >= 0 else list(reversed(arcs[~i]))
        return pts
    def conv(spec):
        if not spec:
            return []
        if isinstance(spec[0], int):
            return [[ring_of(spec)]]                    # Polygon 单环
        if isinstance(spec[0][0], int):
            return [[ring_of(r) for r in spec]]         # Polygon 多环（含洞）
        return [[ring_of(r) for r in poly] for poly in spec]   # MultiPolygon
    coords = conv(geom_arcs)
    # 单多边形（单环/带洞）→ Polygon; 多组 → MultiPolygon
    if len(coords) == 1:
        return "Polygon", coords[0]
    return "MultiPolygon", coords


def main():
    raw = fetch_src("/tmp/taiwan_counties_10t.json")
    arcs = decode_topo(raw)
    features = []
    for g in raw["objects"]["counties"]["geometries"]:
        p = g["properties"]
        name = p["COUNTYNAME"].translate(T2S)
        gtype, coords = rings_of(g.get("arcs", []), arcs)
        geom = {"type": gtype, "coordinates": coords}
        # center/centroid: 边界框中心（与 DataV 惯例一致）; 递归收集全部坐标点
        def pts(coord, acc):
            if coord and isinstance(coord[0], (int, float)):
                acc.append(coord)
                return
            for c in coord:
                pts(c, acc)
        acc = []
        pts(geom["coordinates"], acc)
        if not acc:
            continue
        cx = (min(a[0] for a in acc) + max(a[0] for a in acc)) / 2
        cy = (min(a[1] for a in acc) + max(a[1] for a in acc)) / 2
        features.append({
            "type": "Feature",
            "properties": {"adcode": CODES.get(name, 0), "name": name,
                           "center": [cx, cy], "centroid": [cx, cy]},
            "geometry": geom,
        })
    assert len(features) == 22, f"应 22 县市, 实际 {len(features)}"
    out = {"type": "FeatureCollection", "features": features}
    header = ("/* 台湾省 22 县市边界（一个中国原则, 简体中文）。\n"
              "   数据源: 台湾内政部开放资料「直辖市、县市界线(TWD97经纬度)」\n"
              "   经 dkaoster/taiwan-atlas (MIT) 转档, p197 转换生成。 */\n")
    path = os.path.join(GEO, "geo_710000.js")
    with open(path, "w", encoding="utf-8") as f:
        f.write(header + "window.__GEO_710000__="
                + json.dumps(out, ensure_ascii=False, separators=(",", ":")) + ";")
    print(f"geo_710000.js 已生成: {len(features)} 县市")
    for ft in features:
        print("  ", ft["properties"]["name"], ft["properties"]["adcode"])


if __name__ == "__main__":
    main()
