# -*- coding: utf-8 -*-
"""P1: 中央部委 + 省级政府 信息公开专栏 URL 解析。

输入: gov_dept_sites.html / gov_local_sites.html (gov.cn 官方导航页)
输出: central.jsonl / province.jsonl
"""
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from bs4 import BeautifulSoup

sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
from common import fetch, find_xxgk_url, probe_xxgk_paths, norm_url

# ---------------- 中央机构分类（2023 国务院机构改革后口径） ----------------
DEPT_CLASSIFY = {
    # 组成部门 26
    "外交部": ("国务院组成部门", ""), "国防部": ("国务院组成部门", ""),
    "国家发展和改革委员会": ("国务院组成部门", ""), "教育部": ("国务院组成部门", ""),
    "科学技术部": ("国务院组成部门", ""), "工业和信息化部": ("国务院组成部门", ""),
    "国家民族事务委员会": ("国务院组成部门", ""), "公安部": ("国务院组成部门", ""),
    "国家安全部": ("国务院组成部门", ""), "民政部": ("国务院组成部门", ""),
    "司法部": ("国务院组成部门", ""), "财政部": ("国务院组成部门", ""),
    "人力资源和社会保障部": ("国务院组成部门", ""), "自然资源部": ("国务院组成部门", ""),
    "生态环境部": ("国务院组成部门", ""), "住房和城乡建设部": ("国务院组成部门", ""),
    "交通运输部": ("国务院组成部门", ""), "水利部": ("国务院组成部门", ""),
    "农业农村部": ("国务院组成部门", ""), "商务部": ("国务院组成部门", ""),
    "文化和旅游部": ("国务院组成部门", ""), "国家卫生健康委员会": ("国务院组成部门", ""),
    "退役军人事务部": ("国务院组成部门", ""), "应急管理部": ("国务院组成部门", ""),
    "中国人民银行": ("国务院组成部门", ""), "审计署": ("国务院组成部门", ""),
    # 直属特设机构
    "国务院国有资产监督管理委员会": ("国务院直属特设机构", ""),
    # 直属机构 14
    "海关总署": ("国务院直属机构", ""), "国家税务总局": ("国务院直属机构", ""),
    "国家市场监督管理总局": ("国务院直属机构", ""), "国家金融监督管理总局": ("国务院直属机构", ""),
    "中国证券监督管理委员会": ("国务院直属机构", ""), "国家广播电视总局": ("国务院直属机构", ""),
    "国家体育总局": ("国务院直属机构", ""), "国家信访局": ("国务院直属机构", ""),
    "国家统计局": ("国务院直属机构", ""), "国家知识产权局": ("国务院直属机构", ""),
    "国家国际发展合作署": ("国务院直属机构", ""), "国家医疗保障局": ("国务院直属机构", ""),
    "国务院参事室": ("国务院直属机构", ""), "国家机关事务管理局": ("国务院直属机构", ""),
    # 办事机构
    "国务院研究室": ("国务院办事机构", ""), "国务院侨务办公室": ("国务院办事机构", ""),
    "国务院港澳事务办公室": ("国务院办事机构", ""), "国务院台湾事务办公室": ("国务院办事机构", ""),
    "国家互联网信息办公室": ("国务院办事机构", ""), "国务院新闻办公室": ("国务院办事机构", ""),
    # 直属事业单位
    "新华通讯社": ("国务院直属事业单位", ""), "中国科学院": ("国务院直属事业单位", ""),
    "中国社会科学院": ("国务院直属事业单位", ""), "中国工程院": ("国务院直属事业单位", ""),
    "国务院发展研究中心": ("国务院直属事业单位", ""), "中央广播电视总台": ("国务院直属事业单位", ""),
    "中国气象局": ("国务院直属事业单位", ""), "国家行政学院": ("国务院直属事业单位", ""),
    # 部委管理的国家局
    "国家粮食和物资储备局": ("部委管理的国家局", "国家发展和改革委员会"),
    "国家能源局": ("部委管理的国家局", "国家发展和改革委员会"),
    "国家数据局": ("部委管理的国家局", "国家发展和改革委员会"),
    "国家国防科技工业局": ("部委管理的国家局", "工业和信息化部"),
    "国家烟草专卖局": ("部委管理的国家局", "工业和信息化部"),
    "国家移民管理局": ("部委管理的国家局", "公安部"),
    "国家林业和草原局": ("部委管理的国家局", "自然资源部"),
    "国家铁路局": ("部委管理的国家局", "交通运输部"),
    "中国民用航空局": ("部委管理的国家局", "交通运输部"),
    "国家邮政局": ("部委管理的国家局", "交通运输部"),
    "国家文物局": ("部委管理的国家局", "文化和旅游部"),
    "国家中医药管理局": ("部委管理的国家局", "国家卫生健康委员会"),
    "国家疾病预防控制局": ("部委管理的国家局", "国家卫生健康委员会"),
    "国家矿山安全监察局": ("部委管理的国家局", "应急管理部"),
    "国家消防救援局": ("部委管理的国家局", "应急管理部"),
    "国家外汇管理局": ("部委管理的国家局", "中国人民银行"),
    "国家药品监督管理局": ("部委管理的国家局", "国家市场监督管理总局"),
    # 加挂牌子 / 合署办公
    "国家语言文字工作委员会": ("加挂牌子", "教育部"),
    "国家航天局": ("加挂牌子", "工业和信息化部"),
    "国家原子能机构": ("加挂牌子", "工业和信息化部"),
    "国家外国专家局": ("加挂牌子", "科学技术部"),
    "国家海洋局": ("加挂牌子", "自然资源部"),
    "国家核安全局": ("加挂牌子", "生态环境部"),
    "国家反垄断局": ("加挂牌子", "国家市场监督管理总局"),
    "国家认证认可监督管理委员会": ("加挂牌子", "国家市场监督管理总局"),
    "国家标准化管理委员会": ("加挂牌子", "国家市场监督管理总局"),
    "国家新闻出版署": ("加挂牌子", "中共中央宣传部"),
    "（国家版权局）": ("加挂牌子", "中共中央宣传部"),
    "国家宗教事务局": ("加挂牌子", "中共中央统一战线工作部"),
}

SKIP_NAMES = {"（国家版权局）"}


def parse_central_links(html):
    """从国务院部门网站导航页提取 (名称, URL) 列表。"""
    soup = BeautifulSoup(html, "lxml")
    out = []
    for a in soup.find_all("a"):
        t = re.sub(r"\s+", "", a.get_text(" ", strip=True))
        h = a.get("href") or ""
        if not t or not h.startswith(("http://", "https://")):
            continue
        if t in DEPT_CLASSIFY or t in SKIP_NAMES:
            out.append((t, h))
    return out


def parse_province_links(html):
    soup = BeautifulSoup(html, "lxml")
    out = []
    for a in soup.find_all("a"):
        t = re.sub(r"\s+", "", a.get_text(" ", strip=True))
        h = a.get("href") or ""
        if t in ("北京", "天津", "河北", "山西", "内蒙古", "辽宁", "吉林", "黑龙江",
                 "上海", "江苏", "浙江", "安徽", "福建", "江西", "山东", "河南",
                 "湖北", "湖南", "广东", "广西", "海南", "重庆", "四川", "贵州",
                 "云南", "西藏", "陕西", "甘肃", "青海", "宁夏", "新疆",
                 "新疆生产建设兵团") and h.startswith(("http://", "https://")):
            out.append((t, h))
    return out


def resolve_one(rec):
    """rec: dict(name, portal_url) → 填 xxgk_url。返回 rec。"""
    html = fetch(rec["portal_url"])
    rec["home_ok"] = bool(html)
    if html:
        url = find_xxgk_url(html, rec["portal_url"])
        if url:
            rec["xxgk_url"] = norm_url(url)
            rec["xxgk_src"] = "导航链接"
            return rec
    # 兜底：常见路径探测
    url = probe_xxgk_paths(rec["portal_url"])
    if url:
        rec["xxgk_url"] = norm_url(url)
        rec["xxgk_src"] = "路径探测"
    return rec


def main():
    dept_html = open("gov_dept_sites.html", encoding="utf-8").read()
    prov_html = open("gov_local_sites.html", encoding="utf-8").read()

    centrals = []
    seen = set()
    for name, url in parse_central_links(dept_html):
        if name in seen:
            continue
        seen.add(name)
        cat, parent = DEPT_CLASSIFY.get(name, ("其他中央机构", ""))
        centrals.append({
            "name": name, "category": cat, "parent": parent,
            "portal_url": norm_url(url), "source": "gov.cn国务院部门网站导航",
        })
    print(f"中央机构 {len(centrals)} 个")

    provinces = []
    seen = set()
    for name, url in parse_province_links(prov_html):
        if name in seen:
            continue
        seen.add(name)
        provinces.append({
            "name": name, "category": "省级人民政府" if name != "新疆生产建设兵团" else "省级（兵团）",
            "portal_url": norm_url(url), "source": "gov.cn地方政府网站导航",
        })
    print(f"省级 {len(provinces)} 个")

    # 并发解析信息公开专栏
    def worker(rec):
        return resolve_one(rec)

    total = len(centrals) + len(provinces)
    with ThreadPoolExecutor(max_workers=16) as ex:
        futs = [ex.submit(worker, r) for r in centrals + provinces]
        for i, f in enumerate(as_completed(futs)):
            f.result()
            if (i + 1) % 40 == 0:
                print(f"xxgk解析进度 {i+1}/{total}", flush=True)

    with open("central.jsonl", "w", encoding="utf-8") as f:
        for r in centrals:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open("province.jsonl", "w", encoding="utf-8") as f:
        for r in provinces:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    ok = sum(1 for r in centrals + provinces if r.get("xxgk_url"))
    print(f"信息公开URL命中: {ok}/{total}")
    miss = [r["name"] for r in centrals + provinces if not r.get("xxgk_url")]
    print("未命中:", miss)


if __name__ == "__main__":
    main()
