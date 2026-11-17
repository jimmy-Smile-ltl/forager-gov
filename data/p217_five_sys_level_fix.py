#!/usr/bin/env python
# p217 五系统「县级机构误挂市级」修复（2026-11-17 第四轮）
# 背景: p205 审计的 title 匹配只查「市名出现在 title」——长沙县人民法院
#   含「长沙」即通过，导致 15 个市级节点挂着县/区法院、4 个挂县区检察院、
#   4 个挂区纪委、1 个挂区政协。本轮全部用权威源重新采集并 title 验证:
#   法院 → 省高院官网「中院」导航（elink elid 解码）
#   检察 → 省检察院官网 select 市级院列表（江西检察网）
#   监委 → 省纪委监委官网市县导航（广东/广西/秦风网）
#   政协 → 省政协+市门户+全国政协三渠道均无（云浮）→ 列名
# 另: 把 registry 中已严谨验证、但树里为空的 12 个节点补填
#   （来源=registry 历史 L1/L2 采集，本轮逐条 title 复验通过）
# 写前备份 tree/registry，写后种 p204/p206 cleared 标记。
import json, os, re, shutil, sys, time, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, "data")
TREE_F = os.path.join(D, "tree.json")
REG_F = os.path.join(D, "site_registry.json")
BAK_DIR = os.path.join(ROOT, "backups", "2026-11-17")
DRY = "--dry" in sys.argv

# (prov, city, system, new_url, note)  note 前缀 L1/L2/REG 决定 source_level
REPLACE = [
    # 法院：省高院官网中院导航（elink elid → 直链），县级站点错挂修正
    ("河北省", "承德市", "市中级人民法院", "https://cdzy.hebeicourt.gov.cn/",
     "L1|registry 已验 title=河北省承德市中级人民法院（原 cdx=承德县法院）"),
    ("辽宁省", "抚顺市", "市中级人民法院", "http://fs.lncourt.gov.cn/index.shtml",
     "L1|辽宁省高级人民法院官网「中院」导航 elink 解码, title=辽宁省抚顺市中级人民法院网"),
    ("辽宁省", "本溪市", "市中级人民法院", "http://bx.lncourt.gov.cn/index.shtml",
     "L1|辽宁省高级人民法院官网「中院」导航 elink 解码, title=本溪市中级人民法院网"),
    ("辽宁省", "阜新市", "市中级人民法院", "http://fx.lncourt.gov.cn/index.shtml",
     "L1|辽宁省高级人民法院官网「中院」导航 elink 解码, title=辽宁省阜新市中级人民法院"),
    ("辽宁省", "辽阳市", "市中级人民法院", "http://ly.lncourt.gov.cn/index.shtml",
     "L1|辽宁省高级人民法院官网「中院」导航 elink 解码, title=辽宁省辽阳市中级人民法院"),
    ("辽宁省", "铁岭市", "市中级人民法院", "http://tl.lncourt.gov.cn/index.shtml",
     "L1|辽宁省高级人民法院官网「中院」导航 elink 解码, title=辽宁省铁岭市中级人民法院"),
    ("辽宁省", "朝阳市", "市中级人民法院", "http://cy.lncourt.gov.cn/index.shtml",
     "L1|辽宁省高级人民法院官网「中院」导航 elink 解码, title=辽宁省朝阳市中级人民法院"),
    ("江西省", "南昌市", "市中级人民法院", "https://nczy.jxfy.gov.cn",
     "L1|registry 已验 title=江西省南昌市中级人民法院网（原 ncxfy=南昌县法院）"),
    ("江西省", "吉安市", "市中级人民法院", "https://jazy.jxfy.gov.cn",
     "L1|registry 已验 title=江西省吉安市中级人民法院（原 jaxfy=吉安县法院）"),
    ("四川省", "广安市", "市中级人民法院", "http://gazy.scssfw.gov.cn",
     "L1|registry 已验 title=四川省广安市中级人民法院（原 gaqfy=广安区法院）"),
    ("湖南省", "长沙市", "市中级人民法院", "http://cszy.hunancourt.gov.cn/index.shtml",
     "L1|registry 已验 title=湖南省长沙市中级人民法院（原 csxfy=长沙县法院）"),
    ("湖南省", "湘潭市", "市中级人民法院", "http://xtzy.hunancourt.gov.cn/index.shtml",
     "L1|registry 已验 title=湖南省湘潭市中级人民法院（原 xtxfy=湘潭县法院）"),
    ("湖南省", "衡阳市", "市中级人民法院", "http://hyzy.hunancourt.gov.cn/index.shtml",
     "L1|registry 已验 title=湖南省衡阳市中级人民法院（原 hyxfy=衡阳县法院）"),
    ("湖南省", "邵阳市", "市中级人民法院", "http://hnsyzy.hunancourt.gov.cn/index.shtml",
     "L1|registry 已验 title=湖南省邵阳市中级人民法院（原 hnsyfy=邵阳县法院）"),
    ("湖南省", "岳阳市", "市中级人民法院", "http://hnyyzy.hunancourt.gov.cn/index.shtml",
     "L1|registry 已验 title=湖南省岳阳市中级人民法院（原 yyxfy=岳阳县法院）"),
    # 检察：省检察院官网 select 市级院列表 / registry 已验
    ("江苏省", "南京市", "市人民检察院", "https://nj.jsjc.gov.cn/",
     "L1|registry 已验 title=南京市人民检察院（原 njjy=建邺区检察院）"),
    ("江苏省", "南通市", "市人民检察院", "https://nt.jsjc.gov.cn/",
     "L1|registry 已验 title=南通市人民检察院（原 nttz=通州区检察院）"),
    ("江西省", "抚州市", "市人民检察院", "https://www.jxfuzhou.jcy.gov.cn/",
     "L1|江西检察网首页「市级院」select 下拉 HTML 提取, title=抚州检察网（原 fuzhoulc=临川区检察院）"),
    # 监委：省纪委监委官网市县导航
    ("广东省", "梅州市", "市监委", "http://jw.meizhou.gov.cn/",
     "L1|广东纪检监察网首页市县导航 HTML 提取, title=中共梅州市纪律检查委员会 梅州市监察委员会（原 jw.gdmx=梅县区纪委）"),
    ("广西壮族自治区", "百色市", "市监委", "http://www.bsjw.gov.cn/",
     "L1|广西纪检监察网首页市县导航 HTML 提取, title=百色纪检监察网（原 yjq.bsjw=右江区监委）"),
    ("陕西省", "铜川市", "市监委", "https://tongchuan.qinfeng.gov.cn/",
     "L1|秦风网首页市县导航 HTML 提取, title=中共铜川市纪律检查委员会（原 yintai=印台区纪委）"),
    ("陕西省", "宝鸡市", "市监委", "https://baoji.qinfeng.gov.cn/",
     "L1|秦风网首页市县导航 HTML 提取, title=中共宝鸡市纪律检查委员会（原 chencang=陈仓区纪委）"),
]
# 树里为空、registry 已有且本轮 title 复验通过的补填
BACKFILL = [
    ("广东省", "东莞市", "市中级人民法院", "http://www.dgcourt.gov.cn/",
     "REG|registry 已验 title=东莞市中级人民法院"),
    ("河北省", "邢台市", "市政协", "http://www.xingtai.gov.cn/zwgk/czyjszl/bmjs/zx/",
     "REG|registry 已验 title=政协河北省邢台市委员会（门户官方政协频道）"),
    ("黑龙江省", "七台河市", "市政协", "https://www.qth.gov.cn/qth/zxqthswyh/ldzc.shtml",
     "REG|registry 已验 title=政协七台河市委员会（门户官方政协频道）"),
    ("内蒙古自治区", "锡林郭勒盟", "市人民检察院", "http://www.xilinguole.jcy.gov.cn/",
     "REG|registry 已验 title=锡林郭勒盟检察分院"),
    ("内蒙古自治区", "阿拉善盟", "市人民检察院", "http://alsjcy.gov.cn/",
     "REG|registry 已验 title=阿拉善盟检察分院"),
    ("浙江省", "台州市", "市人民检察院", "https://tz.zjjcy.gov.cn/index.html",
     "REG|registry 已验 title=台州检察网"),
    ("山东省", "德州市", "市人民检察院", "http://www.sdjcy.gov.cn/jwgk/syjs/sjyjj/dzsjcy/",
     "REG|registry 已验 title=德州市检察机关（山东省检察院官方频道）"),
    ("海南省", "海口市", "市人民检察院", "https://www.hi.jcy.gov.cn/haikou.html",
     "REG|registry 已验 title=海南省海口市人民检察院"),
    ("海南省", "三亚市", "市人民检察院", "https://www.hi.jcy.gov.cn/sanya.html",
     "REG|registry 已验 title=海南省三亚市人民检察院"),
    ("海南省", "儋州市", "市人民检察院", "https://www.hi.jcy.gov.cn/danzhou.html",
     "REG|registry 已验 title=海南省儋州市人民检察院"),
    ("宁夏回族自治区", "吴忠市", "市人民检察院", "https://www.nx.jcy.gov.cn/WZJCY/",
     "REG|registry 已验 title=吴忠市人民检察院"),
    ("宁夏回族自治区", "中卫市", "市人民检察院", "https://www.nx.jcy.gov.cn/ZWJCY/",
     "REG|registry 已验 title=中卫市人民检察院"),
]
# 清除：三渠道（省政协官网/市门户/全国政协）均无市级政协官网，原值为云城区政协
CLEAR = [
    ("广东省", "云浮市", "市政协",
     "2026-11-17 p217：原值 qzx.yfyunchengqu.gov.cn=云城区政协（县级）错挂；"
     "广东政协网「市县政协」/云浮市政府门户/中国政协网地方政协页均无云浮市政协官网"
     "（SERP 兜底仅新闻页与百科）→ 列名"),
]
# 块树已正确、仅条树/registry 持有县区值（益阳检察：条树=资阳区院）
TIAO_ONLY = [
    ("湖南省", "益阳市", "市人民检察院", "https://www.yiyang.jcy.gov.cn/",
     "L1|registry 已验 title=益阳市人民检察院外网门户网站（原 yiyangzy=资阳区检察院）"),
]


def unorm(u):
    u = (u or "").strip()
    if not u:
        return ""
    u = u.split("#")[0]
    m = re.match(r"^(https?)://([^/]+)(/.*)?$", u, re.I)
    if not m:
        return u.lower()
    sch, host, path = m.group(1).lower(), m.group(2).lower(), m.group(3) or "/"
    if path != "/" and path.endswith("/"):
        path = path[:-1]
    return f"{sch}://{host}{path}"


def ukey(u):
    x = unorm(u)
    return re.sub(r"^https?://", "", x) if x else ""


def atomic(obj, path):
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
    with os.fdopen(fd, "w") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def level_of(note, old="L2"):
    if note.startswith("L1|"):
        return "L1"
    if note.startswith("REG|"):
        return old or "L2"
    if "SERP" in note:
        return "L3"
    return "L2"


def main():
    t = json.load(open(TREE_F, encoding="utf-8"))

    def find(n, name):
        if n.get("n") == name:
            return n
        for c in n.get("ks") or []:
            r = find(c, name)
            if r:
                return r
        return None

    blk = next(g for g in t["ks"] if g.get("n", "").startswith("省级"))

    def block_node(prov, city, sysn):
        p = find(blk, prov); c = find(p, city) if p else None
        jg = next((x for x in (c or {}).get("ks", []) if x.get("c") == "并列机关"), None)
        return find(jg, sysn) if jg else None

    # 条树节点：递归遍历条根各系统子树，按城市名+机构词收窄
    def tiao_nodes(city, sysn):
        out = []
        core = re.sub(r"(市|地区|盟|自治州)$", "", city)
        kw = {"市中级人民法院": ("中级", "法院"), "市人民检察院": ("检察",)}.get(sysn, ("",))

        def walk(n):
            nm = n.get("n") or ""
            if (core and core in nm and all(k in nm for k in kw)
                    and len(nm) <= len(core) + 12 and n is not blk):
                out.append(n)
            for c in n.get("ks") or []:
                walk(c)

        for top in t["ks"]:
            if (top.get("n") or "").startswith("条"):
                for sub in top.get("ks") or []:
                    walk(sub)
        return out

    stats = {"replace": 0, "backfill": 0, "clear": 0, "skip": 0, "tiao": 0}
    reg = json.load(open(REG_F, encoding="utf-8"))
    # registry 按旧 URL 建索引
    idx = {}
    for k, v in reg.items():
        x = ukey(v.get("u"))
        if x:
            idx.setdefault(x, []).append(k)
    changes = []  # (city, sysn, old, new, note)

    def do_set(prov, city, sysn, newu, note, allow_existing):
        o = block_node(prov, city, sysn)
        if not o:
            print(f"SKIP 未找到节点 {prov}/{city}/{sysn}"); stats["skip"] += 1; return
        old = (o.get("u") or "").strip()
        if old and not allow_existing:
            if ukey(old) == ukey(newu):
                print(f"SKIP 已是目标值 {prov}/{city}/{sysn}"); stats["skip"] += 1; return
            print(f"SKIP 非空(非替换目标) {prov}/{city}/{sysn} 当前={old[:60]}"); stats["skip"] += 1; return
        if not old and allow_existing:
            tok = old
            print(f"BACKFILL {prov}/{city}/{sysn} -> {newu}")
            stats["backfill"] += 1
        elif old:
            print(f"REPLACE  {prov}/{city}/{sysn}\n    {old[:70]}\n -> {newu}")
            stats["replace"] += 1
        else:
            print(f"BACKFILL {prov}/{city}/{sysn} -> {newu}")
            stats["backfill"] += 1
        o["u"] = newu
        o["s"] = f"来源:{note}；2026-11-17 p217 层级错配修复"
        changes.append((city, sysn, old, newu, note))

    for prov, city, sysn, u, note in REPLACE:
        do_set(prov, city, sysn, u, note, allow_existing=True)
    for prov, city, sysn, u, note in BACKFILL:
        do_set(prov, city, sysn, u, note, allow_existing=False)

    for prov, city, sysn, note in CLEAR:
        o = block_node(prov, city, sysn)
        if not o or not (o.get("u") or "").strip():
            print(f"SKIP 已空 {prov}/{city}/{sysn}"); stats["skip"] += 1; continue
        old = o["u"]
        print(f"CLEAR    {prov}/{city}/{sysn}: {old[:70]}")
        o["u"] = ""
        o["s"] = note
        changes.append((city, sysn, old, "", note))
        stats["clear"] += 1

    # 条树单独持有错值的（块树已正确）：旧值取条树节点的实际 URL
    for prov, city, sysn, newu, note in TIAO_ONLY:
        olds = [n.get("u") for n in tiao_nodes(city, sysn)
                if (n.get("u") or "").strip() and ukey(n.get("u")) != ukey(newu)]
        for old in olds:
            print(f"TIAO-ONLY {city}/{sysn}: {old[:70]} -> {newu}")
            changes.append((city, sysn, old, newu, note))
        if not olds:
            print(f"SKIP 条树无错值 {city}/{sysn}")

    # 条树同步：同城市同系统且 URL 仍等于旧值的节点一起改（避免两边不一致）
    for city, sysn, old, newu, note in changes:
        if not old:
            continue
        for n in tiao_nodes(city, sysn):
            if ukey(n.get("u")) == ukey(old):
                print(f"TIAO     {city}/{sysn}: {n.get('n')} {n.get('u')[:60]} -> {newu or '(空)'}")
                n["u"] = newu
                n["s"] = f"来源:{note}；2026-11-17 p217 同步"
                stats["tiao"] += 1

    # registry 同步
    # 规则:
    #   ① 按旧 URL 匹配 → 仅改市级条目（县级人民法院| 等县级键一律跳过，它
    #      们持有县法院 URL 本来就是对的）
    #   ② 补填: 已有「城市+机构词」条目 → 空的填、已等于新值跳过、不同则报冲突
    #   ③ 都没有才按类别约定新建
    reg_stats = {"upd": 0, "ins": 0, "miss": 0, "ok": 0, "conflict": 0}
    CAT = {"市中级人民法院": ("法院",), "市人民检察院": ("检察院系统", "检察", "法院"),
           "市政协": ("政协",), "市人大": ("人大",), "市监委": ("纪委", "法院", "人大")}
    CNT = {"市中级人民法院": "人民法院", "市人民检察院": "人民检察院",
           "市政协": "政协", "市人大": "人大", "市监委": "监委"}
    for city, sysn, old, newu, note in changes:
        core = re.sub(r"(市|地区|盟|自治州)$", "", city)
        cat = CAT.get(sysn, ())
        cn = CNT.get(sysn, "")
        # ① 旧 URL 命中（限市级条目）
        hit = [k for k in idx.get(ukey(old), [])
               if (core in k or core in (reg[k].get("n") or ""))
               and not k.startswith("县级")]
        for k in hit:
            e = reg[k]
            oldl = e.get("source_level")
            e["u"] = newu
            e["status"] = "ok" if newu else "cleared"
            e["verified_at"] = "2026-11-17"
            if newu:
                e["source_level"] = level_of(note, oldl)
            print(f"REG-UPD  [{k}] {old[:55] or '(空)'} -> {newu[:60] or '(空)'}")
            reg_stats["upd"] += 1
        if hit:
            continue
        # ② 城市+机构词条目
        named = [k for k, v in reg.items()
                 if (core in k or core in (v.get("n") or "")) and cn and cn in k
                 and any(c in k for c in cat)]
        filled = False
        for k in named:
            e = reg[k]
            cu = (e.get("u") or "").strip()
            if not cu:
                e["u"] = newu
                e["status"] = "ok" if newu else "cleared"
                e["verified_at"] = "2026-11-17"
                e["source_level"] = level_of(note, e.get("source_level"))
                print(f"REG-FILL [{k}] (空) -> {newu[:60]}")
                reg_stats["upd"] += 1
                filled = True
            elif ukey(cu) == ukey(newu):
                print(f"REG-OK   [{k}] 已是新值")
                reg_stats["ok"] += 1
                filled = True
            else:
                # 现值是已知污染类（上级域名/媒体/新闻页）→ 直接以新值覆盖
                bad = re.search(r"ccgp\.gov\.cn|npc\.gov\.cn|cppcc\.gov\.cn|mzfzw\.net|"
                                r"ccdi\.gov\.cn|gzrd\.gov\.cn|/art/|/content-|/columns/|/\d{6}/",
                                cu)
                if bad:
                    e["u"] = newu
                    e["status"] = "ok"
                    e["verified_at"] = "2026-11-17"
                    e["source_level"] = level_of(note, e.get("source_level"))
                    print(f"REG-CLEANUP [{k}] 污染值 {cu[:50]} -> {newu[:60]}")
                    reg_stats["upd"] += 1
                else:
                    print(f"REG-CONFLICT [{k}] 现值={cu[:55]} 新值={newu[:55]}")
                    reg_stats["conflict"] += 1
                filled = True
        if filled:
            continue
        # ③ 新建
        if not newu:
            print(f"REG-MISS {city}/{sysn} old={old[:55]}（清除无条目，跳过）")
            reg_stats["miss"] += 1
            continue
        if sysn == "市人民检察院":
            base = city if city.endswith(("市", "盟", "州", "地区")) else city + "市"
            key = f"检察院系统|{base}人民检察院"
        elif sysn == "市中级人民法院":
            key = f"法院|{city}中级人民法院"
        elif sysn == "市政协":
            key = f"政协|{city}政协"
        elif sysn == "市监委":
            key = f"法院|市监委|{city}"
        else:
            key = f"人大|{city}人大"
        if key in reg:
            print(f"REG-CONFLICT [{key}] 已存在 {reg[key].get('u','')[:50]}")
            reg_stats["conflict"] += 1
        else:
            reg[key] = {"u": newu, "n": f"{city}{sysn}", "locations": ["块", "条"],
                        "source_level": level_of(note, "L2"), "verified_at": "2026-11-17",
                        "status": "ok", "snapshot": ""}
            print(f"REG-INS  [{key}] -> {newu}")
            reg_stats["ins"] += 1

    print("\n统计:", stats, "registry:", reg_stats, "DRY" if DRY else "")
    if DRY:
        return
    os.makedirs(BAK_DIR, exist_ok=True)
    ts = time.strftime("%H%M%S")
    shutil.copy2(TREE_F, os.path.join(BAK_DIR, f"tree_before_p217_{ts}.json"))
    shutil.copy2(REG_F, os.path.join(BAK_DIR, f"registry_before_p217_{ts}.json"))
    atomic(t, TREE_F)
    atomic(reg, REG_F)
    print("已落库，备份时间戳:", ts)

    # 云浮政协列名后种 cleared 标记，防 p204/p206 重新采到云城区 URL
    for sf in ("p204_state.json", "p206_state.json"):
        f = os.path.join(D, sf)
        if not os.path.exists(f):
            continue
        st = json.load(open(f, encoding="utf-8"))
        done = st.setdefault("done", {})
        key = "广东省|云浮市|市政协"
        if not done.get(key):
            done[key] = "cleared:2026-11-17"
            shutil.copy2(f, os.path.join(BAK_DIR, f"{sf[:-5]}_before_p217_{ts}.json"))
            atomic(st, f)
            print(f"{sf}: +1 cleared 标记 ({key})")


if __name__ == "__main__":
    main()
