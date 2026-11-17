#!/usr/bin/env python
# p220 死域名清理 + 衡阳县错挂修正（2026-11-17 第五轮）
# 背景:
#   ① p205 审计新增 DNS 存活检查（NXDOMAIN=硬问题）——此前 23 个权威来源
#      URL 已整站下线/迁域，却因「title 空+来源权威」长期归入存疑：
#      新疆 xjcourt.org / *.chinacourt.gov.cn 子域、glzy、wzrd、tlrd 等。
#   ② 衡阳县县级节点 u=https://www.hengyang.gov.cn/（市门户）——用户指出
#      衡阳门户首页无县区入口，真实入口在「网站群-县市区人民政府」页
#      (hengyang.gov.cn/wzzq/xsqrmzf/index.html)，从中提取 12 县区全量，
#      衡阳县正确官网=http://www.hyx.gov.cn/（title=衡阳县人民政府门户网站）。
#   ③ 濮阳中院节点挂 hnpyfy.hncourt.gov.cn=濮阳县法院网（县级错挂），
#      正确 https://pyzy.hncourt.gov.cn/（title=濮阳市中级人民法院）。
# 做法: 替换 3 + 清除 29（新疆 11 + 死域名 18），同步 registry，写前备份。
import json, os, re, shutil, sys, tempfile, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, "data")
TREE_F = os.path.join(D, "tree.json")
REG_F = os.path.join(D, "site_registry.json")
BAK_DIR = os.path.join(ROOT, "backups", "2026-11-17")
DRY = "--dry" in sys.argv

# (prov, city, system, old_url, new_url, note)
REPLACE = [
    ("新疆维吾尔自治区", "昌吉回族自治州", "市中级人民法院",
     "http://cjzy.chinacourt.gov.cn/index.shtml", "https://cjzy.xjcourt.gov.cn/",
     "L1|新疆法院网「法院网站群」导航旧域已死，昌吉中院现行站 title=昌吉回族自治州中级人民法院"
     "（registry 法院|昌吉州中院 同值）"),
    ("河南省", "濮阳市", "市中级人民法院",
     "http://hnpyfy.hncourt.gov.cn", "https://pyzy.hncourt.gov.cn/",
     "L1|河南高院官网中院导航/registry 已验 title=濮阳市中级人民法院"
     "（原 hnpyfy=濮阳县法院网，县级错挂）"),
    ("湖南省", "娄底市", "市政协",
     "http://www.ldzx.gov.cn/", "http://ldzx.hnloudi.gov.cn/",
     "L2|娄底市政府门户首页「市政协」链接 HTML 提取, title=政协娄底市委员会"
     "（原 www.ldzx.gov.cn 域名 NXDOMAIN）"),
    ("甘肃省", "酒泉市", "市政协",
     "http://zx.jiuquan.gov.cn/", "https://www.jqzx.gov.cn/",
     "L2|酒泉市政府门户首页「酒泉政协网」链接 HTML 提取（站点对自动请求超时/"
     "拦截，title 未取；原 zx.jiuquan.gov.cn NXDOMAIN）"),
    ("湖南省", "衡阳市", "县级:衡阳县",
     "https://www.hengyang.gov.cn/", "http://www.hyx.gov.cn/",
     "L2|衡阳市政府门户「网站群-县市区人民政府」页 HTML 提取, "
     "title=衡阳县人民政府门户网站（原值误挂市门户）"),
    # —— 县级错挂/包装链接批量修正（2026-11-17 本轮核实）——
    # 曲靖 9 县区：原值为市门户 link.html?t= 包装跳转，展开为官方目标域
    ("云南省", "曲靖市", "县级:麒麟区",
     "https://www.qj.gov.cn/link.html?t=https://www.ql.gov.cn/", "https://www.ql.gov.cn/",
     "L2|曲靖门户县区导航跳转目标展开, title=曲靖市麒麟区人民政府"),
    ("云南省", "曲靖市", "县级:沾益区",
     "https://www.qj.gov.cn/link.html?t=https://www.zhanyi.gov.cn/", "https://www.zhanyi.gov.cn/",
     "L2|曲靖门户县区导航跳转目标展开, title=曲靖市沾益区人民政府"),
    ("云南省", "曲靖市", "县级:马龙区",
     "https://www.qj.gov.cn/link.html?t=https://www.malong.gov.cn/", "https://www.malong.gov.cn/",
     "L2|曲靖门户县区导航跳转目标展开, title=曲靖市马龙区人民政府"),
    ("云南省", "曲靖市", "县级:陆良县",
     "https://www.qj.gov.cn/link.html?t=https://www.luliang.gov.cn/", "https://www.luliang.gov.cn/",
     "L2|曲靖门户县区导航跳转目标展开, title=陆良县人民政府"),
    ("云南省", "曲靖市", "县级:师宗县",
     "https://www.qj.gov.cn/link.html?t=https://www.ynsz.gov.cn/", "https://www.ynsz.gov.cn/",
     "L2|曲靖门户县区导航跳转目标展开, title=师宗县人民政府网"),
    ("云南省", "曲靖市", "县级:罗平县",
     "https://www.qj.gov.cn/link.html?t=https://www.luoping.gov.cn/", "https://www.luoping.gov.cn/",
     "L2|曲靖门户县区导航跳转目标展开, title=罗平县人民政府门户网站"),
    ("云南省", "曲靖市", "县级:富源县",
     "https://www.qj.gov.cn/link.html?t=https://www.qjfy.gov.cn/", "https://www.qjfy.gov.cn/",
     "L2|曲靖门户县区导航跳转目标展开, title=富源县人民政府门户网站"),
    ("云南省", "曲靖市", "县级:会泽县",
     "https://www.qj.gov.cn/link.html?t=https://www.huize.gov.cn/", "https://www.huize.gov.cn/",
     "L2|曲靖门户县区导航跳转目标展开, title=会泽县人民政府门户网站"),
    ("云南省", "曲靖市", "县级:宣威市",
     "https://www.qj.gov.cn/link.html?t=https://www.xw.gov.cn/", "https://www.xw.gov.cn/",
     "L2|曲靖门户县区导航跳转目标展开, title=宣威市人民政府"),
    # 大同 10 区县：原值全部误挂市门户 dt.gov.cn
    ("山西省", "大同市", "县级:新荣区", "http://www.dt.gov.cn/",
     "http://www.xr.gov.cn/", "L2|大同市政府门户县区导航 HTML 提取, title=新荣区人民政府"),
    ("山西省", "大同市", "县级:平城区", "http://www.dt.gov.cn/",
     "http://www.pingcheng.gov.cn/", "L2|大同市政府门户县区导航 HTML 提取, title=平城区人民政府"),
    ("山西省", "大同市", "县级:云冈区", "http://www.dt.gov.cn/",
     "http://www.yungang.gov.cn/", "L2|大同市政府门户县区导航 HTML 提取, title=云冈区人民政府"),
    ("山西省", "大同市", "县级:云州区", "http://www.dt.gov.cn/",
     "http://www.yunzhou.gov.cn/", "L2|大同市政府门户县区导航 HTML 提取, title=云州区人民政府"),
    ("山西省", "大同市", "县级:阳高县", "http://www.dt.gov.cn/",
     "http://www.dtyg.gov.cn/", "L2|大同市政府门户县区导航 HTML 提取, title=阳高县人民政府"),
    ("山西省", "大同市", "县级:天镇县", "http://www.dt.gov.cn/",
     "http://www.dttz.gov.cn/", "L2|大同市政府门户县区导航 HTML 提取, title=天镇县人民政府"),
    ("山西省", "大同市", "县级:广灵县", "http://www.dt.gov.cn/",
     "http://www.sx-guangling.gov.cn/", "L2|大同市政府门户县区导航 HTML 提取, title=广灵县人民政府"),
    ("山西省", "大同市", "县级:灵丘县", "http://www.dt.gov.cn/",
     "http://www.lingqiu.gov.cn/", "L2|大同市政府门户县区导航 HTML 提取, title=灵丘县人民政府"),
    ("山西省", "大同市", "县级:浑源县", "http://www.dt.gov.cn/",
     "http://www.hunyuan.gov.cn/", "L2|大同市政府门户县区导航 HTML 提取, title=浑源县人民政府"),
    ("山西省", "大同市", "县级:左云县", "http://www.dt.gov.cn/",
     "http://www.zuoyun.gov.cn/", "L2|大同市政府门户县区导航 HTML 提取, title=左云县人民政府"),
    # 西藏昌都/甘肃临夏/江苏苏州/新疆和田：原值为文章页/旅游页/市门户
    ("西藏自治区", "昌都市", "县级:芒康县",
     "http://www.changdu.gov.cn/cdrmzf/zfdtr/202411/2c02d4de241a43f788a989bd8e0a2240.shtml",
     "http://mangkang.changdu.gov.cn",
     "L2|昌都市政府门户「芒康县人民政府」链接 HTML 提取, title=芒康县人民政府"),
    ("甘肃省", "临夏回族自治州", "县级:永靖县",
     "https://www.linxia.gov.cn/lxz/lxly/jdzs/yjx/index.html", "http://www.gsyongjing.gov.cn",
     "L2|临夏州门户「永靖县政府网」链接 HTML 提取, title=永靖县人民政府"),
    ("甘肃省", "临夏回族自治州", "县级:广河县",
     "https://www.linxia.gov.cn/lxz/lxly/jdzs/ghx/index.html", "http://www.ghx.gov.cn/",
     "L2|临夏州门户「广河县政府网」链接 HTML 提取, title=广河县人民政府"),
    ("江苏省", "苏州市", "县级:苏州工业园区",
     "http://www.suzhou.gov.cn", "http://www.sipac.gov.cn/",
     "L2|苏州市门户「苏州工业园区管委会」链接 HTML 提取, title=苏州工业园区管理委员会"),
    ("新疆维吾尔自治区", "和田地区", "县级:和田市",
     "https://www.xjht.gov.cn/", "http://www.hts.gov.cn/",
     "L2|和田地区门户「和田市」链接 HTML 提取（站点对自动请求返回 403，title 未取）"),
]
# (prov, city, system, old_url, note)  old_url=None 表示不校验当前值
CLEAR = [
    # 新疆 10：xjcourt.org / *.chinacourt.gov.cn 子域全 NXDOMAIN；
    # 巴音郭楞为诉讼资产网详情页（非机构站）；阿克苏/阿勒泰还挂成市法院；
    # 乌鲁木齐 elink 目标 www.urumqicourt.org 存活但全路径 404（站已下线）
    ("新疆维吾尔自治区", "乌鲁木齐市", "市中级人民法院",
     "https://elink.chinacourt.cn/link?elid=http://www.urumqicourt.org/", None),
    ("新疆维吾尔自治区", "吐鲁番市", "市中级人民法院",
     "http://tlfzy.chinacourt.gov.cn/index.shtml", None),
    ("新疆维吾尔自治区", "哈密市", "市中级人民法院",
     "https://elink.chinacourt.cn/link?elid=http://hmzy.xjcourt.org/", None),
    ("新疆维吾尔自治区", "博尔塔拉蒙古自治州", "市中级人民法院",
     "https://elink.chinacourt.cn/link?elid=http://bzzy.xjcourt.org/", None),
    ("新疆维吾尔自治区", "巴音郭楞蒙古自治州", "市中级人民法院",
     "https://www.rmfysszc.gov.cn/statichtml/rm_xmdetail/6213505-1.shtml", None),
    ("新疆维吾尔自治区", "阿克苏地区", "市中级人民法院",
     "http://akss.xjcourt.org/", None),
    ("新疆维吾尔自治区", "克孜勒苏柯尔克孜自治州", "市中级人民法院",
     "https://elink.chinacourt.cn/link?elid=http://kzzy.xjcourt.org/", None),
    ("新疆维吾尔自治区", "喀什地区", "市中级人民法院",
     "https://elink.chinacourt.cn/link?elid=http://kszy.xjcourt.org/", None),
    ("新疆维吾尔自治区", "塔城地区", "市中级人民法院",
     "https://elink.chinacourt.cn/link?elid=http://tczy.xjcourt.org/", None),
    ("新疆维吾尔自治区", "阿勒泰地区", "市中级人民法院",
     "http://alts.xjcourt.org/", None),
    # 其余 18 个 NXDOMAIN（系统 DNS+阿里公共 DNS 双重复核）
    ("河北省", "承德市", "市人大", "https://cdrd.hehechengde.cn/", None),
    ("江苏省", "常州市", "市中级人民法院", "http://fy.changzhou.gov.cn", None),
    ("陕西省", "汉中市", "市人大", "http://rd.hanzhong.gov.cn/", None),
    ("陕西省", "汉中市", "市政协", "http://zx.hanzhong.gov.cn/", None),
    ("吉林省", "通化市", "市政协", "http://thszhengxie.gov.cn", None),
    ("内蒙古自治区", "阿拉善盟", "市人大", "http://www.alsrd.gov.cn/", None),
    ("甘肃省", "定西市", "市人大", "http://www.dxrdw.gov.cn/", None),
    ("湖南省", "衡阳市", "市政协", "http://www.hnhyzx.gov.cn/", None),
    ("甘肃省", "陇南市", "市政协", "http://www.lnszx.gov.cn/", None),
    ("甘肃省", "临夏回族自治州", "市政协", "http://www.lxzzx.gov.cn/", None),
    ("四川省", "眉山市", "市人民检察院", "http://www.msjcy.gov.cn/", None),
    ("河南省", "平顶山市", "市政协", "http://www.pdszx.gov.cn/", None),
    ("吉林省", "松原市", "市政协", "http://www.songyuanzx.gov.cn/", None),
    ("辽宁省", "铁岭市", "市人大", "http://www.tlrd.gov.cn/", None),
    ("浙江省", "温州市", "市人大", "http://www.wzrd.gov.cn", None),
    ("四川省", "凉山彝族自治州", "市政协", "http://zx.lsz.gov.cn", None),
    ("广西壮族自治区", "桂林市", "市中级人民法院", "http://glzy.chinacourt.gov.cn", None),
]
XJ = "新疆法院网（xjfy.xjcourt.gov.cn）「法院网站群」导航仍指向旧域 xjcourt.org/chinacourt.gov.cn，目标域全部 NXDOMAIN；" \
     "各市政府门户首页无法院入口；无合规在线替代"
DEAD = "站点域名 NXDOMAIN（系统 DNS + 阿里公共 DNS 双重复核），权威导航仍指向旧域，暂无合规在线替代"


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


ETHNIC = ("蒙古", "藏", "回", "维吾尔", "哈萨克", "柯尔克孜", "朝鲜", "壮", "苗",
          "侗", "白", "傣", "彝", "哈尼", "拉祜", "傈僳", "佤", "水", "羌",
          "布依", "仡佬", "仫佬", "毛南", "瑶", "畲", "土家", "锡伯", "达斡尔",
          "鄂温克", "鄂伦春", "赫哲", "俄罗斯", "塔塔尔", "乌孜别克", "塔吉克",
          "撒拉", "保安", "裕固", "东乡", "纳西", "景颇", "阿昌", "普米",
          "怒", "德昂", "独龙", "基诺", "门巴", "珞巴", "京")


def core_of(city):
    x = re.sub(r"(自治州|地区|盟|市)$", "", city)
    for e in ETHNIC:
        x = re.sub(e + "族?$", "", x)
    return x or city


def atomic(obj, path):
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
    with os.fdopen(fd, "w") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


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

    def node_of(prov, city, sysn):
        if sysn.startswith("县级:"):
            c = find(find(blk, prov), city)
            return find(c, sysn.split(":", 1)[1]) if c else None
        p = find(blk, prov); c = find(p, city) if p else None
        jg = next((x for x in (c or {}).get("ks", []) if x.get("c") == "并列机关"), None)
        return find(jg, sysn) if jg else None

    reg = json.load(open(REG_F, encoding="utf-8"))
    # 显式 registry 键（形态特殊/分类错位的）
    REG_FORCE = {
        ("湖南省", "衡阳市", "县级:衡阳县"): "县级人民政府|衡阳县",
        ("湖南省", "娄底市", "市政协"): "人大|娄底市政协",
        ("河南省", "濮阳市", "市中级人民法院"): "法院|濮阳市人民法院",
    }

    stats = {"replace": 0, "clear": 0, "skip": 0, "reg": 0}
    changes = []
    for prov, city, sysn, old, new, note in REPLACE:
        o = node_of(prov, city, sysn)
        if not o:
            print(f"SKIP 未找到节点 {prov}/{city}/{sysn}"); stats["skip"] += 1; continue
        cur = (o.get("u") or "").strip()
        if old and ukey(cur) != ukey(old):
            print(f"SKIP 现值不符 {prov}/{city}/{sysn} 当前={cur[:60]} 期望旧值={old[:60]}")
            stats["skip"] += 1; continue
        o["u"] = new
        o["s"] = f"来源:{note}；2026-11-17 p220 死链/错挂修复"
        print(f"REPLACE {prov}/{city}/{sysn}\n    {cur[:70]}\n -> {new}")
        changes.append((prov, city, sysn, cur, new, note)); stats["replace"] += 1

    for prov, city, sysn, old, _ in CLEAR:
        o = node_of(prov, city, sysn)
        if not o:
            print(f"SKIP 未找到节点 {prov}/{city}/{sysn}"); stats["skip"] += 1; continue
        cur = (o.get("u") or "").strip()
        if not cur:
            print(f"SKIP 已空 {prov}/{city}/{sysn}"); stats["skip"] += 1; continue
        if old and ukey(cur) != ukey(old):
            print(f"SKIP 现值不符 {prov}/{city}/{sysn} 当前={cur[:60]} 期望={old[:60]}")
            stats["skip"] += 1; continue
        reason = XJ if prov == "新疆维吾尔自治区" else DEAD
        o["u"] = ""
        o["s"] = f"2026-11-17 p220：原值 {cur[:90]}；{reason} → 列名"
        m = o.get("m") or ""
        add = f"2026-11-17：原官网 {cur[:80]} 已失效（{reason}）"
        if add not in m:
            o["m"] = (m + "；" + add) if m else add
        print(f"CLEAR   {prov}/{city}/{sysn}\n    {cur[:70]}")
        changes.append((prov, city, sysn, cur, "", reason)); stats["clear"] += 1

    # 条树同步（5 系统）：同城市同系统且 URL 仍等于旧值的节点一起改，
    # 避免块树与条树不一致（地图 fy/rd/zx/jcy/jw 条模式由块树派生，
    # 但 tree.json 条树仍需同源）。县级政府节点条树无对应，跳过。
    TIAO_KW = {"市人大": ("人大",), "市政协": ("政协",),
               "市中级人民法院": ("法院", "中级"), "市人民检察院": ("检察",),
               "市监委": ("监委", "纪委", "纪检监察")}

    def tiao_nodes(city, sysn):
        core = core_of(city)
        kws = TIAO_KW.get(sysn, ())
        out = []

        def walk(n):
            nm = n.get("n") or ""
            if core and core in nm and kws and all(k in nm for k in kws) \
                    and len(nm) <= len(core) + 14 and n is not blk:
                out.append(n)
            for c in n.get("ks") or []:
                walk(c)

        for top in t.get("ks") or []:
            if (top.get("n") or "").startswith("条"):
                for sub in top.get("ks") or []:
                    walk(sub)
        return out

    stats["tiao"] = 0
    for prov, city, sysn, old, new, note in REPLACE:
        if sysn.startswith("县级:"):
            continue
        for n in tiao_nodes(city, sysn):
            if ukey(n.get("u")) == ukey(old):
                print(f"TIAO     {city}/{sysn}: {n.get('n')} {n.get('u')[:60]} -> {new[:60]}")
                n["u"] = new
                n["s"] = f"来源:{note}；2026-11-17 p220 同步"
                stats["tiao"] += 1
    for prov, city, sysn, old, _ in CLEAR:
        if sysn.startswith("县级:"):
            continue
        for n in tiao_nodes(city, sysn):
            if ukey(n.get("u")) == ukey(old):
                print(f"TIAO     {city}/{sysn}: {n.get('n')} {n.get('u')[:60]} -> (空)")
                n["u"] = ""
                n["s"] = f"2026-11-17 p220：原值 {old[:80]} 域名失效 → 列名"
                stats["tiao"] += 1

    # registry 同步
    def reg_update(prov, city, sysn, old, new, note):
        k = REG_FORCE.get((prov, city, sysn))
        target = None
        if sysn.startswith("县级:"):
            name = sysn.split(":", 1)[1]
            cand = f"县级人民政府|{name}"
            if cand in reg:
                target = cand
            else:
                hits = [kk for kk, v in reg.items()
                        if ukey(v.get("u")) == ukey(old) and name in kk]
                target = hits[0] if hits else None
        elif k and k in reg:
            target = k
        else:
            core = core_of(city)
            cands = [kk for kk, v in reg.items()
                     if ukey(v.get("u")) == ukey(old) and core in (kk + (v.get("n") or ""))
                     and not kk.startswith("县级法院")]
            if cands:
                cands = [kk for kk in cands if not kk.startswith("县级人民政府|")]
            target = cands[0] if cands else None
        if not target:
            if sysn.startswith("县级:") and new:
                name = sysn.split(":", 1)[1]
                key = f"县级人民政府|{name}"
                if key not in reg:
                    reg[key] = {"u": new, "n": name, "locations": ["块"],
                                "source_level": "L2", "verified_at": "2026-11-17",
                                "status": "ok", "snapshot": ""}
                    print(f"REG-INS [{key}] -> {new[:60]}")
                    stats["reg"] += 1
                    return
            print(f"REG-MISS {prov}/{city}/{sysn} old={old[:50]}")
            return
        e = reg[target]
        e["u"] = new
        e["status"] = "ok" if new else "cleared"
        e["verified_at"] = "2026-11-17"
        if new:
            e["source_level"] = "L1" if note.startswith("L1|") else "L2"
        print(f"REG   [{target}] {old[:50] or '(空)'} -> {new[:60] or '(空)'}")
        stats["reg"] += 1

    for prov, city, sysn, old, new, note in changes:
        reg_update(prov, city, sysn, old, new, note)

    print("\n统计:", stats, "DRY" if DRY else "")
    if DRY:
        return
    os.makedirs(BAK_DIR, exist_ok=True)
    ts = time.strftime("%H%M%S")
    shutil.copy2(TREE_F, os.path.join(BAK_DIR, f"tree_before_p220_{ts}.json"))
    shutil.copy2(REG_F, os.path.join(BAK_DIR, f"registry_before_p220_{ts}.json"))
    atomic(t, TREE_F)
    atomic(reg, REG_F)
    print("已落库，备份时间戳:", ts)


if __name__ == "__main__":
    main()
