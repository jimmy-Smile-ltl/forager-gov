# -*- coding: utf-8 -*-
"""P152: 242 市院 CDP 渲染轮——首页+机构页找基层检察院。断点续跑。"""
import json, os, re, shutil, subprocess, sys, time
sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开")
sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开/util")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

STATE_F = "jc_render2_state.json"
state = json.load(open(STATE_F, encoding="utf-8")) if os.path.exists(STATE_F) \
    else {"done": [], "rows": []}
done = set(state["done"])
rows = state["rows"]
jobs = json.load(open("/tmp/jc_render_jobs.json", encoding="utf-8"))
jobs = [j for j in jobs if f"{j[0]}|{j[1]}" not in done]
print(f"待渲染: {len(jobs)}", flush=True)

def launch():
    shutil.rmtree("/tmp/xxgk_rs_profile", ignore_errors=True)
    from util.browser_lifecycle import PROJECT_CHROME
    return subprocess.Popen([PROJECT_CHROME, "--headless=new",
                             "--remote-debugging-port=9344",
                             "--user-data-dir=/tmp/xxgk_rs_profile",
                             "--no-sandbox", "--disable-gpu", "--no-first-run",
                             "about:blank"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def get_ws():
    import httpx
    for _ in range(30):
        try:
            r = httpx.get("http://127.0.0.1:9344/json/version", timeout=3)
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
    for i, (pn, shiname, shiurl, counties) in enumerate(jobs):
        key = f"{pn}|{shiname}"
        try:
            page.get(shiurl)
            time.sleep(6)
            html = page.html
            hits = {}
            for u, txt in re.findall(
                    r'<a[^>]+href="([^"]+)"[^>]*>\s*([^<]{3,24}?)\s*</a>', html):
                t2 = txt.strip()
                m = re.match(r'^(.*?[区县旗市])人民检察院$', t2)
                if m and u.startswith("http"):
                    core = m.group(1)
                    for cn in counties:
                        cn_core = re.sub(r'(自治县|区|县|旗|市)$', '', cn)
                        if core == cn or core == cn_core:
                            hits[cn] = u
                            break
            rows.append({"province": pn, "shi": shiname, "hits": hits})
            done.add(key)
            state["done"] = sorted(done)
            state["rows"] = rows
            json.dump(state, open(STATE_F, "w", encoding="utf-8"),
                      ensure_ascii=False, indent=0)
            if i % 15 == 0:
                print(f"{i}/{len(jobs)} {shiname}: {len(hits)}", flush=True)
        except Exception as e:
            print(f"{shiname}: 失败 {str(e)[:35]}", flush=True)
            done.add(key)
finally:
    subprocess.run(["pkill", "-9", "-f", "remote-debugging-port=9344"])
    time.sleep(2)

with open("jc_render2.jsonl", "w", encoding="utf-8") as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
n_hits = sum(len(r["hits"]) for r in rows)
print(f"p152 完成: {n_hits} 条，done {len(done)}")
