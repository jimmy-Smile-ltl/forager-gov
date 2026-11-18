#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""p238 市级五系统补采（2026-11-17，用户「县级缺失太严重」配套：市级同病）。

现状（tree.json 实测）：市人大 67 缺、市政协 119 缺（345 个市级节点），
市监委 85 缺、市人民检察院 35 缺。县级补采机器（p223/p235/p237）只覆盖
COUNTY_C 县级节点，市级并列机关从未跑过任何补采轮——本脚本补上这一层。

复用 p223 的全部校验器与四档渠道（task 结构与县级完全一致，只是把
county=市级节点、parent=省级节点）：
  S1 上级（省）同系统官网名录   L1
  S2 本级市政府门户导航         L2
  S3 同级同系统（省内其他市站） L1
  S4 SERP 兜底 + 严格 title 验证 L3

用法：
  cd data && uv run python p238_city_5sys_fill.py --dry
  cd data && uv run python p238_city_5sys_fill.py --stage s1,s2
  cd data && uv run python p238_city_5sys_fill.py --stage s4 --limit 50
"""
import datetime
import json
import os
import re
import shutil
import sys
from collections import Counter

DATA = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(DATA)
sys.path.insert(0, DATA)
sys.path.insert(0, os.path.join(ROOT, "util"))
import p223_county_5sys_fill as P  # noqa: E402

TREE_F = os.path.join(DATA, "tree.json")
REG_F = os.path.join(DATA, "site_registry.json")
STATE_F = os.path.join(DATA, "p238_state.json")
TODAY = datetime.date.today().isoformat()
DRY = "--dry" in sys.argv

# 市级节点名 → 复用县级校验器键（ORG5/ORG_PATH/PARENT_ORG 全部按县级键定义）
CITY_ORGS = {
    "市人民法院": "县人民法院",
    "市人民检察院": "县人民检察院",
    "市人大": "县人大",
    "市政协": "县政协",
    "市监委": "县监委",
}
CITY_L = ("市", "地级区")
# 省站上的「市院/市人大简介」栏目路径（不是机构官网；市子站 /subsite/ 不算）
PROFILE_PATH = re.compile(r"(syjs|sjyjj|jianjie|jjgk|jgjj|/jj/|/gk/)", re.I)
# 政府门户的信息公开/预决算目录页（实测：石嘴山市政协 ← /zfxxgkml/czyjsgk/…、
# 固原市政协 ← /zwgk/bmxxgkml/…、黔西南州政协 ← /bmyjsjsgjf/dqbm/zzxb/）
XXGK_PATH = re.compile(r"(czyjsgk|bmyjsjsgjf|bmxxgkml|zfxxgkml|xxgkml|"
                       r"qtbmxxgk|dwzc|dwgy|bgt/list|/list_\d+\.)", re.I)
# 省站上的市州频道栏目（HTML 频道目录，不是市机构官网）
PROV_COLUMN = re.compile(r"/(html|col|channel)/(gsdb|xwzx|zwgk|szdt)/", re.I)


def collect_city(tree):
    blk = next(g for g in tree["ks"] if g["n"].startswith("省级"))
    tasks = []
    for prov in blk["ks"]:
        for city in prov.get("ks") or []:
            if city.get("k") != "人民政府" or city.get("l") not in CITY_L:
                continue
            grp = next((g for g in city.get("ks") or [] if g.get("c") == "并列机关"),
                       None)
            if not grp:
                continue
            for cn, cv in CITY_ORGS.items():
                o = next((x for x in grp.get("ks") or [] if x.get("n") == cn), None)
                if o is None:
                    continue
                tasks.append({"prov": prov.get("n") or "", "parent": prov,
                              "county": city, "org": o, "org_name": cv,
                              "city_org": cn,
                              "filled": bool((o.get("u") or "").strip())})
    return blk, tasks


def same_system_prov_host(prov, city_org):
    """省级同系统节点 host（用于识别「省站栏目页冒充市机构官网」）。"""
    grp = next((g for g in prov.get("ks") or [] if g.get("c") == "并列机关"), None)
    if not grp:
        return ""
    want = {"市人大": ("省人大",), "市政协": ("省政协",),
            "市监委": ("省监委", "省纪委"),
            "市人民法院": ("省高级人民法院",),
            "市人民检察院": ("省人民检察院",)}[city_org]
    for o in grp.get("ks") or []:
        if o.get("n") in want and (o.get("u") or "").strip():
            return P.urlparse(o["u"]).netloc.lower()
    return ""


def audit(tree, reg):
    """市级五系统 URL 复核：省站栏目页 / 区县机构页 / 文章页 / 栏目页。

    只清**明确错配**，其余保留并打印供人工复核。
    """
    from concurrent.futures import ThreadPoolExecutor
    blk = next(g for g in tree["ks"] if g["n"].startswith("省级"))
    blk, tasks = collect_city(tree)
    todo = [t for t in tasks if (t["org"].get("u") or "").strip()
            and any(k in (t["org"].get("s") or "")
                    for k in ("辖区链接", "导航", "互链", "SERP"))]
    prov_host = {}
    for t in tasks:
        key = (t["prov"], t["city_org"])
        if key not in prov_host:
            prov_host[key] = same_system_prov_host(t["parent"], t["city_org"])
    print(f"p238 审计：待复核 {len(todo)} 条（市级五系统）")

    def _own_root(t, u, pu, host, tt):
        """子页是否在机构**自有站点**上（域名含机构特征 + 标题带本市名）。
        是 → 返回站点根（归一，不清空）。"""
        feat = P.ORG5[t["org_name"]]["feat"]
        b0 = P.geo_base(t["county"].get("n") or "")
        if host.startswith("m."):
            return ""          # 移动版域是省/市站的镜像，不是机构自有站
        if tt and b0 and b0 in tt and re.search(feat, host, re.I):
            return f"__root__:{pu.scheme}://{pu.netloc}/"
        return ""

    def check(t):
        u = (t["org"].get("u") or "").strip()
        pu = P.urlparse(u)
        host = pu.netloc.lower()
        path = pu.path or "/"
        ph = prov_host.get((t["prov"], t["city_org"])) or ""
        if P.LOGIN_PATH.search(u):
            return t, "财政/领导/后台类栏目"
        if XXGK_PATH.search(path):
            return t, "信息公开/预决算目录页"
        if ph and host == ph and PROV_COLUMN.search(path):
            return t, "省级站市州频道栏目页"
        if re.search(r"/(m|laws|mobile)\.html?$", path, re.I):
            # 12388 子站的移动版法规页 → 归一到该市举报站目录
            d = path.rsplit("/", 1)[0]
            if d and "12388.gov.cn" in host:
                return t, f"__root__:{pu.scheme}://{pu.netloc}{d}/"
            return t, "移动版模板页"
        if re.search(r"/node_\d+\.", path, re.I):
            r = _own_root(t, u, pu, host, P.page_title(u) or "")
            return t, r or "CMS 栏目页(node_)"
        if (P.NEWS_PATH.search(u) or P.NEWS_QUERY.search(u)) \
                and not P.CHANNEL_OK.search(u):
            return t, "文章/新闻路径"
        if P.LEADER_PATH.search(u) or P.BAD_COLUMN.search(u):
            # 机构**自有站点**的领导/简介子页 → 归一到站点根（不是清空）
            r = _own_root(t, u, pu, host, P.page_title(u) or "")
            return t, r or "财政/领导/后台类栏目"
        # 只清「简介/概况」类栏目页；省站下的**市子站**（/subsite/、/aksjcy/）
        # 是该市机构的真实官方入口，保留
        if ph and host == ph and path not in ("", "/") \
                and PROFILE_PATH.search(path):
            return t, f"省级同系统站简介栏目({ph})"
        tt = P.page_title(u) or ""
        if tt:
            if P.TITLE_BAD.search(tt.replace("政治协商会议", "")) \
                    or P.KIND_BAD.search(tt):
                r = _own_root(t, u, pu, host, tt)
                if r:
                    return t, r
                bad = P.TITLE_BAD.search(tt.replace("政治协商会议", ""))
                if bad:
                    return t, f"业务/简介栏目页 title={tt[:28]}"
                return t, f"领导/建议类栏目({P.KIND_BAD.search(tt).group(1)})"
            b = P.geo_base(t["county"].get("n") or "")
            # 市本级机构却落到「本市某区/县」的机构站（云浮市政协 ← 云城区政协）
            # 注意「XX地区」是地级区划名，不能当成「区」机构
            if b and re.search(re.escape(b) + r"市?[一-龥]{1,8}(?<!地)(区|县|旗)"
                               r"(人民|政协|人大|纪委|法院|检察)", tt):
                if not re.search(re.escape(b) + r"市?人民(代表|政府)", tt):
                    return t, f"区县机构页 title={tt[:28]}"
        return t, ""

    wrong = []
    with ThreadPoolExecutor(8) as ex:
        for t, why in ex.map(check, todo):
            if why:
                wrong.append((t, why))
    for t, why in wrong:
        print(f"  AUDIT-{why[:26]:<26} {t['prov']}/{t['county'].get('n')}/{t['city_org']}"
              f" {(t['org'].get('u') or '')[:58]}")
    if not DRY and wrong:
        d = os.path.join(ROOT, "backups", TODAY)
        os.makedirs(d, exist_ok=True)
        ts = datetime.datetime.now().strftime("%H%M%S")
        shutil.copy2(TREE_F, os.path.join(d, f"tree_before_p238audit_{ts}.json"))
        nclear = nroot = 0
        for t, why in wrong:
            u = t["org"].get("u") or ""
            if why.startswith("__root__:"):
                root = why.split(":", 1)[1]
                t["org"]["u"] = root
                t["org"]["s"] = (f"{t['org'].get('s') or ''}｜p238 审计: 子页归一到"
                                 f"站点根（原 {u[:50]}）")
                nroot += 1
                continue
            t["org"]["s"] = f"{t['org'].get('s') or ''}｜p238 审计: {why}，清除（原 {u[:50]}）"
            t["org"]["u"] = ""
            nclear += 1
        json.dump(tree, open(TREE_F, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        print(f"p238 审计已清除 {nclear} 条、归一站点根 {nroot} 条")
    return len(wrong)


def main():
    tree = json.load(open(TREE_F, encoding="utf-8"))
    reg = json.load(open(REG_F, encoding="utf-8"))
    st = {}
    if os.path.exists(STATE_F):
        try:
            st = json.load(open(STATE_F, encoding="utf-8"))
        except Exception:  # noqa: BLE001
            st = {}
    blk, tasks = collect_city(tree)
    gap = [t for t in tasks if not t["filled"]]
    c = Counter(t["city_org"] for t in gap)
    print(f"p238 市级五系统：全部 {len(tasks)}，待补 {len(gap)} {dict(c)}")
    if not gap:
        return
    if DRY:
        P.DRY = True          # apply_fill 读的是 p223 模块级开关
    prov_map = {p.get("n") or "": p for p in blk["ks"]}
    P.ALL_PROV_BASES.update(P.prov_base(x) for x in prov_map if P.prov_base(x))
    city_bases = {P.geo_base(t["county"].get("n") or "") for t in tasks}
    city_bases.discard("")
    name_prov = {}
    for t in tasks:
        name_prov.setdefault(t["county"].get("n"), set()).add(t["prov"])
    dup_names = {n for n, ps in name_prov.items() if len(ps) > 1}

    stages = os.environ.get("P238_STAGE", "")
    for a in sys.argv:
        if a.startswith("--stage"):
            stages = a.split("=", 1)[1] if "=" in a else stages
    if "--stage" in sys.argv:
        i = sys.argv.index("--stage")
        if i + 1 < len(sys.argv):
            stages = sys.argv[i + 1]
    if "--audit" in sys.argv:
        stages = "audit"
    stages = [x for x in str(stages).split(",") if x] or ["s1", "s2", "s3", "s4"]
    limit = int(os.environ.get("P238_LIMIT", "0")) or None
    only = [x for x in (os.environ.get("P238_ORG") or "").split(",") if x]
    if only:
        pending = [t for t in gap if t["city_org"] in only]
    else:
        pending = list(gap)

    filled0 = 0
    if "audit" in stages:
        audit(tree, reg)
        return
    if "s1" in stages:
        filled0 += P.run_s1(pending, reg, dup_names, st, prov_map, limit=limit)
    if "s2" in stages:
        filled0 += P.run_s2(pending, reg, dup_names, st, city_bases, limit=limit)
    if "s3" in stages:
        filled0 += P.run_s3(pending, reg, dup_names, st, limit=limit)
    if "s4" in stages:
        # SERP 变体轮实测两类漏网：
        #  ① 区县级机构顶替市级（云浮市政协 ← 云浮市云城区政协）
        #  ② 门户「两会专题/政协报道」「人大政协、民主党派」类目页冒充机构页
        _orig_apply = P.apply_fill

        def _city_apply(reg, task, u, src, level, dup_names):
            if task.get("city_org"):
                tt = P.page_title(u) or ""
                b = P.geo_base(task["county"].get("n") or "")
                if b and re.search(re.escape(b) + r"市?[一-龥]{1,8}(?<!地)(区|县|旗)"
                                   r"(人民|政治协商|政协|人大|纪委|法院|检察)", tt):
                    print(f"  REJECT 区县机构顶替 {tt[:34]} {u[:60]}")
                    return False
                if "报道" in tt or "专题" in tt or ("人大" in tt and "政协" in tt):
                    print(f"  REJECT 门户类目/专题页 {tt[:34]} {u[:60]}")
                    return False
            return _orig_apply(reg, task, u, src, level, dup_names)

        P.apply_fill = _city_apply
        os.environ.setdefault("P223_S4_NS", "s4city")
        filled0 += P.run_s4(pending, reg, dup_names, st, limit=limit)
        P.apply_fill = _orig_apply

    now_gap = sum(1 for t in tasks if not (t["org"].get("u") or "").strip())
    print(f"p238 本轮 filled: {filled0}；市级五系统剩余缺口 {now_gap}/{len(tasks)}")
    if not DRY and filled0:
        d = os.path.join(ROOT, "backups", TODAY)
        os.makedirs(d, exist_ok=True)
        ts = datetime.datetime.now().strftime("%H%M%S")
        for f, tag in ((TREE_F, "tree"), (REG_F, "registry")):
            shutil.copy2(f, os.path.join(d, f"{tag}_before_p238_{ts}.json"))
        json.dump(tree, open(TREE_F, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        json.dump(reg, open(REG_F, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        json.dump(st, open(STATE_F, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        print("  已写 tree.json / site_registry.json / p238_state.json")


if __name__ == "__main__":
    main()
