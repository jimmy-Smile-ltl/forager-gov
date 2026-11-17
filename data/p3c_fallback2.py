# -*- coding: utf-8 -*-
"""P3c: 兜底第 2 轮 —— 对 p3b 后仍缺门户的市/县，强化查询策略。

pinyin 多指纹重试 + Bing 多查询词 + Bing cite 域名提取 + 结果放宽。
"""
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
from search_bing import search as bing_search

SUFFIX_RE = re.compile(r"(人民政府)?(市|区|县|旗|自治县|自治旗|自治州|地区|盟|林区|特区|联合旗)$")


def short_name(name):
    s = SUFFIX_RE.sub("", name)
    return s if s else name


def http_get(url, timeout=12):
    from curl_cffi import requests as creq
    for imp in ("chrome124", "chrome110", "safari17_0"):
        try:
            r = creq.get(url, timeout=timeout, impersonate=imp, verify=False)
            if r.status_code == 200 and len(r.content) > 500:
                for enc in ("utf-8", "gb18030"):
                    try:
                        return r.content.decode(enc)
                    except UnicodeDecodeError:
                        continue
                return r.content.decode("utf-8", errors="replace")
        except Exception:
            continue
    return None


def title_contains(html, name):
    if not html:
        return False
    m = re.search(r"<title>(.*?)</title>", html, re.S | re.I)
    if not m:
        return False
    t = re.sub(r"[\s|·\-—]", "", m.group(1))
    sn = short_name(name)
    return sn and sn in t


def fill_v2(rec):
    name, prov = rec["name"], rec["province"]
    sn = short_name(name)
    prov_sn = short_name(prov)

    # 1) Bing（多查询词，宽筛选）
    queries = [f"{name}人民政府", f"{prov_sn}{name}人民政府官网", f"{name}政府门户网站"]
    seen_hosts = set()
    for q in queries:
        try:
            results = bing_search(q, count=8, sleep=0.6)
        except Exception:
            results = []
        for r in results:
            host = urlparse(r["url"] or "").netloc.lower()
            if not host or not host.endswith(".gov.cn") or host in seen_hosts:
                continue
            blob = (r["title"] or "") + " " + (r["cite"] or "")
            if sn not in blob and name not in blob:
                continue
            seen_hosts.add(host)
            root = f"https://{host}/"
            if title_contains(http_get(root), name):
                rec["portal_url"] = root
                rec["how"] = "p3c-bing"
                return True
            # 非 www 前缀也试
            root2 = f"https://{host.replace('www.', '', 1) if host.startswith('www.') else host}/"
            if root2 != root and title_contains(http_get(root2), name):
                rec["portal_url"] = root2
                rec["how"] = "p3c-bing"
                return True
    return False


def main():
    todo = []
    for fn in ("city_portals.jsonl", "county_portals.jsonl"):
        for line in open(fn, encoding="utf-8"):
            r = json.loads(line)
            if not r.get("portal_url"):
                todo.append(r)
    print(f"p3c 目标 {len(todo)}", flush=True)

    ok = fail = 0
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = {ex.submit(fill_v2, r): r for r in todo}
        for i, f in enumerate(as_completed(futs)):
            try:
                ok += bool(f.result())
            except Exception:
                fail += 1
            if (i + 1) % 30 == 0:
                print(f"[p3c] {i+1}/{len(todo)} ok={ok} fail={fail + (len(todo)-i-1)-(len(todo)-i-1)}", flush=True)
    print(f"[p3c] done ok={ok}", flush=True)

    for fn in ("city_portals.jsonl", "county_portals.jsonl"):
        rows = [json.loads(l) for l in open(fn, encoding="utf-8")]
        by_code = {r["code"]: r for r in rows}
        for r in todo:
            if r["code"] in by_code:
                by_code[r["code"]].update(r)
        with open(fn, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print("回写完成", flush=True)


if __name__ == "__main__":
    main()
