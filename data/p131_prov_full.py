# -*- coding: utf-8 -*-
"""P131: 32 省政府门户全量渲染——提取市州政府 + 省直部门链接。

用户指正：理论上省级政府官网应能提取全部下级市政府和厅局 URL。
渲染后匹配树里市级/厅局节点名（权威名单）。断点续跑。
"""
import json, os, re, shutil, subprocess, sys, time
sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开")
sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开/util")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import save_snap

STATE_F = "prov_full_state.json"
state = json.load(open(STATE_F, encoding="utf-8")) if os.path.exists(STATE_F) \
    else {"done": [], "rows": []}
done = set(state["done"])
rows = state["rows"]

tree = json.load(open("tree.json", encoding="utf-8"))
prov = next(g for g in tree["ks"] if g["n"].startswith("省级"))

# 每省：市级名单 + 厅局名单
jobs = []
for p in prov["ks"]:
    pn = p["n"]
    if pn in done or not p.get("u"):
        continue
    shi_names, ting_names = [], []
    for top in p.get("ks", []):
        if top.get("k") == "分组" and "部门" in top.get("n"):
            ting_names = [x["n"] for x in top.get("ks", [])]
        def walk(n):
            if n.get("l") == "市" and n.get("k") == "人民政府":
                shi_names.append(n["n"])
            for k in n.get("ks", []):
                walk(k)
        walk(top)
    jobs.append((pn, p["u"], shi_names, ting_names))

print(f"待渲染: {len(jobs)} 省", flush=True)

def launch():
    shutil.rmtree("/tmp/xxgk_rs_profile", ignore_errors=True)
    from util.browser_lifecycle import PROJECT_CHROME
    return subprocess.Popen([PROJECT_CHROME, "--headless=new",
                             "--remote-debugging-port=9341",
                             "--user-data-dir=/tmp/xxgk_rs_profile",
                             "--no-sandbox", "--disable-gpu", "--no-first-run",
                             "about:blank"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def get_ws():
    import httpx
    for _ in range(30):
        try:
            r = httpx.get("http://127.0.0.1:9341/json/version", timeout=3)
            if r.status_code == 200:
                return r.json()["webSocketDebuggerUrl"]
        except Exception:
            pass
        time.sleep(1)
    raise RuntimeError("CDP 未就绪")

def core_of(nm):
    c = re.sub(r"(自治州|自治县|地区|盟|市|区|县)$", "", nm)
    c = re.sub(r"(维吾尔|壮族|回族|蒙古族|藏族|土家族|苗族|彝族|朝鲜族|满族|白族|侗族|瑶族|布依族|哈尼族|傣族|黎族|傈僳族|佤族|畲族|拉祜族|水族|东乡族|纳西族|景颇族|柯尔克孜族|土族|达斡尔族|仫佬族|羌族|布朗族|撒拉族|毛南族|仡佬族|锡伯族|阿昌族|普米族|塔吉克族|怒族|乌孜别克族|俄罗斯族|鄂温克族|德昂族|保安族|裕固族|京族|塔塔尔族|独龙族|鄂伦春族|赫哲族|门巴族|珞巴族|基诺族|哈萨克族)+$", "", c)
    return c

proc = launch()
try:
    from DrissionPage import ChromiumPage
    page = ChromiumPage(addr_or_opts=get_ws())
    for i, (pn, u, shi_names, ting_names) in enumerate(jobs):
        try:
            page.get(u)
            time.sleep(9)
            html = page.html
            save_snap("shixian", pn, f"{pn}政府门户", "home_full", html)
            # 全页链接
            links = {}
            for uu, txt in re.findall(
                    r'<a[^>]+href="([^"]+)"[^>]*>\s*([^<]{2,30}?)\s*</a>', html):
                t2 = txt.strip()
                if uu.startswith("http") and ".gov.cn" in uu:
                    links.setdefault(t2, uu)
            # 市州匹配
            shi_hits = {}
            for nm in shi_names:
                c = core_of(nm)
                for t2, uu in links.items():
                    t2c = core_of(t2.replace("人民政府", "").replace("政府门户", ""))
                    if (nm == t2 or t2 == f"{nm}人民政府" or
                            (len(c) >= 2 and t2c == c and "政府" in t2)):
                        shi_hits[nm] = uu
                        break
            # 厅局匹配
            ting_hits = {}
            for nm in ting_names:
                c = re.sub(r"(委员会|办公室|厅|局|署)$", "", nm)
                c = re.sub(r"^省", "", c)
                for t2, uu in links.items():
                    if (nm == t2 or nm in t2 or
                            (len(c) >= 3 and c in t2 and "gov.cn" in uu)):
                        ting_hits[nm] = uu
                        break
            rows.append({"province": pn, "shi": shi_hits, "ting": ting_hits})
            done.add(pn)
            state["done"] = sorted(done)
            state["rows"] = rows
            json.dump(state, open(STATE_F, "w", encoding="utf-8"),
                      ensure_ascii=False, indent=0)
            print(f"{pn}: 市 {len(shi_hits)}/{len(shi_names)}，厅局 {len(ting_hits)}/{len(ting_names)}",
                  flush=True)
        except Exception as e:
            print(f"{pn}: 失败 {str(e)[:40]}", flush=True)
finally:
    subprocess.run(["pkill", "-9", "-f", "remote-debugging-port=9341"])
    time.sleep(2)

with open("prov_full.jsonl", "w", encoding="utf-8") as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
print(f"p131 完成: {len(rows)} 省")
