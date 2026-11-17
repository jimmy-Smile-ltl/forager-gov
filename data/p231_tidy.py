#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""p231 末期数据清理（2026-11-17）：
  A 剥离入库 URL 的 WAF 会话参数（?WebShieldDRSessionVerify=… / jsessionid …）
  B 删除空名占位节点（浙江省政府部门下 2 个 n="" 的残节点）
  C 同一节点内重复子节点（同名同 URL）去重
  D 报告：u 非空但仍是首页根址之外的深链疑似文章页（只报告）

用法：
  cd data && uv run python p231_tidy.py --dry
  cd data && uv run python p231_tidy.py
"""
import datetime
import json
import os
import re
import shutil
import sys
from urllib.parse import urlparse

DATA = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(DATA)
sys.path.insert(0, DATA)
from p223_county_5sys_fill import _WAF_Q  # noqa: E402

TREE_F = os.path.join(DATA, "tree.json")
REG_F = os.path.join(DATA, "site_registry.json")
TODAY = datetime.date.today().isoformat()
DRY = "--dry" in sys.argv


def strip_q(u):
    u = (u or "").strip()
    if "?" not in u:
        return u
    head, _, q = u.partition("?")
    # _WAF_Q 带 ?/& 前缀断言，匹配时把 ? 补回去
    q2 = _WAF_Q.sub("", "?" + q).lstrip("?").lstrip("&")
    return head + (("?" + q2) if q2 else "")


# 移动版入口页 → 站点根（实测：陆河县检察院被填成 /lhjcy/phone/mindex.shtml）
_MOBILE = re.compile(r"/(phone|wap|m|mobile)/(m?index\.[a-z]+)$", re.I)


def norm_url(u):
    u = strip_q(u)
    m = _MOBILE.search(urlparse(u).path or "")
    if m:
        p = urlparse(u)
        return f"{p.scheme}://{p.netloc}/"
    return u


# 国家部委级机构名——出现在「市级政府部门」分组里一定是门户「国家部委」
# 友情链接区块被误采（实测：嘉峪关市部门下挂着 交通运输部/外交部/公安部…）
NATIONAL = re.compile(
    r"^(中华人民共和国|国务院|"
    r"国家[^省市县区州盟旗]{1,20}?(总局|总署|局|委员会|银行|办公室|研究院|院)$)")


# 明确的招标/企业信息聚合站——绝不是机构官网（实测 3 条 qianlima 命中）
AGG_HOST = ("qianlima.com", "chinabidding", "bidcenter", "zhaobiao.cn")


def main():
    tree = json.load(open(TREE_F, encoding="utf-8"))
    reg = json.load(open(REG_F, encoding="utf-8"))
    stat = {"url_clean": 0, "empty_del": 0, "dup_del": 0, "nation_del": 0,
            "group_del": 0}

    # 中央子树机构名全集——市级部门里同名即「国家部委链接区块」误采
    # （实测：3,504 个节点，含短名 教育部/水利部/商务部… 正则抓不到）
    ctr = next((g for g in tree["ks"] if g["n"].startswith("中央")), None)
    nat = set()
    if ctr:
        st = [ctr]
        while st:
            cur = st.pop()
            for c in cur.get("ks") or []:
                nm = (c.get("n") or "").strip()
                if nm:
                    nat.add(nm)
                st.append(c)
    # 短名：中华人民共和国教育部→教育部、国家体育总局→体育总局
    # （只对 部/总局/总署/署 后缀做剥离——「国家统计局→统计局」这类
    #   短名在市级是真实部门，绝不能列入）
    nat_short = set()
    for nm in nat:
        for pre in ("中华人民共和国", "国家", "国务院"):
            if nm.startswith(pre):
                s = nm[len(pre):]
                if s and re.search(r"(部|总局|总署|署)$", s):
                    nat_short.add(s)

    # 中央子树的**内部厅室**（办公厅/信访室/立案庭/政治部…）与市级部门重名，
    # 但市级门户「部门导航」里也会出现「宣传部/组织部」这类真实条目——
    # 一律不作为国家部委判定依据（宁可留一个陈旧节点，不可误删真节点）
    # 同名但**确实是市级部门**的：机关事务管理局（国管局）、各专门委员会
    # （人大/政协委员会在市门户部门导航里也是真实条目）
    GENERIC = {"办公厅", "办公室", "信访室", "法规室", "研究室", "组织部",
               "宣传部", "统战部", "政治部", "执行局", "立案庭", "机关党委",
               "机关事务管理局", "财政经济委员会", "经济委员会",
               "社会建设委员会", "华侨委员会", "外事委员会", "民族委员会",
               "提案委员会", "港澳台侨委员会", "计划预算委员会"}
    nat_safe = {x for x in nat if x not in GENERIC
                and not re.search(r"(室|厅|庭|处|科|组|中心|队|所|站)$", x)}

    def is_national(nm):
        nm = (nm or "").strip()
        return (bool(NATIONAL.match(nm)) or nm in nat_safe
                or nm in nat_short)

    def walk(n):
        yield n
        for c in list(n.get("ks") or []):
            yield from walk(c)

    # 市级政府部门分组里的国家部委级节点（门户「国家部委」链接区块误采）
    for n in walk(tree):
        if not ("市级政府部门" in (n.get("c") or "")
                or "市级政府部门" in (n.get("n") or "")):
            continue
        kids = n.get("ks")
        if not kids:
            continue
        natn = sum(1 for c in kids if is_national(c.get("n")))
        # 整块都是国家部委（≥85%）：该容器就是门户「国家部委」链接区块，
        # 子节点全删（否则短名如「体育总局/国有资产监督管理委员会」会漏网）
        whole = len(kids) >= 5 and natn / len(kids) >= 0.85
        keep = []
        for c in kids:
            if whole or is_national(c.get("n")):
                stat["nation_del"] += 1
                continue
            keep.append(c)
        if len(keep) != len(kids):
            if not DRY:
                n["ks"] = keep
            if not keep:
                n["_empty"] = True
    # 清空后的空分组删除（含各层）
    stack = [tree]
    while stack:
        cur = stack.pop()
        kids = cur.get("ks")
        if not kids:
            continue
        keep = [c for c in kids if not c.get("_empty")]
        for c in keep:
            c.pop("_empty", None)
            stack.append(c)
        if len(keep) != len(kids):
            stat["group_del"] += len(kids) - len(keep)
            if not DRY:
                cur["ks"] = keep

    for n in walk(tree):
        u = n.get("u") or ""
        if u:
            h = urlparse(u).netloc.lower()
            if any(a in h for a in AGG_HOST):
                stat["agg_del"] = stat.get("agg_del", 0) + 1
                if not DRY:
                    n["s"] = (f"{n.get('s') or ''}｜p231: 聚合站({{h}})非官网，"
                              f"清除（原 {u[:60]}）")
                    n["u"] = ""
                else:
                    print("  AGG-DEL", n.get("n"), u[:70])
                continue
            u2 = norm_url(u)
            if u2 != u:
                stat["url_clean"] += 1
                if not DRY:
                    n["u"] = u2
        # 子节点去重（同名同 URL）
        kids = n.get("ks")
        if kids:
            seen = set()
            keep = []
            for c in kids:
                nm = (c.get("n") or "").strip()
                cu = (c.get("u") or "").strip().rstrip("/")
                if not nm and not cu and not (c.get("ks")):
                    stat["empty_del"] += 1
                    continue
                key = (nm, cu)
                if nm and key in seen:
                    stat["dup_del"] += 1
                    continue
                seen.add(key)
                keep.append(c)
            if len(keep) != len(kids) and not DRY:
                n["ks"] = keep

    for k, e in list(reg.items()):
        u = (e.get("u") or "")
        u2 = norm_url(u)
        if u2 != u and not DRY:
            e["u"] = u2
            stat["url_clean"] += 1

    print("p231:", ", ".join(f"{k}={v}" for k, v in stat.items()),
          "（DRY 未写库）" if DRY else "")
    if not DRY and any(stat.values()):
        d = os.path.join(ROOT, "backups", TODAY)
        os.makedirs(d, exist_ok=True)
        ts = datetime.datetime.now().strftime("%H%M%S")
        shutil.copy2(TREE_F, os.path.join(d, f"tree_before_p231_{ts}.json"))
        shutil.copy2(REG_F, os.path.join(d, f"registry_before_p231_{ts}.json"))
        json.dump(tree, open(TREE_F, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        json.dump(reg, open(REG_F, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("  已写 tree.json / site_registry.json")


if __name__ == "__main__":
    main()
