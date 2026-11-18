"""成都门户（瑞数 + 本机 IP 被封）专项探针：走 dps 代理的独立 context，
等到瑞数挑战 JS 放行、真实首页 DOM 出现为止，落盘后离线抽机构链接。"""
import os
import sys

os.environ["PROXY_MODE"] = "dps"
os.environ["P246_RENDER_PROXY"] = "1"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from p246_zzjg_pages import _proxied_page  # noqa: E402

URL = "https://www.chengdu.gov.cn/"
with _proxied_page(URL) as pp:
    if not pp:
        print("NO_PROXY", flush=True)
        sys.exit(2)
    page, _ctx = pp
    try:
        page.goto(URL, wait_until="domcontentloaded", timeout=40000)
    except Exception as e:
        print("goto:", type(e).__name__, str(e)[:120], flush=True)
    best = ""
    for i in range(12):          # 最多约 36s：瑞数挑战→重定向→真页
        page.wait_for_timeout(3000)
        try:
            html = page.content() or ""
        except Exception:
            html = ""
        print(f"[{i}] len={len(html)} url={page.url[:90]}", flush=True)
        if len(html) > len(best):
            best = html
        if len(html) > 20000 and "成都" in html:
            try:
                for _ in range(3):
                    page.mouse.wheel(0, 8000)
                    page.wait_for_timeout(1200)
                h2 = page.content() or ""
                if len(h2) > len(best):
                    best = h2
            except Exception:
                pass
            break
    with open("/tmp/chengdu.html", "w", encoding="utf-8") as f:
        f.write(best)
    print("saved", len(best), flush=True)
