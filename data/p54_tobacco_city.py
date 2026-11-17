# -*- coding: utf-8 -*-
"""P54: 烟草系统市级细化 —— 省局官网城市子站链接提取（真实 HTML）。

模式（江苏例）：省局首页 <ul id="con-four-1"> 内 <a title="南京"
  href="/col/col483/index.html"> —— 城市为省局子站栏目（相对路径），
  无独立域名。通用做法：省局首页全部 <a> 中 title/text 精确匹配行政区划名
  （市/州/盟；直辖市=区）→ urljoin。
输出 tobacco_city.jsonl {province(全名), city, url}
"""
import json
import re
import sys
import os
from urllib.parse import urljoin

sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开")
sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开/util")

SKIP = {"西藏", "新疆", "大连", "深圳"}   # 总局子路径/计划单列市局，无市级列表


def sf(url):
    try:
        from util.smart_fetch import smart_fetch
        html, _ = smart_fetch(url, timeout=25)
        return html
    except Exception:
        return None


def main():
    d = json.load(open("tobacco_official.json", encoding="utf-8"))
    tree = json.load(open("tree.json", encoding="utf-8"))
    prov_g = next(g for g in tree["ks"] if g["n"].startswith("省级"))

    # 各级行政区划名表（省→市；直辖市→地级区）
    name_map = {}
    for p in prov_g["ks"]:
        names = []
        lv = "地级区" if p["n"] in ("北京市", "天津市", "上海市", "重庆市") else "市"
        for top in p.get("ks", []):
            def walk(n):
                if n.get("l") == lv and n.get("k") == "人民政府":
                    names.append(n["n"])
                for k in n.get("ks", []):
                    walk(k)
            walk(top)
        name_map[p["n"]] = names

    rows = []
    for it in d["省级单位"]:
        short = it["n"]
        if short in SKIP:
            continue
        from p53_tobacco_rebuild import NAME_MAP
        pname = NAME_MAP.get(short, short)
        names = name_map.get(pname, [])
        if not names:
            continue
        html = sf(it["u"])
        if not html:
            print(f"{pname}: 抓取失败", flush=True)
            continue
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "lxml")
        bases = {re.sub(r"(自治州|地区|盟|市|区|县)$", "", n): n for n in names}
        hits = {}
        for a in soup.find_all("a"):
            t = re.sub(r"\s+", "", (a.get("title") or a.get_text(" ", strip=True)).strip())
            h = a.get("href") or ""
            if not t or not h or h.startswith(("javascript:", "#")):
                continue
            if t in bases or t in names:
                u = urljoin(it["u"], h)
                hits[t] = u
        for t, u in hits.items():
            rows.append({"province": pname, "city": bases.get(t, t), "url": u})
        print(f"{pname}: {len(hits)} 个城市子站", flush=True)

    with open("tobacco_city.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"p54 完成：{len(rows)} 条")


if __name__ == "__main__":
    main()
