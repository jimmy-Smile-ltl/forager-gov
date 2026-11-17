# -*- coding: utf-8 -*-
"""P53: 烟草系统模块重建（总局官网导航真实 HTML 提取，替换拼音探测数据）。

结构：烟草系统（5）
  国家烟草专卖局（u=总局, x=信息公开专栏）
  司局子站（28）       —— 办公室（外事司）…内设司局（总局子路径页）
  省级单位（33）       —— 31省+大连/深圳市烟草专卖局（真实域名，含吉林/云南/
                        西藏/新疆等非 tobacco.gov.cn 子域的特殊域名）
  工业企业（17）       —— 各省中烟工业公司（tobacco.com.cn）
  其他直属机构（6）    —— 南纤/昆纤/珠纤/郑州院/进修学院/合肥设计院
清理旧拼音探测烟草规则；块树国家烟草专卖局补信息公开专栏 URL。
"""
import json
import re

NAME_MAP = {
    "北京": "北京市", "天津": "天津市", "河北": "河北省", "山西": "山西省",
    "内蒙古": "内蒙古自治区", "辽宁": "辽宁省", "吉林": "吉林省",
    "黑龙江": "黑龙江省", "大连": "大连市", "上海": "上海市", "江苏": "江苏省",
    "浙江": "浙江省", "安徽": "安徽省", "福建": "福建省", "江西": "江西省",
    "山东": "山东省", "河南": "河南省", "湖北": "湖北省", "湖南": "湖南省",
    "广东": "广东省", "广西": "广西壮族自治区", "海南": "海南省",
    "深圳": "深圳市", "重庆": "重庆市", "四川": "四川省", "贵州": "贵州省",
    "云南": "云南省", "西藏": "西藏自治区", "陕西": "陕西省", "甘肃": "甘肃省",
    "青海": "青海省", "宁夏": "宁夏回族自治区", "新疆": "新疆维吾尔自治区",
}

CODE = '''# -*- coding: utf-8 -*-
"""{title} 提取规则。

方法：国家烟草专卖局官网 tobacco.gov.cn 顶部导航「{sec}▼」下拉
     （静态 HTML，<li class="m"><ul class="inLinkUl"><li><a> 结构）
     → 链接全量提取 + urljoin 相对路径 → 机构登记。
     （真实 HTML 提取，非域名探测）
来源页：http://www.tobacco.gov.cn/
"""
import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE = "http://www.tobacco.gov.cn/"
html = requests.get(BASE, timeout=15, verify=False,
                    headers={{"User-Agent": "Mozilla/5.0"}}).content \
    .decode("gb18030", errors="replace")
soup = BeautifulSoup(html, "lxml")
for li in soup.find_all("li", class_="m"):
    a = li.find("a")
    if not a or "{sec}" not in a.get_text():
        continue
    ul = li.find("ul")
    if not ul:
        continue
    for sub in ul.find_all("a"):
        t = re.sub(r"\\s+", "", sub.get_text(" ", strip=True))
        h = sub.get("href") or ""
        u = urljoin(BASE, h) if not h.startswith(("http://", "https://")) else h
        print("  ", t, "->", u)
'''


def leaf(nm, cat, u, lv, x=""):
    return {"n": nm, "l": lv, "k": cat, "c": cat, "u": u, "x": x,
            "s": "", "m": ""}


def grp(nm, cat, kids):
    return {"n": nm, "l": "条", "k": "分组", "c": cat, "u": "",
            "x": "", "s": "", "m": "", "ks": kids}


def main():
    d = json.load(open("tobacco_official.json", encoding="utf-8"))
    tree = json.load(open("tree.json", encoding="utf-8"))
    rules = json.load(open("extraction_rules.json", encoding="utf-8"))

    # ---- 清理旧拼音探测烟草规则 ----
    old_keys = [k for k in rules if k.startswith("烟草系统（")]
    for k in old_keys:
        del rules[k]
    print(f"清理旧烟草规则 {len(old_keys)} 条")

    # ---- 组装新烟草系统 ----
    gjyc = leaf("国家烟草专卖局", "烟草系统", d["_国家局"]["u"], "中央",
                x=d["_国家局"]["xxgk"])
    sections = []
    for sec in ("司局子站", "省级单位", "工业企业", "其他直属机构"):
        kids = []
        for it in d[sec]:
            name = it["n"]
            if sec == "省级单位":
                name = NAME_MAP.get(name, name)
                if name in ("大连市", "深圳市"):
                    kids.append(leaf(f"{name}烟草专卖局", "烟草系统", it["u"], "市"))
                else:
                    kids.append(leaf(f"{name}烟草专卖局", "烟草系统", it["u"], "省"))
            else:
                kids.append(leaf(name, "烟草系统", it["u"], "中央"))
        sections.append(grp(f"{sec}（{len(kids)}）", "烟草系统", kids))

    new_grp = grp("烟草系统（5）", "烟草系统", [gjyc] + sections)

    # 替换条根组内的烟草系统
    tiao = next(g for g in tree["ks"] if g["n"] == "条（垂直管理系统）")
    tiao["ks"] = [g if not g["n"].startswith("烟草系统") else new_grp
                  for g in tiao["ks"]]
    if not any(g["n"].startswith("烟草系统") for g in tiao["ks"]):
        tiao["ks"].append(new_grp)

    # ---- 块树：国家烟草专卖局补信息公开专栏 ----
    central = next(g for g in tree["ks"] if g["n"].startswith("中央"))
    gw = next(g for g in central["ks"] if g["n"].startswith("国务院"))
    gjj = next(g for g in gw["ks"] if g["n"].startswith("部委管理的国家局"))
    yc = next((n for n in gjj["ks"] if n["n"] == "国家烟草专卖局"), None)
    if yc:
        yc["x"] = d["_国家局"]["xxgk"]

    # ---- 规则 ----
    def add_rule(key, r):
        rules[key] = r

    all_members = [gjyc] + [m for s in sections for m in s["ks"]]
    add_rule("烟草系统（5）", {
        "portal": d["_国家局"]["u"],
        "method": "总局官网顶部导航四栏目（司局子站/省级单位/工业企业/其他直属机构）"
                  "下拉真实 HTML 提取",
        "sources": [d["_国家局"]["u"]],
        "code": CODE.format(title="烟草系统（5）", sec="省级单位"),
        "depts": [{"n": m["n"], "u": m["u"], "o": i}
                  for i, m in enumerate(all_members)],
        "cities": [],
    })
    add_rule("烟草系统（5）·国家烟草专卖局", {
        "portal": d["_国家局"]["u"],
        "method": "总局官网；信息公开专栏页提取",
        "sources": [d["_国家局"]["u"]],
        "code": CODE.format(title="国家烟草专卖局", sec="省级单位"),
        "depts": [{"n": "国家烟草专卖局", "u": d["_国家局"]["u"], "o": 0}],
        "cities": [],
    })
    for s in sections:
        add_rule(s["n"], {
            "portal": d["_国家局"]["u"],
            "method": f"总局官网导航「{s['n'].split('（')[0]}▼」下拉真实 HTML 提取",
            "sources": [d["_国家局"]["u"]],
            "code": CODE.format(title=s["n"], sec=s["n"].split("（")[0]),
            "depts": [{"n": m["n"], "u": m["u"], "o": i}
                      for i, m in enumerate(s["ks"])],
            "cities": [],
        })
        for m in s["ks"]:
            add_rule(f"{s['n']}·{m['n']}", {
                "portal": m["u"],
                "method": "总局官网导航「%s▼」下拉真实 HTML 提取" % s["n"].split("（")[0],
                "sources": [m["u"]],
                "code": (f'# -*- coding: utf-8 -*-\n"""{m["n"]} 提取规则。\n'
                         f'门户：{m["u"]}（来源：总局官网导航 HTML 提取）\n"""\n'
                         'import requests\n\n'
                         f'resp = requests.get("{m["u"]}", timeout=15, verify=False, '
                         'headers={"User-Agent": "Mozilla/5.0"})\n'
                         'print("页面长度:", len(resp.content))\n'),
                "depts": [{"n": m["n"], "u": m["u"], "o": 0}],
                "cities": [],
            })

    json.dump(tree, open("tree.json", "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    json.dump(rules, open("extraction_rules.json", "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    print(f"p53 完成：烟草系统 5 组 {len(all_members)} 成员，rules 总数 {len(rules)}")


if __name__ == "__main__":
    main()
