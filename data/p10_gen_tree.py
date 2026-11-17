# -*- coding: utf-8 -*-
"""P10 v2: 生成政府信息公开体系树形数据（兵团/港澳台补齐、直辖市级别严谨化）。"""
import json
import re

PSEUDO = re.compile(r"(市辖区|开发区|高新区|管理区|园区|工业区|示范区|合作区|保税区|实验区|管委会|循环化工园区|风景名胜区|新城|新区)")

HK_DISTRICTS = ["中西区", "湾仔区", "东区", "南区", "油尖旺区", "深水埗区", "九龙城区", "黄大仙区",
                "观塘区", "葵青区", "荃湾区", "屯门区", "元朗区", "北区", "大埔区", "沙田区", "西贡区", "离岛区"]
MO_PARISHES = ["花地玛堂区", "圣安多尼堂区", "大堂区", "望德堂区", "风顺堂区", "嘉模堂区", "路氹填海区", "圣方济各堂区"]
TW_COUNTIES = None  # 由 taiwan_counties.json 载入（含门户）
BINGTUAN_CITY_PREFIX = ("6590",)  # 兵团直辖县级市代码前缀

# 中共中央直属机构（多数无独立公开门户 → 列名）
CPC_DIRECT_AGENCIES = [
    "中央办公厅", "中央组织部", "中央宣传部", "中央统战部", "中央政法委员会",
    "中央政策研究室", "中央全面深化改革委员会办公室", "中央财经委员会办公室",
    "中央外事工作委员会办公室", "中央国家安全委员会办公室",
    "中央机构编制委员会办公室", "中央和国家机关工作委员会", "中央台湾工作办公室",
    "中央党校（国家行政学院）", "中央党史和文献研究院", "中央社会主义学院",
]
# 中央直属事业单位（媒体等）
CPC_DIRECT_MEDIA = [
    ("人民日报社", "https://www.people.com.cn/", "中央直属事业单位（媒体）"),
    ("求是杂志社", "https://www.qstheory.cn/", "中央直属事业单位（媒体）"),
    ("光明日报社", "https://www.gmw.cn/", "中央直属事业单位（媒体）"),
    ("经济日报社", "https://www.ce.cn/", "中央直属事业单位（媒体）"),
]
# 全国人大专门委员会
NPC_COMMITTEES = ["民族委员会", "宪法和法律委员会", "监察和司法委员会", "财政经济委员会",
                  "教育科学文化卫生委员会", "外事委员会", "华侨委员会",
                  "环境与资源保护委员会", "农业与农村委员会", "社会建设委员会"]
# 全国政协专门委员会
CPPCC_COMMITTEES = ["提案委员会", "经济委员会", "农业和农村委员会", "人口资源环境委员会",
                    "教育科学文化体育委员会", "社会和法制委员会", "民族和宗教委员会",
                    "港澳台侨委员会", "外事委员会", "文化文史和学习委员会"]
# 最高人民法院内设机构（列名）
SPC_DEPTS = ["办公厅", "政治部", "立案庭", "刑事审判第一庭", "刑事审判第二庭", "刑事审判第三庭",
             "刑事审判第四庭", "刑事审判第五庭", "民事审判第一庭", "民事审判第二庭",
             "民事审判第三庭", "民事审判第四庭", "环境资源审判庭", "行政审判庭",
             "审判监督庭", "赔偿委员会办公室", "执行局", "研究室", "审判管理办公室",
             "国际合作局", "司法行政装备管理局", "六个巡回法庭"]
# 中央纪委国家监委内设机构（列名，公开口径）
NCC_DEPTS = ["办公厅", "组织部", "宣传部", "研究室", "法规室", "党风政风监督室", "信访室",
             "中央巡视工作领导小组办公室", "案件监督管理室", "监督检查室", "审查调查室",
             "国际合作局", "机关事务管理局", "机关党委", "离退休干部局"]
# 最高人民检察院内设机构（列名）
SPP_DEPTS = ["办公厅", "政治部", "第一检察厅", "第二检察厅", "第三检察厅", "第四检察厅",
             "第五检察厅", "第六检察厅", "第七检察厅", "第八检察厅", "第九检察厅",
             "第十检察厅", "法律政策研究室", "案件管理办公室", "国际合作局",
             "检务督察局", "计划财务装备局"]

# 直属海关所在省（垂直管理系统）
CUSTOMS_PROV = {
    "北京海关": "北京市", "天津海关": "天津市", "石家庄海关": "河北省", "太原海关": "山西省",
    "呼和浩特海关": "内蒙古自治区", "满洲里海关": "内蒙古自治区", "大连海关": "辽宁省", "沈阳海关": "辽宁省",
    "长春海关": "吉林省", "哈尔滨海关": "黑龙江省", "上海海关": "上海市", "南京海关": "江苏省",
    "杭州海关": "浙江省", "宁波海关": "浙江省", "合肥海关": "安徽省", "福州海关": "福建省",
    "厦门海关": "福建省", "南昌海关": "江西省", "青岛海关": "山东省", "济南海关": "山东省",
    "郑州海关": "河南省", "武汉海关": "湖北省", "长沙海关": "湖南省", "广州海关": "广东省",
    "黄埔海关": "广东省", "深圳海关": "广东省", "拱北海关": "广东省", "汕头海关": "广东省",
    "江门海关": "广东省", "湛江海关": "广东省", "南宁海关": "广西壮族自治区", "海口海关": "海南省",
    "重庆海关": "重庆市", "成都海关": "四川省", "贵阳海关": "贵州省", "昆明海关": "云南省",
    "拉萨海关": "西藏自治区", "西安海关": "陕西省", "兰州海关": "甘肃省", "西宁海关": "青海省",
    "银川海关": "宁夏回族自治区", "乌鲁木齐海关": "新疆维吾尔自治区",
}

# 市县并列机关列名（党委领导下一府一委两院+人大政协）
CITY_PARALLEL_NAMES = ["市委", "市人大", "市政协", "市监委", "市中级人民法院", "市人民检察院"]
COUNTY_PARALLEL_NAMES = ["县委", "县人大", "县政协", "县监委", "县人民法院", "县人民检察院"]


def load(fn):
    return [json.loads(l) for l in open(fn, encoding="utf-8")]


def n(name, level, kind, cat, prov="", parent="", code="", portal="", xxgk="", src="", note="", kids=None):
    d = {"n": name, "l": level, "k": kind, "c": cat}
    if prov: d["p1"] = prov
    if parent: d["p2"] = parent
    if code: d["cd"] = code
    if portal: d["u"] = portal
    if xxgk: d["x"] = xxgk
    if src: d["s"] = src
    if note: d["m"] = note
    if kids: d["ks"] = kids
    return d


def prov_short(full):
    s = re.sub(r"(省|市|特别行政区)$", "", full)
    return re.sub(r"(壮族|回族|维吾尔)?自治区$", "", s)


def cc_row(cc, code, key):
    for r in cc:
        if r["code"] == code:
            return r.get(key, "")
    return ""


def main():
    central = load("central.jsonl")
    provs = load("province.jsonl")
    depts = load("prov_depts.jsonl")
    cc = load("city_county_final.jsonl")
    divs = json.load(open("divisions.json", encoding="utf-8"))
    parallel = load("prov_parallel.jsonl") if __import__("os").path.exists("prov_parallel.jsonl") else []
    customs = json.load(open("customs_cities.json", encoding="utf-8")) if __import__("os").path.exists("customs_cities.json") else []

    # ---- 中央（党中央 + 国务院 + 并列机关，合并为一个板块） ----
    cen_kids = []
    # 中共中央
    party_kids = [
        n(f"中央直属机构（{len(CPC_DIRECT_AGENCIES)}）", "中央", "分组", "中央直属机构",
          kids=[n(x, "中央", "党委机构", "中央直属机构",
                  note="党委工作机关，多数无独立公开门户，列名参考")
                for x in CPC_DIRECT_AGENCIES]),
        n(f"中央直属事业单位（媒体等 {len(CPC_DIRECT_MEDIA)}）", "中央", "分组", "中央直属事业单位",
          kids=[n(nm, "中央", "党委机构", cat, portal=url)
                for nm, url, cat in CPC_DIRECT_MEDIA]),
    ]
    cen_kids.append(n("中共中央（党中央）", "中央", "党委领导机关", "中共中央",
                      note="党中央领导机关，无独立公开门户",
                      kids=party_kids))
    # 国务院（部委按类别分组挂国务院下）
    gw_sub = []
    cat_order = ["国务院组成部门", "国务院直属特设机构", "国务院直属机构", "国务院办事机构",
                 "国务院直属事业单位", "部委管理的国家局", "加挂牌子"]
    for cat in cat_order:
        items = [r for r in central if r.get("category") == cat]
        if not items:
            continue
        gw_sub.append(
            n(f"{cat}（{len(items)}）", "中央", "分组", cat,
              kids=[n(r["name"], "中央", "部门", r.get("category", ""), prov="",
                      portal=r.get("portal_url", ""), xxgk=r.get("xxgk_url", ""),
                      src=r.get("xxgk_src", ""),
                      note=("无独立门户网站" if r["name"] == "国务院研究室" else ""),
                      kids=(
                          [n(f"直属海关（{len(customs)}，垂直管理）", "省", "分组", "海关",
                             kids=[n(c["name"], "省", "海关", "直属海关（垂直管理）",
                                     prov=CUSTOMS_PROV.get(c["name"], ""), portal=c["portal"],
                                     note="海关总署垂直管理，厅级单位驻地方")
                                   for c in customs])]
                          if (r["name"] == "海关总署" and customs) else None))
                    for r in items]))
    cen_kids.append(n("国务院（中央人民政府）", "中央", "人民政府", "国务院",
                      portal="https://www.gov.cn/", xxgk="https://www.gov.cn/zhengce/xxgk/",
                      src="导航链接", kids=gw_sub))
    # 全国人大（与国务院并列）
    cen_kids.append(n("全国人民代表大会（全国人大常委会）", "中央", "并列机关", "全国人大",
                      portal="https://www.npc.gov.cn/",
                      note="与国务院并列，党委领导",
                      kids=[n(f"专门委员会（{len(NPC_COMMITTEES)}）", "中央", "分组", "全国人大专门委员会",
                             kids=[n(x, "中央", "并列机关", "全国人大专门委员会", note="列名参考")
                                   for x in NPC_COMMITTEES])]))
    # 全国政协（与国务院并列）
    cen_kids.append(n("中国人民政治协商会议全国委员会", "中央", "并列机关", "全国政协",
                      portal="https://www.cppcc.gov.cn/",
                      note="与国务院并列，党委领导",
                      kids=[n(f"专门委员会（{len(CPPCC_COMMITTEES)}）", "中央", "分组", "全国政协专门委员会",
                             kids=[n(x, "中央", "并列机关", "全国政协专门委员会", note="列名参考")
                                   for x in CPPCC_COMMITTEES])]))
    # 国家监察委（与国务院并列）
    cen_kids.append(n("国家监察委员会（与中央纪委合署办公）", "中央", "并列机关", "国家监委",
                      portal="https://www.ccdi.gov.cn/", note="与国务院并列，党委领导",
                      kids=[n(f"内设机构（{len(NCC_DEPTS)}）", "中央", "分组", "国家监委内设机构",
                             kids=[n(x, "中央", "并列机关", "国家监委内设机构", note="列名参考")
                                   for x in NCC_DEPTS])]))
    # 最高人民法院（与国务院并列，内设机构展开）
    cen_kids.append(n("最高人民法院", "中央", "并列机关", "最高人民法院",
                      portal="https://www.court.gov.cn/", note="与国务院并列，党委领导",
                      kids=[n(f"内设机构（{len(SPC_DEPTS)}）", "中央", "分组", "最高法内设机构",
                             kids=[n(x, "中央", "并列机关", "最高法内设机构", note="列名参考")
                                   for x in SPC_DEPTS])]))
    # 最高人民检察院（与国务院并列，内设机构展开）
    cen_kids.append(n("最高人民检察院", "中央", "并列机关", "最高人民检察院",
                      portal="https://www.spp.gov.cn/", note="与国务院并列，党委领导",
                      kids=[n(f"内设机构（{len(SPP_DEPTS)}）", "中央", "分组", "最高检内设机构",
                             kids=[n(x, "中央", "并列机关", "最高检内设机构", note="列名参考")
                                   for x in SPP_DEPTS])]))
    root_kids = [n("中央（党中央、国务院及并列机关）", "中央", "分组", "", kids=cen_kids)]
    # ---- 省级 ----
    full_name = {prov_short(d["name"]): d["name"] for d in divs if d["level"] in ("省", "特别行政区")}
    prov_nodes = []
    bingtuan_cities = {r["code"]: r for r in cc
                       if r["level"] == "县" and r["province"] == "新疆维吾尔自治区"
                       and r["code"].startswith("6590")}

    for r in provs:
        if r["name"] == "新疆生产建设兵团":
            continue
        pshort = r["name"]
        pname = full_name.get(pshort, pshort)
        kids = []
        # 并列机关（省委/省人大/省政协/省监委/省高院/省检察院）
        par_rows = [r for r in parallel if r["province"] == pshort]
        par_nodes = [n("省委（党委领导机关）", "省", "并列机关", "省委",
                       prov=pname, note="党委机关，多数无独立公开门户，列名参考")]
        for cat, cname in (("人大", "省人大"), ("政协", "省政协"), ("监委", "省监委"),
                           ("法院", "省高级人民法院"), ("检察院", "省人民检察院")):
            row = None
            for r in par_rows:
                nm = r["name"]
                if cat == "监委" and ("监察委" in nm or "纪委" in nm):
                    row = r; break
                if cat == "法院" and "法院" in nm:
                    row = r; break
                if cat == "检察院" and ("检察" in nm and "监察" not in nm):
                    row = r; break
                if cat in ("人大", "政协") and cat in nm:
                    row = r; break
            if row:
                par_nodes.append(n(cname, "省", "并列机关", f"省{cat}",
                                   prov=pname, portal=row.get("portal_url", ""),
                                   note="与省人民政府并列，党委领导"))
            else:
                par_nodes.append(n(cname, "省", "并列机关", f"省{cat}",
                                   prov=pname, note="并列机关，门户待补"))
        kids.append(n(f"并列机关（{len(par_nodes)}）", "省", "分组", "并列机关", kids=par_nodes))
        # 厅局
        dept_list = [d for d in depts if d["province"] == pshort]
        if dept_list:
            kids.append(n(f"省政府部门（{len(dept_list)}）", "省", "分组", "厅局",
                          kids=[n(d["name"], "省", "部门", d.get("category", ""),
                                  prov=pname, portal=d.get("portal_url", ""),
                                  xxgk=d.get("xxgk_url", ""), src=d.get("xxgk_src", ""))
                                for d in sorted(dept_list, key=lambda x: (x.get("order", 999), x["name"]))]))
        # 市州（含其区县）
        cities = [d for d in divs if d["level"] == "市" and d["province"] == pname]
        for c in cities:
            counties = [r for r in cc if r["level"] == "县" and r["parent"] == c["name"]
                        and r["name"] not in ("市辖区", "县")]
            city_kids = [n(f"并列机关（{len(CITY_PARALLEL_NAMES)}）", "市", "分组", "并列机关",
                              prov=pname, parent=c["name"],
                              kids=[n(x, "市", "并列机关", "市委/市人大/市政协/市监委/市中院/市检察院",
                                      prov=pname, parent=c["name"],
                                      note="与市人民政府并列，党委领导，门户待补")
                                    for x in CITY_PARALLEL_NAMES])]
            city_kids += [n(r["name"], "县", "人民政府", "县级人民政府", prov=pname,
                                  parent=c["name"], code=r["code"],
                                  portal=r.get("portal_url", ""), xxgk=r.get("xxgk_url", ""),
                                  src=r.get("xxgk_src", ""),
                                  note=("功能区/管委会（非民政部区划序列，据政府门户实存）" if PSEUDO.search(r["name"]) else ""),
                                  kids=None if PSEUDO.search(r["name"]) else
                                      [n(f"并列机关（{len(COUNTY_PARALLEL_NAMES)}）", "县", "分组", "并列机关",
                                         prov=pname, parent=r["name"],
                                         kids=[n(x, "县", "并列机关", "县委/县人大/县政协/县监委/县法院/县检察院",
                                                 prov=pname, parent=r["name"],
                                                 note="与县人民政府并列，党委领导，门户待补")
                                               for x in COUNTY_PARALLEL_NAMES])])
                                for r in sorted(counties, key=lambda x: x["code"])]
            kids.append(n(c["name"], "市", "人民政府", "地级市人民政府", prov=pname,
                          code=c["code"], portal=cc_row(cc, c["code"], "portal_url"),
                          xxgk=cc_row(cc, c["code"], "xxgk_url"), src=cc_row(cc, c["code"], "xxgk_src"),
                          kids=city_kids))
        # 直辖县级单位（省直辖县级市/县；直辖市 → 市辖区/县 分列；新疆兵团市除外）
        direct_all = [r for r in cc if r["level"] == "县" and r["province"] == pname
                      and (r["parent"] == pname or r["parent"] in ("市辖区", "县"))
                      and r["name"] not in ("市辖区", "县")
                      and not r["code"].startswith("6590")]
        gongneng = [r for r in direct_all if PSEUDO.search(r["name"])]
        direct = [r for r in direct_all if not PSEUDO.search(r["name"])]
        if gongneng:
            kids.append(n(f"功能区（{len(gongneng)}，非民政部区划序列）", "县", "分组", "功能区",
                          kids=[n(r["name"], "县", "功能区", "功能区/管委会（非民政部区划序列，据政府门户实存）",
                                  prov=pname, parent=pname, code=r["code"],
                                  portal=r.get("portal_url", ""), xxgk=r.get("xxgk_url", ""),
                                  src=r.get("xxgk_src", ""))
                                for r in sorted(gongneng, key=lambda x: x["code"])]))
        if direct:
            if pname in ("北京市", "天津市", "上海市", "重庆市"):
                qu = [r for r in direct if not re.search(r"(自治县|县)$", r["name"])]
                xian = [r for r in direct if re.search(r"(自治县|县)$", r["name"])]
                if qu:
                    kids.append(n(f"市辖区（{len(qu)}，地级行政区划）", "地级区", "分组", "直辖市辖区",
                                  kids=[n(r["name"], "地级区", "人民政府", "市辖区（地级行政区划）",
                                          prov=pname, parent=pname, code=r["code"],
                                          portal=r.get("portal_url", ""), xxgk=r.get("xxgk_url", ""),
                                          src=r.get("xxgk_src", ""),
                                          kids=[n(f"并列机关（{len(COUNTY_PARALLEL_NAMES)}）", "地级区", "分组", "并列机关",
                                                  prov=pname, parent=r["name"],
                                                  kids=[n(x, "地级区", "并列机关", "区委/区人大/区政协/区监委/区法院/区检察院",
                                                          prov=pname, parent=r["name"],
                                                          note="与区人民政府并列，党委领导，门户待补")
                                                        for x in COUNTY_PARALLEL_NAMES])])
                                        for r in sorted(qu, key=lambda x: x["code"])]))
                if xian:
                    kids.append(n(f"县（{len(xian)}，县级行政区划）", "县", "分组", "直辖市辖县",
                                  kids=[n(r["name"], "县", "人民政府", "直辖市辖县（县级行政区划）",
                                          prov=pname, parent=pname, code=r["code"],
                                          portal=r.get("portal_url", ""), xxgk=r.get("xxgk_url", ""),
                                          src=r.get("xxgk_src", ""),
                                          kids=[n(f"并列机关（{len(COUNTY_PARALLEL_NAMES)}）", "县", "分组", "并列机关",
                                                  prov=pname, parent=r["name"],
                                                  kids=[n(x, "县", "并列机关", "县委/县人大/县政协/县监委/县法院/县检察院",
                                                          prov=pname, parent=r["name"],
                                                          note="与县人民政府并列，党委领导，门户待补")
                                                        for x in COUNTY_PARALLEL_NAMES])])
                                        for r in sorted(xian, key=lambda x: x["code"])]))
            else:
                kids.append(n(f"省直辖县级行政单位（{len(direct)}）", "县", "分组", "省直辖县级",
                              kids=[n(r["name"], "县", "人民政府", "省直辖县级市/县/林区",
                                      prov=pname, parent=pname, code=r["code"],
                                      portal=r.get("portal_url", ""), xxgk=r.get("xxgk_url", ""),
                                      src=r.get("xxgk_src", ""),
                                      kids=[n(f"并列机关（{len(COUNTY_PARALLEL_NAMES)}）", "县", "分组", "并列机关",
                                              prov=pname, parent=r["name"],
                                              kids=[n(x, "县", "并列机关", "县委/县人大/县政协/县监委/县法院/县检察院",
                                                      prov=pname, parent=r["name"],
                                                      note="与县（市）人民政府并列，党委领导，门户待补")
                                                    for x in COUNTY_PARALLEL_NAMES])])
                                    for r in sorted(direct, key=lambda x: x["code"])]))
        prov_code = next((d["code"] for d in divs if d["level"] in ("省", "特别行政区") and d["name"] == pname), "")
        prov_nodes.append(n(pname, "省", "人民政府", r.get("category", "省级人民政府"),
                            code=prov_code, portal=r.get("portal_url", ""), xxgk=r.get("xxgk_url", ""),
                            src=r.get("xxgk_src", ""), kids=kids))

    # 兵团（含兵团直辖县级市）
    bingtuan = next((r for r in provs if r["name"] == "新疆生产建设兵团"), None)
    if bingtuan:
        kids = [n(f"兵团直辖县级市（{len(bingtuan_cities)}，自治区直辖）", "县", "分组", "兵团市",
                  kids=[n(r["name"], "县", "人民政府", "兵团直辖县级市（自治区直辖县级市）",
                          prov="新疆维吾尔自治区", parent="新疆生产建设兵团", code=r["code"],
                          portal=r.get("portal_url", ""), xxgk=r.get("xxgk_url", ""),
                          src=r.get("xxgk_src", ""),
                          kids=[n(f"并列机关（{len(CITY_PARALLEL_NAMES)}）", "县", "分组", "并列机关",
                                  prov="新疆维吾尔自治区", parent=r["name"],
                                  kids=[n(x, "县", "并列机关", "市委/市人大/市政协/市监委/市法院/市检察院",
                                          prov="新疆维吾尔自治区", parent=r["name"],
                                          note="与市人民政府并列，党委领导，门户待补")
                                        for x in CITY_PARALLEL_NAMES])])
                        for r in sorted(bingtuan_cities.values(), key=lambda x: x["code"])])]
        prov_nodes.append(n("新疆生产建设兵团", "省", "人民政府", "省级（兵团）",
                            portal=bingtuan.get("portal_url", ""), xxgk=bingtuan.get("xxgk_url", ""),
                            src=bingtuan.get("xxgk_src", ""), kids=kids))

    root_kids.append(n("省级（31省、直辖市、自治区＋兵团）", "省", "分组", "", kids=prov_nodes))

    # ---- 港澳台（独立顶层分组） ----
    gat_kids = [
        n("香港特别行政区", "特别行政区", "人民政府", "特别行政区政府",
          portal="https://www.gov.hk/",
          note="非内地政府信息公开体系，另行公开制度（公开资料守则）",
          kids=[n(f"{d}（区议会分区）", "港澳台", "区划", "地区（区议会分区）",
                  note="非内地政府信息公开体系，仅列名参考") for d in HK_DISTRICTS]),
        n("澳门特别行政区", "特别行政区", "人民政府", "特别行政区政府",
          portal="https://www.gov.mo/",
          note="非内地政府信息公开体系，另行公开制度",
          kids=[n(f"{d}（堂区）", "港澳台", "区划", "堂区",
                  note="非内地政府信息公开体系，仅列名参考") for d in MO_PARISHES]),
        n("台湾省", "省", "人民政府", "省级人民政府",
          note="无内地政府门户，台湾地区县市政府门户仅列参考（内地网络不可达）",
          kids=[n(c["name"], "港澳台", "区划", "台湾地区县市政府",
                  portal=c["portal"],
                  note=c.get("note") or "台湾地区县市政府门户，内地网络一般无法访问，列名参考")
                for c in (json.load(open("taiwan_counties.json", encoding="utf-8"))
                          if __import__("os").path.exists("taiwan_counties.json") else [])]),
    ]
    root_kids.append(n("港澳台（特别行政区与台湾）", "港澳台", "分组", "", kids=gat_kids))

    tree = n("中国政府信息公开体系", "根", "分组", "", kids=root_kids)
    json.dump(tree, open("tree.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    import os
    print("tree.json", os.path.getsize("tree.json"), "bytes")


if __name__ == "__main__":
    main()
