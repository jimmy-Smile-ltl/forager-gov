# -*- coding: utf-8 -*-
"""P100: 政协交互提取——点击「市县政协/设区市政协/盟市政协」按钮切换列表。"""
import json, os, re, shutil, subprocess, sys, time
sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开")
sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开/util")

TARGETS = [
    ("内蒙古自治区", "http://www.nmgzx.gov.cn/", "cityLinks2", "市县政协链接"),
    ("江苏省", "https://www.jszx.gov.cn/", None, "各设区市政协"),
    ("云南省", "http://www.ynzx.gov.cn/", None, "州市政协"),
    ("安徽省", "http://www.ahzx.gov.cn/", None, "市县政协"),
    ("山东省", "http://www.sdzx.gov.cn/", None, "市县政协"),
    ("河南省", "http://www.hnzx.gov.cn/", None, "市县政协"),
    ("河北省", "http://www.hebzx.gov.cn/", None, "市县政协"),
    ("山西省", "http://www.shanxizx.gov.cn/", None, "市县政协"),
    ("海南省", "http://www.hainanzx.gov.cn/", None, "市县政协"),
    ("湖南省", "http://www.hunanzx.gov.cn/", None, "市州政协"),
    ("黑龙江省", "http://www.hljzx.gov.cn/", None, "市县政协"),
    ("贵州省", "http://www.gzszx.gov.cn/", None, "市州政协"),
    ("新疆维吾尔自治区", "http://www.xjzx.gov.cn/", None, "地州政协"),
    ("西藏自治区", "https://www.xizangzx.gov.cn/", None, "地市政协"),
    ("上海市", "https://www.shszx.gov.cn/", None, "区政协"),
    ("辽宁省", "http://www.lnzx.gov.cn/", None, "市县政协"),
]

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
    for pn, u, cid, kw in TARGETS:
        try:
            page.get(u)
            time.sleep(8)
            # 优先按 id 点；否则按文本点
            clicked = False
            if cid:
                try:
                    el = page.ele(f'#{cid}')
                    el.click(by_js=True)
                    clicked = True
                    time.sleep(2)
                except Exception:
                    pass
            if not clicked:
                for xp in (f'xpath://*[contains(text(),"{kw}")]',
                           f'xpath://a[contains(text(),"{kw}")]',
                           f'xpath://span[contains(text(),"{kw}")]'):
                    try:
                        el = page.ele(xp)
                        el.click(by_js=True)
                        clicked = True
                        time.sleep(2)
                        break
                    except Exception:
                        continue
            html = page.html
            d = {}
            for uu, txt in re.findall(
                    r'<a[^>]+href="([^"]+)"[^>]*>\s*([^<]{2,26}?)\s*</a>', html):
                t2 = txt.strip()
                if re.search(r'(市政协|州政协|盟政协|区政协)', t2) and \
                        uu.startswith("http") and \
                        not re.match(r'(北京|天津|河北|山西|内蒙古|辽宁|吉林|黑龙江|上海|江苏|浙江|安徽|福建|江西|山东|河南|湖北|湖南|广东|广西|海南|重庆|四川|贵州|云南|西藏|陕西|甘肃|青海|宁夏|新疆|中国|全国)省?政协', t2):
                    d[t2] = uu
            out[pn] = {"clicked": clicked, "links": d}
            print(f"{pn}: clicked={clicked}, {len(d)} 链接", flush=True)
            for k, v in list(d.items())[:14]:
                print(f"   {k} -> {v[:65]}", flush=True)
        except Exception as e:
            print(f"{pn}: 失败 {str(e)[:50]}", flush=True)
            out[pn] = {"clicked": False, "links": {}}
finally:
    subprocess.run(["pkill", "-9", "-f", "remote-debugging-port=9334"])
    time.sleep(2)

json.dump(out, open("/tmp/p100_out.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=0)
print("p100 完成")
