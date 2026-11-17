# -*- coding: utf-8 -*-
"""下载行政区划 GeoJSON（阿里云 DataV GeoAtlas）并打包为 geo/*.js。
全国省界 → geo/china.js；每省县级界 → geo/geo_{adcode}.js（惰性加载）。"""
import json, os, time, urllib.request

GEO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "geo")
os.makedirs(GEO, exist_ok=True)

def fetch(url, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=25) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            if i == tries - 1:
                print(f"  失败 {url}: {e}")
                return None
            time.sleep(1.5)

# 1) 全国省界
china = fetch("https://geo.datav.aliyun.com/areas_v3/bound/100000_full.json")
if china:
    provs = [f for f in china["features"] if f["properties"].get("level") == "province"]
    with open(os.path.join(GEO, "china.js"), "w", encoding="utf-8") as f:
        f.write("window.__GEO_CHINA__=" + json.dumps(china, ensure_ascii=False, separators=(",", ":")) + ";")
    print(f"全国省界: {len(provs)} 省 → geo/china.js")
    # 2) 每省: 市级列表 → 逐市县级
    for p in provs:
        ad = p["properties"]["adcode"]
        name = p["properties"]["name"]
        # 港澳: DataV 有区/堂区下钻（_full 直接是子区划, 三级变两级）
        if ad in (810000, 820000):
            out_path = os.path.join(GEO, f"geo_{ad}.js")
            if os.path.exists(out_path) and os.path.getsize(out_path) > 200:
                print(f"跳过 {name}（已有）")
                continue
            prov_f = fetch(f"https://geo.datav.aliyun.com/areas_v3/bound/{ad}_full.json")
            if prov_f:
                out = {"type": "FeatureCollection", "features": prov_f["features"]}
                with open(out_path, "w", encoding="utf-8") as f:
                    f.write(f"window.__GEO_{ad}__=" + json.dumps(out, ensure_ascii=False, separators=(",", ":")) + ";")
                print(f"{name}({ad}): {len(prov_f['features'])} 区/堂区 → geo_{ad}.js")
            continue
        # 台湾: DataV 无县市边界 → 用 p197（taiwan-atlas 内政部开放数据）生成 geo_710000.js
        if ad == 710000:
            try:
                import p197_taiwan_geo
                p197_taiwan_geo.main()
            except Exception as e:
                print(f"台湾边界生成失败: {e}")
            continue
        out_path = os.path.join(GEO, f"geo_{ad}.js")
        if os.path.exists(out_path) and os.path.getsize(out_path) > 200:
            print(f"跳过 {name}（已有）")
            continue
        prov_f = fetch(f"https://geo.datav.aliyun.com/areas_v3/bound/{ad}_full.json")
        if not prov_f:
            continue
        lvls = {f["properties"].get("level") for f in prov_f["features"]}
        if "district" in lvls:
            # 直辖市: 市级=区（geo_{省} 存区=市级图, 区下无县——三级变两级）
            city_feats = [f for f in prov_f["features"]
                          if f["properties"].get("level") == "district"]
        else:
            city_feats = [f for f in prov_f["features"]
                          if f["properties"].get("level") == "city"]
        # 省文件 = 市级图
        out = {"type": "FeatureCollection", "features": city_feats}
        with open(os.path.join(GEO, f"geo_{ad}.js"), "w", encoding="utf-8") as f:
            f.write(f"window.__GEO_{ad}__=" + json.dumps(out, ensure_ascii=False, separators=(",", ":")) + ";")
        # 每市文件 = 县级图
        for c in city_feats:
            cad = c["properties"]["adcode"]
            cpath = os.path.join(GEO, f"geo_{cad}.js")
            if os.path.exists(cpath) and os.path.getsize(cpath) > 200:
                continue
            cf = fetch(f"https://geo.datav.aliyun.com/areas_v3/bound/{cad}_full.json")
            if not cf:
                continue
            dist = [f for f in cf["features"]
                    if f["properties"].get("level") == "district"]
            cout = {"type": "FeatureCollection", "features": dist}
            with open(cpath, "w", encoding="utf-8") as f:
                f.write(f"window.__GEO_{cad}__=" + json.dumps(cout, ensure_ascii=False, separators=(",", ":")) + ";")
            time.sleep(0.3)
        print(f"{name}({ad}): {len(city_feats)} 市 → geo_{ad}.js + 各市县级文件")
