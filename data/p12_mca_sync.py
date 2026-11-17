# -*- coding: utf-8 -*-
"""P12 v2: 民政部区划同步（修正版：滤自引用行、直辖市辖区为地级层级）。"""
import json
import sys
import time

import httpx

sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))

API = "https://dmfw.mca.gov.cn/xzqh/getCodeList"
API2 = "https://dmfw.mca.gov.cn/xzqh/getCodeList2"
TABLE = "Xzqh20251231"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://dmfw.mca.gov.cn/XzqhVersionPublish.html",
}
CLIENT = httpx.Client(timeout=20, verify=False, headers=HEADERS)


def query(parent_code, level_type, page):
    url = API2 if level_type == 3 else API
    data = {"parentCode": parent_code, "placeCode": "", "title": "",
            "tableName": TABLE, "type": level_type, "pageNum": page, "pageSize": 100}
    for attempt in range(4):
        try:
            resp = CLIENT.post(url, data=data)
            return resp.json().get("data") or []
        except Exception:
            time.sleep(2 * (attempt + 1))
    return []


def crawl(parent_code, level_type):
    rows, page = [], 1
    while True:
        batch = query(parent_code, level_type, page)
        if not batch:
            break
        rows += batch
        if len(batch) < 100:
            break
        page += 1
        time.sleep(0.3)
    # 滤自引用行
    return [r for r in rows if r["code"] != parent_code]


def main():
    provs = crawl("", 1)
    print("省级:", len(provs), flush=True)
    tree = []
    for p in provs:
        kids = crawl(p["code"], 2)
        pnode = {"name": p["name"], "code": p["code"], "kids": []}
        for c in kids:
            cnode = {"name": c["name"], "code": c["code"], "kids": []}
            # 直辖市辖区（6位码尾两位非00）无县级下级；常规地级查县级
            c6 = c["code"][:6]
            if c6[4:6] == "00":
                cnode["kids"] = [{"name": x["name"], "code": x["code"]} for x in crawl(c["code"], 3)]
            pnode["kids"].append(cnode)
            time.sleep(0.2)
        tree.append(pnode)
        print(f"  {p['name']}: 地级{len(kids)}", flush=True)
        time.sleep(0.4)
    json.dump(tree, open("mca_tree.json", "w", encoding="utf-8"), ensure_ascii=False)
    n_c = sum(len(p["kids"]) for p in tree)
    n_x = sum(len(c["kids"]) for p in tree for c in p["kids"])
    print(f"民政部区划: 省{len(tree)} 地级{n_c} 县级{n_x}", flush=True)


if __name__ == "__main__":
    main()
