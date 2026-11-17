# -*- coding: utf-8 -*-
"""P119: 落库 5 个条系统权威名录（人行/税务/邮政/金融监管/督察）。

来源（全部总局官网真实 HTML）：
- 人行 36：pbc.gov.cn「分支机构」栏目页（31 省分行 + 5 计划单列市分行）
- 税务 36：chinatax.gov.cn 首页「省级税务局」区块
- 邮政 31：spb.gov.cn 首页省级局链接区块
- 金融监管 36：nfra.gov.cn 机构概况页 /branch/xx/（相对路径）
- 督察 9：mnr.gov.cn wzdh/pcjg/ 栏目页
"""
import json
import re

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
              "新疆": "新疆维吾尔自治区"}

# 人行（pbc 分支机构页）
t = open("/tmp/pbc_fenzhi.html", encoding="utf-8", errors="replace").read()
PB = {}
for u, txt in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>\s*([^<]{2,26}?)\s*</a>', t):
    t2 = txt.strip()
    m = re.match(r'^(北京|天津|河北|山西|内蒙古|辽宁|吉林|黑龙江|上海|江苏|浙江|安徽|福建|江西|山东|河南|湖北|湖南|广东|广西|海南|重庆|四川|贵州|云南|西藏|陕西|甘肃|青海|宁夏|新疆)(?:省|市|自治区)?(?:分行)$', t2)
    m2 = re.match(r'^(厦门|大连|宁波|深圳|青岛)市分行$', t2)
    if m and u.startswith("http"):
        core = m.group(1)
        if core in SHORT2FULL:
            PB[SHORT2FULL[core]] = u
    elif m2 and u.startswith("http"):
        PB[f"{m2.group(1)}市"] = u

# 税务（chinatax 首页区块）
t2 = open("/tmp/bd_税务.html", encoding="utf-8", errors="replace").read()
i = t2.find("省级税务局", 100000)
seg = t2[max(0, i-300):i+5000]
TAX = {}
for u, txt in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>\s*([^<]{2,12}?)\s*</a>', seg):
    t3 = txt.strip()
    m = re.match(r'^(北京|天津|河北|山西|内蒙古|辽宁|吉林|黑龙江|上海|江苏|浙江|安徽|福建|江西|山东|河南|湖北|湖南|广东|广西|海南|重庆|四川|贵州|云南|西藏|陕西|甘肃|青海|宁夏|新疆)$', t3)
    if m and "chinatax.gov.cn" in u:
        TAX[SHORT2FULL[m.group(1)]] = u

# 邮政（spb 首页）
t3 = open("/tmp/bd_邮政.html", encoding="utf-8", errors="replace").read()
SPB = {}
for u, txt in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>\s*([^<]{2,12}?)\s*</a>', t3):
    t4 = txt.strip()
    m = re.match(r'^(北京|天津|河北|山西|内蒙古|辽宁|吉林|黑龙江|上海|江苏|浙江|安徽|福建|江西|山东|河南|湖北|湖南|广东|广西|海南|重庆|四川|贵州|云南|西藏|陕西|甘肃|青海|宁夏|新疆)$', t4)
    if m and "spb.gov.cn" in u:
        SPB[SHORT2FULL[m.group(1)]] = u

# 金融监管（nfra 机构页 /branch/xx/）
t4 = open("snapshots/other/中央/金融监管总局/20261105_jigou.html", encoding="utf-8", errors="replace").read()
JRJG = {}
for u, txt in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>\s*([^<]{2,12}?)\s*</a>', t4):
    t5 = txt.strip()
    m = re.match(r'^(北京|天津|河北|山西|内蒙古|辽宁|吉林|黑龙江|上海|江苏|浙江|安徽|福建|江西|山东|河南|湖北|湖南|广东|广西|海南|重庆|四川|贵州|云南|西藏|陕西|甘肃|青海|宁夏|新疆)监管局$', t5)
    if m and "/branch/" in u:
        JRJG[SHORT2FULL[m.group(1)]] = "https://www.nfra.gov.cn" + u
# 计划单列市
for u, txt in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>\s*([^<]{2,12}?)\s*</a>', t4):
    t5 = txt.strip()
    m = re.match(r'^(大连|宁波|青岛|深圳|厦门)监管局$', t5)
    if m and "/branch/" in u:
        JRJG[f"{m.group(1)}市"] = "https://www.nfra.gov.cn" + u

# 督察（mnr pcjg 页）
t5 = open("/tmp/dc_pcjg.html", encoding="utf-8", errors="replace").read()
DC = {}
for u, txt in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>\s*([^<]{2,30}?)\s*</a>', t5):
    t6 = txt.strip()
    m = re.match(r'^国家自然资源督察(北京|沈阳|上海|南京|济南|武汉|广州|成都|西安)局$', t6)
    if m and u.startswith("http"):
        DC[t6] = u

# 落库
tree = json.load(open("tree.json", encoding="utf-8"))
tiao = next(g for g in tree["ks"] if g["n"].startswith("条"))
stats = {}
for syskw, data, node_pat, leaf_fmt in [
    ("人民银行", PB, "人民银行", "{n}分行"),
    ("税务", TAX, "税务", "{n}税务局"),
    ("邮政", SPB, "邮政", "{n}邮政管理局"),
    ("金融监管", JRJG, "金融监管", "{n}监管局"),
    ("自然资源督察", DC, "自然资源督察", None),
]:
    g = next(x for x in tiao["ks"] if syskw in x["n"])
    fixed = 0
    if node_pat == "自然资源督察":
        for k in g["ks"]:
            if k["n"] in DC:
                k["u"] = DC[k["n"]]
                fixed += 1
    else:
        for k in g["ks"]:
            pname = re.sub(r"(分行|税务局|邮政管理局|监管局)$", "", k["n"])
            pname = re.sub(r"(省|市|自治区)$", "", pname)
            full = SHORT2FULL.get(pname) or (pname + "省" if pname in
                    ("青海", "甘肃", "贵州", "云南", "辽宁", "吉林", "黑龙江",
                     "福建", "江西", "山东", "河南", "湖北", "湖南", "广东",
                     "海南", "四川", "陕西", "浙江", "江苏", "安徽", "河北",
                     "山西") else pname)
            if k["n"] in ("大连市分行", "大连市税务局", "大连市监管局"):
                full = "大连市"
            elif k["n"].startswith(("宁波", "青岛", "深圳", "厦门")):
                full = k["n"].replace("市分行", "").replace("市税务局", "").replace("市监管局", "")
            if full in data or k["n"][:2] in data:
                key = full if full in data else [x for x in data if x.startswith(k["n"][:2])][0]
                k["u"] = data[key]
                fixed += 1
    stats[syskw] = fixed

json.dump(tree, open("tree.json", "w", encoding="utf-8"),
          ensure_ascii=False, separators=(",", ":"))
print("p119 落库:", stats)
print("人行提取:", len(PB), "税务:", len(TAX), "邮政:", len(SPB),
      "金融监管:", len(JRJG), "督察:", len(DC))
