# -*- coding: utf-8 -*-
"""P94: 政协市级数据汇总 → rd_zx.jsonl。

来源（全部省政协官网真实 HTML 提取，逐省探测）：
- 北京 bjzx.gov.cn「各区政协」页（11/16 区）
- 陕西 sxzx.gov.cn select「政协X市委员会」（9/10，咸阳→市政府门户=占位列名）
- 吉林 jlzx.gov.cn 渲染 select（7/9）
- 甘肃 gszx.gov.cn select（9/14；金昌/武威/庆阳/定西/甘南指向门户=占位列名）
- 湖北 hbzx.gov.cn 区块（16/17，缺天门）
- 福建 fjzx.gov.cn 区块（8/9，缺宁德）
- 广西 gxzx.gov.cn 区块（4/14）
- 青海 qhszx.gov.cn 区块（3/8）
- 广东 gdszx.gov.cn 区块（4/21）
- 重庆 cqzx.gov.cn 区块（4/38）
- 天津 tjszx.gov.cn 首页（2/16：河北区/南开区）
- 江西 jxzx.jxnews.com.cn 区块（2/11）
- 其余 19 省：官网首页及「市县政协」栏目页均无市级政协官网导航 → 全列名
"""
import json
import re

LINKED = {
    "北京市": {
        "西城区": "http://zhengxie.bjxch.gov.cn/index.html",
        "朝阳区": "http://chyzx.bjchy.gov.cn/",
        "海淀区": "http://hdzx.bjhd.gov.cn/",
        "丰台区": "http://zhengxie.bjft.gov.cn/",
        "门头沟区": "http://zx.bjmtg.gov.cn",
        "房山区": "http://zx.bjfsh.gov.cn/",
        "通州区": "http://zhengxie.bjtzh.gov.cn/",
        "顺义区": "http://zhengxie.bjshy.gov.cn/",
        "大兴区": "http://zhengxie.bjdx.gov.cn/",
        "怀柔区": "http://www.hrzx.gov.cn/",
        "延庆区": "http://zhengxie.bjyq.gov.cn/",
    },
    "陕西省": {
        "西安市": "https://www.xa-cppcc.gov.cn/",
        "宝鸡市": "http://www.baojizx.cn/",
        "铜川市": "http://www.sxtczx.gov.cn/",
        "渭南市": "http://www.wnszx.gov.cn/",
        "延安市": "http://www.yazx.gov.cn/",
        "榆林市": "https://www.ylzx.gov.cn/",
        "汉中市": "https://zx.hanzhong.gov.cn/",
        "安康市": "https://zx.ankang.gov.cn/",
        "商洛市": "http://www.slzxw.gov.cn/",
    },
    "吉林省": {
        "长春市": "http://ccszx.changchun.gov.cn/",
        "吉林市": "http://www.jlszx.gov.cn",
        "四平市": "http://www.sipingszx.gov.cn/",
        "通化市": "http://thszhengxie.gov.cn",
        "白山市": "http://www.bsszx.gov.cn/",
        "松原市": "http://www.songyuanzx.gov.cn/",
        "延边朝鲜族自治州": "http://ybzx.gov.cn/",
    },
    "甘肃省": {
        "兰州市": "http://www.gslzzx.gov.cn/",
        "嘉峪关市": "http://www.jygzhx.cn/",
        "酒泉市": "http://zx.jiuquan.gov.cn/",
        "张掖市": "http://www.zhangyezx.gov.cn/",
        "白银市": "http://www.byszx.cn/",
        "天水市": "http://www.tsszx.gov.cn/",
        "平凉市": "http://zx.pingliang.gov.cn/",
        "陇南市": "http://www.lnszx.gov.cn/",
        "临夏回族自治州": "http://www.lxzzx.gov.cn",
    },
    "湖北省": {
        "武汉市": "https://www.whzx.gov.cn/",
        "黄石市": "http://www.hsszxw.gov.cn",
        "十堰市": "http://cppcc.shiyan.gov.cn",
        "襄阳市": "http://www.xyszx.gov.cn/",
        "宜昌市": "http://www.ycszx.gov.cn/",
        "荆州市": "http://www.hbjzszx.gov.cn",
        "荆门市": "http://www.jmzx.gov.cn/",
        "鄂州市": "http://www.ezzx.gov.cn/",
        "孝感市": "http://www.xgszx.gov.cn/",
        "黄冈市": "http://www.hgzx.gov.cn/",
        "咸宁市": "http://www.hbxnzx.gov.cn/",
        "随州市": "http://www.hbszzx.gov.cn/",
        "恩施土家族苗族自治州": "http://www.eszzx.gov.cn/",
        "仙桃市": "http://xtzx.cnxiantao.com",
        "潜江市": "http://www.hbqjzx.gov.cn/",
        "神农架林区": "http://www.snjzxb.com",
    },
    "福建省": {
        "福州市": "http://zx.fuzhou.gov.cn/",
        "厦门市": "http://www.zxxm.gov.cn/",
        "漳州市": "http://www.zzszx.gov.cn/",
        "泉州市": "http://www.qzzx.gov.cn/",
        "三明市": "http://www.smszx.gov.cn/",
        "莆田市": "http://www.ptszx.cn/",
        "南平市": "http://zx.np.gov.cn/",
        "龙岩市": "http://zx.longyan.gov.cn/",
    },
    "广西壮族自治区": {
        "柳州市": "http://lzzx.liuzhou.gov.cn/",
        "梧州市": "http://www.gxwzzx.gov.cn/",
        "钦州市": "http://www.zxqzsw.gov.cn/",
        "贺州市": "http://www.gxhzzx.gov.cn/",
    },
    "青海省": {
        "西宁市": "http://www.xnszx.gov.cn/",
        "海南藏族自治州": "http://hnzzx.gov.cn/",
        "海西蒙古族藏族自治州": "http://www.hxzx.gov.cn/",
    },
    "广东省": {
        "广州市": "https://www.gzzx.gov.cn/",
        "梅州市": "https://www.mzszx.gov.cn/",
        "惠州市": "http://www.hzszx.gov.cn/",
        "潮州市": "http://czzx.gov.cn/",
    },
    "重庆市": {
        "渝中区": "http://zx.cqyz.gov.cn/",
        "沙坪坝区": "https://www.spbzx.gov.cn/site/default.jsp",
        "巴南区": "http://bnzx.gov.cn/",
        "璧山区": "http://www.bswxw.com/ztzgrmzzxshyzqsbsqwyh",
    },
    "天津市": {
        "河北区": "http://www.tjhb.gov.cn/zxhbqwyh/",
        "南开区": "http://www.tjnk.gov.cn/NKQZF/QZX8640/",
    },
    "江西省": {
        "赣州市": "http://www.jxgzzx.gov.cn/",
        "抚州市": "http://www.jxfzzx.gov.cn/",
    },
}

tree = json.load(open("tree.json", encoding="utf-8"))
prov_g = next(g for g in tree["ks"] if g["n"].startswith("省级"))

def city_names(pn, lvs):
    p = next(x for x in prov_g["ks"] if x["n"] == pn)
    s = []
    for top in p.get("ks", []):
        def walk(n):
            if n.get("l") in lvs and n.get("k") in ("人民政府", "功能区") and \
               "开发区" not in n["n"] and "高新区" not in n["n"] and \
               "园区" not in n["n"] and "管理区" not in n["n"]:
                s.append(n["n"])
            for k in n.get("ks", []):
                walk(k)
        walk(top)
    return s

MUNI = {"北京市": ("地级区", "县"), "天津市": ("地级区", "县"),
        "上海市": ("地级区", "县"), "重庆市": ("地级区", "县")}
rows = []
for p in prov_g["ks"]:
    pn = p["n"]
    if pn == "新疆生产建设兵团":
        continue
    lvs = MUNI.get(pn, ("市",))
    names = city_names(pn, lvs)
    if pn == "湖北省":
        names = city_names(pn, ("市",)) + ["仙桃市", "潜江市", "天门市", "神农架林区"]
    linked = LINKED.get(pn, {})
    for nm in names:
        u = linked.get(nm, "")
        # 湖北神农架在树里可能叫「神农架林区」直接匹配
        rows.append({"province": pn, "name": nm, "url": u, "listed": bool(u)})

with open("rd_zx.jsonl", "w", encoding="utf-8") as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")

n_u = sum(1 for r in rows if r["listed"])
print(f"p94 完成：rd_zx.jsonl {len(rows)} 条（{n_u} 有官网）")
by = {}
for r in rows:
    by.setdefault(r["province"], [0, 0])
    by[r["province"]][0] += 1
    if r["listed"]:
        by[r["province"]][1] += 1
for pn, (t, n) in sorted(by.items()):
    print(f"  {pn}: {n}/{t}")
