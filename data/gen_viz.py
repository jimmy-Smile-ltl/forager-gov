# -*- coding: utf-8 -*-
"""可视化数据生成（p22 管线组件）——从 tree.json 重组块/条两视图，
输出 ../viz_tree_data.js（块·行政区划）与 ../viz_tiao_data.js（条·垂直系统）。

兼容性设计（2026-11-09 用户指令「图需要兼容后续数据更新」）：
- 所有 tree.json 字段用 .get() 防御访问——结构变化不崩；
- 节点 schema 固定 {n,u,t,ks}（t=机构类型, 前端按 t 配色/分类），
  tree.json 新增字段不影响（新展示需求再扩展 m 等）；
- 新系统/新板块自动纳入（遍历式重组，无硬编码系统清单）；
- 数据规模无上限（按需渲染，前端只画展开路径）。"""
import json, os, sys

def t_of(node, nn):
    n = node or {}
    if "人大" in nn: return "rd"
    if "政协" in nn: return "zx"
    if "监委" in nn or "监察" in nn: return "jw"
    if "法院" in nn: return "fy"
    if "检察" in nn: return "jcy"
    if "党委" in nn: return "party"
    if n.get("c") == "群团组织" or "群团" in nn: return "qt"
    if n.get("k") in ("人民政府", "区划"): return "gov"   # 各级政府/区划门户
    if n.get("c") and "人民政府" in n.get("c", ""): return "gov"
    if n.get("k") in ("厅局", "部门") or "部门" in n.get("k", ""): return "dept"
    return "group"

# ═══ 块视图 ═══════════════════════════════════
def _extra(node, fields=("l", "k", "c", "x", "s", "m", "cd", "dt")):
    """展示层需要但不参与结构的字段（2026-11-19：此前部门/并列/群团叶子只投影
    n/u/t，导致「信息公开专栏」x、来源 s、代码 cd 在列表视图全部丢失，
    1,685 个有专栏的节点被误显示为「待核」）。"""
    return {f: node[f] for f in fields if node.get(f)}


def build_block_node(node, depth):
    n, u = node.get("n", ""), node.get("u", "")
    out = {"n": n, "u": u, "t": t_of(node, n)}
    for f in ("l", "k", "c", "x", "s", "m"):
        v = node.get(f, "")
        if v:
            out[f] = v
    depts, binglie, quntuan, subgov = [], [], [], []
    binglie_note = ""
    for k in node.get("ks", []) or []:
        kn, kc, kk = k.get("n", ""), k.get("c", ""), k.get("k", "")
        if kk == "分组" and any(x in kn for x in ("部门", "厅局", "直属", "内设")):
            for d in k.get("ks", []) or []:
                # 65k 县级部门名录叶子只带展示必需字段（l 供层级筛选、dt 供
                # 乡镇/党委标注）；k/c 与 t=dept 重复，省下 ~1.3MB 首屏体积
                depts.append({"n": d.get("n", ""), "u": d.get("u", ""), "t": "dept",
                              **_extra(d, ("l", "x", "s", "m", "cd", "dt"))})
        elif kk == "分组" and "并列" in kn:
            kids = k.get("ks", []) or []
            # 兄弟叶子同值字段去重（2026-11-19）：县级并列机关 6 个叶子的 c
            # 都是同一串「县委/县人大/…/县检察院」（与子节点列表等价）、m 都是
            # 同一句体制备注，逐叶复制白占 ~2MB。同值则 c 直接省去（下级构成
            # 已由兄弟列表表达），m 上提到组节点展示一次。
            drop, gm = set(), ""
            if kids:
                if len({d.get("c", "") for d in kids}) == 1:
                    drop.add("c")
                ms = {d.get("m", "") for d in kids}
                if len(ms) == 1:
                    gm, drop = (ms.pop() or ""), drop | {"m"}
            for d in kids:
                e = {f: v for f, v in _extra(d).items() if f not in drop}
                binglie.append({"n": d.get("n", ""), "u": d.get("u", ""),
                                "t": t_of(d, d.get("n", "")), **e})
            if gm:
                binglie_note = gm
        elif kc == "群团组织" or "群团" in kn:
            if k.get("ks"):
                for d in k.get("ks", []):
                    quntuan.append({"n": d.get("n", ""), "u": d.get("u", ""),
                                    "t": "qt", **_extra(d)})
            else:
                quntuan.append({"n": kn, "u": k.get("u", ""), "t": "qt", **_extra(k)})
        elif kk == "分组" and k.get("ks") and any(
                d.get("k") in ("人民政府", "区划") for d in k.get("ks", [])):
            # 区划型分组（兵团直辖县级市、自治区直辖县等特例）: 子级作为下级区划
            for d in k.get("ks", []):
                if d.get("ks"):
                    subgov.append(build_block_node(d, depth + 1))
                else:
                    # 2026-11-16: 叶子节点携带 m/s/l（合署标注等备注须进展示层）
                    _leaf = {"n": d.get("n", ""), "u": d.get("u", ""), "t": "gov",
                             **_extra(d, ("m", "s", "l", "k", "c", "x", "cd", "dt"))}
                    subgov.append(_leaf)
        elif kc and "人民政府" in kc and k.get("ks"):
            subgov.append(build_block_node(k, depth + 1))
        elif kc and "人民政府" in kc and not k.get("ks"):
            _leaf = {"n": kn, "u": k.get("u", ""), "t": "gov",
                     **_extra(k, ("m", "s", "l", "k", "c", "x", "cd", "dt"))}
            subgov.append(_leaf)
    ks = [{"n": "人民政府", "u": u, "t": "govhome", "ks": depts}]
    if binglie:
        _bg = {"n": "并列机关", "u": "", "t": "binglie", "ks": binglie}
        if binglie_note:
            _bg["m"] = binglie_note
        ks.append(_bg)
    if quntuan:
        ks.append({"n": "群团组织", "u": "", "t": "qt", "ks": quntuan})
    ks.extend(subgov)
    out["ks"] = ks
    return out

def build_block(tree):
    root = {"n": tree.get("n", "中国政府网站体系"), "u": "", "t": "root", "ks": []}
    for g in tree.get("ks", []) or []:
        gn = g.get("n", "")
        if gn.startswith("省级"):
            root["ks"].append({"n": "地方（32 省级）", "t": "block",
                               "ks": [build_block_node(p, 1) for p in g.get("ks", []) or []]})
        elif gn.startswith("中央"):
            kids = []
            for k in g.get("ks", []) or []:
                kn = k.get("n", "")
                if "国务院" in kn:
                    gov = {"n": "国务院（中央人民政府）", "u": k.get("u", ""),
                           "t": "govhome", "ks": []}
                    for sub in k.get("ks", []) or []:
                        if sub.get("k") == "分组":
                            for d in sub.get("ks", []) or []:
                                gov["ks"].append({"n": d.get("n", ""), "u": d.get("u", ""), "t": "dept"})
                        else:
                            gov["ks"].append({"n": sub.get("n", ""), "u": sub.get("u", ""),
                                              "t": t_of(sub, sub.get("n", ""))})
                    kids.append(gov)
                else:
                    kids.append({"n": kn, "u": k.get("u", ""), "t": t_of(k, kn),
                                 "ks": [{"n": d.get("n", ""), "u": d.get("u", ""),
                                         "t": t_of(d, d.get("n", ""))}
                                        for d in k.get("ks", []) or []]})
            root["ks"].append({"n": "中央", "t": "block", "ks": kids})
        elif gn.startswith("港澳台"):
            # 港澳台: 特区政府/台湾省 + 其下区划（台湾 22 县市、香港 18 区、澳门 8 堂区）
            kids = []
            for k in g.get("ks", []) or []:
                node = {"n": k.get("n", ""), "u": k.get("u", ""),
                        "t": "gov" if "人民政府" in k.get("c", "") else "group",
                        "ks": [{"n": d.get("n", ""), "u": d.get("u", ""), "t": "gov"}
                               for d in k.get("ks", []) or []]}
                kids.append(node)
            root["ks"].append({"n": gn, "t": "block", "ks": kids})
    return root

# ═══ 条视图 ═══════════════════════════════════
_CENTRAL = {
    "rd":  ("全国人民代表大会", "http://www.npc.gov.cn/"),
    "zx":  ("中国人民政治协商会议全国委员会", "http://www.cppcc.gov.cn/"),
    "jw":  ("中央纪委国家监委", "https://www.ccdi.gov.cn/"),
    "fy":  ("最高人民法院", "https://www.court.gov.cn/"),
    "jcy": ("最高人民检察院", "https://www.spp.gov.cn/"),
}
_BASE = {"rd": "人大", "zx": "政协", "jw": "监委", "fy": "人民法院", "jcy": "人民检察院"}

def _org_of(parent, cat):
    for jg in parent.get("ks", []) or []:
        if jg.get("k") != "分组":
            continue
        for o in jg.get("ks", []) or []:
            nn = o.get("n", "")
            if cat == "rd" and nn in ("省人大", "县人大"): return o
            if cat == "zx" and nn in ("省政协", "县政协"): return o
            if cat == "jw" and nn in ("省监委", "县监委"): return o
            if cat == "fy" and "法院" in nn: return o
            if cat == "jcy" and "检察" in nn: return o
    return None

def build_5sys(tree, cat):
    blk = next((g for g in tree.get("ks", []) if g.get("n", "").startswith("省级")), None)
    rootn, rootu = _CENTRAL[cat]
    root = {"n": rootn, "u": rootu, "t": cat if cat in ("rd","zx","jw","fy","jcy") else "group",
            "ks": []}
    if blk is None:
        return root
    for p in blk.get("ks", []) or []:
        pn = p.get("n", "")
        po = _org_of(p, cat)
        pnode = {"n": pn + _BASE[cat].replace("人民法院", "法院").replace("人民检察院", "检察院"),
                 "u": (po or {}).get("u", ""), "t": root["t"], "l": (po or {}).get("l", ""),
                 "ks": []}
        if (po or {}).get("x"): pnode["x"] = po["x"]
        if (po or {}).get("m"): pnode["m"] = po["m"]
        for c in p.get("ks", []) or []:
            if c.get("c") not in ("地级市人民政府", "市辖区（地级行政区划）"):
                continue
            co = _org_of(c, cat)
            cnode = {"n": c.get("n", "") + _BASE[cat],
                     "u": (co or {}).get("u", ""), "t": root["t"],
                     "l": (co or {}).get("l", ""), "ks": []}
            if (co or {}).get("x"): cnode["x"] = co["x"]
            if (co or {}).get("m"): cnode["m"] = co["m"]
            for x in c.get("ks", []) or []:
                if x.get("c") != "县级人民政府":
                    continue
                xo = _org_of(x, cat)
                if xo is None:
                    continue
                xr = {"n": x.get("n", "") + _BASE[cat],
                      "u": xo.get("u", ""), "t": root["t"], "l": xo.get("l", "")}
                if xo.get("x"): xr["x"] = xo["x"]
                if xo.get("m"): xr["m"] = xo["m"]
                cnode["ks"].append(xr)
            pnode["ks"].append(cnode)
        root["ks"].append(pnode)
    return root

def build_tiao(tree):
    """条视图按党的领导体制组织（2026-11-10 用户指令）:
    党中央在前: 中央政法委员会(领导最高法/最高检/司法部/公安部) →
    中央财经委员会办公室(领导财政部/人行/证监会/金融监管/税务) →
    中央外事工作委员会办公室(领导外交部及外交系统); 其后人大/政协/
    纪委/群团/其余垂管系统。"""
    tiao = next((g for g in tree.get("ks", []) if g.get("n", "").startswith("条")), None)
    blk = next((g for g in tree.get("ks", []) if g.get("n", "").startswith("中央")), None)
    def slim(n):
        out = {"n": n.get("n", ""), "u": n.get("u", ""), "t": t_of(n, n.get("n", ""))}
        for f in ("l", "k", "c", "x", "s", "m"):
            v = n.get(f, "")
            if v:
                out[f] = v
        if n.get("ks"):
            out["ks"] = [slim(k) for k in n["ks"]]
        return out
    def find_tiao(name_part):
        for g in (tiao.get("ks", []) if tiao else []):
            if name_part in g.get("n", ""):
                return slim(g)
        return None
    def find_dept(name_part):
        for k in (blk.get("ks", []) if blk else []):
            if "国务院" not in k.get("n", ""):
                continue
            for grp in k.get("ks", []) or []:
                for x in grp.get("ks", []) or []:
                    if name_part in x.get("n", ""):
                        return {"n": x.get("n", ""), "u": x.get("u", ""), "t": "dept",
                                "m": x.get("m", "")}
        return None
    # 党中央（政治局常委会 → 各议事协调机构）
    party_root = {"n": "中共中央（党中央）", "u": "", "t": "party", "ks": [
        {"n": "中央委员会", "u": "", "t": "party", "ks": [
            {"n": "中央政治局", "u": "", "t": "party", "ks": [
                {"n": "中央政治局常务委员会", "u": "", "t": "party", "ks": []}]}]},
        # 中央政法委员会 → 政法口
        {"n": "中央政法委员会", "u": "", "t": "party", "ks": [
            build_5sys(tree, "fy"),
            build_5sys(tree, "jcy"),
            find_dept("司法部") or {"n": "司法部", "u": "", "t": "dept"},
            find_dept("公安部") or {"n": "公安部", "u": "", "t": "dept"},
            find_dept("国家安全部") or {"n": "国家安全部", "u": "", "t": "dept"},
        ]},
        # 中央财经委员会办公室 → 财经口
        {"n": "中央财经委员会办公室", "u": "", "t": "party", "ks": [
            find_dept("财政部") or {"n": "财政部", "u": "", "t": "dept"},
            find_tiao("人民银行") or {"n": "人民银行系统", "u": "", "t": "dept"},
            find_tiao("证监会") or {"n": "证监会系统", "u": "", "t": "dept"},
            find_tiao("金融监管") or {"n": "金融监管系统", "u": "", "t": "dept"},
            find_tiao("税务") or {"n": "税务系统", "u": "", "t": "dept"},
        ]},
        # 中央外事工作委员会办公室 → 外交口
        {"n": "中央外事工作委员会办公室", "u": "", "t": "party", "ks": [
            find_tiao("外交") or {"n": "外交系统", "u": "", "t": "dept"},
        ]},
        # 其余党中央机构（有官网的）
        {"n": "其他中央直属机构", "u": "", "t": "party", "ks": []},
    ]}
    # 其他党中央机构: 从块树中央直属机构拿有 u 的
    other_party = party_root["ks"][4]["ks"]
    for k in (blk.get("ks", []) if blk else []):
        if "中共中央" not in k.get("n", ""):
            continue
        for grp in k.get("ks", []) or []:
            for x in grp.get("ks", []) or []:
                if any(w in x.get("n", "") for w in ("政法委员会", "财经委员会", "外事工作委员会")):
                    continue
                if x.get("u"):
                    other_party.append({"n": x.get("n", ""), "u": x.get("u", ""),
                                        "t": "party", "m": x.get("m", "")})
    # 其后: 人大 / 政协 / 纪委 / 群团 / 其余系统
    five_rest = [build_5sys(tree, "rd"), build_5sys(tree, "zx"), build_5sys(tree, "jw")]
    others = [slim(g) for g in (tiao.get("ks", []) if tiao else [])
              if not any(s in g.get("n", "") for s in ("人大", "政协", "法院", "检察", "纪委", "外交", "财经"))]
    return {"n": "垂直管理系统（条）", "u": "", "t": "root",
            "ks": [party_root] + five_rest + others}

# ═══ 入口 ═══════════════════════════════════
def build_records(block, tiao, registry):
    """USR 扁平记录（大一统）: 块+条两树全部叶子, l 精确, adcode 桥接。"""
    import csv as _csv
    # adcode: 区划名 → 统计局区划码
    adc = {}
    try:
        csv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "geo", "ok_data_level3.csv")
        for r in _csv.DictReader(open(csv_path, encoding="utf-8-sig")):
            adc[r["ext_name"]] = r["ext_id"]
    except Exception:
        pass
    # registry 按 u 索引
    u2r = {}
    for k, v in (registry or {}).items():
        if v.get("u"):
            u2r[v["u"]] = v
    records = {}
    # 2026-11-19：市政府部门/县政府部门两个聚合分组不进 USR 记录——它们 6.5 万条
    # 部门名录叶子只有 n/u（tree 已带），塞进 records 会让文件从 8.5MB 涨到 22MB
    # （p219 限额 25MiB，加 JSON 开销后 36.7MB 直接超限）。叶子 t="dept"。
    SKIP_GROUPS = ("市政府部门", "县政府部门")
    def walk(n, path, prefix):
        nid = "/".join(path)
        full = prefix + "·" + n.get("n", "") if prefix else n.get("n", "")
        if n.get("n") in SKIP_GROUPS and n.get("t") == "block":
            return
        kids = n.get("ks", []) or []
        if not kids:
            usr = {"id": nid, "name": n.get("n", ""), "type": n.get("t", "group")}
            lv = n.get("l", "")
            if lv:
                usr["level"] = lv
            if n.get("u"):
                usr["u"] = n["u"]
                v = u2r.get(n["u"])
                if v:
                    st = v.get("status", "")
                    if st and st != "ok": usr["status"] = st   # ok 为默认不存
                    usr["verified_at"] = v.get("verified_at", "")
                    if v.get("xxgk"): usr["x"] = v["xxgk"]
            elif n.get("x"): usr["x"] = n["x"]
            if n.get("m"): usr["m"] = n["m"]
            # adcode: 区划名（或条树名剥后缀）→ 区划码
            name = n.get("n", "")
            code = adc.get(name)
            if not code:
                import re as _re
                bare = _re.sub(r"(高级)?人民法院$|人民检察院$|人大$|政协$|监察委员会$|监委$",
                               "", name)
                code = adc.get(bare)
            if code:
                usr["adcode"] = code
            records[nid] = usr
        for k in kids:
            walk(k, path + [k.get("n", "")], full)
    walk(block, [block.get("n", "")], "")
    walk(tiao, [tiao.get("n", "")], "")
    return records


def gen_viz(tree_path="tree.json"):
    """生成统一数据文件 gov_data.js（树图/地图/列表三视图共用一套数据）。

    统一数据格式（2026-11-11 定稿）:
      window.__GOV_DATA__ = {
        meta: {version, generated},
        block: 块树根（行政区划: 中央/省级→市→县, 每级人民政府+并列机关）,
        tiao:  条树根（垂直系统: 党中央→政法/财经/外事 + 15 系统, 法检四级重组）
      }
      节点 schema（三视图通用）: {n,u,t,m,ks}
        n=名称  u=官网URL(空=列名)  t=机构类型(rd/zx/fy/jcy/jw/gov/dept/party/qt/...)
        m=备注(经验之谈)  ks=子节点
      树图消费 block/tiao 树; 地图消费同树(遍历算区划×类型覆盖)+geo/*.js 边界;
      列表消费同 tree.json 经 p22 拆分产物(同源, 字段为 schema 超集)。"""
    tree = json.load(open(tree_path, encoding="utf-8"))
    here = os.path.dirname(os.path.abspath(__file__))
    blk = build_block(tree)
    # 2026-11-18 用户指令：树模式新增「市政府部门 / 县政府部门」两个节点
    # （生成层注入，tree.json 主数据不动；数据源 p246/p248 采集结果）
    try:
        import zzjg_nodes
        blk["ks"].extend(zzjg_nodes.block_groups())
    except Exception as _e:
        print("!! 市政府部门/县政府部门 节点生成失败:", _e)
    tiao = build_tiao(tree)
    # registry 合并 USR 全字段
    reg_path = os.path.join(here, "site_registry.json")
    registry = {}
    try:
        registry = json.load(open(reg_path, encoding="utf-8"))
    except Exception:
        pass
    records = build_records(blk, tiao, registry) if registry else {}
    # records（USR 扁平索引, 约 10MB raw / 1.3MB br）与树数据分离——慢网下
    # 它占首屏 payload 2/3（2026-11-17 线上实测 1.94MB br 里约 1.35MB 是
    # records），而首屏只有「全国总览卡」用得到；改为独立文件按需加载。
    s = json.dumps({"meta": {"version": "2026-11-11",
                             "generated": "2026-11-11",
                             "recordsFile": "gov_data_records.js"},
                    "block": blk, "tiao": tiao},
                   ensure_ascii=False, separators=(",", ":"))
    out = ("window.__GOV_DATA__=" + s + ";\n"
           "window.__TREE__=window.__GOV_DATA__.block;\n"   # 兼容别名(过渡期)
           "window.__TIAO__=window.__GOV_DATA__.tiao;\n"
           "window.__GOV_DATA__.loadRecords=function(cb){\n"
           "  if(window.__GOV_DATA__.records){cb&&cb();return}\n"
           "  var q=window.__recordsQ=window.__recordsQ||[];if(cb)q.push(cb);\n"
           "  if(window.__recordsLoading)return;window.__recordsLoading=1;\n"
           "  var s=document.createElement('script');\n"
           "  s.src=window.__GOV_DATA__.meta.recordsFile+'?v='+(window.__GOV_DATA__.meta.generated||'');\n"
           "  s.onload=function(){window.__GOV_DATA__.records=window.__GOV_DATA_RECORDS__||{};\n"
           "    (window.__recordsQ||[]).forEach(function(f){try{f()}catch(e){}});window.__recordsQ=[]};\n"
           "  s.onerror=function(){window.__recordsLoading=0};\n"
           "  document.head.appendChild(s);\n"
           "};\n")
    open(os.path.join(here, "..", "gov_data.js"), "w", encoding="utf-8").write(out)
    rec = ("window.__GOV_DATA_RECORDS__="
           + json.dumps(records, ensure_ascii=False, separators=(",", ":")) + ";\n")
    open(os.path.join(here, "..", "gov_data_records.js"), "w", encoding="utf-8").write(rec)
    # 旧文件保留软引用（指向统一数据）, 页面迁移后可删
    for old_name, key in (("viz_tree_data.js", "__TREE__"),
                          ("viz_tiao_data.js", "__TIAO__")):
        open(os.path.join(here, "..", old_name), "w", encoding="utf-8").write(
            f"/* 已统一到 gov_data.js, 本文件为兼容引用 */\n"
            f"window.{key}=window.__GOV_DATA__.{'block' if key=='__TREE__' else 'tiao'};\n")
    def cnt(n):
        c = 1
        for k in n.get("ks", []) or []: c += cnt(k)
        return c
    print(f"统一数据已生成: gov_data.js ({len(s)/1024:.0f}KB) 块 {cnt(blk)} 节点 / 条 {cnt(tiao)} 节点")

if __name__ == "__main__":
    gen_viz()
