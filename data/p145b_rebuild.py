# -*- coding: utf-8 -*-
"""P145b: 从 data_js 备份恢复 + 完成条模块重构。"""
import json

tree = json.load(open("tree.json", encoding="utf-8"))
tiao = next(g for g in tree["ks"] if g["n"].startswith("条"))
old = json.load(open("/tmp/old_tiao_backup.json", encoding="utf-8"))

def find_old(prefix):
    return next((g for g in old["ks"] if g["n"].startswith(prefix)), None)

# 群团系统（tree.json 现有，p145 已建好）
quntuan = next((g for g in tiao["ks"] if "群团" in g["n"]), None)

# 财经系统：人民银行+证监会+金融监管+税务
caijing_kids = []
for kw in ("人民银行", "证监会", "金融监管", "税务"):
    g = find_old(kw)
    if g:
        g["c"] = "财经系统"
        for k in g.get("ks", []):
            k["c"] = "财经系统"
            if isinstance(k.get("ks"), list):
                for x in k["ks"]:
                    x["c"] = "财经系统"
                    x["k"] = "财经系统"
        caijing_kids.append(g)
caijing = {"n": f"财经系统（{len(caijing_kids)} 机构）", "l": "条", "k": "分组",
           "c": "财经系统", "u": "", "x": "", "s": "", "m": "", "ks": caijing_kids}

# 国务院垂直管理：海关+移民+自然资源督察
gw_kids = []
for kw in ("海关", "移民", "自然资源督察"):
    g = find_old(kw)
    if g:
        g["c"] = "国务院垂直管理"
        for k in g.get("ks", []):
            k["c"] = "国务院垂直管理"
            if isinstance(k.get("ks"), list):
                for x in k["ks"]:
                    x["c"] = "国务院垂直管理"
                    x["k"] = "国务院垂直管理"
        gw_kids.append(g)
guowuyuan = {"n": f"国务院垂直管理系统（{len(gw_kids)} 机构）", "l": "条",
             "k": "分组", "c": "国务院垂直管理", "u": "", "x": "", "s": "", "m": "",
             "ks": gw_kids}

# 其余保留组（人大/政协/法院/检察院/纪委/外交/药监/烟草/邮政/铁路）
keep_prefixes = ["人大系统", "政协系统", "法院系统", "检察院系统", "纪委系统",
                 "外交系统", "药监系统", "烟草系统", "邮政系统", "铁路系统"]
new_ks = []
ORDER = ["人大系统", "政协系统", "法院系统", "检察院系统", "纪委系统",
         "外交系统", "__caijing__", "__guowuyuan__", "__quntuan__",
         "药监系统", "烟草系统", "邮政系统", "铁路系统"]
group_pool = {g["n"]: g for g in tiao["ks"]}
for name in ORDER:
    if name == "__caijing__":
        new_ks.append(caijing)
    elif name == "__guowuyuan__":
        new_ks.append(guowuyuan)
    elif name == "__quntuan__":
        if quntuan:
            new_ks.append(quntuan)
    else:
        g = next((x for x in tiao["ks"] if x["n"].startswith(name)), None)
        if g:
            new_ks.append(g)
# 移除旧顶层分组（已并入新分组的）
removed_kws = ("人民银行", "证监会", "金融监管", "税务", "海关", "移民",
               "自然资源督察", "工会")
new_ks = [g for g in new_ks
          if not any(kw in g["n"] for kw in removed_kws)
          or g["n"].startswith("群团")]
tiao["ks"] = new_ks

json.dump(tree, open("tree.json", "w", encoding="utf-8"),
          ensure_ascii=False, separators=(",", ":"))
print("最终条模块:")
for g in tiao["ks"]:
    n = len(g.get("ks", []))
    print(f"  {g['n']}: {n} 子组")
