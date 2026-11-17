# -*- coding: utf-8 -*-
"""P100c: 政协交互提取 v2——点击后匹配纯地名链接（不要求含政协字样）。"""
import json, os, re, shutil, subprocess, sys, time
sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开")
sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开/util")

TARGETS = [
    ("江苏省", "https://www.jszx.gov.cn/", ["各设区市政协", "设区市政协", "市县政协"]),
    ("云南省", "http://www.ynzx.gov.cn/", ["州市政协", "各州市政协", "州市县政协"]),
    ("安徽省", "http://www.ahzx.gov.cn/", ["市县政协", "各市政协", "市政协网站"]),
    ("山东省", "http://www.sdzx.gov.cn/", ["市县政协", "各市政协"]),
    ("河南省", "http://www.hnzx.gov.cn/", ["市县政协", "省辖市政协", "各市政协"]),
    ("河北省", "http://www.hebzx.gov.cn/", ["市县政协", "各市政协"]),
    ("山西省", "http://www.shanxizx.gov.cn/", ["市县政协", "各市政协"]),
    ("海南省", "http://www.hainanzx.gov.cn/", ["市县政协", "各市县政协"]),
    ("湖南省", "http://www.hunanzx.gov.cn/", ["市州政协", "各市州政协"]),
    ("黑龙江省", "http://www.hljzx.gov.cn/", ["市县政协", "市地政协", "各市政协"]),
    ("贵州省", "http://www.gzszx.gov.cn/", ["市州政协", "各市州政协", "市县政协"]),
    ("新疆维吾尔自治区", "http://www.xjzx.gov.cn/", ["地州政协", "地州市政协", "州市政协"]),
    ("西藏自治区", "https://www.xizangzx.gov.cn/", ["地市政协", "各地市政协", "市县政协"]),
    ("上海市", "https://www.shszx.gov.cn/", ["区政协", "各区政协", "地区政协"]),
    ("辽宁省", "http://www.lnzx.gov.cn/", ["市县政协", "各市政协"]),
    ("浙江省", "http://www.zjzx.gov.cn/", ["市县政协", "各市政协", "地市政协"]),
    ("宁夏回族自治区", "http://www.nxzx.gov.cn/", ["市县政协", "各市政协"]),
    ("江西省", "http://jxzx.jxnews.com.cn/", ["市县政协", "各市政协", "设区市政协"]),
]

tree = json.load(open("tree.json", encoding="utf-8"))
prov_g = next(g for g in tree["ks"] if g["n"].startswith("省级"))
def city_names(pn):
    p = next(x for x in prov_g["ks"] if x["n"] == pn)
    lvs = ("地级区", "县") if pn in ("北京市", "天津市", "上海市", "重庆市") else ("市",)
    s = set()
    for top in p.get("ks", []):
        def walk(n):
            if n.get("l") in lvs and n.get("k") in ("人民政府", "功能区") and \
               "开发区" not in n["n"] and "高新区" not in n["n"] and \
               "园区" not in n["n"] and "管理区" not in n["n"]:
                s.add(n["n"])
            for k in n.get("ks", []):
                walk(k)
        walk(top)
    return s

def launch():
    shutil.rmtree("/tmp/xxgk_rs_profile", ignore_errors=True)
    from util.browser_lifecycle import PROJECT_CHROME
    return subprocess.Popen([PROJECT_CHROME, "--headless=new",
                             "--remote-debugging-port=9334",
                             "--user-data-dir=/tmp/xxgk_rs_profile",
                             "--no-sandbox", "--disable-gpu", "--no-first-run",
                             "about:blank"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def get_ws():
    import httpx
    for _ in range(30):
        try:
            r = httpx.get("http://127.0.0.1:9334/json/version", timeout=3)
            if r.status_code == 200:
                return r.json()["webSocketDebuggerUrl"]
        except Exception:
            pass
        time.sleep(1)
    raise RuntimeError("CDP 未就绪")

out = {}
proc = launch()
try:
    from DrissionPage import ChromiumPage
    page = ChromiumPage(addr_or_opts=get_ws())
    for pn, u, kws in TARGETS:
        try:
            page.get(u)
            time.sleep(8)
            clicked = False
            for kw in kws:
                for xp in (f'xpath://*[contains(text(),"{kw}")]',
                           f'xpath://a[contains(text(),"{kw}")]',
                           f'xpath://span[contains(text(),"{kw}")]',
                           f'xpath://li[contains(text(),"{kw}")]'):
                    try:
                        el = page.ele(xp)
                        el.click(by_js=True)
                        clicked = True
                        time.sleep(2.5)
                        break
                    except Exception:
                        continue
                if clicked:
                    break
            html = page.html
            names = city_names(pn)
            d = {}
            for uu, txt in re.findall(
                    r'<a[^>]+href="([^"]+)"[^>]*>\s*([^<]{2,14}?)\s*</a>', html):
                t2 = txt.strip()
                if not uu.startswith("http"):
                    continue
                if t2 in names or t2.replace("政协", "") in names:
                    d[t2] = uu
            out[pn] = d
            print(f"{pn}: clicked={clicked}, {len(d)} 链接", flush=True)
            for k, v in list(d.items())[:15]:
                print(f"   {k} -> {v[:65]}", flush=True)
        except Exception as e:
            print(f"{pn}: 失败 {str(e)[:50]}", flush=True)
            out[pn] = {}
finally:
    subprocess.run(["pkill", "-9", "-f", "remote-debugging-port=9334"])
    time.sleep(2)

json.dump(out, open("/tmp/p100c_out.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=0)
print("p100c 完成")
