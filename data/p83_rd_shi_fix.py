# -*- coding: utf-8 -*-
"""P83: 补 6 省市级人大（福建/陕西/黑龙江/辽宁/青海/重庆）→ rd_shi.jsonl。

来源（全部真实 HTML，p82 渲染/静态保存）：
- 福建 http://szrd.fjrd.gov.cn/ 首页 footer「我省地方人大网站」区块（9/9）
- 陕西 sxrd.gov.cn/#/index「陕西省各地人大网站」隐藏层（10/10）
- 黑龙江 hljrd.gov.cn 首页 select「市级人大网站」（3/13，其余列名）
- 辽宁 lnrd.gov.cn 首页 select「市级人大网站」（13/14，缺鞍山列名）
- 青海 qhrd.gov.cn 首页底部「地方人大」区块（8/8 市州 + 县级备用）
- 重庆 cqrd.gov.cn 首页「区县人大」区块（10/38，其余列名）
"""
import json
import re

HTMLS = {
    "福建省": "p82_福建省.html",
    "陕西省": "p82_陕西省.html",
    "黑龙江省": "p82_黑龙江省.html",
    "辽宁省": "p82_辽宁省.html",
    "青海省": "p82_青海省.html",
    "重庆市": "p82_重庆市.html",
}


def links_in(html, pat):
    """按正则匹配 <a> 返回 {text: url}。"""
    out = {}
    for u, txt in re.findall(pat, html):
        t = re.sub(r"\s+", "", txt)
        if u.startswith(("http://", "https://")) and t not in out:
            out[t] = u
    return out


def extract_fj(html):
    """福建：footer「我省地方人大网站」区块——省人大链接块之后、站点地图之前。"""
    m = re.search(r'福建省人大[^<]*</a>|我省地方人大', html)
    # 直接从「福州市人大」到「站点地图」之间的区块抓
    seg = html[max(0, html.find("福州市人大") - 300):html.find("站点地图")]
    d = {}
    for u, txt in re.findall(
            r'<a[^>]+href="([^"]+)"[^>]*>\s*([^<]{4,24}?)\s*</a>', seg):
        t = re.sub(r"\s+", "", txt)
        if "人大" in t and t not in d:
            d[t] = u
    return d


def extract_sx(html):
    """陕西：「陕西省各地人大网站」隐藏层 xqrd。"""
    m = re.search(r'class="yqlj-content xqrd"[^>]*>(.*?)</div>', html, re.S)
    if not m:
        return {}
    d = {}
    for u, txt in re.findall(
            r'<a[^>]+href="([^"]+)"[^>]*>\s*<span[^>]*>([^<]{2,8}?)</span>', m.group(1)):
        d[re.sub(r"\s+", "", txt)] = u
    return d


def extract_hlj(html):
    """黑龙江：select name=link3 市级人大网站。"""
    m = re.search(r'<select[^>]*name="link3"[^>]*>(.*?)</select>', html, re.S)
    if not m:
        return {}
    d = {}
    for v, txt in re.findall(r'<option value="([^"]+)">([^<]+)</option>', m.group(1)):
        if v == "0" or "人大网站" in txt:
            continue
        d[re.sub(r"\s+", "", txt)] = v
    return d


def extract_ln(html):
    """辽宁：含市人大选项的 select（第二个下拉）。"""
    d = {}
    for sel in re.findall(r'<select[^>]*>(.*?)</select>', html, re.S):
        opts = re.findall(r'<option value="([^"]+)">([^<]+)</option>', sel)
        if any("市人大" in x[1] for x in opts):
            for v, txt in opts:
                if "人大" in txt and "省" not in txt:
                    d[re.sub(r"\s+", "", txt)] = v
    return d


def extract_qh(html):
    """青海：底部「地方人大」区块（市州县全量）。"""
    m = re.search(r'地方人大', html)
    if not m:
        return {}
    seg = html[m.start():m.start() + 40000]
    d = {}
    for u, txt in re.findall(
            r'<a[^>]+href="([^"]+)"[^>]*>\s*([^<]{3,24}?)\s*</a>', seg):
        t = re.sub(r"\s+", "", txt)
        if "人大" in t and t not in d:
            d[t] = u
    return d


def extract_cq(html):
    """重庆：首页「区县人大」区块（渝中区人大锚点定位）。"""
    p = html.find("渝中区人大")
    if p < 0:
        return {}
    seg = html[max(0, p - 500):p + 30000]
    d = {}
    for u, txt in re.findall(
            r'<a[^>]+href="([^"]+)"[^>]*>\s*([^<]{3,24}?)\s*</a>', seg):
        t = re.sub(r"\s+", "", txt)
        if ("人大" in t and "要闻" not in t and "会议" not in t) and t not in d:
            d[t] = u
    return d


def main():
    tree = json.load(open("tree.json", encoding="utf-8"))
    prov_g = next(g for g in tree["ks"] if g["n"].startswith("省级"))

    # 目标省下级地名集合
    city_sets = {}
    ETH = ("维吾尔|壮族|回族|蒙古族|藏族|土家族|苗族|彝族|朝鲜族|满族|白族|"
            "侗族|瑶族|布依族|哈尼族|傣族|黎族|傈僳族|佤族|畲族|高山族|拉祜族|"
            "水族|东乡族|纳西族|景颇族|柯尔克孜族|土族|达斡尔族|仫佬族|羌族|"
            "布朗族|撒拉族|毛南族|仡佬族|锡伯族|阿昌族|普米族|塔吉克族|怒族|"
            "乌孜别克族|俄罗斯族|鄂温克族|德昂族|保安族|裕固族|京族|塔塔尔族|"
            "独龙族|鄂伦春族|赫哲族|门巴族|珞巴族|基诺族|哈萨克族")
    def core_of(nm):
        c = re.sub(r"(自治州|自治县)$", "", nm)
        c = re.sub(rf"(?:{ETH})+$", "", c)
        return re.sub(r"(地区|盟|市|区|县)$", "", c)

    for p in prov_g["ks"]:
        if p["n"] not in HTMLS:
            continue
        lvs = ("地级区", "县") if p["n"] == "重庆市" else ("市",)
        s = set()
        for top in p.get("ks", []):
            def walk(n):
                if n.get("l") in lvs and n.get("k") == "人民政府":
                    s.add((n["n"], core_of(n["n"])))
                for k in n.get("ks", []):
                    walk(k)
            walk(top)
        city_sets[p["n"]] = s

    new_rows = []
    for pn, fn in HTMLS.items():
        html = open(fn, encoding="utf-8", errors="replace").read()
        if pn == "福建省":
            d = extract_fj(html)
        elif pn == "陕西省":
            d = extract_sx(html)
        elif pn == "黑龙江省":
            d = extract_hlj(html)
        elif pn == "辽宁省":
            d = extract_ln(html)
        elif pn == "青海省":
            d = extract_qh(html)
        else:
            d = extract_cq(html)
        print(f"{pn}: 提取 {len(d)} 个链接: {sorted(d)[:12]}")
        # 匹配地名
        for nm, base in city_sets[pn]:
            hit = None
            for t in d:
                t2 = re.sub(r"人大$|人大常委会$|人民代表大会常务委员会$", "", t)
                if t == nm or t2 == nm or t == base or t2 == base:
                    hit = d[t]
                    break
            if hit is None:
                # 辽宁「抚顺人大」式名称；青海「海南州」式简称
                for t in d:
                    t2 = re.sub(r"人大$|人大常委会$|人民代表大会常务委员会$", "", t)
                    if len(base) >= 2 and (t2.startswith(base) or
                                           base.startswith(t2)):
                        hit = d[t]
                        break
            new_rows.append({"province": pn, "name": nm, "url": hit or "",
                             "listed": bool(hit)})
        print(f"  -> {sum(1 for r in new_rows if r['province']==pn and r['listed'])}/"
              f"{len(city_sets[pn])} 有 URL")

    # 合并回 rd_shi.jsonl（去重：同省同名保留新值）
    old = [json.loads(l) for l in open("rd_shi.jsonl", encoding="utf-8")]
    old = [r for r in old if r["province"] not in HTMLS]
    rows = old + new_rows
    with open("rd_shi.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    n_listed = sum(1 for r in rows if r["listed"])
    print(f"p83 完成：rd_shi.jsonl 共 {len(rows)} 条（{n_listed} 有官网）")


if __name__ == "__main__":
    main()
