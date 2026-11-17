# -*- coding: utf-8 -*-
"""P89: 批量补 12 省市级人大（真实 HTML/官网 JS 配置提取）。

来源（全部官方页面数据）：
- 山东 sdrd.gov.cn 首页 select「省内人大」（16/16）
- 山西 sxpc.gov.cn 首页 select（6/11，其余列名）
- 湖北 hppc.gov.cn 首页 select「市州人大」（17 含省直管）
- 甘肃 gsrdw.gov.cn 首页 select（10/14 市州，其余列名）
- 内蒙古 nmgrd.gov.cn 首页 select（12/12 含盟工委）
- 安徽 ahrd.gov.cn js/index.js cityLinks 地图配置（16/16）
- 浙江 zjrd.gov.cn 首页内联 footer linkList（11/11）
- 吉林 jlrd.gov.cn 首页「市县人大」区块（6/9，void(0)→列名）
- 宁夏/天津/西藏：官网无市级人大导航 → 全列名（清旧误匹配）
"""
import json
import re

def read(fn):
    return open(fn, encoding="utf-8", errors="replace").read()

def sel_options(html, key):
    """含 key 文本选项的 select 全部 option。"""
    for sel in re.findall(r'<select[^>]*>(.*?)</select>', html, re.S):
        opts = re.findall(r'<option[^>]*value="([^"]*)"[^>]*>\s*([^<]+?)\s*</option>', sel)
        if any(key in x[1] for x in opts):
            return [(x[1].strip(), x[0].strip()) for x in opts]
    return []

def core_of(nm):
    ETH = ("维吾尔|壮族|回族|蒙古族|藏族|土家族|苗族|彝族|朝鲜族|满族|白族|"
           "侗族|瑶族|布依族|哈尼族|傣族|黎族|傈僳族|佤族|畲族|高山族|拉祜族|"
           "水族|东乡族|纳西族|景颇族|柯尔克孜族|土族|达斡尔族|仫佬族|羌族|"
           "布朗族|撒拉族|毛南族|仡佬族|锡伯族|阿昌族|普米族|塔吉克族|怒族|"
           "乌孜别克族|俄罗斯族|鄂温克族|德昂族|保安族|裕固族|京族|塔塔尔族|"
           "独龙族|鄂伦春族|赫哲族|门巴族|珞巴族|基诺族|哈萨克族")
    c = re.sub(r"(自治州|自治县|自治旗|地区|盟|林区)$", "", nm)
    c = re.sub(rf"(?:{ETH})+$", "", c)
    return re.sub(r"(市|区|县)$", "", c)

def match_txt(txt, names):
    t2 = re.sub(r"人大$|人大常委会$|人民代表大会常务委员会$|人大网$", "", txt)
    t2 = t2.replace("人大", "").replace("工作委员会", "")
    for nm, base in names:
        c = core_of(nm)
        if t2 == nm or t2 == base or t2 == c or \
           (len(t2) >= 2 and (t2.startswith(c) or c.startswith(t2))):
            return nm
    return None

def build(prov, names, links):
    """links: {提取文本: url}；按 names 匹配，未命中列名。"""
    rows = []
    used = set()
    for nm in names:
        hit = None
        for t, u in links.items():
            if match_txt(t, [(nm, core_of(nm))]):
                hit = u
                used.add(t)
                break
        rows.append({"province": prov, "name": nm, "url": hit or "",
                     "listed": bool(hit)})
    return rows

tree = json.load(open("tree.json", encoding="utf-8"))
prov_g = next(g for g in tree["ks"] if g["n"].startswith("省级"))

def city_names(pn, lvs=("市", "县")):
    p = next(x for x in prov_g["ks"] if x["n"] == pn)
    s = []
    for top in p.get("ks", []):
        def walk(n):
            if n.get("l") in lvs and n.get("k") == "人民政府" and \
               "开发区" not in n["n"] and "新区" not in n["n"] and \
               "园区" not in n["n"] and "管理区" not in n["n"]:
                s.append(n["n"])
            for k in n.get("ks", []):
                walk(k)
        walk(top)
    return s

new = []

# 山东 16
opts = sel_options(read("/tmp/p87_山东省.html"), "济南人大")
links = {t: v for t, v in opts if v and v != "#" and "人大" in t and "省" not in t}
names = city_names("山东省", ("市",))
new += build("山东省", names, links)

# 山西 11
opts = sel_options(read("/tmp/p87_山西省.html"), "太原人大")
links = {t: v for t, v in opts if v and v != "#"}
new += build("山西省", city_names("山西省", ("市",)), links)

# 湖北 13市州 + 4省直管
opts = sel_options(read("/tmp/p87_湖北省.html"), "武汉人大")
links = {t: v for t, v in opts if v and v != "#"}
names = city_names("湖北省", ("市",)) + ["仙桃市", "潜江市", "天门市", "神农架林区"]
new += build("湖北省", names, links)

# 甘肃 14 市州
opts = sel_options(read("/tmp/p87_甘肃省.html"), "天水人大")
links = {t: v for t, v in opts if v and v != "#" and "人大" in t}
new += build("甘肃省", city_names("甘肃省", ("市",)), links)

# 内蒙古 12 盟市
opts = sel_options(read("/tmp/p87_内蒙古自治区.html"), "呼和浩特市人大")
links = {t: v for t, v in opts if v and v != "#"}
new += build("内蒙古自治区", city_names("内蒙古自治区", ("市",)), links)

# 安徽 16（js cityLinks）
js = read("/tmp/ah_index.js")
m = re.search(r'cityLinks:\{"', js)
links = {}
if m:
    seg = js[m.start():m.start()+1400]
    for k, v in re.findall(r'"([^"]+)":"((?:http|https)://[^"]+)"', seg):
        links[k] = v
new += build("安徽省", city_names("安徽省", ("市",)), links)

# 浙江 11（内联 linkList）
raw = read("/tmp/zj_raw.html")
i = raw.find("title: '市县人大'")
links = {}
if i > 0:
    seg = raw[i:i+5000]
    for t, u in re.findall(r"text:\s*'([^']+)',\s*url:\s*'([^']+)'", seg):
        links[t] = u
new += build("浙江省", city_names("浙江省", ("市",)), links)

# 吉林 9
html = read("/tmp/p87_吉林省.html")
links = {}
m2 = re.search(r'<a[^>]+href="([^"]+)"[^>]*>\s*长春市人大\s*</a>', html)
if m2:
    i = html.rfind('<a', 0, m2.start())
    seg = html[max(0, i-200):m2.end()+4000]
    for u, t in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>\s*([^<]{3,24}?)\s*</a>', seg):
        t2 = t.strip()
        if "人大" in t2 and "void" not in u:
            links[t2] = u
new += build("吉林省", city_names("吉林省", ("市",)), links)

# 宁夏 5 全列名 / 西藏 7 全列名 / 天津 16 区全列名（清除旧误匹配）
new += build("宁夏回族自治区", city_names("宁夏回族自治区", ("市",)), {})
new += build("西藏自治区", city_names("西藏自治区", ("市",)), {})
tj_names = []
p = next(x for x in prov_g["ks"] if x["n"] == "天津市")
for top in p.get("ks", []):
    def walk(n):
        if n.get("l") == "地级区" and n.get("k") == "人民政府":
            tj_names.append(n["n"])
        for k in n.get("ks", []):
            walk(k)
    walk(top)
new += build("天津市", tj_names, {})

# 合并写回
old = [json.loads(l) for l in open("rd_shi.jsonl", encoding="utf-8")]
old = [r for r in old if r["province"] not in
       {"山东省", "山西省", "湖北省", "甘肃省", "内蒙古自治区", "安徽省",
        "浙江省", "吉林省", "宁夏回族自治区", "西藏自治区", "天津市"}]
rows = old + new
with open("rd_shi.jsonl", "w", encoding="utf-8") as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")

by = {}
for r in new:
    by.setdefault(r["province"], [0, 0])
    by[r["province"]][0] += 1
    if r["listed"]:
        by[r["province"]][1] += 1
for pn, (t, n) in sorted(by.items()):
    print(f"{pn}: {n}/{t} 有官网")
print(f"p89 完成：rd_shi.jsonl 共 {len(rows)} 条")
