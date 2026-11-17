# -*- coding: utf-8 -*-
"""P44: 省级工会官网浏览器渲染补采市级工会（p43 的 JS 渲染补充）。

对 p43 静态 0 命中或抓取失败的省份：CloakBrowser(9334)+DrissionPage 渲染
→ 读渲染后 DOM 的 <select><option> 与 <a> → 市名匹配 → 并入 union_state.json。
"""
import json
import os
import re
import shutil
import subprocess
import sys
import time

sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开")
sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开/util")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from p43_union_collect import PROV_UNION, BAD_DOM  # noqa: E402


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


def main():
    tree = json.load(open("tree.json", encoding="utf-8"))
    prov_g = next(g for g in tree["ks"] if g["n"].startswith("省级"))
    prov_urls = {}
    for p in prov_g["ks"]:
        grp = next((k for k in p.get("ks", []) if k.get("c") == "群团组织"), None)
        if grp:
            m = next((x for x in grp["ks"] if x["n"] == "省总工会"), None)
            if m and m.get("u"):
                prov_urls[p["n"]] = m["u"]
    prov_urls.update(PROV_UNION)

    state = json.load(open("union_state.json", encoding="utf-8"))
    rows = state.get("rows", [])
    # 渲染目标：已 done 但 0 命中，或不在 done（抓取失败）
    hit_provs = {r["province"] for r in rows}
    targets = [p for p, u in prov_urls.items() if p not in hit_provs]
    print(f"p44 渲染目标 {len(targets)} 省", flush=True)

    proc = launch()
    try:
        from DrissionPage import ChromiumPage
        page = ChromiumPage(addr_or_opts=get_ws())
        for i, pname in enumerate(targets):
            url = prov_urls[pname]
            pnode = next(p for p in prov_g["ks"] if p["n"] == pname)
            city_names = []
            def walk(n):
                if n.get("l") == "市" and n.get("k") == "人民政府":
                    city_names.append(n["n"])
                for k in n.get("ks", []):
                    walk(k)
            walk(pnode)
            try:
                page.get(url)
                time.sleep(7)
                hits = page.run_js("""
                  const out = [];
                  const seen = new Set();
                  document.querySelectorAll('select option').forEach(op => {
                    const t = (op.textContent||'').trim().replace(/\\s+/g,'');
                    const h = op.value || '';
                    const k = t + '|' + h;
                    if (t && h.startsWith('http') && !seen.has(k)) { seen.add(k); out.push([t,h]); }
                  });
                  document.querySelectorAll('a').forEach(a => {
                    const t = ((a.getAttribute('title')||'') + ' ' + (a.textContent||''))
                      .trim().replace(/\\s+/g,'');
                    const h = a.href || '';
                    const k = t + '|' + h;
                    if (t && h.startsWith('http') && !seen.has(k)) { seen.add(k); out.push([t,h]); }
                  });
                  return out;
                """)
                matched = []
                for t, h in hits:
                    if BAD_DOM.search(h) or len(t) > 18:
                        continue
                    core = re.sub(r"(总)?工会.*$|网站.*$", "", t)
                    for cn in city_names:
                        base = re.sub(r"(自治州|市|地区|盟)$", "", cn)
                        if core == cn or core == base or (len(core) >= 2 and core in cn):
                            matched.append({"province": pname, "city": cn,
                                            "label": t, "url": h})
                            break
                for r in matched:
                    if not any(x["province"] == pname and x["city"] == r["city"]
                               for x in rows):
                        rows.append(r)
                print(f"  {i+1}/{len(targets)} {pname}: 渲染命中 {len(matched)}",
                      flush=True)
            except Exception as e:
                print(f"  {i+1}/{len(targets)} {pname}: 渲染失败 {str(e)[:50]}",
                      flush=True)
            state["rows"] = rows
            json.dump(state, open("union_state.json", "w", encoding="utf-8"),
                      ensure_ascii=False, indent=0)
    finally:
        subprocess.run(["pkill", "-9", "-f", "remote-debugging-port=9334"])
        time.sleep(2)
        left = subprocess.run(["ps", "aux"], capture_output=True, text=True).stdout
        n = sum(1 for l in left.splitlines()
                if "remote-debugging-port=9334" in l and "grep" not in l)
        print(f"浏览器清理复验: 残留 {n}", flush=True)

    with open("union_system.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"p44 完成：累计 {len(rows)} 个市级工会", flush=True)


if __name__ == "__main__":
    main()
