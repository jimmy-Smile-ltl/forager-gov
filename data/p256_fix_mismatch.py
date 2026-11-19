# -*- coding: utf-8 -*-
"""P256: 2026-11-19 数据巡检修复（四组问题）。

起因：用户指令「检查网站数据，优化网站布局，丰富信息展示」后的数据审计。

一、条视图同父重名去重（14 个）
   - 佛山市中级人民法院 ×2（广东省高院下）：一条是本局官网，另一条是省法院
     网站的改革案例文章页（/content/post_*.html）→ 删文章页，保官网。
   - 江苏 13 个市烟草专卖局 ×2：一条是省局网站各市栏目（col/colNNN/index.html，
     p173 真实提取），另一条是 xzsp.js.tobacco.gov.cn 的办事指南 SPA
     （#/guide?areaCode=...，无来源留痕）→ 删 SPA，保栏目页。
   打分规则：文章页 -10、SPA hash 页 -2、无来源 -4，保留高分者。

二、清除本地机构节点上的「上级/平台」错配 URL（55 个）
   省级/市级 dept 节点 URL 指向中央部委根域（ndrc/mnr/sasac/neac/cnipa/nhc/
   forestry/mps 等）或省级政务服务网根域的，一律置 u=""（列名留痕），m 记原
   URL。这些是门户导航把「国家部委」链接当成市局官网提取的错配，按 CLAUDE.md
   「门户/上级站点是错配」「宁缺毋滥」处理。
   保留合法形态：csrc.gov.cn/{省}/、nfra.gov.cn/branch/{省}/、nra.gov.cn/zzjg/
   jgj/{局}/、xx.caac.gov.cn、{省}.chinatax.gov.cn、fj.mof.gov.cn 等下级专属域名。

三、组名计数与脏节点
   - 省政府部门（N）组名按实际子节点数重算（河北 39→38、浙江 29→27、
     四川 47→46、新疆 47→46）。
   - 删除浙江「网站声明」脏节点（页脚声明被当成部门，URL 是 art 文章页）。

四、registry 同步
   - 二中被清 URL 的节点：按「URL 相同 + 名称匹配」找到对应 registry 条目，
     u 置空、status="nosite"、留痕，保留其余字段（xxgk 等）。
   - 省政府* 类别中 URL 明显错配的条目（指向中央部委根域或其他省份站点）：
     树里有该部门的正常 URL 就用树值回填（u/status/source/verified_at），
     树里没有 URL 就把错误 URL 清空。
"""
import json
import re
from urllib.parse import urlparse

TODAY = "2026-11-19"

# ---- 中央部委/国家级机关根域（本地机构节点用它就是错配）----
CENTRAL_ROOTS = {
    "ndrc.gov.cn", "sasac.gov.cn", "mnr.gov.cn", "cnipa.gov.cn", "neac.gov.cn",
    "nhc.gov.cn", "stats.gov.cn", "mof.gov.cn", "miit.gov.cn", "mot.gov.cn",
    "mwr.gov.cn", "mee.gov.cn", "moa.gov.cn", "mohurd.gov.cn", "mofcom.gov.cn",
    "mct.gov.cn", "mem.gov.cn", "mca.gov.cn", "moj.gov.cn", "moe.gov.cn",
    "most.gov.cn", "mod.gov.cn", "samr.gov.cn", "cac.gov.cn", "nrta.gov.cn",
    "sport.gov.cn", "caac.gov.cn", "gacc.gov.cn", "chinatax.gov.cn",
    "mps.gov.cn", "mfa.gov.cn", "nsfc.gov.cn", "cnsa.gov.cn",
    "forestry.gov.cn", "nea.gov.cn", "nra.gov.cn", "sara.gov.cn",
    "caea.gov.cn", "chinamine-safety.gov.cn", "nmpa.gov.cn", "nfsa.gov.cn",
    "mva.gov.cn", "pbc.gov.cn", "audit.gov.cn", "csrc.gov.cn",
    "nfra.gov.cn", "customs.gov.cn", "gjxfj.gov.cn", "119.gov.cn", "cea.gov.cn",
    "nhsa.gov.cn", "ndcpa.gov.cn", "natcm.gov.cn", "ggj.gov.cn", "lswz.gov.cn",
    "gov.cn",
}
PLATFORM_ROOTS = {"hbzwfw.gov.cn", "sczwfw.gov.cn", "gjzwfw.gov.cn"}

# 省级行政区 → 域名里的完整拼音 token（按 host label 精确匹配，避免
# 山西 shanxi / 陕西 shaanxi 的子串互伤）
PROV_TOKENS = [
    ("北京市", "beijing"), ("天津市", "tianjin"), ("河北省", "hebei"),
    ("山西省", "shanxi"), ("内蒙古自治区", "neimenggu"), ("辽宁省", "liaoning"),
    ("吉林省", "jilin"), ("黑龙江省", "heilongjiang"), ("上海市", "shanghai"),
    ("江苏省", "jiangsu"), ("浙江省", "zhejiang"), ("安徽省", "anhui"),
    ("福建省", "fujian"), ("江西省", "jiangxi"), ("山东省", "shandong"),
    ("河南省", "henan"), ("湖北省", "hubei"), ("湖南省", "hunan"),
    ("广东省", "guangdong"), ("广西壮族自治区", "guangxi"), ("海南省", "hainan"),
    ("重庆市", "chongqing"), ("四川省", "sichuan"), ("贵州省", "guizhou"),
    ("云南省", "yunnan"), ("西藏自治区", "xizang"), ("陕西省", "shaanxi"),
    ("甘肃省", "gansu"), ("青海省", "qinghai"), ("宁夏回族自治区", "ningxia"),
    ("新疆维吾尔自治区", "xinjiang"),
]


def prov_of(kn):
    for name, tok in PROV_TOKENS:
        if kn.startswith(name):
            return name, tok
    return None, None


def host_labels(u):
    h = (urlparse(u).hostname or "").lower()
    return h.split(".")

# 保留：下级专属域名（本地机构在上级站点上的合法页面）
KEEP_HOST_RE = re.compile(
    r"^(?:\w+\.)?(?:csrc|nfra|nra)\.gov\.cn$"      # 证监局/金融监管局/铁路监管局
    r"|^\w+\.caac\.gov\.cn$"                        # 民航地区管理局
    r"|^\w+\.chinatax\.gov\.cn$"                    # 各省税务局
    r"|^\w+\.mof\.gov\.cn$"                         # 财政部监管局
    r"|^(?:scsm|snsm)\.mnr\.gov\.cn$"               # 四川/陕西测绘局
)

LEVELS_LOCAL = {"省", "市", "地级区", "县", "特别行政区", "港澳台"}
ARTICLE_RE = re.compile(
    r"/content/|/post_\d+|/art(icle)?(_\d+)?/\d{4}/|/art_\d+|/t\d{8,10}_\d+|"
    r"/c_\d+\.html?$|/\d{4}/\d{2}/\d{2}/")


def walk(n, path=()):
    yield n, path
    for k in n.get("ks") or []:
        yield from walk(k, path + (n,))


def host_root(u):
    try:
        h = (urlparse(u).hostname or "").lower()
    except ValueError:
        return ""
    return h[4:] if h.startswith("www.") else h


def is_bad_local_url(u):
    h = host_root(u)
    if not h:
        return False
    if KEEP_HOST_RE.match(h):
        return False
    return h in CENTRAL_ROOTS or h in PLATFORM_ROOTS


def score(u, s):
    sc = 0
    if not ARTICLE_RE.search(u or ""):
        sc += 10
    if "#/" not in (u or ""):
        sc += 2
    if s:
        sc += 4
    return sc


def main(dry=False):
    tree = json.load(open("tree.json", encoding="utf-8"))
    reg = json.load(open("site_registry.json", encoding="utf-8"))
    stat = {"dedupe": [], "cleared": [], "group": [], "junk": [], "reg_clear": 0,
            "reg_fill": 0, "reg_fill_rows": [], "reg_clear_rows": []}

    # ---------- 一、条树同父重名去重 ----------
    tiao = next(g for g in tree["ks"] if g["n"].startswith("条"))
    for parent, _path in walk(tiao):
        kids = parent.get("ks") or []
        by_name = {}
        for c in kids:
            by_name.setdefault(c.get("n"), []).append(c)
        for nm, cs in by_name.items():
            if not nm or len(cs) < 2:
                continue
            cs.sort(key=lambda c: -score(c.get("u"), c.get("s")))
            keep = cs[0]
            for c in cs[1:]:
                kids.remove(c)
                stat["dedupe"].append((parent.get("n"), nm, c.get("u", ""),
                                       keep.get("u", "")))

    # ---------- 二、组名计数与脏节点 ----------
    prov = next(g for g in tree["ks"] if g["n"].startswith("省级"))
    central = next(g for g in tree["ks"] if g["n"].startswith("中央"))
    # 中央机构名（含其官网 host）：市级/县级部门列表里出现同名 + 同 host 的节点，
    # 是门户导航把「国务院/中央部委」链接当成市局提取的，删节点而不是列名
    cnames = {}
    for c, _ in walk(central):
        if c is central or not c.get("u"):
            continue
        cnames.setdefault(c.get("n"), host_root(c["u"]))
    JUNK_NAME_RE = re.compile(r"^(中央人民政府|中华人民共和国中央|中国共产党第|国务院$)")

    def is_junk_dept(c):
        cn = (c.get("n") or "").strip()
        cu = c.get("u") or ""
        if JUNK_NAME_RE.match(cn):
            return True
        return bool(cn in cnames and cu and host_root(cu) == cnames[cn])

    junk_keys = []          # 供 registry 删除
    for p in prov["ks"]:
        for n, _path in walk(p):
            if n.get("l") not in ("省", "市", "地级区", "县"):
                continue
            gname = n.get("n") or ""
            if not re.search(r"(省政府部门|市级政府部门|县政府部门)", gname):
                continue
            kids = n.get("ks") or []
            if not kids:
                continue
            for c in list(kids):
                cn = (c.get("n") or "").strip()
                cu = c.get("u") or ""
                if gname.startswith("省政府") and (
                        cn in ("网站声明", "网站地图", "联系我们", "关于我们") or
                        (not c.get("ks") and ARTICLE_RE.search(cu)
                         and re.search(r"/art/|/content/|/post_", cu))):
                    kids.remove(c)
                    stat["junk"].append((p.get("n"), cn, cu))
                    continue
                if not gname.startswith("省政府") and is_junk_dept(c):
                    kids.remove(c)
                    stat["junk"].append((p.get("n"), cn, cu))
                    junk_keys.append((cn, cu))

    # 组名计数：所有「…部门（N）」按实际子节点数重算
    for p in prov["ks"]:
        for n, _path in walk(p):
            m = re.match(r"^(.*部门)（(\d+)）$", n.get("n") or "")
            if not m or not n.get("ks"):
                continue
            if int(m.group(2)) != len(n["ks"]):
                old = n["n"]
                n["n"] = f"{m.group(1)}（{len(n['ks'])}）"
                stat["group"].append((p.get("n"), old, n["n"]))

    # ---------- 三、清除本地节点上的错配 URL ----------
    for n, path in walk(tree):
        if n.get("l") not in LEVELS_LOCAL:
            continue
        u = (n.get("u") or "").strip()
        if not u or not is_bad_local_url(u):
            continue
        # 若同节点只有专栏、没有自己的站，也照清；x 是信息公开专栏，口径独立
        n["u"] = ""
        note = f"p256 清除错配URL（原指向 {host_root(u)}）"
        n["m"] = (n.get("m") + "；" + note) if n.get("m") else note
        stat["cleared"].append((n.get("l"), n.get("n"), u,
                                " / ".join(x.get("n", "") for x in path[-2:])))

    # ---------- 三b、信息公开专栏(x)同样错配的清除 ----------
    # x 口径只适用于政府机关；指向中央部委/中国政府网的「信息公开」入口
    # （如 内蒙古林草局→国家林草局政府公开、岳池县→gov.cn 政策页）不是本机
    # 构的专栏，一律清空留痕。
    cleared_x = []
    for n, path in walk(tree):
        if n.get("l") not in LEVELS_LOCAL:
            continue
        x = (n.get("x") or "").strip()
        if not x or not is_bad_local_url(x):
            continue
        n["x"] = ""
        note = f"p256 清除错配专栏（原指向 {host_root(x)}）"
        n["m"] = (n.get("m") + "；" + note) if n.get("m") else note
        cleared_x.append((n.get("n"), x))
        stat.setdefault("cleared_x", []).append((n.get("n"), x))
    stat["reg_x"] = 0
    for k, v in reg.items():
        x = (v.get("xxgk") or "").strip()
        if not x or not is_bad_local_url(x):
            continue
        kn = k.split("|", 1)[-1]
        if any(kn.endswith(nm) or (v.get("n") or "") == nm for nm, _ in cleared_x):
            v["xxgk"] = ""
            v["xxgk_src"] = "p256 清除错配专栏"
            stat["reg_x"] += 1

    # ---------- 四、registry 同步 ----------
    cleared_urls = {}
    for _l, nm, u, _p in stat["cleared"]:
        cleared_urls.setdefault(u, []).append(nm)

    # 4c. 脏节点对应的 registry 条目整条删除（中央机构名混入市/县部门列表）
    junk_names = {nm for nm, _u in junk_keys if nm}
    del_keys = [k for k in reg
                if k.startswith(("市级政府部门", "县政府部门", "省政府"))
                and k.split("|", 1)[-1].endswith(tuple(junk_names))] if junk_names else []
    for k in del_keys:
        reg.pop(k, None)
    stat["reg_junk"] = len(del_keys)

    for k, v in list(reg.items()):
        u = (v.get("u") or "").strip()
        if not u:
            continue
        kn = k.split("|", 1)[-1]
        # 4a. 被清 URL 的条目（名称精确匹配，避免「统计局」误伤「国家统计局」）
        if u in cleared_urls:
            hit = any(kn == nm or (v.get("n") or "") == nm
                      for nm in cleared_urls[u])
            if hit:
                v["u"] = ""
                v["status"] = "nosite"
                v["verified_at"] = TODAY
                v["source"] = "p256 清除错配URL（原指向中央部委/政务服务网）"
                stat["reg_clear"] += 1
                stat["reg_clear_rows"].append((k, u))
                continue
        # 4b. 省政府* 条目 URL 明显错配 → 用树值回填或清空
        if k.startswith("省政府"):
            pname, ptok = prov_of(kn)
            if not pname:
                continue
            bad = is_bad_local_url(u)
            if not bad:
                labels = host_labels(u)
                for _n2, tok2 in PROV_TOKENS:
                    if tok2 != ptok and tok2 in labels:
                        bad = True
                        break
            if not bad:
                continue
            p = next((x for x in prov["ks"] if x["n"] == pname), None)
            tgt = None
            if p:
                for c, _ in walk(p):
                    if c is p:
                        continue
                    cn = c.get("n") or ""
                    if cn and (cn == (v.get("n") or "") or kn.endswith(cn)) \
                            and c.get("u") and not is_bad_local_url(c["u"]):
                        tgt = c
                        break
            if tgt:
                v["u"] = tgt["u"]
                v["status"] = "ok"
                v["verified_at"] = TODAY
                v["source"] = "p256 按树回填（原 registry URL 跨省/中央错配）"
                stat["reg_fill"] += 1
                stat["reg_fill_rows"].append((k, u, tgt["u"]))
            else:
                v["u"] = ""
                v["status"] = "nosite"
                v["verified_at"] = TODAY
                v["source"] = "p256 清除错配URL（原指向中央部委/其他省份站点）"
                stat["reg_clear"] += 1
                stat["reg_clear_rows"].append((k, u))

    # ---------- 报告 ----------
    print(f"一、条树去重 {len(stat['dedupe'])}:")
    for x in stat["dedupe"]:
        print("   ", x[0], "›", x[1], "| 删", x[2][:60], "| 留", x[3][:60])
    print(f"三、清除错配 URL {len(stat['cleared'])}:")
    for x in stat["cleared"]:
        print("   ", x[0], x[1], "|", x[2][:70], "|", x[3])
    print(f"二、组名改 {len(stat['group'])}  脏节点删 {len(stat['junk'])}:")
    for x in stat["group"]:
        print("   ", x[0], x[1], "→", x[2])
    for x in stat["junk"]:
        print("   ", x[0], x[1], x[2][:60])
    print(f"三b、清除错配专栏(x) {len(stat.get('cleared_x') or [])}:")
    for nm, x in stat.get("cleared_x") or []:
        print("   ", nm, "|", x[:80])
    print(f"四、registry 删除脏条目 {stat['reg_junk']}，清空 {stat['reg_clear']}，"
          f"回填 {stat['reg_fill']}，清空专栏 {stat['reg_x']}")

    for k, old, new in stat["reg_fill_rows"]:
        print("   回填", k, "|", old[:55], "→", new[:55])
    for k, old in stat["reg_clear_rows"]:
        print("   清空", k, "|", old[:70])
    if dry:
        print("--dry 干跑，未写盘")
        return
    with open("tree.json", "w", encoding="utf-8") as f:
        json.dump(tree, f, ensure_ascii=False, indent=1)
        f.write("\n")
    with open("site_registry.json", "w", encoding="utf-8") as f:
        json.dump(reg, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print("已写 tree.json / site_registry.json")


if __name__ == "__main__":
    import sys
    main(dry="--dry" in sys.argv)
