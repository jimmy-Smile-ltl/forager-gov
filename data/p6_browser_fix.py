# -*- coding: utf-8 -*-
"""P6: WAF/JS 站点信息公开专栏浏览器修复（独立 Chromium，符合浏览器隔离铁律）。

使用 playwright 自带 Chromium（com.google.Chrome.forTesting，项目浏览器），
单实例顺序访问，结束即杀（SIGKILL 复验）。仅用于 p1/p4 未命中的少量站点。
"""
import json
import re
import sys

sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))

XXGK_HREF_RE = re.compile(r"href=[\"']([^\"']*(?:zfxxgk|zfxxgkm|xxgk|zwgk|govinfo)[^\"']*)[\"']", re.I)


def collect_browser_links(page):
    """在已加载页面中提取 信息公开 相关链接。"""
    try:
        links = page.eval_on_selector_all(
            "a",
            """els => els.map(e => ({
                t: (e.innerText||'').replace(/\\s+/g,'').slice(0,24),
                h: e.href
            }))"""
        )
    except Exception:
        return []
    out = []
    for l in links:
        t, h = l["t"], l["h"]
        if not h or not h.startswith(("http://", "https://")):
            continue
        if ("信息公开" in t or "政务公开" in t or t == "公开" or
                XXGK_HREF_RE.search(h) and len(t) <= 20):
            out.append((t, h))
    return out


def browser_resolve(portal_url):
    """返回 (xxgk_url or None)。"""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent=("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"),
            locale="zh-CN",
        )
        page = ctx.new_page()
        try:
            page.goto(portal_url, timeout=30000, wait_until="domcontentloaded")
            page.wait_for_timeout(4000)  # 等 JS 挑战/菜单渲染
            links = collect_browser_links(page)
        except Exception:
            links = []
        finally:
            browser.close()
    # 优先级排序
    links.sort(key=lambda x: (0 if x[0] in ("政府信息公开", "政务公开") else 1))
    for t, h in links:
        if h:
            return h
    return None


def main():
    targets = []
    for fn in ("central.jsonl", "province.jsonl"):
        for line in open(fn, encoding="utf-8"):
            r = json.loads(line)
            if not r.get("xxgk_url"):
                targets.append(r)
    print(f"浏览器修复目标 {len(targets)} 个")

    for i, r in enumerate(targets):
        print(f"[{i+1}/{len(targets)}] {r['name']} {r['portal_url'][:60]}", flush=True)
        u = browser_resolve(r["portal_url"])
        if u:
            r["xxgk_url"] = u
            r["xxgk_src"] = "浏览器修复"
            print(f"   -> {u}", flush=True)
        else:
            print("   -> 仍未命中", flush=True)

    for fn in ("central.jsonl", "province.jsonl"):
        rows = [json.loads(l) for l in open(fn, encoding="utf-8")]
        for r in targets:
            for row in rows:
                if row["name"] == r["name"]:
                    row.update(r)
        with open(fn, "w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print("done", flush=True)


if __name__ == "__main__":
    main()
