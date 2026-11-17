#!/usr/bin/env python
# p218 死域名清理 + 衡阳县错挂修正（2026-11-17 第五轮）
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
    ("河南省", "濮阳市", "市中级人民法院",
     "http://hnpyfy.hncourt.gov.cn", "https://pyzy.hncourt.gov.cn/",
     "L1|河南高院官网中院导航/registry 已验 title=濮阳市中级人民法院"
     "（原 hnpyfy=濮阳县法院网，县级错挂）"),
    ("湖南省", "娄底市", "市政协",
     "http://www.ldzx.gov.cn/", "http://ldzx.hnloudi.gov.cn/",
     "L2|娄底市政府门户首页「市政协」链接 HTML 提取, title=政协娄底市委员会"
     "（原 www.ldzx.gov.cn 域名 NXDOMAIN）"),
    ("湖南省", "衡阳市", "县级:衡阳县",
     "https://www.hengyang.gov.cn/", "http://www.hyx.gov.cn/",
     "L2|衡阳市政府门户「网站群-县市区人民政府」页 HTML 提取, "
     "title=衡阳县人民政府门户网站（原值误挂市门户）"),
]
# (prov, city, system, old_url, note)  old_url=None 表示不校验当前值
CLEAR = [
    # 新疆 11：xjcourt.org / *.chinacourt.gov.cn 子域全 NXDOMAIN；
    # 巴音郭楞为诉讼资产网详情页（非机构站）；阿克苏/阿勒泰还挂成市法院
    ("新疆维吾尔自治区", "乌鲁木齐市", "市中级人民法院",
     "https://elink.chinacourt.cn/link?elid=http://www.urumqicourt.org/", None),
    ("新疆维吾尔自治区", "吐鲁番市", "市中级人民法院",
     "http://tlfzy.chinacourt.gov.cn/index.shtml", None),
    ("新疆维吾尔自治区", "哈密市", "市中级人民法院",
     "https://elink.chinacourt.cn/link?elid=http://hmzy.xjcourt.org/", None),
    ("新疆维吾尔自治区", "昌吉回族自治州", "市中级人民法院",
     "http://cjzy.chinacourt.gov.cn/index.shtml", None),
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
    ("甘肃省", "酒泉市", "市政协", "http://zx.jiuquan.gov.cn/", None),
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
        o["s"] = f"来源:{note}；2026-11-17 p218 死链/错挂修复"
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
        o["s"] = f"2026-11-17 p218：原值 {cur[:90]}；{reason} → 列名"
        m = o.get("m") or ""
        add = f"2026-11-17：原官网 {cur[:80]} 已失效（{reason}）"
        if add not in m:
            o["m"] = (m + "；" + add) if m else add
        print(f"CLEAR   {prov}/{city}/{sysn}\n    {cur[:70]}")
        changes.append((prov, city, sysn, cur, "", reason)); stats["clear"] += 1

    # registry 同步
    def reg_update(prov, city, sysn, old, new, note):
        k = REG_FORCE.get((prov, city, sysn))
        target = None
        if k and k in reg:
            target = k
        else:
            core = re.sub(r"(市|地区|盟|自治州)$", "", city)
            cands = [kk for kk, v in reg.items()
                     if ukey(v.get("u")) == ukey(old) and core in (kk + (v.get("n") or ""))
                     and not kk.startswith("县级法院")]
            # 「县级:X县」形态只认县级人民政府键
            if sysn.startswith("县级:"):
                cands = [kk for kk in cands if kk.startswith("县级人民政府|")]
            elif cands:
                cands = [kk for kk in cands if not kk.startswith("县级人民政府|")]
            target = cands[0] if cands else None
        if not target:
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
    shutil.copy2(TREE_F, os.path.join(BAK_DIR, f"tree_before_p218_{ts}.json"))
    shutil.copy2(REG_F, os.path.join(BAK_DIR, f"registry_before_p218_{ts}.json"))
    atomic(t, TREE_F)
    atomic(reg, REG_F)
    print("已落库，备份时间戳:", ts)


if __name__ == "__main__":
    main()
