# -*- coding: utf-8 -*-
"""P101: 政协交互提取结果合并入 rd_zx.jsonl（内蒙古/山东/湖南/贵州）。"""
import json

NEW = {
    "内蒙古自治区": {
        "呼和浩特市": "http://www.hhhtzx.gov.cn/",
        "包头市": "http://www.btzx.gov.cn/",
        "呼伦贝尔市": "http://www.hlbezx.gov.cn/",
        "兴安盟": "http://www.xam.gov.cn/zx/663193/index.html",
        "通辽市": "http://www.tlcppcc.gov.cn/",
        "赤峰市": "http://www.chifeng.gov.cn/",
        "锡林郭勒盟": "http://zx.xlgl.gov.cn/",
        "乌兰察布市": "http://www.wlcbzx.gov.cn/",
        "鄂尔多斯市": "http://www.ordoszx.gov.cn/",
        "巴彦淖尔市": "http://www.bynrzx.gov.cn/",
        "乌海市": "http://www.whszx.gov.cn/",
        "阿拉善盟": "http://www.alszx.gov.cn/",
    },
    "山东省": {
        "济南市": "http://www.jnzx.gov.cn/",
        "青岛市": "http://qdzx.qingdao.gov.cn/",
        "淄博市": "http://www.zbszx.gov.cn/",
        "枣庄市": "http://www.zzzx.gov.cn/",
        "东营市": "http://dyzx.dongying.gov.cn/",
        "烟台市": "http://zx.yantai.gov.cn/",
        "潍坊市": "http://www.wfzx.gov.cn/",
        "济宁市": "http://www.jnszx.gov.cn/",
        "泰安市": "http://www.tazx.gov.cn/",
        "威海市": "http://zx.weihai.gov.cn/",
        "日照市": "http://www.rzzx.gov.cn/",
        "临沂市": "http://zx.linyi.cn",
        "德州市": "http://dzszx.dezhou.gov.cn/",
        "聊城市": "http://www.lcszx.gov.cn/",
        "滨州市": "http://www.bzzx.gov.cn/",
        "菏泽市": "http://www.hezezx.gov.cn/",
    },
    "湖南省": {
        "长沙市": "http://www.cszx.gov.cn/",
        "株洲市": "http://www.hnzzzx.gov.cn/",
        "湘潭市": "http://www.xiangtan.com.cn/",
        "衡阳市": "http://www.hnhyzx.gov.cn/",
        "益阳市": "http://www.yyzx.gov.cn",
        "常德市": "http://www.cdzx.gov.cn/",
        "岳阳市": "http://www.yyszx.gov.cn/",
        "邵阳市": "http://www.syszx.gov.cn/",
        "郴州市": "http://www.czszxw.gov.cn/",
        "娄底市": "http://www.ldzx.gov.cn/",
        "永州市": "http://www.hnyzzx.gov.cn/",
        "怀化市": "http://www.hnhhszx.com/",
    },
    "贵州省": {
        "贵阳市": "https://www.gyszx.gov.cn",
        "遵义市": "http://zhengxie.zunyi.gov.cn/",
        "六盘水市": "http://szx.gzlps.gov.cn/",
        "安顺市": "http://zx.anshun.gov.cn/",
        "铜仁市": "https://www.trszx.gov.cn/",
    },
}

rows = [json.loads(l) for l in open("rd_zx.jsonl", encoding="utf-8")]
updated = added = 0
for r in rows:
    pn = r["province"]
    if pn in NEW and r["name"] in NEW[pn]:
        if not r["url"]:
            r["url"] = NEW[pn][r["name"]]
            r["listed"] = True
            added += 1
        elif r["url"] != NEW[pn][r["name"]]:
            r["url"] = NEW[pn][r["name"]]
            updated += 1
with open("rd_zx.jsonl", "w", encoding="utf-8") as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
n_u = sum(1 for r in rows if r["listed"])
print(f"p101 完成：新增 {added} 更新 {updated}，总计 {len(rows)} 条（{n_u} 有官网）")
