#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""p233 群团 / 民主党派「省级缺口」SERP 兜底（2026-11-17）。

p227 已把群团省级缺口从 45% 降到 25.7%，剩余 116 个叶子 + 民主党派 61 个
（多为台盟/致公/民革未建站省份）经上级官网确认无独立站点。本脚本按用户
四档策略的**兜底档**（百度 SERP + 严格检验）再扫一遍：

  1. 查询词 = 机构真实全名（民主党派节点名是合成名「山西省民革省委会」，
     需还原为「民革山西省委」）
  2. 候选只取百度 SERP 的 `mu` 真实 URL
  3. 严格检验：title 必须**同时**含省名基底 + 机构核心词（无法靠域名猜），
     且不得是新闻/文章路径、不得是媒体/聚合站、不得是下级组织（大学/
     医院/公司/支部…）
  4. 通过则落库 u + s（来源留痕），registry 同步；找不到保持列名

用法：
  cd data && uv run python p233_qt_serp.py --dry
  cd data && uv run python p233_qt_serp.py
  P233_LIMIT=100 P233_WORKERS=5
"""
import datetime
import json
import os
import re
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

DATA = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(DATA)
sys.path.insert(0, DATA)
sys.path.insert(0, os.path.join(ROOT, "util"))
from site_contract import base as _base, upsert_registry  # noqa: E402
from p223_county_5sys_fill import (NEWS_PATH, NEWS_QUERY,  # noqa: E402
                                   page_title, serp)

TREE_F = os.path.join(DATA, "tree.json")
REG_F = os.path.join(DATA, "site_registry.json")
STATE_F = os.path.join(DATA, "p233_state.json")
TODAY = datetime.date.today().isoformat()
DRY = "--dry" in sys.argv
LIMIT = int(os.environ.get("P233_LIMIT", "0")) or None
WORKERS = int(os.environ.get("P233_WORKERS", "5"))

BAD_DOM = ("baidu.com", "weixin", "weibo", "people.com.cn", "xinhuanet",
           "news.cn", "cctv.com", "mzfzw", "qq.com", "163.com", "sohu.com",
           "sina.com", "ifeng.com", "toutiao", "zhihu", "doc88", "wenku",
           "chinacourt.org", "npc.gov.cn", "cppcc.gov.cn", "ccdi.gov.cn",
           "spp.gov.cn", "court.gov.cn",
           # 媒体/平台（实测：安徽新协被填成安徽新闻网 ah.anhuinews.com 频道）
           "anhuinews", "zjol.com.cn", "eol.cn", "gmw.cn", "chinanews",
           "ce.cn", "youth.cn", "cnr.cn", "cri.cn", "huanqiu", "chinadaily")
EDU = re.compile(r"\.edu\.cn$|\.edu$|\.ac\.cn$")
# 登录页/CMS 页面碎片（实测：浙江科协被填成统一工作平台 /cas/login）
JUNK_PATH = re.compile(r"(/cas/|/login|/signin|/passport|/auth/|/_t\d+/|"
                       r"/page\.htm|/upload/|/download|\.pdf$|\.doc$|"
                       # 兄弟单位的「学会之窗/专业协会」名录频道页——不是本机构官网
                       r"/(xhzc|zhxh|xhgz|xhdt|xhjs)/)", re.I)
# 下级组织/非本体特征（「北京交通大学九三学社」「XX公司工会」这类要拦）
SUB_ORG = re.compile(r"(大学|学院|中学|小学|医院|公司|集团|支行|分行|营业部|"
                     r"街道|社区|支部|支社|分社|研究[所院]|中心|基地|项目组)")
PROV_KEYS = ("省", "市", "自治区", "壮族", "回族", "维吾尔", "藏族", "内蒙古")

# 民主党派：节点合成名 → (真实机构核心词, 查询用全名模板)
PARTY = [
    ("民革省委会", "民革", "中国国民党革命委员会{prov}委员会"),
    ("民盟省委会", "民盟", "中国民主同盟{prov}委员会"),
    ("民建省委会", "民建", "中国民主建国会{prov}委员会"),
    ("民进省委会", "民进", "中国民主促进会{prov}委员会"),
    ("农工民主党省委会", "农工党", "中国农工民主党{prov}委员会"),
    ("致公党省委会", "致公党", "中国致公党{prov}委员会"),
    ("九三学社委员会", "九三学社", "{prov}九三学社委员会"),
    ("台盟省委会", "台盟", "台湾民主自治同盟{prov}委员会"),
]
# 群团：机构核心词（节点名里去掉省名后的部分）
QT_CORE = ("科学技术协会", "新闻工作者协会", "台湾同胞联谊会", "计划生育协会",
           "人民对外友好协会", "欧美同学会", "总工会", "妇女联合会", "共青团",
           "文学艺术界联合会", "作家协会", "归国华侨联合会", "国际贸易促进委员会",
           "残疾人联合会", "红十字会", "工商业联合会", "法学会")


def prov_of(name):
    m = re.match(r"^(.{2,10}?(?:省|市|自治区|维吾尔自治区|壮族自治区|"
                 r"回族自治区))", name)
    return m.group(1) if m else ""


def tasks_of(tree):
    tiao = [g for g in tree["ks"] if g["n"].startswith("条")][0]
    out = []

    def walk(n):
        for c in n.get("ks") or []:
            yield c
            yield from walk(c)

    # 群团（条模块下「群团组织系统」子树的所有空叶子）
    qt = [s for s in tiao["ks"] if s["n"].startswith("群团")]
    if qt:
        for c in walk(qt[0]):
            nm = (c.get("n") or "").strip()
            if not nm or (c.get("ks") or []) or (c.get("u") or "").strip():
                continue
            core = next((k for k in QT_CORE if k in nm), None)
            pv = prov_of(nm)
            if not core or not pv:
                continue
            out.append({"node": c, "prov": pv, "core": core, "kind": "群团",
                        "name": nm, "q": nm})

    # 民主党派（中央子树里「民主党派中央（8）」分组 + 同层各党派中央）
    ctr = [g for g in tree["ks"] if g["n"].startswith("中央")][0]
    roots = []
    for g in ctr.get("ks") or []:
        nm = g.get("n") or ""
        if "民主党派中央" in nm:
            roots.extend(g.get("ks") or [])
        elif any(s in nm for s in
                 ("民革", "民盟", "民建", "民进", "农工", "致公", "九三", "台盟")):
            roots.append(g)
    for g in roots:
        for c in [g] + list(walk(g)):
            nm = (c.get("n") or "").strip()
            if not nm or (c.get("ks") or []) or (c.get("u") or "").strip():
                continue
            for suf, core, tpl in PARTY:
                if nm.endswith(suf):
                    pv = prov_of(nm)
                    if not pv:
                        break
                    out.append({"node": c, "prov": pv, "core": core,
                                "kind": "民主党派", "name": nm,
                                "q": tpl.format(prov=pv)})
                    break
    return out


def title_ok(title, t):
    if not title:
        return False, "title空"
    pb = _base(t["prov"]) or t["prov"]
    if t["core"] not in title:
        return False, "无机构核心词"
    if not (pb in title or t["prov"] in title):
        return False, "无省名"
    if SUB_ORG.search(title):
        return False, "下级组织页"
    # 官网首页标题≈机构名本身；长标题基本都是文章/专题页
    # （实测：江苏省科协被填成东南大学某页 page.htm）
    if len(title) > len(t["prov"]) + len(t["core"]) + 16:
        return False, "标题过长(疑文章页)"
    return True, "ok"


def valid(t, u):
    if not u.startswith("http"):
        return False, "非http"
    dom = urlparse(u).netloc.lower()
    if not dom or "." not in dom:
        return False, "域名异常"
    if any(b in dom for b in BAD_DOM):
        return False, "媒体/聚合站"
    if EDU.search(dom):
        return False, "教育网域名"
    if JUNK_PATH.search(urlparse(u).path or ""):
        return False, "登录页/文档/CMS碎片"
    if NEWS_PATH.search(u) or NEWS_QUERY.search(u):
        return False, "新闻/文章路径"
    ttl = page_title(u) or ""
    return title_ok(ttl, t)


def main():
    tree = json.load(open(TREE_F, encoding="utf-8"))
    reg = json.load(open(REG_F, encoding="utf-8"))
    st = json.load(open(STATE_F, encoding="utf-8")) if os.path.exists(STATE_F) else {}
    seen = st.setdefault("s4", {})
    tasks = tasks_of(tree)
    pending = [t for t in tasks if seen.get(t["q"]) != "miss"]
    if LIMIT:
        pending = pending[:LIMIT]
    print(f"p233 群团/民主党派缺口 {len(tasks)} 条，本轮查 {len(pending)}（{WORKERS} 并发）")

    def probe(t):
        h = serp(t["q"] + " 官网")
        if not h:
            return t, "__serpfail__", ""
        for u in re.findall(r'mu="(https?://[^"]+)"', h):
            ok, note = valid(t, u)
            if ok:
                return t, u, note
        return t, None, ""

    filled = 0
    with ThreadPoolExecutor(WORKERS) as ex:
        for t, u, note in ex.map(probe, pending):
            if u == "__serpfail__":
                seen[t["q"]] = "serp-fail"
                continue
            got = False
            if u:
                src = f"来源:SERP线索+title严格验证({note})·p233"
                if DRY:
                    print(f"  [DRY] {t['name']} -> {u[:70]}")
                else:
                    t["node"]["u"] = u
                    t["node"]["s"] = src
                    key = f"{t['kind']}|{t['name']}"
                    upsert_registry(reg, key, u, name=t["name"],
                                    source_level="L3", source=src,
                                    verified_at=TODAY, locations=["条"])
                got = True
            seen[t["q"]] = "hit" if got else "miss"
            if got:
                filled += 1
                print(f"  S4 {t['name']} -> {u[:76]}")
    print("p233 filled:", filled)

    if not DRY and filled:
        d = os.path.join(ROOT, "backups", TODAY)
        os.makedirs(d, exist_ok=True)
        ts = datetime.datetime.now().strftime("%H%M%S")
        for f, tag in ((TREE_F, "tree"), (REG_F, "registry")):
            shutil.copy2(f, os.path.join(d, f"{tag}_before_p233_{ts}.json"))
        json.dump(tree, open(TREE_F, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        json.dump(reg, open(REG_F, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        json.dump(st, open(STATE_F, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("  已写 tree.json / site_registry.json / p233_state.json")


if __name__ == "__main__":
    main()
