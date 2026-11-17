# -*- coding: utf-8 -*-
"""P178: 市级政协第四轮重查——增强版 smart_fetch 逐省政协官网,
首页找「市县政协/政协机构」入口 → 栏目页提取市级链接。
重点: 广东/辽宁/新疆/黑龙江/河北/山西/浙江/西藏/宁夏/上海 10 省。"""
import json, os, re, sys
sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开")
sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开/util")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from smart_fetch import smart_fetch
from common import save_snap

# 重点省优先（缺口大）
PRIORITY = ["广东省", "辽宁省", "新疆维吾尔自治区", "黑龙江省", "河北省", "山西省",
            "浙江省", "西藏自治区", "宁夏回族自治区", "上海市", "青海省", "甘肃省",
            "安徽省", "云南省", "贵州省", "广西壮族自治区", "吉林省", "河南省",
            "海南省", "陕西省"]
PORTS = {
 "广东省": "https://www.gdszx.gov.cn/", "辽宁省": "http://www.lnzx.gov.cn/",
 "新疆维吾尔自治区": "http://www.xjzx.gov.cn/", "黑龙江省": "http://www.hljzx.gov.cn/",
 "河北省": "http://www.hebzx.gov.cn/", "山西省": "http://www.shanxizx.gov.cn/",
 "浙江省": "http://www.zjzx.gov.cn/", "西藏自治区": "https://www.xizangzx.gov.cn/",
 "宁夏回族自治区": "http://www.nxzx.gov.cn/", "上海市": "http://www.shszx.gov.cn/",
 "青海省": "http://www.qhszx.gov.cn/", "甘肃省": "http://www.gszx.gov.cn",
 "安徽省": "http://www.ahzx.gov.cn/", "云南省": "http://www.ynzx.gov.cn/",
 "贵州省": "http://www.gzszx.gov.cn/", "广西壮族自治区": "http://www.gxzx.gov.cn/",
 "吉林省": "http://www.jlzx.gov.cn/", "河南省": "http://www.hnzx.gov.cn/",
 "海南省": "http://www.hainanzx.gov.cn/", "陕西省": "http://www.sxzx.gov.cn/",
}
STATE_F = "zx_city_state.json"
state = json.load(open(STATE_F, encoding="utf-8")) if os.path.exists(STATE_F) \
    else {"done": {}, "found": {}}

KW = re.compile(r"(市州政协|市县政协|地方政协|政协机构|各市政协|市政协.*链接|州政协)")
LINK = re.compile(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>\s*([^<]{2,40}?)\s*</a>', re.S)

for pn in PRIORITY:
    if pn in state["done"]:
        continue
    portal = PORTS[pn]
    html, m = smart_fetch(portal, timeout=25)
    print(f"{pn}: {m} {len(html)}B", flush=True)
    if not html or len(html) < 2000:
        state["done"][pn] = {"method": m, "hits": 0}
        json.dump(state, open(STATE_F, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
        continue
    save_snap("shixian", pn, "省政协", "home", html)
    # 首页找「市县政协」入口
    hits = []
    for uu, txt in LINK.findall(html):
        t2 = re.sub(r"\s+", "", txt)
        if KW.search(t2):
            hits.append({"text": t2, "href": uu})
    # 也找 select option
    for uu, txt in re.findall(r'<option[^>]+value="([^"]+)"[^>]*>\s*([^<]{2,30}?)\s*</option>', html):
        t2 = re.sub(r"\s+", "", txt)
        if "政协" in t2 and t2.endswith("政协"):
            hits.append({"text": t2, "href": uu, "opt": True})
    print(f"  入口候选: {[h['text'] for h in hits[:8]]}", flush=True)
    state["done"][pn] = {"method": m, "hits": len(hits),
                         "entries": hits[:10]}
    json.dump(state, open(STATE_F, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
print("P178 完成", flush=True)
