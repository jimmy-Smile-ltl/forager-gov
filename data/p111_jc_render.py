# -*- coding: utf-8 -*-
"""P111: CDP 渲染轮——0 命中的 189 个市院官网提取基层检察院。断点续跑。"""
import json, os, re, shutil, subprocess, sys, time
sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开")
sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开/util")

STATE_F = "jc_jc2_state.json"
state = json.load(open(STATE_F, encoding="utf-8")) if os.path.exists(STATE_F) \
    else {"done": [], "rows": []}
done = set(state["done"])
rows = state["rows"]
miss = json.load(open("/tmp/jc_miss.json", encoding="utf-8"))
miss = [m for m in miss if f"{m[0]}|{m[1]}" not in done]

tree = json.load(open("tree.json", encoding="utf-8"))
prov_g = next(g for g in tree["ks"] if g["n"].startswith("省级"))
counties_by_prov = {}
for p in prov_g["ks"]:
    counties = {}
    for top in p.get("ks", []):
        def walk(n):
            if n.get("l") == "县" and n.get("k") == "人民政府":
                counties[n["n"]] = re.sub(r"(自治县|区|县|市)$", "", n["n"])
            for k in n.get("ks", []):
                walk(k)
        walk(top)
    counties_by_prov[p["n"]] = counties

def launch():
    shutil.rmtree("/tmp/xxgk_rs_profile", ignore_errors=True)
    from util.browser_lifecycle import PROJECT_CHROME
    return subprocess.Popen([PROJECT_CHROME, "--headless=new",
                             "--remote-debugging-port=9335",
                             "--user-data-dir=/tmp/xxgk_rs_profile",
                             "--no-sandbox", "--disable-gpu", "--no-first-run",
                             "about:blank"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def get_ws():
    import httpx
    for _ in range(30):
        try:
            r = httpx.get("http://127.0.0.1:9335/json/version", timeout=3)
            if r.status_code == 200:
                return r.json()["webSocketDebuggerUrl"]
        except Exception:
            pass
        time.sleep(1)
    raise RuntimeError("CDP 未就绪")

print(f"待渲染: {len(miss)} 个市院", flush=True)
proc = launch()
try:
    from DrissionPage import ChromiumPage
    page = ChromiumPage(addr_or_opts=get_ws())
    for i, (pname, shiname, shiurl) in enumerate(miss):
        key = f"{pname}|{shiname}"
        try:
            page.get(shiurl)
            time.sleep(7)
            html = page.html
            counties = counties_by_prov.get(pname, {})
            hits = {}
            for u, txt in re.findall(
                    r'<a[^>]+href="([^"]+)"[^>]*>\s*([^<]{3,24}?)\s*</a>', html):
                t2 = txt.strip()
                if re.search(r'人民检察院$', t2) and u.startswith("http"):
                    core = re.sub(r'人民检察院$', '', t2)
                    core_b = re.sub(r'(自治县|区|县|市)$', '', core)
                    for cn, base in counties.items():
                        if core == cn or core_b == base or core == base:
                            hits[cn] = u
                            break
            for cn, u in hits.items():
                rows.append({"province": pname, "shi": shiname,
                             "county": cn, "url": u})
            done.add(key)
            state["done"] = sorted(done)
            state["rows"] = rows
            json.dump(state, open(STATE_F, "w", encoding="utf-8"),
                      ensure_ascii=False, indent=0)
            if i % 5 == 0:
                print(f"{i}/{len(miss)} {shiname}: {len(hits)} 基层", flush=True)
        except Exception as e:
            print(f"{shiname}: 失败 {str(e)[:40]}", flush=True)
            done.add(key)
finally:
    subprocess.run(["pkill", "-9", "-f", "remote-debugging-port=9335"])
    time.sleep(2)

with open("jc_jc2.jsonl", "w", encoding="utf-8") as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
print(f"p111 完成: {len(rows)} 条，done {len(done)}/{len(miss) + len(done)}")
