#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""p227 群团：条树 → 块树省级 URL 同步（2026-11-17）。

块视图 31 省「群团组织（17）」分组下省妇联/省文联/省作协等大量节点 u 为空
（README 群团省级缺失 45%），而条视图「群团组织系统」里这些机构 90%+ 有
官方 URL（来自各中央群团官网「省级组织」名录，L1 权威）。同一机构两视图
不一致属同步缺口，不是采集缺口——本脚本按省基底 + 机构族匹配回填。

规则（p78 纪律）：
  - 只填空节点 u（与条树不一致时只报告，不覆盖——另有审计脚本处理）；
  - registry 写标准键 `群团|<省名><机构全名>`
  - 来源留痕 s：条树同源回填

用法：
  cd data && uv run python p227_qt_tiao2kuai.py --dry
  cd data && uv run python p227_qt_tiao2kuai.py
"""
import datetime
import json
import os
import re
import shutil
import sys

DATA = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(DATA)
sys.path.insert(0, DATA)
from site_contract import base, upsert_registry  # noqa: E402

TREE_F = os.path.join(DATA, "tree.json")
REG_F = os.path.join(DATA, "site_registry.json")
TODAY = datetime.date.today().isoformat()
DRY = "--dry" in sys.argv

# 块树节点名 → (条树族名前缀, 机构名结尾特征)
FAM = {
    "省总工会": ("", ("总工会",)),
    "团省委": ("省级团委", ("共产主义青年团", "团委")),
    "省妇联": ("省级妇联", ("妇女联合会",)),
    "省科协": ("中国科学技术协会", ("科学技术协会",)),
    "省文联": ("中国文学艺术界联合会", ("文学艺术界联合会",)),
    "省作协": ("中国作家协会", ("作家协会",)),
    "省侨联": ("中华全国归国华侨联合会", ("归国华侨联合会",)),
    "省人民对外友好协会": ("中国人民对外友好协会", ("人民对外友好协会", "对外友好协会")),
    "省台联": ("中华全国台湾同胞联谊会", ("台湾同胞联谊会",)),
    "省残联": ("中国残疾人联合会", ("残疾人联合会",)),
    "省贸促会": ("中国国际贸易促进委员会", ("国际贸易促进委员会", "贸促会")),
    "省红十字会": ("中国红十字会总会", ("红十字会",)),
    "省工商联": ("中华全国工商业联合会", ("工商业联合会",)),
    "省法学会": ("中国法学会", ("法学会",)),
    "省记协": ("中华全国新闻工作者协会", ("新闻工作者协会", "记协")),
    "省计划生育协会": ("中国计划生育协会", ("计划生育协会",)),
    "省欧美同学会": ("欧美同学会", ("欧美同学会", "留学人员联谊会")),
}
PROV_SUF = re.compile(r"(维吾尔自治区|壮族自治区|回族自治区|自治区|特别行政区|省|市)$")
# 条树里的非独立官网链接（媒体频道/文章页/聚合页）——不得回填块树
BAD_SRC_HOST = ("chinawriter.com.cn", "taiwan.cn", "ts.cn", "people.com.cn",
                "xinhuanet.com", "news.cn", "mzfzw.net", "cctv.com", "sina.com",
                "sohu.com", "qq.com", "163.com", "weixin")
NEWSISH = re.compile(r"(/n\d{4}/|/t\d{8}_|/\d{8}\.s?html?|/\d{6,}\.s?html?"
                     r"|/content_\d+|/art/|/news|/djyw/|/zt\d+/|/local/.+/stjg_)", re.I)


def bad_src(u):
    from urllib.parse import urlparse as _up
    p = _up(u)
    h = p.netloc.lower()
    if any(b in h for b in BAD_SRC_HOST):
        return True
    if "xn--" in h:      # punycode 中文域名无法人工核验，不回填
        return True
    return bool(NEWSISH.search(p.path or ""))


def prov_base(n):
    x = base(n)
    for suf in ("维吾尔自治区", "壮族自治区", "回族自治区", "自治区", "特别行政区", "省", "市"):
        if x.endswith(suf) and len(x) > len(suf):
            return x[:-len(suf)]
    return x


def walk(n, p=""):
    yield n, p
    for c in n.get("ks") or []:
        yield from walk(c, p + "/" + (n.get("n") or "")[:14])


def main():
    tree = json.load(open(TREE_F, encoding="utf-8"))
    reg = json.load(open(REG_F, encoding="utf-8"))
    blk = next(g for g in tree["ks"] if g["n"].startswith("省级"))
    tiao = next(g for g in tree["ks"] if g["n"].startswith("条"))
    qt = next(x for x in tiao["ks"] if x["n"].startswith("群团"))

    # 条：族 → [(全名, url)]
    src = {}
    for org in qt.get("ks") or []:
        for fam in FAM.values():
            if fam[0] and org["n"].startswith(fam[0]):
                lst = src.setdefault(fam[0], [])
                for leaf, _ in walk(org):
                    u = (leaf.get("u") or "").strip()
                    if u:
                        lst.append(((leaf.get("n") or ""), u))

    def pick(fam, prov_full, pb):
        """按省名前缀匹配条树叶（河北省妇女联合会 ← 河北省/河北）。"""
        for full, u in src.get(fam, []):
            if full.startswith(prov_full) or full.startswith(pb):
                return full, u
        return None

    # 同一 URL 被 ≥3 个省共用 = 典型错配（如各省「团省委」都挂 bjyouth.net）
    host_use = {}
    for p in blk["ks"]:
        for proot in p.get("ks") or []:
            for n, _ in walk(proot):
                nm = n.get("n") or ""
                if nm in FAM and (n.get("u") or "").strip():
                    from urllib.parse import urlparse as _up
                    h = _up(n["u"].strip()).netloc.lower()
                    host_use.setdefault(nm, {}).setdefault(h, set()).add(p.get("n"))

    filled = mismatch = fixed = 0
    prov_names = set()
    for p in blk["ks"]:
        pb = prov_base(p.get("n") or "")
        prov_names.add(pb)
        for proot in p.get("ks") or []:
            for n, _ in walk(proot):
                nm = n.get("n") or ""
                if "群团" not in (n.get("c") or "") or nm not in FAM:
                    continue
                fam, sufs = FAM[nm]
                if not fam:
                    continue
                cand = pick(fam, p.get("n") or "", pb)
                if not cand:
                    continue
                full, u = cand
                if bad_src(u):
                    continue
                cur = (n.get("u") or "").strip()
                if cur:
                    from urllib.parse import urlparse as _up
                    ch = _up(cur).netloc.lower()
                    shared = len(host_use.get(nm, {}).get(ch, ())) >= 3
                    same_site = ch.replace("www.", "") == _up(u).netloc.lower().replace("www.", "")
                    if shared and not same_site and not DRY:
                        # 一 URL 挂多省 = 错配，用条树权威 URL 纠正
                        n["u"] = u
                        n["s"] = f"来源:{full}官网名录·条树同源纠正（p227，原挂 {cur[:40]} 多省共用）"
                        upsert_registry(reg, f"群团|{full}", u, name=full,
                                        source_level="L1", source=n["s"],
                                        verified_at=TODAY, locations=["块", "条"])
                        fixed += 1
                        print(f"  FIX {p.get('n')}/{nm}: {cur[:44]} -> {u[:44]}")
                        continue
                    if cur.rstrip("/") != u.rstrip("/") and not same_site:
                        mismatch += 1
                        print(f"  MISMATCH {p.get('n')}/{nm}: 块={cur[:50]} 条={u[:50]}")
                    continue
                if DRY:
                    print(f"  [DRY] {p.get('n')}/{nm} <- {full} {u[:60]}")
                else:
                    n["u"] = u
                    n["s"] = f"来源:{full}官网名录·条树同源回填（p227）"
                    upsert_registry(reg, f"群团|{full}", u, name=full,
                                    source_level="L1", source=n["s"],
                                    verified_at=TODAY, locations=["块", "条"])
                filled += 1

    print(f"p227 群团条→块: 回填 {filled}, 纠正 {fixed}, 冲突 {mismatch}"
          f"{'（DRY 未写库）' if DRY else ''}")
    if not DRY and (filled or fixed):
        d = os.path.join(ROOT, "backups", TODAY)
        os.makedirs(d, exist_ok=True)
        ts = datetime.datetime.now().strftime("%H%M%S")
        shutil.copy2(TREE_F, os.path.join(d, f"tree_before_p227_{ts}.json"))
        shutil.copy2(REG_F, os.path.join(d, f"registry_before_p227_{ts}.json"))
        json.dump(tree, open(TREE_F, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        json.dump(reg, open(REG_F, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("  已写 tree.json / site_registry.json")


if __name__ == "__main__":
    main()
