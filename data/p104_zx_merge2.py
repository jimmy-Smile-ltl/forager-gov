# -*- coding: utf-8 -*-
"""P104: 政协第二轮合并（江苏/河南/江西/海南 简称与编码修正提取）。"""
import json

NEW = {
    "江苏省": {
        "南京市": "http://www.njzx.gov.cn",
        "无锡市": "http://zx.wuxi.gov.cn",
        "徐州市": "http://www.xzzx.gov.cn",
        "常州市": "http://zx.changzhou.gov.cn",
        "苏州市": "http://www.zx.suzhou.gov.cn",
        "南通市": "http://zx.nantong.gov.cn",
        "连云港市": "http://zx.lyg.gov.cn/lygszx/",
        "淮安市": "http://zx.huaian.gov.cn/",
        "盐城市": "http://www.jsyczx.gov.cn",
        "扬州市": "http://zx.yangzhou.gov.cn",
        "镇江市": "http://www.zjszx.gov.cn",
        "泰州市": "http://zx.taizhou.gov.cn",
        "宿迁市": "http://www.sqzx.gov.cn",
    },
    "河南省": {
        "郑州市": "http://www.zzzxy.gov.cn/",
        "开封市": "https://kf.hnzx.gov.cn/",
        "洛阳市": "http://www.lyzzxs.gov.cn/",
        "平顶山市": "http://www.pdszx.gov.cn/",
        "安阳市": "https://ay.hnzx.gov.cn/",
        "新乡市": "http://www.xxszx.gov.cn/",
        "焦作市": "http://www.jzzx.gov.cn/",
        "濮阳市": "http://www.pyzx.gov.cn/",
        "许昌市": "http://www.xcszxw.gov.cn/",
        "漯河市": "https://lh.hnzx.gov.cn/",
        "三门峡市": "http://www.smxzxw.gov.cn/",
        "南阳市": "https://ny.hnzx.gov.cn/",
        "商丘市": "https://sq.hnzx.gov.cn/",
        "信阳市": "https://xy.hnzx.gov.cn/",
        "周口市": "https://zk.hnzx.gov.cn/",
        "驻马店市": "http://www.zmdzx.gov.cn/",
    },
    "海南省": {
        "海口市": "https://www.hainanzx.gov.cn/sxzx/hk/",
        "三亚市": "https://www.hainanzx.gov.cn/sxzx/sy/",
        "儋州市": "https://www.hainanzx.gov.cn/sxzx/dz/",
    },
    "江西省": {
        "南昌市": "https://nczx.nc.gov.cn/",
        "九江市": "http://www.jjszx.gov.cn/",
        "景德镇市": "http://www.jdzzx.gov.cn/",
        "萍乡市": "https://www.jxpxzx.gov.cn/",
        "新余市": "http://www.xyzx.gov.cn/",
        "鹰潭市": "http://www.ytzx.gov.cn/",
        "赣州市": "http://www.jxgzzx.gov.cn/",
        "宜春市": "http://www.zxyc.gov.cn/",
        "上饶市": "http://www.srzx.gov.cn/",
        "吉安市": "http://www.jxjazx.gov.cn/",
        "抚州市": "http://www.jxfzzx.gov.cn/",
    },
}

rows = [json.loads(l) for l in open("rd_zx.jsonl", encoding="utf-8")]
added = updated = 0
for r in rows:
    pn = r["province"]
    if pn in NEW and r["name"] in NEW[pn]:
        if not r["url"]:
            r["url"] = NEW[pn][r["name"]]
            r["listed"] = True
            added += 1
        elif r["url"] != NEW[pn][r["name"]]:
            r["url"] = NEW[pn][r["name"]]
            updated += 1
with open("rd_zx.jsonl", "w", encoding="utf-8") as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
n_u = sum(1 for r in rows if r["listed"])
print(f"p104 完成：新增 {added} 更新 {updated}，总计 {len(rows)} 条（{n_u} 有官网）")
