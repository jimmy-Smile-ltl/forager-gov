# -*- coding: utf-8 -*-
"""P6b: 浏览器修复 v2 —— 长等待 + 每站点候选路径直连 + 残留链接 dump。"""
import json
import re
import sys

sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))

CANDIDATES = {
    "海关总署": ["http://www.customs.gov.cn/customs/302249/302310/index.html",
                "http://www.customs.gov.cn/customs/302249/index.html"],
    "国家卫生健康委员会": ["http://www.nhc.gov.cn/wjw/xxgk/xxgk.shtml",
                          "http://www.nhc.gov.cn/wjw/xxgk/index.shtml"],
    "国家药品监督管理局": ["https://www.nmpa.gov.cn/zwgk/zfxxgkzq/index.html",
                          "https://www.nmpa.gov.cn/zwgk/"],
    "湖北": ["https://www.hubei.gov.cn/zfxxgk/", "http://www.hubei.gov.cn/zfxxgk/"],
    "甘肃": ["https://www.gansu.gov.cn/zfxxgk/", "http://www.gansu.gov.cn/zfxxgk/"],
    "国务院新闻办公室": ["http://www.scio.gov.cn/zfxxgk/", "http://www.scio.gov.cn/zfxxgk.htm"],
    "国家互联网信息办公室": ["http://www.cac.gov.cn/zfxxgk.htm", "http://www.cac.gov.cn/zfxxgk/"],
    "国防部": ["http://www.mod.gov.cn/gfbw/gfxxgk/index.htm"],
    "国家消防救援局": ["https://www.119.gov.cn/zfxxgk/", "https://www.119.gov.cn/zwgk/"],
    "国家认证认可监督管理委员会": ["http://www.cnca.gov.cn/zwgk/", "http://www.cnca.gov.cn/zwgk/index.shtml"],
    "国务院港澳事务办公室": ["https://www.hmo.gov.cn/zwgk/"],
}

XXGK_TITLE_RE = re.compile(r"信息公开|政务公开|公开", re.I)


def page_has_xxgk(page):
    try:
        title = page.title() or ""
        body_head = page.evaluate("() => document.body ? document.body.innerText.slice(0,2000) : ''")
    except Exception:
        return False
    return bool(XXGK_TITLE_RE.search(title + (body_head or "")))


def main():
    from playwright.sync_api import sync_playwright

    targets = []
    for fn in ("central.jsonl", "province.jsonl"):
        for line in open(fn, encoding="utf-8"):
            r = json.loads(line)
            if not r.get("xxgk_url") and r["name"] in CANDIDATES:
                targets.append(r)
    print(f"v2 目标 {len(targets)} 个", flush=True)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent=("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"),
            locale="zh-CN",
        )
        for i, r in enumerate(targets):
            name = r["name"]
            print(f"[{i+1}/{len(targets)}] {name}", flush=True)
            page = ctx.new_page()
            found = None
            try:
                # 首页导航（长等待）
                page.goto(r["portal_url"], timeout=30000, wait_until="domcontentloaded")
                page.wait_for_timeout(8000)
                try:
                    links = page.eval_on_selector_all(
                        "a",
                        """els => els.map(e => ({
                            t: (e.innerText||'').replace(/\\s+/g,'').slice(0,24),
                            h: e.href
                        }))""")
                    for l in sorted(links, key=lambda x: (0 if x["t"] in ("政府信息公开", "政务公开", "信息公开") else 1)):
                        if (("信息公开" in l["t"] or "政务公开" in l["t"])
                                and l["h"].startswith(("http://", "https://"))):
                            found = l["h"]
                            break
                except Exception:
                    pass
                # 候选路径直连
                if not found:
                    for cand in CANDIDATES.get(name, []):
                        try:
                            page.goto(cand, timeout=30000, wait_until="domcontentloaded")
                            page.wait_for_timeout(6000)
                            if page_has_xxgk(page):
                                found = cand
                                break
                        except Exception:
                            continue
            except Exception as e:
                print("   ERR", str(e)[:60], flush=True)
            finally:
                page.close()
            if found:
                r["xxgk_url"] = found
                r["xxgk_src"] = "浏览器修复v2"
                print(f"   -> {found}", flush=True)
            else:
                print("   -> 仍未命中", flush=True)
        browser.close()

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
