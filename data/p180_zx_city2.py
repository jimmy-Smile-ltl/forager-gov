# -*- coding: utf-8 -*-
"""P180: 市级政协入口页提取——P178 定位的「市县政协」栏目页逐省访问,
提取市级政协真实链接（锚文本纯市名/简称/市X政协 三形态）。"""
import json, os, re, sys
from urllib.parse import urljoin
sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开")
sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开/util")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from smart_fetch import smart_fetch
from common import save_snap

# P178 定位的入口（省 → 入口路径）
ENTRIES = {
 "广东省": ("https://www.gdszx.gov.cn/sxzx/", "http://www.gdszx.gov.cn"),
 "辽宁省": ("http://www.lnzx.gov.cn/lnzx/sxzx/index.shtml", "http://www.lnzx.gov.cn"),
 "河北省": ("http://www.hebzx.gov.cn/zxgz/sxzx", "http://www.hebzx.gov.cn"),
 "浙江省": ("http://www.zjzx.gov.cn/sxdt", "http://www.zjzx.gov.cn"),
 "河南省": ("http://www.hnzx.gov.cn/sxzx/", "http://www.hnzx.gov.cn"),
 "海南省": ("https://www.hainanzx.gov.cn/sxzx/", "https://www.hainanzx.gov.cn"),
 "宁夏回族自治区": ("http://www.nxzx.gov.cn/sxzx", "http://www.nxzx.gov.cn"),
 "新疆维吾尔自治区": ("https://www.xjzx.gov.cn/zxgk/zxjg/", "https://www.xjzx.gov.cn"),
 "云南省": ("https://www.ynzx.gov.cn:443/zxjg/index.jhtml", "https://www.ynzx.gov.cn"),
 "青海省": ("https://www.qhszx.gov.cn/state_CPPCC/", "https://www.qhszx.gov.cn"),
 "西藏自治区": ("https://www.xizangzx.gov.cn/", "https://www.xizangzx.gov.cn"),
 "上海市": ("http://www.shszx.gov.cn/", "http://www.shszx.gov.cn"),
 "山西省": ("http://www.shanxizx.gov.cn/", "http://www.shanxizx.gov.cn"),
 "贵州省": ("http://www.gzszx.gov.cn/", "http://www.gzszx.gov.cn"),
 "黑龙江省": ("http://www.hljzx.gov.cn/", "http://www.hljzx.gov.cn"),
}
STATE_F = "zx_city2_state.json"
state = json.load(open(STATE_F, encoding="utf-8")) if os.path.exists(STATE_F) \
    else {"found": {}}

LINK = re.compile(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>\s*([^<]{2,40}?)\s*</a>', re.S)
for pn, (entry, base) in ENTRIES.items():
    if pn in state["found"]:
        continue
    html, m = smart_fetch(entry, timeout=25)
    print(f"{pn}: {m} {len(html)}B", flush=True)
    if not html or len(html) < 2000:
        continue
    save_snap("shixian", pn, "省政协", "sxzx", html)
    hits = {}
    for uu, txt in LINK.findall(html):
        t2 = re.sub(r"\s+", "", txt)
        # 三形态：XX市政协 / 纯市名(2-4字) / 简称+政协
        if re.search(r"政协$", t2) and len(t2) <= 14 and "省" not in t2[:2] and "全国" not in t2:
            if uu.startswith(("http", "/")):
                hits[t2] = urljoin(base, uu) if uu.startswith("/") else uu
    print(f"  提取 {len(hits)} 个:", list(hits.keys())[:12], flush=True)
    state["found"][pn] = hits
    json.dump(state, open(STATE_F, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
print("P180 完成", flush=True)
