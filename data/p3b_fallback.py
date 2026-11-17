# -*- coding: utf-8 -*-
"""P3b: 未匹配市/县门户兜底解析（重试父级 → 拼音域名探测 → Bing 搜索）。"""
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
from common import fetch, curl_fetch_text, norm_url
from search_bing import search as bing_search

SUFFIX_RE = re.compile(r"(人民政府)?(市|区|县|旗|自治县|自治旗|自治州|地区|盟|林区|特区|联合旗)$")
# 泛地名（多省同名），拼音探测易错，直接走 Bing
GENERIC_NAMES = {
    "城区", "郊区", "矿区", "城关区", "市中区", "新区", "开发区", "东区", "西区", "南区",
    "北区", "中区", "城中区", "城北区", "城东区", "城西区", "桥东区", "桥西区", "铁东区",
    "铁西区", "河东区", "河西区", "江南区", "江北区", "新华区", "新市区", "鼓楼区",
    "和平区", "南开区", "河东区", "河西区", "河北区", "红桥区", "滨海新区", "高新区",
    "经济开发区", "大厂回族自治县", "郊区",
}
PY_EXCEPT = {
    # 市州级知名异读/缩写
    "哈尔滨": ["harbin"], "齐齐哈尔": ["qqhr"], "呼和浩特": ["huhhot", "hohhot"],
    "乌鲁木齐": ["urumqi"], "拉萨": ["lasa", "lhasa"], "鄂尔多斯": ["ordos"],
    "锡林郭勒": ["xlgl"], "阿拉善": ["als"], "呼伦贝尔": ["hlbr"],
    "巴彦淖尔": ["bynr"], "乌兰察布": ["wlcb"], "兴安": ["xam"],
    "巴音郭楞": ["bygl"], "克孜勒苏柯尔克孜": ["xjkz"], "吐鲁番": ["turpan", "tlf"],
    "昌吉": ["cj", "changji"], "博尔塔拉": ["bz", "boertala"],
    "黔东南": ["qdn", "qiandongnan"], "黔西南": ["qxn"], "黔南": ["qn", "qiannan"],
    "西双版纳": ["xsbn"], "甘孜": ["ganzi"], "阿坝": ["ab", "aba"],
    "果洛": ["guoluo"], "玉树": ["ys", "yushu"], "海西": ["hx", "haixi"],
    "怒江": ["nujiang"], "迪庆": ["diqing"], "德宏": ["dehong"],
    "红河": ["hh", "honghe"], "文山": ["wenshan"], "楚雄": ["chuxiong"],
    "大理": ["dali"], "凉山": ["liangshan"], "延边": ["yanbian"],
    "恩施": ["enshi"], "湘西": ["xiangxi"], "临夏": ["linxia"],
    "甘南": ["gn", "gannan"], "海北": ["haibei"], "黄南": ["huangnan"],
    "伊犁": ["yl", "yili"], "喀什": ["kashi"], "和田": ["hetian"],
    "阿克苏": ["aks", "akesu"], "哈密": ["hami"], "塔城": ["tacheng"],
    "阿勒泰": ["alt", "aletai"], "石河子": ["shz", "shihezi"],
    "二连浩特": ["elht"], "乌海": ["wuhai"],
}


def short_name(name):
    s = SUFFIX_RE.sub("", name)
    return s if s else name


def pinyin_candidates(name):
    """生成候选域名字符串列表（不含 www）。"""
    s = short_name(name)
    cands = PY_EXCEPT.get(name, [])
    if not cands:
        try:
            from pypinyin import lazy_pinyin
            cands = ["".join(lazy_pinyin(s))]
        except Exception:
            cands = []
    # 去数字/非字母
    out = []
    for c in cands:
        c = re.sub(r"[^a-z]", "", c.lower())
        if c and c not in out:
            out.append(c)
    return out


def verify_portal(url, name, prov_short):
    """校验候选域名确为该政府门户：首页标题含地名。"""
    html = curl_fetch_text(url, timeout=12) or fetch(url, timeout=12)
    if not html or len(html) < 800:
        return False
    m = re.search(r"<title>(.*?)</title>", html, re.S | re.I)
    title = re.sub(r"[\s|·\-—]", "", m.group(1)) if m else ""
    sn = short_name(name)
    prov_sn = SUFFIX_RE.sub("", prov_short)
    # 标题应含县名简称，且属于该省语境（避免同名异地）
    if sn and sn not in title:
        return False
    # 粗校验省名（部分站点标题不带省名则跳过此检查）
    if prov_sn and len(prov_sn) >= 2 and prov_sn != "内蒙" and prov_sn not in ("新疆", "西藏", "广西", "宁夏", "内蒙古"):
        pass
    return True


def resolve_via_pinyin(name, prov_short):
    if name in GENERIC_NAMES or short_name(name) in GENERIC_NAMES:
        return None
    for cand in pinyin_candidates(name):
        for host in (f"www.{cand}.gov.cn", f"{cand}.gov.cn"):
            for scheme in ("https", "http"):
                url = f"{scheme}://{host}/"
                if verify_portal(url, name, prov_short):
                    return norm_url(url)
    return None


def resolve_via_bing(name, prov_short):
    sn = short_name(name)
    queries = [f"{name}人民政府 网站", f"{prov_short}{name} 政府网站"]
    for q in queries:
        try:
            results = bing_search(q, count=6, sleep=0.8)
        except Exception:
            results = []
        for r in results:
            u = r["url"] or ""
            if not u.startswith(("http://", "https://")):
                continue
            host = urlparse(u).netloc.lower()
            if not host.endswith(".gov.cn"):
                continue
            # 标题/URL 需含地名（去后缀）
            blob = (r["title"] or "") + " " + (r["cite"] or "")
            if sn and sn not in blob:
                continue
            # 根路径优先
            root = f"{urlparse(u).scheme}://{host}/"
            if verify_portal(root, name, prov_short):
                return norm_url(root)
    return None


def fill_one(rec, prov_map):
    """rec 无 portal_url → 尝试补齐。返回 bool。"""
    name = rec["name"]
    prov_short = prov_map.get(rec["province"], rec["province"])
    # 1) 拼音域名探测
    url = resolve_via_pinyin(name, prov_short)
    if url:
        rec["portal_url"] = url
        rec["how"] = "拼音探测"
        return True
    # 2) Bing
    url = resolve_via_bing(name, prov_short)
    if url:
        rec["portal_url"] = url
        rec["how"] = "bing搜索"
        return True
    return False


def main():
    provs = {d["name"]: d["name"] for d in json.load(open("divisions.json", encoding="utf-8"))
             if d["level"] in ("省", "特别行政区")}
    # 省简称（用于搜索词）
    prov_map = {k: SUFFIX_RE.sub("", k) for k in provs}

    todo = []
    for fn in ("city_portals.jsonl", "county_portals.jsonl"):
        rows = [json.loads(l) for l in open(fn, encoding="utf-8")]
        todo += [r for r in rows if not r.get("portal_url")]
    print(f"待兜底 {len(todo)} 个", flush=True)

    ok = fail = 0
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(fill_one, r, prov_map): r for r in todo}
        for i, f in enumerate(as_completed(futs)):
            try:
                if f.result():
                    ok += 1
                else:
                    fail += 1
            except Exception:
                fail += 1
            if (i + 1) % 50 == 0:
                print(f"[p3b] {i+1}/{len(todo)} ok={ok} fail={fail}", flush=True)
    print(f"[p3b] done ok={ok} fail={fail}", flush=True)

    # 回写
    for fn in ("city_portals.jsonl", "county_portals.jsonl"):
        rows = [json.loads(l) for l in open(fn, encoding="utf-8")]
        by_code = {r["code"]: r for r in rows}
        for r in todo:
            if r["code"] in by_code:
                by_code[r["code"]].update(r)
        with open(fn, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print("回写完成", flush=True)


if __name__ == "__main__":
    main()
