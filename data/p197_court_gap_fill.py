# -*- coding: utf-8 -*-
"""P197: 法院条树缺口补采 — 高院官网「辖区法院」区块深挖。

背景（2026-11-12 用户报普洱市地图单色）: 条树法院系统 416 中院中 191 个
无基层法院子级, 块树同步(p189)跟着缺。实测根因: p62c 当年只认「中院名后
紧跟基层链接」的文档顺序形态, 而 32 高院官网的「辖区法院」区块（云龙县法院
→ elink…, 思茅区法院→elink…）不在该形态内被整体漏采。普洱 10 县基层法院
全在云南高院官网首页。

流程: 每高院官网 smart_fetch 静态（无命中则 CloakBrowser 渲染）→ 全页
提取「XX法院/法庭」链接（elink 解码 + 协议相对 urljoin）→ 块树「市→县基底」
映射归位到对应中院 → 挂叶子（已存在跳过）。幂等; P197_ONLY 定向测试。
之后跑 p189 同步块树 → p22 刷新视图。
"""
import base64
import json
import os
import re
import subprocess
import sys
from urllib.parse import urljoin

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, "util"))
os.chdir(BASE)

from smart_fetch import smart_fetch  # noqa: E402

TREE_F = "data/tree.json"

ETH_PY = re.compile(
    r"(哈萨克族?|维吾尔族?|柯尔克孜族?|蒙古族?|藏族?|回族|壮族|苗族|黎族"
    r"|侗族|满族|白族|傣族|彝族|哈尼族?|拉祜族?|傈僳族?|佤族?|水族"
    r"|羌族|布依族?|仡佬族?|仫佬族?|毛南族?|瑶族?|畲族|土家族?|土族"
    r"|锡伯族?|达斡尔族?|鄂温克族?|鄂伦春族?|赫哲族?|俄罗斯族?|塔塔尔族?|乌孜别克族?"
    r"|塔吉克族?|撒拉族?|保安族?|裕固族?|东乡族?|纳西族?|景颇族?|阿昌族?"
    r"|普米族?|怒族|德昂族?|独龙族?|基诺族?|门巴族?|珞巴族?|京族"
    r"|朝鲜族?|各族|自治)$")
SUF = re.compile(
    r"(自治州|自治县|自治旗|地区|盟|市|县|区|旗|行政委员会|行委|管委会|管理委员会|管理区"
    r"|高新技术产业开发区|经济技术开发区|经济开发区|开发区|新区|工业园区|园区|示范区"
    r"|高级人民法院|中级人民法院|人民法院|法院|人民检察院|检察院|人大常委会|人大|政协"
    r"|监察委员会|监委)$")


def base(nm):
    t = nm or ""
    for _ in range(10):
        t0 = t
        t = SUF.sub("", t)
        if not t:
            return re.sub(r"族$", "", t0) or t0
        pre = t
        t = ETH_PY.sub("", t)
        if not t:
            return re.sub(r"族$", "", pre) or pre
        if t == t0:
            break
    return t


def decode_elink(h):
    if "elink.chinacourt.cn" in h:
        m = re.search(r"elid=([^&\s\"']+)", h)
        if m:
            elid = m.group(1)
            if elid.startswith(("http://", "https://")):
                return elid
            try:
                return base64.urlsafe_b64decode(elid + "==").decode()
            except Exception:
                pass
    return h


def extract_court_links(page_url, html):
    """高院页全页扫描基层法院链接（a+option 双通道, elink 解码）。"""
    out = {}
    for m in re.finditer(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html, re.S):
        t = re.sub(r"<[^>]+>", "", m.group(2))
        t = re.sub(r"\s+", "", t)
        if not t or len(t) > 16 or "中级" in t or "高级" in t or "中院" in t:
            continue
        if t.endswith(("法院", "法庭")):
            u = decode_elink(urljoin(page_url, m.group(1)))
            if u.startswith(("http://", "https://")):
                out[t] = u
    for m in re.finditer(r'<option[^>]*value\s*=\s*["\']([^"\']+)["\'][^>]*>\s*([^<]{2,20}?)\s*</option>', html):
        t = re.sub(r"\s+", "", m.group(2))
        if t.endswith(("人民法院", "法院", "法庭")) and "中级" not in t and "高级" not in t and len(t) <= 16:
            u = decode_elink(urljoin(page_url, m.group(1)))
            if u.startswith(("http://", "https://")):
                out[t] = u
    return out


def render(url):
    for _try in range(2):
        try:
            r = subprocess.run(
                [sys.executable, os.path.join(BASE, "data", "p195_render_one.py"), url],
                capture_output=True, text=True, timeout=120)
            out = (r.stdout or "").strip()
            if len(out) > 1000:
                return out
        except Exception:
            pass
    return ""


def walk(n, path):
    yield n, path
    for k in n.get("ks", []) or []:
        yield from walk(k, path + [n])


def main():
    tree = json.load(open(TREE_F, encoding="utf-8"))
    blk = next(g for g in tree["ks"] if g["n"].startswith("省级"))
    tiao = next(g for g in tree["ks"] if g["n"].startswith("条"))
    fy = next((s for s in tiao.get("ks", []) if "法院" in s.get("n", "")), None)
    if not fy:
        print("未找到法院系统")
        return
    holder = max(fy.get("ks", []) or [], key=lambda c: len(c.get("ks", []) or []))
    only = os.environ.get("P197_ONLY", "").strip()

    # 块树 (省 → 市 → 县基底集合) 映射: 高院页基层名归位中院
    prov_city = {}
    for prov in blk.get("ks", []):
        pn = base(prov.get("n", ""))
        city_map = {}
        for n, path in walk(prov, [prov]):
            if n.get("k") != "人民政府":
                continue
            if n.get("n", "").endswith(("市", "州", "地区", "盟")):
                city = base(n.get("n", ""))
                for c in n.get("ks", []) or []:
                    if c.get("k") in ("人民政府", "区划"):
                        city_map[base(c.get("n", ""))] = city
            elif n.get("c") in ("县级人民政府", "市辖区（地级行政区划）",
                                "直辖市辖县（县级行政区划）", "功能区", "直辖市辖区",
                                "直辖市辖县"):
                # 直辖市: 区县直接挂省下 → 挂高院直属
                pass
        prov_city[pn] = city_map

    filled = 0
    for prov in holder.get("ks", []) or []:
        pn = base(prov.get("n", ""))
        if only and only not in prov.get("n", ""):
            continue
        childless = [m for m in (prov.get("ks", []) or []) if not m.get("ks")]
        if not childless:
            continue
        gy_u = prov.get("u")
        if not gy_u:
            print(f"{prov.get('n')}: 高院无 URL, 跳过 {len(childless)} 个空置中院", flush=True)
            continue
        html, m = smart_fetch(gy_u, timeout=25)
        if not html or len(html) < 500:
            print(f"{prov.get('n')}: 高院 fetch fail [{m}]", flush=True)
            continue
        links = extract_court_links(gy_u, html)
        # 只补 childless 中院辖区的县: 静态不够再渲染
        bases_needed = set()
        for mid in childless:
            for cn, city in prov_city.get(pn, {}).items():
                if city == base(mid.get("n", "")):
                    bases_needed.add(cn)
        got = {t: u for t, u in links.items() if base(t) in bases_needed}
        if not got:
            rh = render(gy_u)
            if rh:
                links2 = extract_court_links(gy_u, rh)
                got = {t: u for t, u in links2.items() if base(t) in bases_needed}
        if not got:
            print(f"{prov.get('n')}: 高院页无辖区基层链接 [{m}]", flush=True)
            continue
        mid_by_city = {base(mid.get("n", "")): mid for mid in childless}
        for name, u in got.items():
            lb = base(name)
            city = prov_city.get(pn, {}).get(lb)
            if not city or city not in mid_by_city:
                continue
            mid = mid_by_city[city]
            mid["ks"] = mid.get("ks") or []
            if any(c.get("n") == name for c in mid["ks"]):
                continue
            mid["ks"].append({"n": name, "k": "基层法院", "c": "基层法院",
                              "u": u, "s": "来源：高院官网辖区法院区块（p197）"})
            filled += 1
        print(f"{prov.get('n')}: 静态{m} 链接{len(links)} 命中{len(got)} 补入{filled}",
              flush=True)

    if filled:
        json.dump(tree, open(TREE_F, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
    print(f"P197 完成: 新增 {filled} 个基层法院节点")


if __name__ == "__main__":
    main()
