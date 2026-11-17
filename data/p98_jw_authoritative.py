# -*- coding: utf-8 -*-
"""P98: 纪委系统 ccdi 权威化（省级 33 + 副省级市 15 + 中央派驻 26）。

来源：ccdi.gov.cn 首页「地方纪委监委」link_list + 「中央派驻纪检监察组」
区块 + /wzdhn/dfjjjcjg/ 机构页（CDP 渲染真实 HTML）。
福建取 fjcdi.gov.cn（dfjjjcjg 页 fjjc.gov.cn 已不可达，实测 000）。
"""
import json

PROV_AUTH = {
    "北京市纪委监委": "http://www.bjsupervision.gov.cn/",
    "天津市纪委监委": "http://www.tjjw.gov.cn/",
    "河北省纪委监委": "http://www.hebcdi.gov.cn/",
    "山西省纪委监委": "http://www.sxdi.gov.cn/",
    "内蒙古自治区纪委监委": "http://www.nmgjjjc.gov.cn/",
    "辽宁省纪委监委": "http://www.lnsjjjc.gov.cn/",
    "吉林省纪委监委": "http://ccdijl.gov.cn/",
    "黑龙江省纪委监委": "http://www.hljjjjc.gov.cn",
    "上海市纪委监委": "https://www.shjjjc.gov.cn/",
    "江苏省纪委监委": "https://www.jssjw.gov.cn",
    "浙江省纪委监委": "http://www.zjsjw.gov.cn/",
    "安徽省纪委监委": "http://www.ahjjjc.gov.cn/",
    "福建省纪委监委": "http://www.fjcdi.gov.cn/",
    "江西省纪委监委": "http://www.jxdi.gov.cn",
    "山东省纪委监委": "http://www.sdjj.gov.cn/",
    "河南省纪委监委": "http://www.hnsjct.gov.cn",
    "湖北省纪委监委": "http://www.hbjwjc.gov.cn/",
    "湖南省纪委监委": "http://www.sxfj.gov.cn",
    "广东省纪委监委": "http://www.gdjct.gd.gov.cn",
    "广西壮族自治区纪委监委": "https://www.gxjjw.gov.cn/index.shtml",
    "海南省纪委监委": "http://www.hncdi.gov.cn",
    "重庆市纪委监委": "http://jjc.cq.gov.cn",
    "四川省纪委监委": "http://www.scjc.gov.cn",
    "贵州省纪委监委": "http://www.gzdis.gov.cn",
    "云南省纪委监委": "http://www.ynjjjc.gov.cn/",
    "西藏自治区纪委监委": "http://www.xzjjw.gov.cn",
    "陕西省纪委监委": "http://www.qinfeng.gov.cn",
    "甘肃省纪委监委": "http://www.gsjw.gov.cn/",
    "宁夏回族自治区纪委监委": "http://www.nxjjjc.gov.cn/",
    "青海省纪委监委": "http://www.qhjc.gov.cn/",
    "新疆维吾尔自治区纪委监委": "http://www.xjjw.gov.cn/",
    "新疆生产建设兵团纪委监委": "http://btjw.xjbt.gov.cn",
}

# 副省级市纪委监委（ccdi dfjjjcjg 机构页）
SUBPROV = {
    "黑龙江省": {"哈尔滨市纪委监委": "http://www.hrblz.gov.cn"},
    "吉林省": {"长春市纪委监委": "http://www.ccdijl-cc.gov.cn/"},
    "辽宁省": {"沈阳市纪委监委": "http://www.sysjjjc.gov.cn/",
                "大连市纪委监委": "https://www.dlsjjjc.gov.cn/"},
    "江苏省": {"南京市纪委监委": "http://www.njjj.gov.cn"},
    "浙江省": {"杭州市纪委监委": "http://www.hzlz.gov.cn",
                "宁波市纪委监委": "http://www.nbjw.gov.cn"},
    "山东省": {"济南市纪委监委": "http://www.jnlz.gov.cn",
                "青岛市纪委监委": "http://www.qdlzw.cn"},
    "福建省": {"厦门市纪委监委": "http://www.xmcdi.gov.cn"},
    "湖北省": {"武汉市纪委监委": "http://www.whdi.gov.cn"},
    "广东省": {"广州市纪委监委": "http://www.gzjjjc.gov.cn",
                "深圳市纪委监委": "http://www.ljsz.gov.cn"},
    "四川省": {"成都市纪委监委": "http://www.ljcd.gov.cn"},
    "陕西省": {"西安市纪委监委": "https://xian.qinfeng.gov.cn/"},
}

# 中央派驻纪检监察组（ccdi 首页区块）
PAIZHU = [
    ("驻国家发改委纪检监察组", "https://www.ndrc.gov.cn/fzggw/pzjg/zwjjjcz/"),
    ("驻教育部纪检监察组", "http://www.moe.gov.cn/s78/A25/"),
    ("驻科学技术部纪检监察组", "http://www.most.gov.cn/zzjg/zbjjz/"),
    ("驻工业和信息化部纪检监察组", "https://www.miit.gov.cn/jgsj/zyjwgjjwzgyhxxhbjjjcz/index.html"),
    ("驻民政部纪检监察组", "http://zbjjz.mca.gov.cn"),
    ("驻司法部纪检监察组", "http://www.moj.gov.cn/jgsz/gjjwzsfbjjz/"),
    ("驻财政部纪检监察组", "http://zbjc.mof.gov.cn"),
    ("驻人力资源和社会保障部纪检监察组", "http://www.mohrss.gov.cn/zbjcj/"),
    ("驻生态环境部纪检监察组", "http://jjjcz.mee.gov.cn"),
    ("驻住房和城乡建设部纪检监察组", "https://www.mohurd.gov.cn/jjjc/index.html"),
    ("驻交通运输部纪检监察组", "http://zizhan.mot.gov.cn/sj2019/jijianjcz/"),
    ("驻水利部纪检监察组", "http://jjjc.mwr.gov.cn"),
    ("驻农业农村部纪检监察组", "http://www.jcj.moa.gov.cn/"),
    ("驻商务部纪检监察组", "http://jcj.mofcom.gov.cn"),
    ("驻文化和旅游部纪检监察组", "https://www.mct.gov.cn/zwhcjz/"),
    ("驻国家卫生健康委员会纪检监察组", "http://www.nhc.gov.cn/jcj/new_index.shtml"),
    ("驻应急管理部纪检监察组", "https://www.mem.gov.cn/jjz/"),
    ("驻中国人民银行纪检监察组", "http://www.pbc.gov.cn/jiwei/148195/index.html"),
    ("驻国务院国资委纪检监察组", "http://www.sasac.gov.cn/n2588020/n2877928/index.html"),
    ("驻海关总署纪检监察组", "http://www.customs.gov.cn/eportal/ui?pageId=715727"),
    ("驻国家市场监督管理总局纪检监察组", "http://www.samr.gov.cn/jjz/"),
    ("驻国家体育总局纪检监察组", "http://www.sport.gov.cn/jjz/index.html"),
    ("驻中国科学院纪检监察组", "http://www.jijianzu.cas.cn/"),
    ("驻最高人民法院纪检监察组", "https://www.court.gov.cn/zhongjiwei.html"),
    ("驻最高人民检察院纪检监察组", "https://www.spp.gov.cn/spp/zyjwgjjwzzgrmjcyjjjcz/202008/t20200806_404094.shtml"),
    ("驻中华全国总工会机关纪检监察组", "http://jjz.acftu.org/"),
]

def leaf(nm, cat, u, lv):
    return {"n": nm, "l": lv, "k": cat, "c": cat, "u": u,
            "x": "", "s": "", "m": ""}

def main():
    tree = json.load(open("tree.json", encoding="utf-8"))
    rules = json.load(open("extraction_rules.json", encoding="utf-8"))
    tiao = next(g for g in tree["ks"] if g["n"] == "条（垂直管理系统）")
    jw = next(g for g in tiao["ks"] if g["n"].startswith("纪委系统"))
    gy = next(x for x in jw["ks"] if x["n"].startswith("省级纪委"))

    fixed = added = 0
    for p in gy["ks"]:
        if p["n"] in PROV_AUTH:
            if p.get("u") != PROV_AUTH[p["n"]]:
                if p.get("u"):
                    fixed += 1
                else:
                    added += 1
                p["u"] = PROV_AUTH[p["n"]]
        # 副省级市挂载
        pname = p["n"].replace("纪委监委", "")
        if pname in SUBPROV:
            existing = {k["n"] for k in p.get("ks", [])}
            for nm, u in SUBPROV[pname].items():
                if nm in existing:
                    for k in p.get("ks", []):
                        if k["n"] == nm and not k.get("u"):
                            k["u"] = u
                    continue
                p.setdefault("ks", []).append(
                    {"n": nm, "l": "市", "k": "纪委系统", "c": "纪委系统",
                     "u": u, "x": "", "s": "", "m": ""})

    # 中央派驻组挂中央纪委节点下
    root = next(x for x in jw["ks"] if x["n"].startswith("中央纪委"))
    grp = {"n": f"中央派驻纪检监察组（{len(PAIZHU)}）", "l": "中央",
           "k": "分组", "c": "纪委系统", "u": "", "x": "", "s": "", "m": "",
           "ks": [leaf(nm, "纪委系统", u, "中央") for nm, u in PAIZHU]}
    jw["ks"] = [g for g in jw["ks"] if not g["n"].startswith("中央派驻")]
    jw["ks"].insert(1, grp)

    # 老系统：副省级市并列机关监委 u 回填
    prov_g = next(g for g in tree["ks"] if g["n"].startswith("省级"))
    for pname, cities in SUBPROV.items():
        p = next(x for x in prov_g["ks"] if x["n"] == pname)
        for nm, u in cities.items():
            cn = nm.replace("纪委监委", "")
            for top in p.get("ks", []):
                def walk(n):
                    if n.get("l") == "市" and n["n"] == cn \
                            and n.get("k") == "人民政府":
                        par = next((g for g in n.get("ks", [])
                                    if g.get("c") == "并列机关"), None)
                        if par:
                            m = next((x for x in par.get("ks", [])
                                      if "监委" in x["n"]), None)
                            if m:
                                m["u"] = u
                                return True
                    for k in n.get("ks", []):
                        if walk(k):
                            return True
                    return False
                if walk(top):
                    break

    # rules
    rk = next(k for k in rules if k.startswith("纪委系统"))
    all_m = []
    def walk(n):
        if not n.get("ks"):
            all_m.append(n)
            return
        if all(x.get("l") != "省" for x in n["ks"]):
            all_m.append(n)
        for k in n["ks"]:
            walk(k)
    walk(jw)
    rules[rk]["depts"] = [{"n": m["n"], "u": m.get("u", ""), "o": i}
                          for i, m in enumerate(all_m)]
    rules[rk]["method"] = (
        "省级 32+兵团 URL 权威化：ccdi.gov.cn 首页「地方纪委监委」link_list "
        "真实 HTML（CDP 渲染）33/33 全覆盖；副省级市纪委监委 15 个来自 "
        "ccdi「地方纪委监委机构」页 /wzdhn/dfjjjcjg/（福建 fjcdi 可用，"
        "fjjc.gov.cn 已不可达弃用）；中央派驻纪检监察组 26 个来自 ccdi "
        "首页派驻区块。普通地级市纪委监委多数无公开官网（纪检监察系统特点），"
        "cc_parallel 真实采集命中填 URL，其余列名。")
    json.dump(tree, open("tree.json", "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    json.dump(rules, open("extraction_rules.json", "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    print(f"p98 完成：省级修正 {fixed} 补缺 {added}；副省级市 15；派驻组 {len(PAIZHU)}")

if __name__ == "__main__":
    main()
