# -*- coding: utf-8 -*-
"""P162: 市人大官网 CDP 渲染轮——多形态提取县级人大。

p157 静态轮只命中 66（清死链后 34）。渲染轮补 JS 导航形态：
1) 渲染后锚点「XX县人大(常委会)」2) select 下拉选项
3) 纯县名链接（gov.cn 域名）。断点续跑。
"""
import json, os, re, shutil, subprocess, sys, time
sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开")
sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开/util")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

STATE_F = "rd_xian_render_state.json"
state = json.load(open(STATE_F, encoding="utf-8")) if os.path.exists(STATE_F) \
    else {"done": [], "rows": []}
done = set(state["done"])
rows = state["rows"]

tree = json.load(open("tree.json", encoding="utf-8"))
tiao = next(g for g in tree["ks"] if g["n"].startswith("条"))
rd = next(g for g in tiao["ks"] if g["n"].startswith("人大系统"))
gy = next(x for x in rd["ks"] if x["n"].startswith("省级人大"))

jobs = []
for p in gy["ks"]:
    pname = p["n"].replace("人大", "")
    for shi in p.get("ks", []):
        if shi.get("u"):
            counties = [k["n"].replace("人大", "") for k in shi.get("ks", [])]
            key = f"{pname}|{shi['n']}"
            if key not in done:
                jobs.append((pname, shi["n"], shi["u"], counties))
print(f"渲染任务: {len(jobs)} 市人大", flush=True)

def launch():
    shutil.rmtree("/tmp/xxgk_rs_profile", ignore_errors=True)
    from util.browser_lifecycle import PROJECT_CHROME
    return subprocess.Popen([PROJECT_CHROME, "--headless=new",
                             "--remote-debugging-port=9346",
                             "--user-data-dir=/tmp/xxgk_rs_profile",
                             "--no-sandbox", "--disable-gpu", "--no-first-run",
                             "about:blank"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def get_ws():
    import httpx
    for _ in range(30):
        try:
            r = httpx.get("http://127.0.0.1:9346/json/version", timeout=3)
            if r.status_code == 200:
                return r.json()["webSocketDebuggerUrl"]
        except Exception:
            pass
        time.sleep(1)
    raise RuntimeError("CDP 未就绪")

proc = launch()
try:
    from DrissionPage import ChromiumPage
    page = ChromiumPage(addr_or_opts=get_ws())
    for i, (pname, shiname, shiurl, counties) in enumerate(jobs):
        key = f"{pname}|{shiname}"
        try:
            page.get(shiurl)
            time.sleep(7)
            html = page.html
            hits = {}
            # 1) 锚点 2) select 选项 3) 纯县名
            for u, txt in re.findall(
                    r'<a[^>]+href="([^"]+)"[^>]*>\s*([^<]{2,24}?)\s*</a>', html):
                t2 = txt.strip()
                m = re.match(r'^(.*?[区县旗市])人大(?:常委会|网站|网)?$', t2)
                if not m:
                    continue
                core = m.group(1)
                for cn in counties:
                    cn_core = re.sub(r'(自治县|区|县|旗|市)$', '', cn)
                    if core == cn or core == cn_core:
                        hits[cn] = u if u.startswith("http") else ""
                        break
            for sel in re.findall(r'<select[^>]*>(.*?)</select>', html, re.S):
                opts = re.findall(r'<option[^>]*value="([^"]*)"[^>]*>\s*([^<]+?)\s*</option>', sel)
                for v, txt in opts:
                    t2 = txt.strip()
                    m = re.match(r'^(.*?[区县旗市])人大(?:常委会)?$', t2)
                    if m and v.startswith("http"):
                        core = m.group(1)
                        for cn in counties:
                            cn_core = re.sub(r'(自治县|区|县|旗|市)$', '', cn)
                            if core == cn or core == cn_core:
                                hits[cn] = v
                                break
            rows.append({"province": pname, "shi": shiname, "hits": hits})
            done.add(key)
            state["done"] = sorted(done)
            state["rows"] = rows
            json.dump(state, open(STATE_F, "w", encoding="utf-8"),
                      ensure_ascii=False, indent=0)
            if i % 20 == 0:
                print(f"{i}/{len(jobs)} {shiname}: {len(hits)}", flush=True)
        except Exception as e:
            print(f"{shiname}: 失败 {str(e)[:35]}", flush=True)
finally:
    subprocess.run(["pkill", "-9", "-f", "remote-debugging-port=9346"])
    time.sleep(2)

with open("rd_xian_render.jsonl", "w", encoding="utf-8") as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
n_hits = sum(len(r["hits"]) for r in rows)
print(f"p162 完成: {n_hits} 条")
