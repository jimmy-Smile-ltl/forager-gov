# -*- coding: utf-8 -*-
"""P47: 构建「条（垂直管理系统）」视图树 + 规则。

tree.json 根级新增 条（垂直管理系统），将工会系统移入，并新增 7 个系统：
  海关系统（42）      —— 复用块树海关总署下 42 直属海关
  税务系统（N）       —— {省}税务局（chinatax 子域，市级多无独立域）
  邮政系统（N）       —— 省/市邮政管理局（spb 子域）
  烟草系统（N）       —— 省/市烟草专卖局（tobacco 子域）
  人民银行系统（N）   —— 分行（pbc 子域，省会=省分行）
  铁路系统（19）      —— 总局 + 18 铁路局集团公司（无独立官网→列名）
  金融监管系统（38）  —— 总局 + 31省局+5计划单列+1（派出机构无独立站→列名）
规则键：组={系统组名}；成员={组名}·{成员名}（ruleKeyOf 已加 TIAO 分支）
"""
import json
import re

TIAO_ROOT = "条（垂直管理系统）"

RAILWAYS = ["哈尔滨", "沈阳", "北京", "太原", "呼和浩特", "郑州", "武汉", "西安",
            "济南", "上海", "南昌", "广州", "南宁", "成都", "昆明", "兰州",
            "乌鲁木齐", "青藏"]

CODE_GROUP = '''# -*- coding: utf-8 -*-
"""{title} 提取规则（条条·垂直管理系统）。

方法：{method}
来源页：{sources}

说明：垂直管理系统（条条）机构站点与块块政府门户无隶属页面关系，
     按统一域名体系探测 + 连通性验证采集；{note}
依赖：pip install requests
"""
import re
import requests

UA = {{"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
     "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"}}
DOMAIN_TMPL = "{tmpl}"


def check(name_py):
    url = DOMAIN_TMPL.format(py=name_py)
    try:
        resp = requests.get(url, headers=UA, timeout=12, verify=False)
        return url, resp.status_code, len(resp.content)
    except Exception as e:
        return url, None, type(e).__name__


for item in [{{"n": "{sample_n}", "py": "{sample_py}"}}]:
    print(check(item["py"]))
'''

CODE_RAIL = '''# -*- coding: utf-8 -*-
"""{title} 提取规则。

方法：中国铁路官网 china-railway.com.cn → 18 个铁路局集团公司；
     各局集团公司无独立信息公开门户（信息统一发布于国铁集团官网/95306 货运
     平台/12306 客运平台）→ 18 局列名。
来源页：https://www.china-railway.com.cn/
"""
import requests

resp = requests.get("https://www.china-railway.com.cn/", timeout=15, verify=False,
                    headers={{"User-Agent": "Mozilla/5.0"}})
print("国铁集团官网长度:", len(resp.content))
print("18 铁路局集团公司: 列名（无独立公开门户）")
'''


def member(nm, cat, u, lv):
    return {"n": nm, "l": lv, "k": cat, "c": cat, "u": u,
            "x": "", "s": "", "m": ""}


def main():
    tree = json.load(open("tree.json", encoding="utf-8"))
    rules = json.load(open("extraction_rules.json", encoding="utf-8"))
    vs = [json.loads(l) for l in open("vertical_systems.jsonl", encoding="utf-8")]
    by_sys = {}
    for r in vs:
        by_sys.setdefault(r["system"], []).append(r)

    # ---- 海关：复用块树海关总署下 42 直属海关 ----
    central = next(g for g in tree["ks"] if g["n"].startswith("中央"))
    gw = next(g for g in central["ks"] if g["n"].startswith("国务院"))
    zsj = next(g for g in gw["ks"] if g["n"].startswith("国务院直属机构"))
    hg = next(n for n in zsj["ks"] if n["n"] == "海关总署")
    # 42 直属海关在「直属海关（42，垂直管理）」分组下，摊平复制
    customs_kids = [
        {"n": k["n"], "l": "市", "k": "海关系统", "c": "海关系统",
         "u": k.get("u", ""), "x": "", "s": "", "m": ""}
        for g in hg.get("ks", []) for k in g.get("ks", [])]

    # ---- 各系统组 ----
    sys_specs = [
        ("海关系统", "海关系统", "http://www.customs.gov.cn/",
         customs_kids, "42 直属海关=城市拼音.customs.gov.cn DNS 探测全通",
         "{py}.customs.gov.cn", "北京海关", "beijing"),
        ("税务系统", "税务系统", "https://www.chinatax.gov.cn/",
         [member(f"{r['name']}税务局", "税务系统", r["url"], "省")
          for r in by_sys.get("tax", [])],
         "省局=省名拼音.chinatax.gov.cn（市级税务局多无独立域→列名）",
         "{py}.chinatax.gov.cn", "四川省税务局", "sichuan"),
        ("邮政系统", "邮政系统", "https://www.spb.gov.cn/",
         [member(f"{r['name']}邮政管理局", "邮政系统", r["url"], r["level"])
          for r in by_sys.get("spb", [])],
         "省/市局=拼音.spb.gov.cn（无 www，省局用首字母缩写）",
         "{py}.spb.gov.cn", "广东省邮政管理局", "gd"),
        ("烟草系统", "烟草系统", "http://www.tobacco.gov.cn/",
         [member(f"{r['name']}烟草专卖局", "烟草系统", r["url"], r["level"])
          for r in by_sys.get("tobacco", [])],
         "省/市局=拼音.tobacco.gov.cn（http 为主）",
         "{py}.tobacco.gov.cn", "贵州省烟草专卖局", "gz"),
        ("人民银行系统", "人民银行系统", "http://www.pbc.gov.cn/",
         [member(f"{r['name']}分行", "人民银行系统", r["url"], "市")
          for r in by_sys.get("pbc", [])],
         "分支=城市拼音.pbc.gov.cn（省会=省分行驻地）",
         "{py}.pbc.gov.cn", "成都市分行", "chengdu"),
    ]
    groups = []
    for gname, cat, portal, members, method_note, tmpl, sn, sp in sys_specs:
        groups.append((gname, cat, portal, members, method_note, tmpl, sn, sp))

    # 铁路
    rail_members = [member("中国国家铁路集团有限公司", "铁路系统",
                           "https://www.china-railway.com.cn/", "中央")] + \
        [member(f"中国铁路{r}局集团有限公司", "铁路系统", "", "省")
         for r in RAILWAYS]
    groups.append(("铁路系统", "铁路系统", "https://www.china-railway.com.cn/",
                   rail_members, "18 局集团公司无独立公开门户→列名", "", "", ""))
    # 金融监管
    jrjg = [member("国家金融监督管理总局", "金融监管系统",
                   "https://www.nfra.gov.cn/", "中央")]
    provs_full = [p["n"] for p in next(g for g in tree["ks"]
                                       if g["n"].startswith("省级"))["ks"]]
    for p in provs_full:
        jrjg.append(member(f"国家金融监督管理总局{p}监管局", "金融监管系统",
                           "", "省"))
    jrjg += [member(f"国家金融监督管理总局{n}监管局", "金融监管系统", "", "省")
             for n in ("大连市", "宁波市", "厦门市", "青岛市", "深圳市")]
    groups.append(("金融监管系统", "金融监管系统", "https://www.nfra.gov.cn/",
                   jrjg, "派出机构（省局/计划单列市局）无独立公开门户→列名", "", "", ""))

    # ---- 组装条根组（幂等：先摘除既有条根组及其内工会模块）----
    old_tiao = next((g for g in tree["ks"] if g["n"] == TIAO_ROOT), None)
    union_mod = None
    if old_tiao:
        union_mod = next((g for g in old_tiao["ks"]
                          if g["n"].startswith("工会系统")), None)
        tree["ks"].remove(old_tiao)
    else:
        union_mod = next((g for g in tree["ks"] if g["n"].startswith("工会系统")),
                         None)
        if union_mod:
            tree["ks"].remove(union_mod)
    tiao_root = {"n": TIAO_ROOT, "l": "根", "k": "分组", "c": "条",
                 "u": "", "x": "", "s": "", "m": "", "ks": []}
    if union_mod:
        tiao_root["ks"].append(union_mod)
    for gname, cat, portal, members, method_note, tmpl, sn, sp in groups:
        grp = {"n": f"{gname}（{len(members)}）", "l": "条", "k": "分组",
               "c": cat, "u": portal, "x": "", "s": "", "m": "", "ks": members}
        tiao_root["ks"].append(grp)
        # 组规则
        gkey = grp["n"]
        rules[gkey] = {
            "portal": portal,
            "method": method_note,
            "sources": [portal],
            "code": CODE_RAIL.format(title=gname) if gname == "铁路系统" else
                    (CODE_GROUP.format(title=gname, method=method_note,
                                       sources=portal, note=method_note,
                                       tmpl=tmpl, sample_n=sn, sample_py=sp)
                     if tmpl else
                     f'# -*- coding: utf-8 -*-\n"""{gname}：{method_note}"""\n'),
            "depts": [{"n": m["n"], "u": m.get("u", ""), "o": i}
                      for i, m in enumerate(members)],
            "cities": [],
        }
        # 成员规则
        for m in members:
            mkey = f"{grp['n']}·{m['n']}"
            rules[mkey] = {
                "portal": m.get("u", ""),
                "method": method_note + ("；无独立公开门户 → 列名" if not m.get("u") else ""),
                "sources": [m["u"]] if m.get("u") else [portal],
                "code": (f'# -*- coding: utf-8 -*-\n"""{m["n"]} 提取规则。\n'
                         f'门户：{m.get("u") or "无独立公开门户（列名）"}\n'
                         f'方法：{method_note}\n"""\nimport requests\n\n'
                         f'resp = requests.get("{m.get("u") or portal}", '
                         'timeout=15, verify=False, '
                         'headers={"User-Agent": "Mozilla/5.0"})\n'
                         'print("页面长度:", len(resp.content))\n'),
                "depts": [{"n": m["n"], "u": m.get("u", ""), "o": 0}],
                "cities": [],
            }
    tree["ks"].append(tiao_root)

    json.dump(tree, open("tree.json", "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    json.dump(rules, open("extraction_rules.json", "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    print(f"p47 完成：条根组含 {len(tiao_root['ks'])} 个系统，rules 总数 {len(rules)}")
    for g in tiao_root["ks"]:
        print(f"  {g['n']} ({len(g.get('ks', []))})")


if __name__ == "__main__":
    main()
