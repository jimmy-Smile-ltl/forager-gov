# -*- coding: utf-8 -*-
"""P139: 31 省政协官网全量提取轮（地级市细化）。

每省流程：CDP 渲染首页 → JS 点击「市县政协/各市政协/设区市政协/
市州政协」按钮 → 全页链接匹配树里市级名单（全名/简称/XX市政协三种形态）。
断点续跑 zx_all_state.json。
"""
import json, os, re, shutil, subprocess, sys, time
sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开")
sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开/util")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import save_snap

STATE_F = "zx_all_state.json"
state = json.load(open(STATE_F, encoding="utf-8")) if os.path.exists(STATE_F) \
    else {"done": [], "rows": []}
done = set(state["done"])
rows = state["rows"]

tree = json.load(open("tree.json", encoding="utf-8"))
tiao = next(g for g in tree["ks"] if g["n"].startswith("条"))
zx = next(g for g in tiao["ks"] if g["n"].startswith("政协系统"))
gy = next(x for x in zx["ks"] if x["n"].startswith("省级政协"))

def core_of(nm):
    ETH = "(土家族苗族|蒙古族藏族|藏族羌族|傣族景颇族|布依族苗族|维吾尔|壮族|回族|蒙古族|藏族|土家族|苗族|彝族|朝鲜族|满族|白族|侗族|瑶族|布依族|哈尼族|傣族|黎族|傈僳族|佤族|畲族|拉祜族|水族|东乡族|纳西族|景颇族|柯尔克孜族|土族|达斡尔族|仫佬族|羌族|布朗族|撒拉族|毛南族|仡佬族|锡伯族|阿昌族|普米族|塔吉克族|怒族|乌孜别克族|俄罗斯族|鄂温克族|德昂族|保安族|裕固族|京族|塔塔尔族|独龙族|鄂伦春族|赫哲族|门巴族|珞巴族|基诺族|哈萨克族)"
    c = re.sub(rf"{ETH}?自治州$|(自治县|地区|盟|市|区|县)$", "", nm)
    return re.sub(rf"(?:{ETH})+$", "", c)

prov_g = next(g for g in tree["ks"] if g["n"].startswith("省级"))
city_map = {}
for p in prov_g["ks"]:
    s = []
    for top in p.get("ks", []):
        def walk(n):
            if n.get("l") == "市" and n.get("k") == "人民政府":
                s.append(n["n"])
            for k in n.get("ks", []):
                walk(k)
        walk(top)
    city_map[p["n"]] = s

jobs = [(pn, p["u"], city_map.get(pn, []))
        for p in gy["ks"] for pn in [p["n"].replace("政协", "")]
        if pn not in done and p.get("u")]

print(f"待处理: {len(jobs)} 省", flush=True)

def launch():
    shutil.rmtree("/tmp/xxgk_rs_profile", ignore_errors=True)
    from util.browser_lifecycle import PROJECT_CHROME
    return subprocess.Popen([PROJECT_CHROME, "--headless=new",
                             "--remote-debugging-port=9342",
                             "--user-data-dir=/tmp/xxgk_rs_profile",
                             "--no-sandbox", "--disable-gpu", "--no-first-run",
                             "about:blank"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def get_ws():
    import httpx
    for _ in range(30):
        try:
            r = httpx.get("http://127.0.0.1:9342/json/version", timeout=3)
            if r.status_code == 200:
                return r.json()["webSocketDebuggerUrl"]
        except Exception:
            pass
        time.sleep(1)
    raise RuntimeError("CDP 未就绪")

KW_LIST = ["市县政协", "各市政协", "设区市政协", "市州政协", "州市政协",
           "各设区市政协", "地方政协", "盟市政协"]

proc = launch()
try:
    from DrissionPage import ChromiumPage
    page = ChromiumPage(addr_or_opts=get_ws())
    for i, (pn, u, cities) in enumerate(jobs):
        try:
            page.get(u)
            time.sleep(8)
            # 点击导航按钮
            clicked = False
            for kw in KW_LIST:
                js = ("var els=document.querySelectorAll('*');"
                      f"for(const el of els){{if(el.children.length<=2&&el.textContent&&el.textContent.trim().includes('{kw}')){{el.click();break;}}}}")
                page.run_js(js, as_expr=True)
                time.sleep(1.8)
            html = page.html
            save_snap("zhengxie", pn, f"{pn}政协", "home_all", html)
            # 匹配
            hits = {}
            cores = {c: core_of(c) for c in cities}
            for uu, txt in re.findall(
                    r'<a[^>]+href="([^"]+)"[^>]*>\s*([^<]{2,18}?)\s*</a>', html):
                t2 = txt.strip()
                if not uu.startswith("http") or ".gov.cn" not in uu and ".org.cn" not in uu and ".com.cn" not in uu and ".cn" not in uu:
                    continue
                t2c = core_of(t2.replace("政协", "").replace("委员会", "").replace("网", ""))
                for full, c in cores.items():
                    if len(c) < 2:
                        continue
                    if t2 == full or t2 == c or t2c == c or \
                            (t2.startswith(c) and "政协" in t2 and len(t2) <= len(c) + 4):
                        hits[full] = uu
                        break
            rows.append({"province": pn, "hits": hits})
            done.add(pn)
            state["done"] = sorted(done)
            state["rows"] = rows
            json.dump(state, open(STATE_F, "w", encoding="utf-8"),
                      ensure_ascii=False, indent=0)
            print(f"{pn}: {len(hits)}/{len(cities)} 市命中", flush=True)
        except Exception as e:
            print(f"{pn}: 失败 {str(e)[:45]}", flush=True)
finally:
    subprocess.run(["pkill", "-9", "-f", "remote-debugging-port=9342"])
    time.sleep(2)

with open("zx_all.jsonl", "w", encoding="utf-8") as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
print(f"p139 完成: {len(rows)} 省")
