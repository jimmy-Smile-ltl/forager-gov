# -*- coding: utf-8 -*-
"""P8: 修复错配行（zwfw 政务服务网错配 + 海淀/成都特例）。

zwfw 错配行 → Bing/拼音找真实政府门户 → 重新解析 xxgk（浏览器兜底）。
"""
import json
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
from search_bing import search as bing_search
from p3b_fallback import short_name, SUFFIX_RE
from p7_browser_final import candidates_for, bing_hosts

MANUAL_XXGK = {
    # (province, name) -> xxgk
    ("北京市", "海淀区"): "https://zyk.bjhd.gov.cn/jbdt/",
}
MANUAL_XXGK_SRC = "手动核实（标题确认为政府信息公开专栏）"


def browser_resolve(host_cands, name):
    """浏览器验证门户 + 取 xxgk。返回 (portal_url, xxgk_url) or None。"""
    from playwright.sync_api import sync_playwright

    sn = short_name(name)
    host_cands = [h for h in host_cands if "zwfw" not in h and "icity" not in h]
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent=("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"), locale="zh-CN")
        page = ctx.new_page()
        result = None
        try:
            for host in host_cands[:3]:
                try:
                    page.goto(f"https://{host}/", timeout=25000, wait_until="domcontentloaded")
                    page.wait_for_timeout(6000)
                    title = (page.title() or "").replace(" ", "")
                    if (sn and sn in title) and ("政府" in title) and ("政务服" not in title):
                        xxgk = None
                        try:
                            links = page.eval_on_selector_all(
                                "a",
                                """els => els.map(e => ({t:(e.innerText||'').replace(/\\s+/g,'').slice(0,24),h:e.href}))""")
                            for l in sorted(links, key=lambda x: (0 if x["t"] in ("政府信息公开", "政务公开", "信息公开") else 1)):
                                if ("信息公开" in l["t"] or "政务公开" in l["t"]) and l["h"].startswith(("http://", "https://")):
                                    xxgk = l["h"]
                                    break
                        except Exception:
                            pass
                        result = (f"https://{host}/", xxgk)
                        break
                except Exception:
                    continue
        finally:
            page.close(); ctx.close(); browser.close()
    return result


def check_title_browser(host, kw):
    """浏览器访问 host 首页，标题含 kw 且像政府/公开页面 → True。"""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent=("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"), locale="zh-CN")
        page = ctx.new_page()
        ok = False
        try:
            page.goto(f"https://{host}/", timeout=25000, wait_until="domcontentloaded")
            page.wait_for_timeout(6000)
            title = (page.title() or "").replace(" ", "")
            ok = kw in title
        except Exception:
            ok = False
        finally:
            page.close(); ctx.close(); browser.close()
    return ok


def repair_row(r):
    """r 含 portal_url 可能错配。返回更新后的 r。"""
    name, prov = r["name"], r["province"]
    sn = short_name(name)
    prov_sn = short_name(prov)

    # 手工表
    if (prov, name) in MANUAL_XXGK:
        r["xxgk_url"] = MANUAL_XXGK[(prov, name)]
        r["xxgk_src"] = MANUAL_XXGK_SRC
        return r

    # 成都特例：门户已知正确，只补信息公开平台
    if name == "成都市" and not r.get("xxgk_url"):
        res = browser_resolve(["www.chengdu.gov.cn"], name)
        if res and res[1]:
            r["xxgk_url"] = res[1]
            r["xxgk_src"] = "p8浏览器"
        elif check_title_browser("gk.chengdu.gov.cn", "成都"):
            r["xxgk_url"] = "https://gk.chengdu.gov.cn/"
            r["xxgk_src"] = "成都市政府信息公开平台，待复核"
        return r

    if r.get("portal_url") and "zwfw" not in r["portal_url"]:
        return r  # 门户非 zwfw，无需换

    # 候选：拼音 + Bing
    hosts = candidates_for(name)
    hosts += [h for h in bing_hosts(name, prov_sn) if h not in hosts]
    if not hosts:
        return r
    res = browser_resolve(hosts, name)
    if res:
        r["portal_url"] = res[0]
        r["how"] = "p8修复"
        if res[1]:
            r["xxgk_url"] = res[1]
            r["xxgk_src"] = "p8浏览器"
        else:
            r["xxgk_url"] = ""
            r["xxgk_src"] = ""
    return r


def main():
    # 读 city_county_final.jsonl 和 prov_depts.jsonl
    cc = [json.loads(l) for l in open("city_county_final.jsonl", encoding="utf-8")]
    depts = [json.loads(l) for l in open("prov_depts.jsonl", encoding="utf-8")]
    targets = []
    targets += [r for r in cc if "zwfw" in (r.get("portal_url") or "")]
    targets += [r for r in depts if "zwfw" in (r.get("portal_url") or "")]
    targets += [r for r in cc if (r["province"], r["name"]) in MANUAL_XXGK]
    # 成都特例（xxgk 缺失的大市）
    targets += [r for r in cc if r["name"] in ("成都市",) and r.get("portal_url") and not r.get("xxgk_url")]
    seen = {}
    for r in targets:
        seen[(r.get("province", ""), r["name"])] = r
    targets = list(seen.values())
    print(f"p8 目标 {len(targets)}", flush=True)

    lock = threading.Lock()
    done = {"n": 0}
    with ThreadPoolExecutor(max_workers=3) as ex:
        futs = {ex.submit(repair_row, r): r for r in targets}
        for f in as_completed(futs):
            r = f.result()
            with lock:
                done["n"] += 1
                if done["n"] % 5 == 0:
                    print(f"[p8] {done['n']}/{len(targets)}", flush=True)

    # 回写 city_county_final
    by_code = {r["code"]: r for r in cc}
    for r in targets:
        if r.get("code") and r["code"] in by_code:
            by_code[r["code"]].update(r)
    with open("city_county_final.jsonl", "w", encoding="utf-8") as f:
        for r in sorted(by_code.values(), key=lambda x: x["code"]):
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    # 回写 prov_depts
    by_name = {(r["province"], r["name"]): r for r in depts}
    for r in targets:
        k = (r.get("province", ""), r["name"])
        if k in by_name:
            by_name[k].update(r)
    with open("prov_depts.jsonl", "w", encoding="utf-8") as f:
        for r in sorted(depts, key=lambda x: (x["province"], x["name"])):
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print("p8 回写完成", flush=True)


if __name__ == "__main__":
    main()
