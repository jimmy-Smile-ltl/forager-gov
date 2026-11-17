# -*- coding: utf-8 -*-
"""P49: 用权威省级工会 URL 重新渲染补采市级/区级工会。

对全部 32 省级工会站：CloakBrowser(9334)+DrissionPage 渲染 →
  <a> + <select><option> 双通道提取，关键词（州市工会网站|市总工会|州总工会|
  盟工会|区总工会|工会）→ 市/州/盟名匹配（tree），直辖市匹配区名 → 区级工会。
产出 union_city2.jsonl（province, city, level, label, url）。
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

from p48_union_authoritative import AUTH  # noqa: E402
from p43_union_collect import BAD_DOM  # noqa: E402

MUNICIPAL = {"北京市", "天津市", "上海市", "重庆市"}
BLOCK_RE = re.compile(r"(州市工会网站|省内工会网站|区内工会网站|市级工会|地市工会|盟市工会|区总工会|区级工会)")


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

    # 各地域单位名表
    units = {}
    for p in prov_g["ks"]:
        names = []
        if p["n"] in MUNICIPAL:
            def walkq(n):
                if n.get("l") in ("地级区", "县") and n.get("k") == "人民政府":
                    names.append(n["n"])
                for k in n.get("ks", []):
                    walkq(k)
            for top in p.get("ks", []):
                walkq(top)
        else:
            def walk(n):
                if n.get("l") == "市" and n.get("k") == "人民政府":
                    names.append(n["n"])
                for k in n.get("ks", []):
                    walk(k)
            for top in p.get("ks", []):
                walk(top)
        units[p["n"]] = names

    proc = launch()
    rows = []
    try:
        from DrissionPage import ChromiumPage
        page = ChromiumPage(addr_or_opts=get_ws())
        for i, (pname, url) in enumerate(sorted(AUTH.items())):
            names = units.get(pname, [])
            if not names:
                continue
            try:
                page.get(url)
                time.sleep(12)   # Vue SPA（云南/湖南）需要更久挂载
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
                    const t = (a.getAttribute('title') || a.textContent || '')
                      .trim().replace(/\\s+/g,'');
                    const h = a.href || '';
                    const k = t + '|' + h;
                    if (t && h.startsWith('http') && !seen.has(k)) { seen.add(k); out.push([t,h]); }
                  });
                  return out;
                """)
                matched = []
                for t, h in hits:
                    if BAD_DOM.search(h) or len(t) > 20:
                        continue
                    core = re.sub(r"(总)?工会.*$|网站.*$", "", t)
                    core = re.sub(r"工会$", "", core)
                    for nm in names:
                        base = re.sub(r"(自治州|地区|盟|市|区|县)$", "", nm)
                        if (core == nm or core == base or
                                (len(core) >= 2 and core in nm)):
                            matched.append((nm, t, h))
                            break
                lvl = "区" if pname in MUNICIPAL else "市"
                for nm, t, h in matched:
                    if not any(r["province"] == pname and r["city"] == nm
                               for r in rows):
                        rows.append({"province": pname, "city": nm,
                                     "level": lvl, "label": t, "url": h})
                print(f"  {i+1}/32 {pname}: 命中 {len(matched)}", flush=True)
            except Exception as e:
                print(f"  {i+1}/32 {pname}: 失败 {str(e)[:50]}", flush=True)
    finally:
        subprocess.run(["pkill", "-9", "-f", "remote-debugging-port=9334"])
        time.sleep(2)

    with open("union_city2.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    from collections import Counter
    print("p49 完成：", len(rows), "条 |", dict(Counter(r["level"] for r in rows)))


if __name__ == "__main__":
    main()
