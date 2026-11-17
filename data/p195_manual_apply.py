# -*- coding: utf-8 -*-
"""P195 手工落库: 已验证的县级门户候选 → 块树 u 回填 + registry 登记。
候选来源（全部官方门户 HTML 提取 + title 验证）:
  南京 11 区   — 南京市政府门户「站群导航」二次跳转页(zqdh)
  鄂州 3 区    — 鄂州市政府门户 onclick 跳转链接
  阳江 4 县区  — 阳江市政府门户「友情链接-县市区政府」二次跳转页
  茂名 5 县区  — 茂名市政府门户「茂名县（市、区）」二次跳转页
  梅州 8 县区  — 梅州市政府门户首页 tab 面板
用法: cd data && uv run python p195_manual_apply.py
"""
import datetime, json, os, sys

BASE = os.path.dirname(os.path.abspath(__file__))
TREE_F = os.path.join(BASE, "tree.json")
REG_F = os.path.join(BASE, "site_registry.json")
sys.path.insert(0, BASE)
from site_contract import upsert_registry

# 候选: (省, 市, 县名, URL)
CANDS = [
    # 南京 11 区（站群导航 zqdh）
    ("江苏省", "南京市", "玄武区", "http://www.xwzf.gov.cn/"),
    ("江苏省", "南京市", "秦淮区", "http://www.njqh.gov.cn"),
    ("江苏省", "南京市", "建邺区", "http://www.njjy.gov.cn/"),
    ("江苏省", "南京市", "鼓楼区", "http://www.njgl.gov.cn/"),
    ("江苏省", "南京市", "栖霞区", "http://www.njqxq.gov.cn"),
    ("江苏省", "南京市", "雨花台区", "http://www.njyh.gov.cn/"),
    ("江苏省", "南京市", "江宁区", "http://www.jiangning.gov.cn/"),
    ("江苏省", "南京市", "浦口区", "https://njna.nanjing.gov.cn/"),
    ("江苏省", "南京市", "六合区", "http://www.njlh.gov.cn/"),
    ("江苏省", "南京市", "溧水区", "http://www.njls.gov.cn/"),
    ("江苏省", "南京市", "高淳区", "http://www.njgc.gov.cn/"),
    # 鄂州 3 区（onclick 跳转）
    ("湖北省", "鄂州市", "鄂城区", "http://www.echeng.gov.cn/"),
    ("湖北省", "鄂州市", "华容区", "http://www.hbhr.gov.cn/"),
    ("湖北省", "鄂州市", "梁子湖区", "http://www.liangzh.gov.cn/"),
    # 阳江 4 县区（友情链接 xsqzf）
    ("广东省", "阳江市", "江城区", "http://www.jiangcheng.gov.cn/"),
    ("广东省", "阳江市", "阳东区", "http://www.yangdong.gov.cn/"),
    ("广东省", "阳江市", "阳春市", "http://www.yangchun.gov.cn/"),
    ("广东省", "阳江市", "阳西县", "http://www.yangxi.gov.cn/"),
    # 茂名 5 县区（mmxsq 二次跳转）
    ("广东省", "茂名市", "茂南区", "http://www.maonan.gov.cn/"),
    ("广东省", "茂名市", "电白区", "http://www.dianbai.gov.cn/"),
    ("广东省", "茂名市", "信宜市", "http://www.xinyi.gov.cn/"),
    ("广东省", "茂名市", "高州市", "http://www.gaozhou.gov.cn/"),
    ("广东省", "茂名市", "化州市", "http://www.huazhou.gov.cn/"),
    # 梅州 8 县区（首页 tab 面板）
    ("广东省", "梅州市", "梅江区", "http://www.meijiang.gov.cn/"),
    ("广东省", "梅州市", "梅县区", "http://www.gdmx.gov.cn/"),
    ("广东省", "梅州市", "兴宁市", "http://www.xingning.gov.cn/"),
    ("广东省", "梅州市", "平远县", "http://www.pingyuan.gov.cn/"),
    ("广东省", "梅州市", "蕉岭县", "http://www.jiaoling.gov.cn/"),
    ("广东省", "梅州市", "大埔县", "http://www.dabu.gov.cn/"),
    ("广东省", "梅州市", "丰顺县", "https://www.fengshun.gov.cn/"),
    ("广东省", "梅州市", "五华县", "http://www.wuhua.gov.cn/"),
    # 郴州 10 县区（市政府门户首页 cloakbrowser 渲染真页, title 逐站验证）
    ("湖南省", "郴州市", "北湖区", "http://www.czbeihu.gov.cn/"),
    ("湖南省", "郴州市", "苏仙区", "http://www.hnsx.gov.cn/"),
    ("湖南省", "郴州市", "桂阳县", "http://www.hngy.gov.cn/"),
    ("湖南省", "郴州市", "宜章县", "http://www.yzx.gov.cn"),
    ("湖南省", "郴州市", "永兴县", "http://www.yxx.gov.cn/"),
    ("湖南省", "郴州市", "嘉禾县", "http://www.hnjh.gov.cn/index.html"),
    ("湖南省", "郴州市", "临武县", "https://www.lwx.gov.cn/"),
    ("湖南省", "郴州市", "汝城县", "http://www.rc.gov.cn/"),
    ("湖南省", "郴州市", "桂东县", "http://www.gdx.gov.cn/"),
    ("湖南省", "郴州市", "安仁县", "http://www.anrenzf.gov.cn/"),
    # 昭通 11 县区（门户 Vue el-select el-option 下拉, title 逐站验证）
    ("云南省", "昭通市", "昭阳区", "http://www.zyq.gov.cn"),
    ("云南省", "昭通市", "鲁甸县", "http://www.ludian.gov.cn/"),
    ("云南省", "昭通市", "巧家县", "http://www.qiaojia.gov.cn/"),
    ("云南省", "昭通市", "镇雄县", "http://www.zx.gov.cn/"),
    ("云南省", "昭通市", "彝良县", "http://www.cnyl.gov.cn"),
    ("云南省", "昭通市", "威信县", "http://www.weixin.gov.cn/"),
    ("云南省", "昭通市", "盐津县", "http://www.ztyj.gov.cn"),
    ("云南省", "昭通市", "大关县", "http://www.daguan.gov.cn/"),
    ("云南省", "昭通市", "永善县", "http://www.ynys.gov.cn/"),
    ("云南省", "昭通市", "绥江县", "http://www.suijiang.gov.cn/"),
    ("云南省", "昭通市", "水富市", "http://www.sfs.gov.cn/"),
    # 荆门 5 县区（市政府门户「网站群」栏目页 col904 底部区块, title 逐站验证）
    ("湖北省", "荆门市", "东宝区", "http://www.jmdbq.gov.cn/"),
    ("湖北省", "荆门市", "掇刀区", "http://www.duodao.gov.cn/"),
    ("湖北省", "荆门市", "沙洋县", "http://www.shayang.gov.cn/"),
    ("湖北省", "荆门市", "钟祥市", "http://www.zhongxiang.gov.cn/"),
    ("湖北省", "荆门市", "京山市", "http://www.jingshan.gov.cn/"),
    # 石家庄 4 县 + 新华区修正 + 高新区（门户「县市区政府信息公开」页深链
    # 根化重验; 新华区原挂 czxh.gov.cn=沧州新华区 错配修正）
    ("河北省", "石家庄市", "井陉县", "http://www.sjzjx.gov.cn/"),
    ("河北省", "石家庄市", "正定县", "http://www.zd.gov.cn/"),
    ("河北省", "石家庄市", "晋州市", "http://www.jzs.gov.cn/"),
    ("河北省", "石家庄市", "新乐市", "https://www.xinle.gov.cn/"),
    ("河北省", "石家庄市", "新华区", "http://www.xhqsjz.gov.cn/"),
    ("河北省", "石家庄市", "石家庄高新技术产业开发区", "http://www.shidz.gov.cn/"),
    # 包头 2 旗县区（门户首页旗县区入口区块, title/正文验证）
    ("内蒙古自治区", "包头市", "白云鄂博矿区", "http://www.byeb.gov.cn"),
    ("内蒙古自治区", "包头市", "土默特右旗", "http://www.tmtyq.gov.cn"),
    # 肇庆 8 县区（门户「友情链接-各县市区政府」名录页 yqlj/xsqzf, title 逐站验证）
    ("广东省", "肇庆市", "端州区", "http://www.zqdz.gov.cn/"),
    ("广东省", "肇庆市", "鼎湖区", "http://www.zqdh.gov.cn/"),
    ("广东省", "肇庆市", "高要区", "http://www.gaoyao.gov.cn/"),
    ("广东省", "肇庆市", "四会市", "http://www.sihui.gov.cn/"),
    ("广东省", "肇庆市", "广宁县", "http://www.gdgn.gov.cn/"),
    ("广东省", "肇庆市", "德庆县", "http://www.gddq.gov.cn/"),
    ("广东省", "肇庆市", "封开县", "http://www.fengkai.gov.cn/"),
    ("广东省", "肇庆市", "怀集县", "http://www.huaiji.gov.cn/"),
    # 佛山 5 区（门户「区政府」名录页 qtlm/qzf, title 逐站验证）
    ("广东省", "佛山市", "禅城区", "http://www.chancheng.gov.cn/"),
    ("广东省", "佛山市", "南海区", "http://www.nanhai.gov.cn/"),
    ("广东省", "佛山市", "顺德区", "http://www.shunde.gov.cn/"),
    ("广东省", "佛山市", "高明区", "http://www.gaoming.gov.cn/"),
    ("广东省", "佛山市", "三水区", "http://www.ss.gov.cn/"),
    # 廊坊 10 县区+经开区（门户「网站群导航-县（市、区）政府」名录页
    # Category_1021; 固安县瑞数防护待 loop 攻坚, 暂不落）
    ("河北省", "廊坊市", "三河市", "http://www.san-he.gov.cn/"),
    ("河北省", "廊坊市", "香河县", "https://www.xianghe.gov.cn/"),
    ("河北省", "廊坊市", "大厂回族自治县", "https://www.lfdc.gov.cn/"),
    ("河北省", "廊坊市", "广阳区", "http://www.guangyang.gov.cn/"),
    ("河北省", "廊坊市", "安次区", "https://www.anci.gov.cn/"),
    ("河北省", "廊坊市", "永清县", "https://www.yongqing.gov.cn/"),
    ("河北省", "廊坊市", "霸州市", "http://www.bazhou.gov.cn/"),
    ("河北省", "廊坊市", "文安县", "http://www.wenan.gov.cn/"),
    ("河北省", "廊坊市", "大城县", "http://www.dacheng.gov.cn/"),
    ("河北省", "廊坊市", "廊坊经济技术开发区", "https://www.lfkfqgwh.gov.cn/"),
    # 省级错配修正（2026-11-13 用户指正）: 青海省监委原挂 qinghai.gov.cn
    # 新闻文章页, 正确官网为 qhjc.gov.cn（ccdi 名录）
    ("青海省", "青海省", "省监委", "http://www.qhjc.gov.cn/"),
]


def main():
    tree = json.load(open(TREE_F, encoding="utf-8"))
    reg = json.load(open(REG_F, encoding="utf-8"))
    today = datetime.date.today().isoformat()

    # 索引: (p1,p2,n) -> node（节点自带 p1/p2 字段）
    idx = {}

    def walk(n):
        if n.get("k") == "人民政府" and n.get("c") == "县级人民政府":
            idx[(n.get("p1", ""), n.get("p2", ""), n.get("n", ""))] = n
        for c in n.get("ks", []):
            walk(c)

    walk(tree)

    hit = miss = already = 0
    for p1, p2, nm, u in CANDS:
        nd = idx.get((p1, p2, nm))
        if nd is None:
            print(f"[miss] {p1}/{p2}/{nm} 树中无节点")
            miss += 1
            continue
        old = nd.get("u", "")
        if old and old.rstrip("/") == u.rstrip("/"):
            already += 1
            continue
        nd["u"] = u
        nd["s"] = f"来源：{p2}政府门户县区导航 HTML 提取（title 验证）"
        # registry 是 status/verified_at 主数据，树节点只留 u/s
        key = f"县级人民政府|{nm}"
        upsert_registry(reg, key, u, name=nm, source_level="L2",
                        source=nd["s"], verified_at=today, locations=["块"])
        hit += 1
        print(f"[ok] {p1}/{p2}/{nm} {old or '空'} -> {u}")

    json.dump(tree, open(TREE_F, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(reg, open(REG_F, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"落库完成: hit={hit} already={already} miss={miss}")


if __name__ == "__main__":
    main()
