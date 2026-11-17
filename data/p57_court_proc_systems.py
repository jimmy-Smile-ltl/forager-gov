# -*- coding: utf-8 -*-
"""P57: 构建 法院系统 + 检察院系统 两条垂直系统模块。

法院系统：最高法（court.gov.cn，内设22 复制块树）→ 高级人民法院（32，
  权威 URL 来自最高法官网首页「全国法院」链接块真实 HTML）→ 中院/基层院
  （court_links.jsonl 高院官网链接提取，合规）。
检察院系统：最高检（spp.gov.cn，内设17 复制块树）→ 省级检察院（省门户
  footer 真实提取 + 历史探测数据降级标注）→ 市级检察院（p40 拼音探测 360
  条，标题已验证，method 降级标注待官方名录替换）。
同步：块树省高院 URL 权威化（court.gov.cn 名单覆盖）。
"""
import json
import re

COURTS = {
    "北京市": "https://bjgy.bjcourt.gov.cn",
    "天津市": "https://tjfy.tjcourt.gov.cn",
    "河北省": "http://www.hebeicourt.gov.cn",
    "山西省": "http://sxgy.shanxify.gov.cn",
    "内蒙古自治区": "http://gy.nmgfy.gov.cn",
    "辽宁省": "http://ln.lncourt.gov.cn",
    "吉林省": "http://jlfy.e-court.gov.cn",
    "黑龙江省": "http://www.hljcourt.gov.cn/",
    "上海市": "https://www.hshfy.sh.cn/shfy/web/index.html",
    "江苏省": "http://www.jsfy.gov.cn/",
    "浙江省": "https://www.zjsfgkw.gov.cn/",
    "安徽省": "http://ahfy.ahcourt.gov.cn",
    "福建省": "https://fjfy.fjcourt.gov.cn",
    "江西省": "http://jxgy.jxfy.gov.cn",
    "山东省": "http://www.sdcourt.gov.cn/",
    "河南省": "https://www.hncourt.gov.cn/",
    "湖北省": "http://hubeigy.hbfy.gov.cn",
    "湖南省": "http://hngy.hunancourt.gov.cn",
    "广东省": "http://www.gdcourts.gov.cn/",
    "广西壮族自治区": "http://gxfy.gxcourt.gov.cn",
    "海南省": "http://www.hicourt.gov.cn",
    "重庆市": "http://cqgy.cqfygzfw.gov.cn",
    "四川省": "http://scfy.scssfw.gov.cn",
    "贵州省": "http://www.guizhoucourt.gov.cn/",
    "云南省": "http://fy.yngy.gov.cn",
    "西藏自治区": "http://xzgy.xzcourt.gov.cn",
    "陕西省": "http://sxgy.sxfywcourt.gov.cn",
    "甘肃省": "http://www.chinagscourt.gov.cn/",
    "青海省": "http://qhgy.qhwsfy.gov.cn/",
    "宁夏回族自治区": "http://www.nxfy.gov.cn/",
    "新疆维吾尔自治区": "http://xjfy.xjcourt.gov.cn",
    "新疆生产建设兵团": "http://btfy.btcourt.gov.cn/",
}

CODE = '''# -*- coding: utf-8 -*-
"""{title} 提取规则。

方法：{method}
来源页：{sources}
"""
import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

URL = "{url}"
html = requests.get(URL, timeout=15, verify=False,
                    headers={{"User-Agent": "Mozilla/5.0"}}).content \
    .decode("utf-8", errors="replace")
soup = BeautifulSoup(html, "lxml")
for a in soup.find_all("a"):
    t = re.sub(r"\\s+", "", (a.get("title") or a.get_text(" ", strip=True)).strip())
    h = a.get("href") or ""
    if len(t) <= 30 and h:
        print("  ", t, "->", urljoin(URL, h))
'''


def leaf(nm, cat, u, lv, x=""):
    return {"n": nm, "l": lv, "k": cat, "c": cat, "u": u, "x": x,
            "s": "", "m": ""}


def grp(nm, cat, kids):
    return {"n": nm, "l": "条", "k": "分组", "c": cat, "u": "",
            "x": "", "s": "", "m": "", "ks": kids}


def main():
    tree = json.load(open("tree.json", encoding="utf-8"))
    rules = json.load(open("extraction_rules.json", encoding="utf-8"))
    central = next(g for g in tree["ks"] if g["n"].startswith("中央"))
    prov_g = next(g for g in tree["ks"] if g["n"].startswith("省级"))
    tiao = next(g for g in tree["ks"] if g["n"] == "条（垂直管理系统）")

    # 清理旧法检条规则（若有）
    for pre in ("法院系统", "检察院系统"):
        for k in [x for x in rules if x.startswith(pre)]:
            del rules[k]

    # ---- 块树：最高法/最高检内设 ----
    zgf = next(g for g in central["ks"] if g["n"].startswith("最高人民法院"))
    zgjc = next(g for g in central["ks"] if g["n"].startswith("最高人民检察院"))
    fy_neishe = [{"n": k["n"], "l": "中央", "k": "法院系统", "c": "法院系统",
                  "u": k.get("u", ""), "x": "", "s": "", "m": ""}
                 for g in zgf.get("ks", []) for k in g.get("ks", [])]
    jc_neishe = [{"n": k["n"], "l": "中央", "k": "检察院系统", "c": "检察院系统",
                  "u": k.get("u", ""), "x": "", "s": "", "m": ""}
                 for g in zgjc.get("ks", []) for k in g.get("ks", [])]

    # ---- 法院系统：省级高院（权威）+ 中院/基层（court_links）----
    court_rows = [json.loads(l) for l in open("court_links.jsonl", encoding="utf-8")
                  if json.loads(l).get("kind") == "court"]
    by_prov_c = {}
    for r in court_rows:
        by_prov_c.setdefault(r["province"], []).append(r)

    fy_prov_kids = []
    for pname, u in COURTS.items():
        kids = [{"n": f"{r['name']}{'人民法院' if not r['name'].endswith('人民法院') else ''}",
                 "l": "市" if r["level"] == "市" else "县",
                 "k": "法院系统", "c": "法院系统", "u": r["url"],
                 "x": "", "s": "", "m": ""}
                for r in by_prov_c.get(pname, [])]
        fy_prov_kids.append({"n": f"{pname}高级人民法院", "l": "省",
                             "k": "法院系统", "c": "法院系统", "u": u,
                             "x": "", "s": "", "m": "", "ks": kids})
        # 块树省高院权威化
        pnode = next((p for p in prov_g["ks"] if p["n"] == pname), None)
        if pnode:
            par = next((k for k in pnode.get("ks", []) if k.get("c") == "并列机关"), None)
            if par:
                m = next((x for x in par.get("ks", []) if "法院" in x["n"]), None)
                if m:
                    m["u"] = u
                    mkey = f"{pname}·{m['n']}"
                    if mkey in rules:
                        rules[mkey]["portal"] = u
                        rules[mkey]["sources"] = [u]
                        rules[mkey]["method"] = ("独立门户（最高法官网首页「全国法院」"
                                                 "链接块真实 HTML 提取）")
    fy_root = leaf("最高人民法院", "法院系统", "https://www.court.gov.cn/", "中央")
    fy_sys = grp(f"法院系统（{len(fy_prov_kids) + 2}）", "法院系统",
                 [fy_root,
                  grp(f"内设机构（{len(fy_neishe)}）", "法院系统", fy_neishe),
                  grp(f"高级人民法院（{len(fy_prov_kids)}）", "法院系统", fy_prov_kids)])

    # ---- 检察院系统 ----
    p40 = json.load(open("p40_state.json", encoding="utf-8"))
    jc_hits = p40.get("hits", [])
    by_prov_j = {}
    for h in jc_hits:
        by_prov_j.setdefault(h["province"], []).append(h)
    jc_prov_kids = []
    for pnode in prov_g["ks"]:
        par = next((k for k in pnode.get("ks", []) if k.get("c") == "并列机关"), None)
        if not par:
            continue
        m = next((x for x in par.get("ks", []) if "检察院" in x["n"]), None)
        kids = [{"n": f"{h['name']}检察院" if not h["name"].endswith("检察院") else h["name"],
                 "l": "市" if h["level"] == "市" else "县",
                 "k": "检察院系统", "c": "检察院系统", "u": h["url"],
                 "x": "", "s": "", "m": ""}
                for h in by_prov_j.get(pnode["n"], []) if h["verified"]]
        jc_prov_kids.append({"n": f"{pnode['n']}检察院", "l": "省",
                             "k": "检察院系统", "c": "检察院系统",
                             "u": (m or {}).get("u", ""), "x": "", "s": "", "m": "",
                             "ks": kids})
    jc_root = leaf("最高人民检察院", "检察院系统", "https://www.spp.gov.cn/", "中央")
    jc_sys = grp(f"检察院系统（{len(jc_prov_kids) + 2}）", "检察院系统",
                 [jc_root,
                  grp(f"内设机构（{len(jc_neishe)}）", "检察院系统", jc_neishe),
                  grp(f"省级检察院（{len(jc_prov_kids)}）", "检察院系统", jc_prov_kids)])

    # 插入条根组（替换旧同名）
    tiao["ks"] = [g for g in tiao["ks"]
                  if not g["n"].startswith(("法院系统", "检察院系统"))]
    tiao["ks"].extend([fy_sys, jc_sys])

    # ---- 规则 ----
    def add(key, portal, method, depts, url, srcs):
        rules[key] = {
            "portal": portal, "method": method, "sources": srcs,
            "code": CODE.format(title=key, method=method, sources="、".join(srcs),
                                url=url),
            "depts": depts, "cities": [],
        }

    fy_all = [fy_root] + fy_neishe + fy_prov_kids
    add("法院系统（%d）" % (len(fy_prov_kids) + 2), "https://www.court.gov.cn/",
        "最高法官网首页「全国法院」链接块真实 HTML 提取 32 省级高院；"
        "中院/基层院取自各高院官网链接（court_links，合规）",
        [{"n": m["n"], "u": m["u"], "o": i} for i, m in enumerate(fy_all)],
        "https://www.court.gov.cn/", ["https://www.court.gov.cn/"])
    for pnode in fy_prov_kids:
        add(f"高级人民法院（{len(fy_prov_kids)}）·{pnode['n']}", pnode["u"],
            "最高法官网「全国法院」链接块提取；中基层法院取自本高院官网链接",
            [{"n": m["n"], "u": m["u"], "o": i} for i, m in
             enumerate([pnode] + pnode.get("ks", []))],
            pnode["u"], [pnode["u"]])
    jc_all = [jc_root] + jc_neishe + jc_prov_kids
    add("检察院系统（%d）" % (len(jc_prov_kids) + 2), "https://www.spp.gov.cn/",
        "省级检察院：省门户 footer 链接提取（合规）+ 历史数据；"
        "市级检察院：拼音域名探测+标题验证（降级，待官方名录页替换）",
        [{"n": m["n"], "u": m["u"], "o": i} for i, m in enumerate(jc_all)],
        "https://www.spp.gov.cn/", ["https://www.spp.gov.cn/"])
    for pnode in jc_prov_kids:
        add(f"省级检察院（{len(jc_prov_kids)}）·{pnode['n']}", pnode["u"] or "https://www.spp.gov.cn/",
            "省门户 footer 链接提取（合规）；市级为拼音探测+标题验证（降级待替换）",
            [{"n": m["n"], "u": m["u"], "o": i} for i, m in
             enumerate([pnode] + pnode.get("ks", []))],
            pnode["u"] or "https://www.spp.gov.cn/",
            [pnode["u"] or "https://www.spp.gov.cn/"])

    json.dump(tree, open("tree.json", "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    json.dump(rules, open("extraction_rules.json", "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    print(f"p57 完成：法院系统 {len(fy_all)} 成员（高院 {len(fy_prov_kids)}，"
          f"中基层 {len(court_rows)}）；检察院系统 {len(jc_all)} 成员"
          f"（省级 {len(jc_prov_kids)}，市级 {sum(1 for h in jc_hits if h['verified'])}）；"
          f"rules 总数 {len(rules)}")


if __name__ == "__main__":
    main()
