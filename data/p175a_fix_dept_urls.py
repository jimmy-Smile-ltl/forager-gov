# -*- coding: utf-8 -*-
"""P175a: 修复厅局错配 URL + 删除备案污染节点。

错配节点（政务网/中央部委域名误挂省级厅局）→ 从「XX省·省政府部门」
权威规则（省级门户 footer 提取）按名纠正；规则无 → 清空列名。
财政部驻地方监管局（mof.gov.cn）为正确，不动。
"""
import json, re

tree = json.load(open("tree.json", encoding="utf-8"))
rules = json.load(open("extraction_rules.json", encoding="utf-8"))
reg = json.load(open("site_registry.json", encoding="utf-8"))

WRONG_DOMAINS = ("zwfw.gov.cn", "most.gov.cn", "mohrss.gov.cn", "natcm.gov.cn",
                 "mva.gov.cn", "neac.gov.cn", "beian", "beian.gov.cn")

def prov_name(node_n):
    m = re.match(r"^(北京市|天津市|上海市|重庆市|河北省|山西省|辽宁省|吉林省|黑龙江省|江苏省|浙江省|安徽省|福建省|江西省|山东省|河南省|湖北省|湖南省|广东省|海南省|四川省|贵州省|云南省|陕西省|甘肃省|青海省|台湾省|内蒙古自治区|广西壮族自治区|西藏自治区|宁夏回族自治区|新疆维吾尔自治区|新疆生产建设兵团)", node_n)
    return m.group(1) if m else ""

def rule_lookup(pname, dname):
    """在「XX省·省政府部门」/「XX」规则 depts 里按名找 URL。"""
    keys = [k for k in rules if k.startswith(f"{pname}·省政府部门") or k == pname]
    for rk in keys:
        r = rules.get(rk, {})
        for d in r.get("depts", []) if isinstance(r, dict) else []:
            if isinstance(d, dict) and d.get("u") and d.get("n") == dname:
                return d["u"], f"规则[{rk}]"
        # 前缀匹配（树节点名带「省/自治区/市」前缀而规则不带）
        for d in r.get("depts", []) if isinstance(r, dict) else []:
            if isinstance(d, dict) and d.get("u") and (d["n"] == dname or dname.endswith(d["n"])):
                return d["u"], f"规则[{rk}]后缀匹配"
    return None, None

fixed, cleared, deleted = [], [], []
def walk_parent(n):
    for k in n.get("ks", []):
        if k.get("ks"):
            walk_parent(k)
            continue
        u = k.get("u", "")
        if not u or k.get("x"): continue
        # 备案污染
        if "beian" in u or "beian.gov.cn" in u or "ICP" in k["n"] or "备案" in k["n"] or "安备" in k["n"]:
            deleted.append((k["n"], u))
            k["n"], k["u"], k["s"], k["x"] = "", "", "", ""
            continue
        # 排除：中央部委本身（n 无省前缀且父分组属国务院）、驻X部纪检监察组
        if "纪检监察组" in k["n"] or k["n"] == "国家中医药管理局":
            continue
        # 错配域（政务网+中央部委；mof 监管局排除）
        if any(w in u for w in WRONG_DOMAINS) and "mof.gov.cn" not in u:
            pn = prov_name(n["n"])
            newu, src = rule_lookup(pn, k["n"])
            if newu:
                fixed.append((pn, k["n"], u, newu))
                k["u"] = newu
                k["s"] = f"P175a URL纠错: {src}"
            else:
                cleared.append((pn, k["n"], u))
                k["u"] = ""
                k["s"] = "P175a 错配URL清除（权威规则无纠正）"

walk_parent(tree)

# registry 同步：u 变更后 registry 按旧 u 找不到 → 更新（按名+新u 重建）
json.dump(tree, open("tree.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"p175a: 修复 {len(fixed)} 个, 清除 {len(cleared)} 个, 删污染 {len(deleted)} 个")
for pn, n, old, new in fixed:
    print(f"  ✓ {pn}{n}: {old} → {new}")
for pn, n, old in cleared:
    print(f"  ✗ {pn}{n}: {old} → 列名")
for n, u in deleted:
    print(f"  🗑 {n}: {u}")
