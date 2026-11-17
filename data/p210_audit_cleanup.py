#!/usr/bin/env python
# p210 五系统市级 + 医疗系统 URL 审计清洗落库（2026-11-17 用户指令「检验正确性」）
# 依据 p205_audit_5sys（五系统 1463 条）与 p214_medical_verify（304 条）复验结果:
#   ① 替换: 已由权威源重新确认的 URL（内蒙古 12 盟市纪委、东营中院、青海 3 州纪委频道）
#   ② 根化: 深页/新闻页 → 站点根或频道根（title 已验证）
#   ③ 清除: 新闻页/门户页/张冠李戴 → u=""（列名, 不猜域名）
# 每条动作前验证 title（除非 L1 权威源明确链接）; 写前备份 tree.json。
import json, os, re, sys, shutil, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TREE_F = os.path.join(ROOT, "data", "tree.json")
BAK_DIR = os.path.join(ROOT, "backups", "2026-11-17")
DRY = "--dry" in sys.argv

ETH = r"(哈萨克族?|维吾尔族?|柯尔克孜族?|朝鲜族?|蒙古族?|藏族?|回族?|壮族?|苗族?|黎族?|侗族?|满族?|白族?|傣族?|彝族?|哈尼族?|拉祜族?|傈僳族?|佤族?|水族?|羌族?|布依族?|仡佬族?|仫佬族?|毛南族?|瑶族?|畲族?|土家族?|锡伯族?|达斡尔族?|鄂温克族?|鄂伦春族?|赫哲族?|俄罗斯族?|塔塔尔族?|乌孜别克族?|塔吉克族?|撒拉族?|保安族?|裕固族?|东乡族?|纳西族?|景颇族?|阿昌族?|普米族?|怒族?|德昂族?|独龙族?|基诺族?|门巴族?|珞巴族?|京族?|自治)$"
def base(nm):
    x = re.sub(r"[（(][^（）)]*[）)]$", "", nm or "")
    x = re.sub(r"(自治州|自治县|自治旗|地区|盟|市|县|区|旗|州)$", "", x)
    for _ in range(8):
        x2 = re.sub(ETH, "", x)
        if x2 == x or len(x2) < 2: break
        x = x2
    return x

# ── ① 替换（权威源重新确认）────────────────────────────────────────────
REPLACE = [
    # 内蒙古 12 盟市纪委监委: 内蒙古纪委监委官网 nmgjjjc.gov.cn 盟市导航 HTML 提取
    ("内蒙古自治区", "呼和浩特市", "市监委", "http://hhht.nmgjjjc.gov.cn/", "L1|内蒙古纪委监委官网盟市导航"),
    ("内蒙古自治区", "包头市", "市监委", "http://bts.nmgjjjc.gov.cn/", "L1|内蒙古纪委监委官网盟市导航"),
    ("内蒙古自治区", "呼伦贝尔市", "市监委", "http://hlbes.nmgjjjc.gov.cn/", "L1|内蒙古纪委监委官网盟市导航"),
    ("内蒙古自治区", "兴安盟", "市监委", "http://xam.nmgjjjc.gov.cn/", "L1|内蒙古纪委监委官网盟市导航"),
    ("内蒙古自治区", "通辽市", "市监委", "http://tls.nmgjjjc.gov.cn/", "L1|内蒙古纪委监委官网盟市导航"),
    ("内蒙古自治区", "赤峰市", "市监委", "http://cfs.nmgjjjc.gov.cn/", "L1|内蒙古纪委监委官网盟市导航"),
    ("内蒙古自治区", "锡林郭勒盟", "市监委", "http://xlglm.nmgjjjc.gov.cn/", "L1|内蒙古纪委监委官网盟市导航"),
    ("内蒙古自治区", "乌兰察布市", "市监委", "http://wlcb.nmgjjjc.gov.cn/", "L1|内蒙古纪委监委官网盟市导航"),
    ("内蒙古自治区", "鄂尔多斯市", "市监委", "https://www.ordoslz.gov.cn/", "L1|内蒙古纪委监委官网盟市导航"),
    ("内蒙古自治区", "巴彦淖尔市", "市监委", "http://bynes.nmgjjjc.gov.cn/", "L1|内蒙古纪委监委官网盟市导航"),
    ("内蒙古自治区", "乌海市", "市监委", "http://whs.nmgjjjc.gov.cn/", "L1|内蒙古纪委监委官网盟市导航"),
    ("内蒙古自治区", "阿拉善盟", "市监委", "http://alsm.nmgjjjc.gov.cn/", "L1|内蒙古纪委监委官网盟市导航"),
    # 山东东营中院: 聊城中院官网首页「东营市中级人民法院」真实链接
    ("山东省", "东营市", "市中级人民法院", "http://dyzy.sdcourt.gov.cn", "L1|聊城中院官网友情链接HTML提取+title验证"),
    # 青海 3 州纪委频道: 青海省纪委官网首页市州纪委监委链接（L1, GBK 频道页 title 乱码）
    ("青海省", "黄南藏族自治州", "市监委",
     "http://www.qhjc.gov.cn/subsite/index_4266071fc689ceed_34FA43836CB6C040.html", "L1|青海省纪委官网市州导航"),
    ("青海省", "海西蒙古族藏族自治州", "市监委",
     "http://www.qhjc.gov.cn/subsite/index_4266071fc689ceed_708CA5EACD6615DF.html", "L1|青海省纪委官网市州导航"),
    ("青海省", "果洛藏族自治州", "市监委",
     "http://www.qhjc.gov.cn/subsite/index_4266071fc689ceed_7E529FA9AFBD6274.html", "L1|青海省纪委官网市州导航"),
]

# ── ② 根化（深页/新闻页 → 站点根，title 已验证）────────────────────────
ROOTIZE = [
    ("山西省", "长治市", "市政协", "https://www.czszx.gov.cn/", "深页→站点根, title=中国人民政治协商会议长治市委员会"),
    ("辽宁省", "鞍山市", "市监委", "http://jjjc.anshan.gov.cn/", "新闻页→站点根, title=鞍山纪检监察网"),
    ("新疆维吾尔自治区", "克孜勒苏柯尔克孜自治州", "市人民检察院",
     "http://www.kezilesu.jcy.gov.cn/", "概况深页→站点根, title=克孜勒苏柯尔克孜自治州人民检察院"),
    ("宁夏回族自治区", "石嘴山市", "市人民检察院", "https://nx.jcy.gov.cn/szssy/", "概况深页→频道根, title=石嘴山市人民检察院"),
    ("宁夏回族自治区", "固原市", "市人民检察院", "https://nx.jcy.gov.cn/gysy/", "概况深页→频道根, title=固原市人民检察院"),
]

# ── ③ 清除（新闻页/门户页/张冠李戴 → 列名）──────────────────────────────
CLEAR = [
    ("吉林省", "延边朝鲜族自治州", "市政协"),          # ybzx.gov.cn title=延边州人民政府, 无政协痕迹
    ("河北省", "廊坊市", "市人大"),                    # 市政府门户新闻 Item
    ("辽宁省", "丹东市", "市政协"),                    # 人社局答复文章
    ("辽宁省", "营口市", "市政协"),                    # 工信局新闻
    ("辽宁省", "朝阳市", "市政协"),                    # bjchy=北京朝阳区
    ("吉林省", "通化市", "市人大"),                    # javascript:void(0)
    ("吉林省", "白城市", "市人大"),                    # javascript:void(0)
    ("吉林省", "松原市", "市人大"),                    # wap 门户预算新闻
    ("黑龙江省", "鹤岗市", "市政协"),                  # 省政协新闻
    ("黑龙江省", "双鸭山市", "市政协"),                # 省政协新闻
    ("黑龙江省", "绥化市", "市政协"),                  # 省政协新闻
    ("黑龙江省", "佳木斯市", "市政协"),                # 信用网新闻
    ("湖南省", "湘西土家族苗族自治州", "市监委"),      # 三湘风纪新闻
    ("广东省", "佛山市", "市中级人民法院"),            # 广东法院网新闻
    ("广东省", "东莞市", "市政协"),                    # loading.html 跳转壳
    ("广东省", "东莞市", "市监委"),                    # loading.html 跳转壳
    ("广东省", "东莞市", "市中级人民法院"),            # 广东法院网新闻
    ("广西壮族自治区", "河池市", "市政协"),            # 发改委新闻
    ("广西壮族自治区", "来宾市", "市政协"),            # 忻城县政府新闻
    ("贵州省", "黔东南苗族侗族自治州", "市政协"),      # 投资促进局新闻
    ("云南省", "楚雄彝族自治州", "市人大"),            # 州门户「人大代表建议」栏目
    ("云南省", "红河哈尼族彝族自治州", "市监委"),      # 省纪委新闻
    ("云南省", "大理白族自治州", "市人大"),            # 云南人大网新闻
    ("云南省", "德宏傣族景颇族自治州", "市人大"),      # 云南人大网新闻
    ("云南省", "怒江傈僳族自治州", "市监委"),          # 省纪委新闻
    ("西藏自治区", "拉萨市", "市人大"),                # 北京人大网新闻
    ("西藏自治区", "拉萨市", "市政协"),                # 拉萨市政府新闻
    ("西藏自治区", "日喀则市", "市人大"),              # 市委网新闻
    ("西藏自治区", "日喀则市", "市政协"),              # 市委网新闻
    ("西藏自治区", "昌都市", "市人大"),                # 部门新闻
    ("西藏自治区", "昌都市", "市政协"),                # 部门新闻
    ("西藏自治区", "昌都市", "市监委"),                # 省纪委新闻
    ("西藏自治区", "林芝市", "市人大"),                # 巴宜区公告
    ("西藏自治区", "林芝市", "市政协"),                # 经开区新闻
    ("西藏自治区", "山南市", "市政协"),                # 商务局新闻
    ("西藏自治区", "山南市", "市监委"),                # 省纪委职务页
    ("西藏自治区", "那曲市", "市政协"),                # 市委网新闻
    ("西藏自治区", "阿里地区", "市人大"),              # 西藏政府网新闻
    ("西藏自治区", "阿里地区", "市政协"),              # 地委网领导页
    ("山东省", "淄博市", "市中级人民法院"),            # court.gov.cn=最高法
    ("甘肃省", "武威市", "市人大"),                    # 审计局栏目
    ("甘肃省", "武威市", "市政协"),                    # 政务网栏目
    ("甘肃省", "张掖市", "市人大"),                    # 甘肃人大网新闻
    ("甘肃省", "庆阳市", "市政协"),                    # 市政府门户
    ("宁夏回族自治区", "石嘴山市", "市人大"),          # 市政府预决算栏目
    ("宁夏回族自治区", "石嘴山市", "市政协"),          # 省政协新闻
    ("宁夏回族自治区", "吴忠市", "市人大"),            # 兴庆区党建网新闻
    ("宁夏回族自治区", "吴忠市", "市政协"),            # 市政府栏目
    ("宁夏回族自治区", "固原市", "市政协"),            # 原州区政府新闻
    ("新疆维吾尔自治区", "昌吉回族自治州", "市人大"),  # 昌吉市政府新闻
    ("新疆维吾尔自治区", "昌吉回族自治州", "市政协"),  # 昌吉市政府新闻
    ("新疆维吾尔自治区", "喀什地区", "市人大"),        # 喀什市政府信息公开
    ("新疆维吾尔自治区", "塔城地区", "市人大"),        # 行署「人大建议」栏目
    ("新疆维吾尔自治区", "阿勒泰地区", "市政协"),      # 行署新闻
    ("福建省", "宁德市", "市监委"),                    # 省纪委新闻
    ("江西省", "赣州市", "市监委"),                    # 省纪委新闻
    ("湖北省", "荆州市", "市监委"),                    # 经开区新闻
]

# ── ④ 医疗系统清除（门户页/死链）────────────────────────────────────────
MED_CLEAR = [
    "通化市卫生健康委员会", "韶关市卫生健康委员会", "北海市卫生健康委员会",
    "忠县卫生健康委员会", "南充市卫生健康委员会", "普洱市卫生健康委员会",
    "楚雄彝族自治州卫生健康委员会", "德宏傣族景颇族自治州卫生健康委员会",
    "铜川市卫生健康委员会", "商洛市卫生健康委员会", "阿克苏地区卫生健康委员会",
    "周口市卫生健康委员会", "汉中市卫生健康委员会", "渭南市卫生健康委员会",
]

_lock = None
def verify(u, city, sysn, trust=False):
    """title 验证: 含市名基底 + 机构词; trust=True 的 L1 权威链接直接放行"""
    if trust:
        return True, "(L1 权威源, 免 title 校验)"
    import time as _t
    last = ""
    for attempt in range(3):          # gov 站偶发超时, 单次失败不判死
        try:
            import curl_cffi.requests as cr
            global _lock
            if _lock is None:
                _lock = cr.Session(impersonate="chrome124")
            r = _lock.get(u, timeout=20, verify=False)
            raw = r.content
            m = re.search(rb'charset=["\']?([a-zA-Z0-9-]+)', raw[:4096])
            enc = m.group(1).decode() if m else None
            h = None
            for e in (enc, "utf-8", "gb18030"):
                if not e: continue
                try:
                    h = raw.decode(e); break
                except Exception:
                    continue
            if h is None:
                h = raw.decode("utf-8", "ignore")
            mt = re.search(r"<title[^>]*>(.*?)</title>", h, re.S | re.I)
            tt = re.sub(r"\s+", " ", mt.group(1)).strip() if mt else ""
            if r.status_code != 200 or not tt:
                last = f"HTTP {r.status_code} title空"
                _t.sleep(1.5); continue
            cn = base(city)
            okcity = (cn in tt) or (city in tt)
            # 「中国人民政治协商会议长治市委员会」不含连续「政协」——须含「协商」
            # （p205 OWS 同修；简称站名如「沈阳纪检监察网」「清廉宁波」靠扩展词兜住）
            KW = {"市人大": ("人大常委会", "人民代表大会", "人大"),
                  "市政协": ("政协", "协商"),
                  "市中级人民法院": ("中级人民法院", "人民法院", "法院", "中院"),
                  "市人民检察院": ("人民检察院", "检察院", "检察"),
                  "市监委": ("监察委员会", "纪委监委", "纪律检查委员会", "纪委",
                            "纪检监察", "监委", "廉政", "清风")}
            okkw = any(w in tt for w in KW[sysn])
            if not (okcity and okkw):
                last = tt[:50] + ("" if okcity else " [无市名]") + ("" if okkw else " [无机构词]")
                return False, last          # title 明确不符: 不重试
            return True, tt[:50]
        except Exception as e:
            last = f"{type(e).__name__}:{str(e)[:40]}"
            _t.sleep(1.5)
    return False, last


def main():
    t = json.load(open(TREE_F, encoding="utf-8"))
    blk = next(g for g in t["ks"] if g.get("n", "").startswith("省级"))
    tiao = next(g for g in t["ks"] if "条" in g.get("n", ""))
    med = next(g for g in tiao.get("ks", []) if g.get("n") == "医疗系统（卫生健康）")

    def find(n, name):
        if n.get("n") == name:
            return n
        for c in n.get("ks", []):
            r = find(c, name)
            if r:
                return r
        return None

    stats = {"replace": 0, "rootize": 0, "clear": 0, "med_clear": 0, "skip": 0, "fail": 0}
    log = []

    for prov, city, sysn, u, note in REPLACE:
        p = find(blk, prov); c = find(p, city) if p else None
        jg = next((x for x in (c or {}).get("ks", []) if x.get("c") == "并列机关"), None)
        o = find(jg, sysn) if jg else None
        if not o:
            log.append(f"SKIP 未找到 {prov}/{city}/{sysn}"); stats["skip"] += 1; continue
        ok, info = verify(u, city, sysn, trust=note.startswith("L1|"))
        if not ok:
            log.append(f"FAIL 验证不过 {prov}/{city}/{sysn} -> {u} | {info}"); stats["fail"] += 1; continue
        log.append(f"REPLACE {prov}/{city}/{sysn}\n    {o.get('u','')[:70]}\n -> {u}\n    ({info})")
        o["u"] = u
        o["s"] = f"来源:{note}；2026-11-17 p210 修正"
        stats["replace"] += 1

    for prov, city, sysn, u, note in ROOTIZE:
        p = find(blk, prov); c = find(p, city) if p else None
        jg = next((x for x in (c or {}).get("ks", []) if x.get("c") == "并列机关"), None)
        o = find(jg, sysn) if jg else None
        if not o:
            log.append(f"SKIP 未找到 {prov}/{city}/{sysn}"); stats["skip"] += 1; continue
        ok, info = verify(u, city, sysn)
        if not ok:
            log.append(f"FAIL 验证不过 {prov}/{city}/{sysn} -> {u} | {info}"); stats["fail"] += 1; continue
        log.append(f"ROOTIZE {prov}/{city}/{sysn}: {o.get('u','')[:55]} -> {u} ({info})")
        o["u"] = u
        o["s"] = f"来源:{note}；2026-11-17 p210 根化"
        stats["rootize"] += 1

    for prov, city, sysn in CLEAR:
        p = find(blk, prov); c = find(p, city) if p else None
        jg = next((x for x in (c or {}).get("ks", []) if x.get("c") == "并列机关"), None)
        o = find(jg, sysn) if jg else None
        if not o or not (o.get("u") or "").strip():
            log.append(f"SKIP 已空 {prov}/{city}/{sysn}"); stats["skip"] += 1; continue
        log.append(f"CLEAR {prov}/{city}/{sysn}: {o.get('u','')[:70]}")
        o["u"] = ""
        o["s"] = "2026-11-17 p210 审计清除：原URL为新闻页/门户页/张冠李戴，非本机构官网"
        stats["clear"] += 1

    for nm in MED_CLEAR:
        o = find(med, nm)
        if not o or not (o.get("u") or "").strip():
            log.append(f"SKIP 医疗已空 {nm}"); stats["skip"] += 1; continue
        log.append(f"CLEAR(医疗) {nm}: {o.get('u','')[:70]}")
        o["u"] = ""
        o["s"] = "2026-11-17 p210 审计清除：门户首页/死链，非卫健委官网"
        stats["med_clear"] += 1

    print("\n".join(log))
    print("\n统计:", stats, "DRY" if DRY else "")
    if DRY:
        return
    os.makedirs(BAK_DIR, exist_ok=True)
    bak = os.path.join(BAK_DIR, f"tree_before_p210_{time.strftime('%H%M%S')}.json")
    shutil.copy2(TREE_F, bak)
    json.dump(t, open(TREE_F, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("已落库, 备份:", bak)


if __name__ == "__main__":
    main()
