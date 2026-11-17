# -*- coding: utf-8 -*-
"""P43: 工会系统隶属链采集 —— 省级工会官网 → 市级工会。

口径：全总 acftu.org（省级工会）→ 各省级工会官网「区内/省内工会网站」区块
     → 市级工会。市以下无县级工会官网；部分市无官网 → 列名。
提取：<a> 与 <select><option> 双通道；区块定位（区内工会网站|省内工会网站|
     市级工会|地市工会|盟市工会）；市名与 tree 匹配 + 标题验证。
断点续跑：union_state.json；结果：union_system.jsonl
"""
import json
import os
import re
import sys
import time
from urllib.parse import urlparse

sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开")
sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开/util")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 省级工会 URL（p35 验证 21 + 模式探测/SERP 新发现 9；安徽/青海/兵团列名）
PROV_UNION = {
    "天津市": "http://www.ftutj.cn/",
    "吉林省": "http://www.jlzgh.org/",
    "上海市": "http://www.shzgh.org/",
    "福建省": "https://www.fjgh.org/",
    "江西省": "https://www.jxgh.org.cn/",
    "湖南省": "https://www.hnzgh.org/",
    "重庆市": "https://www.cqgh.org/",
    "西藏自治区": "https://www.xzgh.org.cn/",
}
BLOCK_RE = re.compile(r"(区内工会网站|省内工会网站|市级工会|地市工会|盟市工会|工会网站)")
BAD_DOM = re.compile(r"(acftu|baidu|zhihu|sogou|sina|sohu|qq\.|163\.|126\.net|w3\.org|people\.|news\.cn|xinhuanet|chinanews|douyin|weibo)")


def sf(url):
    try:
        from util.smart_fetch import smart_fetch
        html, _ = smart_fetch(url, timeout=25)
        return html
    except Exception:
        return None


def main():
    tree = json.load(open("tree.json", encoding="utf-8"))
    prov_g = next(g for g in tree["ks"] if g["n"].startswith("省级"))
    # 省级工会 URL：tree 群团组 + PROV_UNION
    prov_urls = {}
    for p in prov_g["ks"]:
        grp = next((k for k in p.get("ks", []) if k.get("c") == "群团组织"), None)
        if grp:
            m = next((x for x in grp["ks"] if x["n"] == "省总工会"), None)
            if m and m.get("u"):
                prov_urls[p["n"]] = m["u"]
    prov_urls.update(PROV_UNION)

    state = json.load(open("union_state.json", encoding="utf-8")) \
        if os.path.exists("union_state.json") else {}
    done = set(state.get("done", []))
    rows = state.get("rows", [])
    todo = [p for p, u in prov_urls.items() if p not in done]
    print(f"p43 省级工会 {len(prov_urls)} 个，本轮 {len(todo)} 个（累计市工会 {len(rows)}）",
          flush=True)

    for pname in todo:
        url = prov_urls[pname]
        pnode = next(p for p in prov_g["ks"] if p["n"] == pname)
        # 该省市名表（含盟/州，匹配 text 或 text+市 变体）
        city_names = []
        def walk(n):
            if n.get("l") == "市" and n.get("k") == "人民政府":
                city_names.append((n["n"], n.get("cd", "")))
            for k in n.get("ks", []):
                walk(k)
        walk(pnode)

        html = sf(url)
        if not html:
            print(f"  {pname}: 省级工会站抓取失败", flush=True)
            done.add(pname)
            continue
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "lxml")
        found = []
        seen = set()
        # <a> 通道
        for a in soup.find_all("a"):
            t = re.sub(r"\s+", "", (a.get("title") or a.get_text(" ", strip=True)).strip())
            h = a.get("href") or ""
            if not t or not h.startswith(("http://", "https://")) or len(t) > 18:
                continue
            if ("工会" not in t and "工会" not in (a.get("title") or "")):
                continue
            if BAD_DOM.search(h):
                continue
            key = t + "|" + h
            if key in seen:
                continue
            seen.add(key)
            found.append((t, h))
        # <select><option> 通道
        for sel in soup.find_all("select"):
            for op in sel.find_all("option"):
                t = re.sub(r"\s+", "", op.get_text(" ", strip=True).strip())
                h = op.get("value") or ""
                if not t or not h.startswith(("http://", "https://")) or len(t) > 18:
                    continue
                key = t + "|" + h
                if key in seen or BAD_DOM.search(h):
                    continue
                seen.add(key)
                found.append((t, h))

        # 市名匹配（core = 去 总工会/工会/市 后缀）
        matched = []
        for t, h in found:
            core = re.sub(r"(总)?工会.*$|网站.*$", "", t)
            for cn, cd in city_names:
                base = re.sub(r"(自治州|市|地区|盟)$", "", cn)
                if core == cn or core == base or core == cn + "市" or \
                        (len(core) >= 2 and core in cn):
                    matched.append((cn, cd, t, h))
                    break
        rows += [{"province": pname, "city": cn, "cd": cd,
                  "label": t, "url": h} for cn, cd, t, h in matched]
        done.add(pname)
        state["done"] = sorted(done)
        state["rows"] = rows
        json.dump(state, open("union_state.json", "w", encoding="utf-8"),
                  ensure_ascii=False, indent=0)
        print(f"  {pname}: 命中 {len(matched)} 个市级工会", flush=True)
        time.sleep(1)

    with open("union_system.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"p43 完成：{len(rows)} 个市级工会链接", flush=True)


if __name__ == "__main__":
    main()
