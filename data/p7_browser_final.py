# -*- coding: utf-8 -*-
"""P7: 剩余真实市/县门户的浏览器终轮解析（含 xxgk）。

4 路并行独立 playwright Chromium（各自独立 profile，无共享实例，无 pkill，
退出即 close），逐实体：拼音候选 + Bing 候选域名 → 浏览器访问验证 → 顺手取 xxgk。
"""
import json
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
from search_bing import search as bing_search

SUFFIX_RE = re.compile(r"(人民政府)?(市|区|县|旗|自治县|自治旗|自治州|地区|盟|林区|特区|联合旗)$")
PSEUDO = re.compile(r"(市辖区|开发区|高新区|管理区|园区|工业区|示范区|合作区|保税区|实验区|管委会|循环化工园区|风景名胜区|新城)")

PY_EXCEPT = {
    "达尔罕茂明安联合旗": ["dmlh"], "阿拉善右旗": ["alsyq"], "科尔沁左翼中旗": ["kzzq"],
    "科尔沁左翼后旗": ["kzhq"], "科尔沁右翼前旗": ["kyqq"], "察哈尔右翼前旗": ["cyqq"],
    "察哈尔右翼中旗": ["cyzq"], "察哈尔右翼后旗": ["cyhq"], "正蓝旗": ["zlq"],
    "恩施土家族苗族自治州": ["enshi"], "湘西土家族苗族自治州": ["xiangxi"],
    "黔南布依族苗族自治州": ["qiannan"], "西双版纳傣族自治州": ["xsbn"],
    "德宏傣族景颇族自治州": ["dehong"], "迪庆藏族自治州": ["diqing"],
    "黄南藏族自治州": ["huangnan"], "果洛藏族自治州": ["guoluo"],
    "玉树藏族自治州": ["yushu"], "海西蒙古族藏族自治州": ["haixi"],
    "平谷区": ["bjpg"], "延庆区": ["bjyq"],
    "西岗区": ["dlxg"], "沙河口区": ["dlshk"],
}


def short_name(name):
    s = SUFFIX_RE.sub("", name)
    return s if s else name


def candidates_for(name):
    cands = list(PY_EXCEPT.get(name, []))
    if not cands:
        try:
            from pypinyin import lazy_pinyin
            cands = ["".join(lazy_pinyin(short_name(name)))]
        except Exception:
            cands = []
    hosts = []
    for c in cands:
        c = re.sub(r"[^a-z]", "", c.lower())
        for h in (f"www.{c}.gov.cn", f"{c}.gov.cn"):
            if h not in hosts:
                hosts.append(h)
    return hosts


def bing_hosts(name, prov_sn, limit=4):
    sn = short_name(name)
    hosts = []
    for q in (f"{name}人民政府", f"{prov_sn}{name}人民政府"):
        try:
            results = bing_search(q, count=6, sleep=0.4)
        except Exception:
            continue
        for r in results:
            host = urlparse(r["url"] or "").netloc.lower()
            if not host.endswith(".gov.cn") or host in hosts:
                continue
            blob = (r["title"] or "") + (r["cite"] or "")
            if sn in blob or name in blob:
                hosts.append(host)
    return hosts[:limit]


def browser_probe(entity, imp):
    """单实体浏览器解析。entity: dict 有 name/province。每线程独立 playwright 实例。"""
    from playwright.sync_api import sync_playwright

    name = entity["name"]
    sn = short_name(name)
    prov_sn = short_name(entity["province"])
    hosts = candidates_for(name)
    hosts += [h for h in bing_hosts(name, prov_sn) if h not in hosts]

    result = None
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent=("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"),
            locale="zh-CN",
        )
        page = ctx.new_page()
        try:
            for host in hosts[:4]:
                url = f"https://{host}/"
                try:
                    page.goto(url, timeout=25000, wait_until="domcontentloaded")
                    page.wait_for_timeout(5000)
                    title = (page.title() or "").replace(" ", "")
                    if sn and sn in title:
                        # 门户确认 → 顺手找 xxgk
                        xxgk = None
                        try:
                            links = page.eval_on_selector_all(
                                "a",
                                """els => els.map(e => ({
                                    t: (e.innerText||'').replace(/\\s+/g,'').slice(0,24),
                                    h: e.href
                                }))""")
                            for l in sorted(links, key=lambda x: (0 if x["t"] in ("政府信息公开", "政务公开", "信息公开") else 1)):
                                if ("信息公开" in l["t"] or "政务公开" in l["t"]) \
                                        and l["h"].startswith(("http://", "https://")):
                                    xxgk = l["h"]
                                    break
                        except Exception:
                            pass
                        result = (url, xxgk)
                        break
                except Exception:
                    continue
        finally:
            page.close()
            ctx.close()
            browser.close()
    return result


def main():
    miss = []
    for fn in ("city_portals.jsonl", "county_portals.jsonl"):
        for line in open(fn, encoding="utf-8"):
            r = json.loads(line)
            if not r.get("portal_url") and not PSEUDO.search(r["name"]):
                miss.append(r)
    print(f"p7 目标 {len(miss)}", flush=True)

    lock = threading.Lock()
    done = {"n": 0, "ok": 0}

    def worker(args):
        i, r = args
        res = browser_probe(r, i)
        with lock:
            done["n"] += 1
            if res:
                done["ok"] += 1
                r["portal_url"] = res[0]
                r["how"] = "p7浏览器"
                if res[1]:
                    r["xxgk_url"] = res[1]
                    r["xxgk_src"] = "p7浏览器"
            if done["n"] % 20 == 0:
                print(f"[p7] {done['n']}/{len(miss)} ok={done['ok']}", flush=True)
        return r

    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = [ex.submit(worker, (i, r)) for i, r in enumerate(miss)]
        results = [f.result() for f in as_completed(futs)]
    print(f"[p7] done ok={done['ok']}/{len(miss)}", flush=True)

    # 回写（只在原行上补字段）
    by_code = {}
    for fn in ("city_portals.jsonl", "county_portals.jsonl"):
        for line in open(fn, encoding="utf-8"):
            r = json.loads(line)
            by_code.setdefault(r["code"], r)
    for r in results:
        by_code[r["code"]].update({k: v for k, v in r.items() if v})
    for fn in ("city_portals.jsonl", "county_portals.jsonl"):
        rows = [json.loads(l) for l in open(fn, encoding="utf-8")]
        for r in rows:
            r.update({k: v for k, v in by_code[r["code"]].items() if v})
        with open(fn, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print("回写完成", flush=True)


if __name__ == "__main__":
    main()
