"""p243 —— 同一 URL 挂在多个不同地区机构上的裁决（跨地区串站清除）。

p240 按「节点自己的地区」逐条核查，标题只含县名的站对多个同名区县都能通过：
实测 `www.szq.ls-jcy.gov.cn`（乐山市市中区人民检察院）同时挂在 济南市/枣庄市/
内江市/乐山市 四个「市中区」节点上；`www.dtsrd.gov.cn`（大同市人大常委会）
挂在大庆市大同区人大节点上；`www.haicheng.jcy.gov.cn`（海城市）挂在北海市
海城区节点上——都是同名区县串站。

做法：
  1. 五系统节点（人大/政协/法院/检察/监委/纪委，排除部门/政府部门）按 URL 分组；
  2. 组内出现 ≥2 个不同「地区身份」即冲突组。身份 = 省 + 市 + 归一地名 + 机构类型：
     归一地名去掉民族修饰（大通回族土族自治县 → 大通县），同一身份的块/条双视图
     与「市级路径缺失城市」的结构变体合并，不算冲突；
  3. 用 p240 已抓的 title/snippet（缺则现抓）给每个身份打分：标题命中身份地区链
     全名 3/2/1 分（最深→最浅）、snippet 减半；同位置被更长候选词覆盖的短词
     不计分（「和县」⊂「太和县」）。**先按标题判**，标题分并列（如四个「市中区」
     都命中标题）时再用 snippet 分判；
  4. 唯一最高分身份视为真实归属，标题分/snippet 分均为 0 的身份节点清空 URL
     留名，并同步 registry；并列最高/全无证据的组不动（人工复核）。

用法（在 data/ 目录）：
    uv run python p243_dup_url_adjudicate.py            # 只出报告
    uv run python p243_dup_url_adjudicate.py --apply    # 清除（写前备份）
环境变量：P243_WORKERS（默认 4）
"""
import datetime
import json
import os
import re
import shutil
import sys
import tempfile
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit, urlunsplit

import p240_full_url_verify as V
import p241_wrong_url_backfill as P

DATA = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(DATA)
TREE_F = os.path.join(DATA, "tree.json")
REG_F = os.path.join(DATA, "site_registry.json")
P240_F = os.path.join(DATA, "p240_results.jsonl")
REPORT_F = os.path.join(DATA, "p243_report.json")
TODAY = datetime.date.today().isoformat()
APPLY = "--apply" in sys.argv
WORKERS = int(os.environ.get("P243_WORKERS", "4"))

FIVE_KINDS = {"并列机关", "检察院系统", "法院系统", "人大系统", "政协系统",
              "纪委系统", "基层法院", "省级检察院", "省级人大", "省级政协",
              "省级纪委监委", "省级法院", "人民政府"}
FIVE_NAME = ("人民检察院", "人民法院", "人大", "政协", "监委", "纪委")
ETHNIC = re.compile(
    r"(蒙古|回|藏|维吾尔|苗|彝|壮|布依|朝鲜|满|侗|瑶|白|土家|哈尼|哈萨克|傣|"
    r"黎|傈僳|佤|畲|高山|拉祜|水|东乡|纳西|景颇|柯尔克孜|土|达斡尔|仫佬|羌|"
    r"布朗|撒拉|毛南|仡佬|锡伯|阿昌|普米|塔吉克|怒|乌孜别克|俄罗斯|鄂温克|"
    r"德昂|保安|裕固|京|塔塔尔|独龙|鄂伦春|赫哲|门巴|珞巴|基诺)+族")


def canon_place(full):
    """地名归一：剥民族修饰、自治区/自治县收敛（大通回族土族自治县→大通县）。"""
    s = ETHNIC.sub("", full or "")
    for a, b in (("自治县", "县"), ("自治州", "州"), ("自治旗", "旗"),
                 ("自治区", ""), ("自治", "")):
        s = s.replace(a, b)
    return s or (full or "")


def norm_u(u):
    return (u or "").strip().rstrip("/").lower()


def swap_scheme(u):
    p = urlsplit(u)
    sch = "http" if p.scheme == "https" else "https"
    return urlunsplit((sch, p.netloc, p.path or "/", p.query, ""))


def is_five(rec):
    if rec["k"] in ("政府部门", "部门", "分组"):
        return False
    if rec["k"] in FIVE_KINDS:
        return True
    return any(w in rec["name"] for w in FIVE_NAME)


def place_of2(name):
    """p240 place_of 的补丁：裸「XX州 / XX地区 / XX盟」不在 ADMIN_SUFFIX 里，
    「昌吉州中级人民法院」会认不出地名、退化成上级「新疆」——按已知基底补认。"""
    p = V.place_of(name)
    if p:
        return p
    n = V.PLACE_PREFIX.sub("", re.sub(r"[（(][^）)]*[）)]", "", name or "")).strip()
    prev = None
    while prev != n:
        prev = n
        n = V.ROLE_TAIL.sub("", n).strip("·、 ")
    for suf in ("州", "地区", "盟"):
        if n.endswith(suf) and len(n) > len(suf) and n[:-len(suf)] in V.ALL_BASE_SET:
            return n, n[:-len(suf)]
    return None


def deep_of(rec):
    seq = []
    for nm in list(rec["path"]) + [rec["name"]]:
        p = place_of2(nm)
        if p and p[0] not in seq:
            seq.append(p[0])
    if not seq:
        return ""
    deep = seq[-1]
    city = city_of(rec)
    # 复合名（「荆州市沙市区」）取末段区划，否则与「沙市区」认不成同一个地名
    if city and deep.startswith(city) and len(deep) > len(city):
        deep = deep[len(city):]
    return deep


def city_of(rec):
    for nm in reversed(list(rec["path"]) + [rec["name"]]):
        p = place_of2(nm)
        if p and V.is_city_level(p[0]):
            return p[0]
    return ""


def place_base(name):
    """地名基底（p240 口径）：沈阳检察院/沈阳市 → 沈阳；荆州市沙市区 → 沙市。"""
    p = place_of2(name or "")
    return p[1] if p else canon_place(name)


def kinds(rs):
    """身份里各地名的地名形态集合。

    prov  = 只解析到省（未解析，不可据此清除）
    pref  = 地级（自治州/州/地区/盟）
    city  = 名字带「市」（地级市或县级市，单看名字分不出）
    county= 区/县/旗/自治县
    """
    out = set()
    for r in rs:
        d = deep_of(r)
        if not d:
            continue
        p = place_of2(d)
        full = p[0] if p else d
        if V.is_real_prov(full):
            out.add("prov")
        elif full.endswith(("自治州", "地区", "盟")):
            out.add("pref")
        elif full.endswith("州"):
            # 裸「XX州」歧义：锦州/广州/惠州是「XX市」的简称，昌吉州才是地级简称。
            # 以同基底是否存在地级全名（自治州/地区/盟）为准。
            prefs = {b for f, b in V.ALL_PLACES.items()
                     if f.endswith(("自治州", "地区", "盟"))}
            out.add("pref" if p and p[1] in prefs else "city")
        elif full.endswith("市"):
            out.add("city")
        else:
            out.add("county")
    return out


def terms_for(rs):
    """身份的地区词表：最深地名（含不同写法）×3、市 ×2、省 ×1。"""
    deeps, cities, provs = [], [], []
    for r in rs:
        d = deep_of(r)
        if d and d not in deeps:
            deeps.append(d)
        c = city_of(r)
        if c and c not in cities:
            cities.append(c)
        p = r.get("prov") or ""
        if p and p not in provs:
            provs.append(p)
    terms = [(d, 3) for d in deeps]
    terms += [(c, 2) for c in cities if c not in deeps]
    terms += [(p, 1) for p in provs]
    return terms


def build_idents(recs):
    """→ [(id_key, terms, [recs])]。

    身份 = 省 + 地名基底 + 机构类型（城市另作拆分维度）：
      · 基底相同即同一地名的不同写法（沈阳检察院/沈阳市人民检察院、
        景宁畲族自治区/景宁畲族自治县、奉化市/奉化区 区划更名）并入同一身份；
      · 同省同基底出现在 ≥2 个城市时按城市拆分（济南/枣庄/乐山/内江的
        「市中区」互不合并，北海海城区/鞍山海城市靠省份+城市分开）。
    """
    buckets = defaultdict(lambda: defaultdict(list))
    for r in recs:
        deep, role = deep_of(r), V.role_of(r) or ""
        if not deep or not role:
            continue
        key = (r.get("prov") or "", place_base(deep), role)
        buckets[key][city_of(r)].append(r)
    out = []
    for key, bycity in buckets.items():
        cities = [c for c in bycity if c]
        if len(cities) <= 1:
            rs = [r for v in bycity.values() for r in v]
            out.append((key + (cities[0] if cities else "",), terms_for(rs), rs))
        else:
            for c in cities:
                rs = list(bycity[c])
                out.append((key + (c,), terms_for(rs), rs))
    return out


def spans(text, term):
    out, start = [], 0
    while True:
        i = text.find(term, start)
        if i < 0:
            return out
        out.append((i, i + len(term)))
        start = i + 1


def score_all(idents, title, snippet):
    """→ {id_key: (标题分, snippet 分)}。

    「和县」⊂「太和县」这类子串误命中：短词的命中位置若被任一更长候选词
    的命中区间覆盖，则该次不计。
    """
    all_terms = sorted({t for _, ts, _ in idents for t, _ in ts}, key=len,
                       reverse=True)
    out = {}
    for key, terms, _ in idents:
        t_score = s_score = 0
        for term, w in terms:
            for text, which in ((title, "t"), (snippet, "s")):
                longer = [sp for o in all_terms if len(o) > len(term)
                          for sp in spans(text, o)]
                hit = sum(1 for a, b in spans(text, term)
                          if not any(a < d and c < b for c, d in longer))
                if which == "t":
                    t_score += w * hit
                else:
                    s_score += w * hit
        out[key] = (t_score, s_score)
    return out


def load_p240():
    """URL → {title, snippet}（p240 全量核查已抓的页面证据）。"""
    ev = {}
    if not os.path.exists(P240_F):
        return ev
    for line in open(P240_F, encoding="utf-8"):
        try:
            d = json.loads(line)
        except Exception:
            continue
        if d.get("u"):
            ev[norm_u(d["u"])] = {"title": d.get("title") or "",
                                  "snippet": d.get("snippet") or ""}
    return ev


def evidence(u, ev):
    """优先 p240 证据；缺失或全空则现抓一次。"""
    for cand in (u, swap_scheme(u)):
        e = ev.get(norm_u(cand))
        if e and (e["title"] or e["snippet"]):
            return e
    s = P.snap(u)
    if not s:
        return {"title": "", "snippet": ""}
    r = s[0]
    return {"title": r.get("title") or "", "snippet": r.get("snippet") or ""}


def atomic(obj, path):
    d = os.path.dirname(path)
    fd, tmp = tempfile.mkstemp(dir=d, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=1)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def reg_clear(reg, name, u):
    """按 URL + 名称后匹配清空 registry（不误清别的机构条目）。"""
    hit = []
    for k, v in reg.items():
        if norm_u(v.get("u")) != norm_u(u):
            continue
        if not (v.get("n") or k.split("|")[-1]).endswith(name):
            continue
        v["u"] = ""
        v["status"] = "cleared"
        v["verified_at"] = TODAY
        v["source"] = ((v.get("source") or "")
                       + f" | p243 跨地区串站清除({TODAY})").strip(" |")
        hit.append(k)
    return hit


def allow_ok(u, deep):
    """p240 人工复核例外（区划调整/合署办公）：这个 URL 本来就是该区划的入口。"""
    for (au, ad) in V.ALLOW_OK:
        if norm_u(au) == norm_u(u) and ad == deep:
            return True
    return False


def main():
    tree = json.load(open(TREE_F, encoding="utf-8"))
    reg = json.load(open(REG_F, encoding="utf-8"))
    V.collect_all_places(tree)
    recs = V.collect_records(tree)
    ev = load_p240()

    by = defaultdict(list)
    for r in recs:
        if is_five(r):
            by[norm_u(r["u"])].append(r)

    groups = []
    for u, it in by.items():
        ids = build_idents(it)
        if len(ids) < 2:
            continue
        groups.append((u, it, ids))

    def judge(g):
        u, it, ids = g
        rs_of = {k: rs for k, _, rs in ids}
        kk = {k: kinds(rs) for k, _, rs in ids}
        e = evidence(u, ev)
        title, snippet = e["title"], e["snippet"]
        scores = score_all(ids, title, snippet)
        base = {"u": u, "title": title,
                "scores": {"/".join(k): list(v) for k, v in scores.items()},
                "keep": "", "drop": []}

        def real_drop(keys, win):
            """去掉 p240 人工复核例外 + 同一机构的结构变体（条树简称/区划更名）。

            同省同基底时只有「州/地区/盟 ↔ 同名市」才是两个机构（恩施州院 vs
            恩施市院、阿勒泰地区院 vs 阿勒泰市院）；其余（锦州检察院/锦州市人民
            检察院、奉化市/奉化区、黔西县/黔西市、隆林县/隆林各族自治县）都是
            同一机构在两个视图里的名字变体，不能清。
            """
            out = []
            for k in keys:
                if any(allow_ok(u, deep_of(r)) for r in rs_of.get(k, [])):
                    continue
                ck = kk[k] - {"prov"}
                if not ck:
                    continue     # 只解析到省 → 归属不明，不清
                if k[0] == win[0]:
                    cw = kk[win]
                    if not ("pref" in ck and "city" in cw
                            or "pref" in cw and "city" in ck):
                        continue
                out.append(k)
            return out

        tmax = max(v[0] for v in scores.values())
        smax = max(v[1] for v in scores.values())
        # 先按标题判：标题只指向一个身份时，标题分 0 的其他身份不可能是这个站
        if tmax > 0:
            tw = [k for k, v in scores.items() if v[0] == tmax]
            if len(tw) > 1:
                return {**base, "res": "tie", "why": "标题并列最高分"}
            win = tw[0]
            drop = real_drop([k for k, v in scores.items() if v[0] == 0], win)
        else:
            # 标题中性（多个同名区县站都是「XX市X区人民法院」）→ 用 snippet 判
            if smax <= 0:
                return {**base, "res": "noevi", "why": "无地区证据"}
            sw = [k for k, v in scores.items() if v[1] == smax]
            if len(sw) > 1:
                return {**base, "res": "tie", "why": "snippet 并列最高分"}
            win = sw[0]
            drop = real_drop([k for k, v in scores.items() if v[1] == 0], win)
        if not drop:
            return {**base, "res": "keep", "why": "各方均有证据",
                    "keep": "/".join(win)}
        return {**base, "res": "clear", "why": "唯一归属",
                "keep": "/".join(win), "drop": [list(k) for k in drop]}

    print(f"五系统带 URL 节点 {sum(len(v) for v in by.values())}"
          f" / 唯一 URL {len(by)}；身份冲突组 {len(groups)}")
    with ThreadPoolExecutor(WORKERS) as ex:
        results = list(ex.map(judge, groups))

    # 每组的 id_key → 记录
    gid = {u: {k: rs for k, _, rs in ids} for u, _, ids in groups}

    nclear = nnode = 0
    for g, res in zip(groups, results):
        u = res["u"]
        tag = {"clear": "✗", "keep": "✓", "tie": "=", "noevi": "?"}[res["res"]]
        print(f"  {tag} {u[:62]}  [{res['why']}] title={res['title'][:26]}")
        if res["scores"]:
            print("      " + " | ".join(
                f"{k}:T{t}/S{s}" for k, (t, s) in res["scores"].items()))
        if res["res"] != "clear":
            continue
        nclear += 1
        for dk in res["drop"]:
            for r in gid[u].get(tuple(dk), []):
                nnode += 1
                print(f"      → 清除 {r['tree']} {r['name']} @ "
                      f"{'/'.join(r['path'][-2:])}")
    print(f"\n裁决: 一归属 {nclear} 组 / 待清节点 {nnode} 个"
          f"（并列 {sum(1 for r in results if r['res']=='tie')}，"
          f"无证据 {sum(1 for r in results if r['res']=='noevi')}）")

    if not APPLY:
        print("（dry-run，未写库；加 --apply 落库）")
    elif nnode:
        d = os.path.join(ROOT, "backups", TODAY)
        os.makedirs(d, exist_ok=True)
        ts = datetime.datetime.now().strftime("%H%M%S")
        shutil.copy2(TREE_F, os.path.join(d, f"tree_before_p243_{ts}.json"))
        shutil.copy2(REG_F, os.path.join(d, f"registry_before_p243_{ts}.json"))
        # 按 (url, 路径, 名称, 视图) 定位要清的节点，再回树里改
        drop_keys = set()
        for res in results:
            if res["res"] != "clear":
                continue
            for dk in res["drop"]:
                for r in gid[res["u"]].get(tuple(dk), []):
                    drop_keys.add((norm_u(r["u"]), tuple(r["path"]), r["name"],
                                   r["tree"]))
        cleared = reged = 0

        def walk(n, path, kind):
            nonlocal cleared, reged
            name = (n.get("n") or "").strip()
            u = norm_u(n.get("u"))
            if u.startswith("http") and (u, tuple(path), name, kind) in drop_keys:
                keep = next((res["keep"] for res in results
                             if res["res"] == "clear" and res["u"] == u), "")
                n["u"] = ""
                n["s"] = ((n.get("s") or "")
                          + f" | p243 跨地区串站清除(同URL属{keep})").strip(" |")
                reged += len(reg_clear(reg, name, u))
                cleared += 1
            for c in n.get("ks") or []:
                walk(c, path + [name], kind)

        for g in tree["ks"]:
            kind = "tiao" if (g.get("l") == "根"
                              or (g.get("n") or "").startswith("条")) else "blk"
            walk(g, [], kind)
        atomic(tree, TREE_F)
        atomic(reg, REG_F)
        print(f"落库: 清节点 {cleared} / registry 条目 {reged}")

    atomic({"generated": datetime.datetime.now().isoformat(timespec="seconds"),
            "applied": APPLY, "groups": len(groups), "rows": results}, REPORT_F)
    print(f"报告: {REPORT_F}")


if __name__ == "__main__":
    main()
