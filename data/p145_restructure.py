# -*- coding: utf-8 -*-
"""P145: 条系统重构——分类归纳 + 重要性排序 + 群团组织系统。

1. 群团组织系统（新建）：全国妇联+32省级妇联、共青团+32省级团委+
   10直属单位、学联/青联/少先队、工会系统并入
2. 财经系统（归纳）：人民银行+证监会+金融监管+税务
3. 国务院垂直管理系统（归纳）：海关+移民管理+自然资源督察
4. 排序（重要性）：人大→政协→法院→检察院→纪委→外交→财经→
   国务院垂直管理→群团组织→药监→烟草→邮政→铁路
"""
import json
import re

def leaf(nm, cat, u, lv):
    return {"n": nm, "l": lv, "k": cat, "c": cat, "u": u,
            "x": "", "s": "", "m": ""}

def grp(nm, cat, kids):
    return {"n": nm, "l": "条", "k": "分组", "c": cat, "u": "",
            "x": "", "s": "", "m": "", "ks": kids}

tree = json.load(open("tree.json", encoding="utf-8"))
rules = json.load(open("extraction_rules.json", encoding="utf-8"))
tiao = next(g for g in tree["ks"] if g["n"].startswith("条"))

# ===== 群团组织系统 =====
women = json.load(open("/tmp/women_serp.json", encoding="utf-8"))
women["河北省"] = "http://www.hebeiwomen.org.cn/"
gqt = json.load(open("/tmp/gqt_data.json", encoding="utf-8"))

SHORT2FULL = {"北京": "北京市", "天津": "天津市", "河北": "河北省",
              "山西": "山西省", "内蒙古": "内蒙古自治区", "辽宁": "辽宁省",
              "吉林": "吉林省", "黑龙江": "黑龙江省", "上海": "上海市",
              "江苏": "江苏省", "浙江": "浙江省", "安徽": "安徽省",
              "福建": "福建省", "江西": "江西省", "山东": "山东省",
              "河南": "河南省", "湖北": "湖北省", "湖南": "湖南省",
              "广东": "广东省", "广西": "广西壮族自治区", "海南": "海南省",
              "重庆": "重庆市", "四川": "四川省", "贵州": "贵州省",
              "云南": "云南省", "西藏": "西藏自治区", "陕西": "陕西省",
              "甘肃": "甘肃省", "青海": "青海省", "宁夏": "宁夏回族自治区",
              "新疆": "新疆维吾尔自治区", "新疆生产建设兵团": "新疆生产建设兵团"}

# 妇联 32 省级
fl = [leaf(f"{k}妇女联合会", "群团组织", v, "省")
      for k, v in sorted(women.items()) if v]
# 共青团 32 省级
tw = [leaf(f"{SHORT2FULL.get(k, k)}共青团委员会", "群团组织", v, "省")
      for k, v in sorted(gqt["prov"].items()) if v]
# 团中央直属单位
zs = [leaf(nm, "群团组织", u, "中央") for nm, u in gqt["zhishu"].items()]
# 群团成员（学联/青联/少先队）
qt = [leaf(nm, "群团组织", u, "中央") for nm, u in gqt["quntuan"].items()
      if nm != "中国共青团网"]
# 工会系统并入（取现有工会系统节点）
gh = next((g for g in tiao["ks"] if "工会" in g["n"]), None)
gh_children = []
if gh:
    for k in gh.get("ks", []):
        if isinstance(k.get("ks"), list):
            gh_children.append(grp(k["n"], "群团组织",
                [leaf(x["n"], "群团组织", x.get("u", ""), x.get("l", "省"))
                 for x in k.get("ks", [])]))
        else:
            gh_children.append(leaf(k["n"], "群团组织", k.get("u", ""), k.get("l", "中央")))

quntuan = grp("群团组织系统（妇联·共青团·工会）", "群团组织", [
    leaf("中华全国妇女联合会", "群团组织", "https://www.women.org.cn/", "中央"),
    grp(f"省级妇联（{len(fl)}）", "群团组织", fl),
    leaf("中国共产主义青年团中央委员会", "群团组织", "https://www.gqt.org.cn/", "中央"),
    grp(f"省级团委（{len(tw)}）", "群团组织", tw),
    grp(f"团中央直属单位（{len(zs)}）", "群团组织", zs),
    grp("共青团系统群团组织", "群团组织", qt),
    grp("工会系统", "群团组织", gh_children),
])

# ===== 财经系统 =====
def regroup(keyword, newname):
    g = next((x for x in tiao["ks"] if keyword in x["n"]), None)
    return g

caijing_children = []
for kw in ("人民银行", "证监会", "金融监管", "税务"):
    g = next((x for x in tiao["ks"] if kw in x["n"]), None)
    if g:
        kids = []
        for k in g.get("ks", []):
            if isinstance(k.get("ks"), list):
                kids.append(grp(k["n"], "财经系统",
                    [leaf(x["n"], "财经系统", x.get("u", ""), x.get("l", "省"))
                     for x in k.get("ks", [])]))
            else:
                kids.append(leaf(k["n"], "财经系统", k.get("u", ""), k.get("l", "中央")))
        caijing_children.append(grp(g["n"], "财经系统", kids))
caijing = grp(f"财经系统（{len(caijing_children)} 机构）", "财经系统", caijing_children)

# ===== 国务院垂直管理系统 =====
guowuyuan_children = []
for kw in ("海关", "移民", "自然资源督察"):
    g = next((x for x in tiao["ks"] if kw in x["n"]), None)
    if g:
        kids = []
        for k in g.get("ks", []):
            if isinstance(k.get("ks"), list):
                kids.append(grp(k["n"], "国务院垂直管理",
                    [leaf(x["n"], "国务院垂直管理", x.get("u", ""), x.get("l", "条"))
                     for x in k.get("ks", [])]))
            else:
                kids.append(leaf(k["n"], "国务院垂直管理", k.get("u", ""), k.get("l", "中央")))
        guowuyuan_children.append(grp(g["n"], "国务院垂直管理", kids))
guowuyuan = grp(f"国务院垂直管理系统（{len(guowuyuan_children)} 机构）",
                "国务院垂直管理", guowuyuan_children)

# ===== 新排序 =====
def find(prefix):
    return next((g for g in tiao["ks"] if g["n"].startswith(prefix)), None)

ORDER = ["人大系统", "政协系统", "法院系统", "检察院系统", "纪委系统",
         "外交系统", None, None, None,
         "药监系统", "烟草系统", "邮政系统", "铁路系统"]
old_groups = {g["n"]: g for g in tiao["ks"]}
new_ks = []
for name in ORDER:
    if name is None:
        continue
    g = find(name)
    if g:
        new_ks.append(g)
wj = find("外交系统")
if wj:
    idx = new_ks.index(wj)
    new_ks.insert(idx + 1, caijing)
    new_ks.insert(idx + 2, guowuyuan)
    new_ks.insert(idx + 3, quntuan)
# 移除旧分组（人民银行/证监会/金融监管/税务/海关/移民/自然资源督察/工会 已并入）
new_ks = [g for g in new_ks
          if not any(kw in g["n"] for kw in ("人民银行", "证监会", "金融监管",
                                             "税务", "海关", "移民",
                                             "自然资源督察"))
          and not g["n"].startswith("工会系统")]
tiao["ks"] = new_ks

json.dump(tree, open("tree.json", "w", encoding="utf-8"),
          ensure_ascii=False, separators=(",", ":"))
print("条模块重排完成:")
for g in tiao["ks"]:
    print(" ", g["n"])
