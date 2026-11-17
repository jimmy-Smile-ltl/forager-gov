# -*- coding: utf-8 -*-
"""政府信息公开名单采集 - 公共抓取模块。

纯 requests 层抓取（不启浏览器，规避浏览器生命周期铁律）。
编码兼容 GBK/UTF-8，httpx 失败时 curl_cffi 兜底。
"""
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin, urlparse

import httpx

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)

HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

_client = None


def get_client() -> httpx.Client:
    global _client
    if _client is None:
        _client = httpx.Client(
            timeout=15.0, follow_redirects=True, verify=False, headers=HEADERS
        )
    return _client


def fetch_text(url: str, timeout: float = 15.0) -> str | None:
    """抓取页面文本，返回解码后的 HTML 或 None。"""
    for attempt in range(2):
        try:
            resp = get_client().get(url, timeout=timeout)
            if resp.status_code >= 400:
                return None
            html = resp.content
            # 优先按响应头编码，否则尝试常见编码
            enc = resp.encoding or ""
            if "gb" in enc.lower():
                return html.decode("gb18030", errors="replace")
            if html[:3] == b"\xef\xbb\xbf":
                return html[3:].decode("utf-8", errors="replace")
            for enc_guess in ("utf-8", "gb18030"):
                try:
                    return html.decode(enc_guess)
                except UnicodeDecodeError:
                    continue
            return html.decode("utf-8", errors="replace")
        except Exception:
            time.sleep(0.5 * (attempt + 1))
    return None


def curl_fetch_text(url: str, timeout: float = 15.0) -> str | None:
    """curl_cffi 兜底（部分站点 TLS 指纹校验）。"""
    try:
        from curl_cffi import requests as creq

        resp = creq.get(url, timeout=timeout, impersonate="chrome", verify=False)
        if resp.status_code >= 400:
            return None
        html = resp.content
        for enc_guess in ("utf-8", "gb18030"):
            try:
                return html.decode(enc_guess)
            except UnicodeDecodeError:
                continue
        return html.decode("utf-8", errors="replace")
    except Exception:
        return None


def fetch(url: str, timeout: float = 15.0) -> str | None:
    """httpx 优先，失败 curl_cffi 兜底。"""
    text = fetch_text(url, timeout)
    if text is None:
        text = curl_fetch_text(url, timeout)
    return text


# 信息公开专栏链接判定文本
XXGK_LINK_PATTERNS = [
    "政府信息公开",
    "政务公开",
    "信息公开",
    "政府信息依申请公开",
]


ARTICLE_URL_RE = re.compile(
    r"/art(icle)?(_\d+)?/\d{4}/\d{1,2}/\d{1,2}/art_\d+(_\d+)?\.(html?|shtml?)$"  # TRS 文章页
    r"|/art_\d+(_\d+)?\.(html?|shtml?)$"
    r"|/t\d{8,10}_\d+\.html?$"                                            # 常见发布稿
    r"|/c_\d+\.html?$"
    r"|/(\d{4}/\d{2}/\d{2}/[a-z0-9]+\.html?)$"
    r"|/[0-9a-f]{24,}/.*\.(html?|shtml?)$")                               # uuid 文章页


def is_article_url(u: str) -> bool:
    """判断是否为新闻/文章详情页（而非专栏入口）。"""
    return bool(ARTICLE_URL_RE.search(u or ""))


def find_xxgk_links(html: str, base_url: str):
    """从页面中找出疑似信息公开专栏的链接列表。

    返回 [(锚文本, 绝对URL, 优先级)]，优先级越小越好：
    1=精确"政府信息公开" 2="政务公开" 3=含"信息公开" 4=其他
    5=URL路径特征+长导航词 6=URL路径特征+空/纯图标链接
    """
    from bs4 import BeautifulSoup

    results = []
    if not html:
        return results
    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception:
        return results
    seen = set()
    for a in soup.find_all("a"):
        text = re.sub(r"\s+", "", a.get_text(" ", strip=True))
        href = a.get("href") or ""
        if not href or href.startswith(("javascript", "#")):
            continue
        abs_url = urljoin(base_url, href)
        if not abs_url.startswith(("http://", "https://")):
            continue
        key = (text, abs_url)
        if key in seen:
            continue
        path_xxgk = bool(re.search(r"/(zfxxgkm?|xxgk|zwgk|govinfo|zfgk|xxgkml)(/|\.|$)", abs_url))
        priority = None
        if text == "政府信息公开" or text.startswith("政府信息公开专栏"):
            priority = 1
        elif text == "政务公开":
            priority = 2
        elif "信息公开" in text and len(text) <= 12:
            priority = 3
        elif "政务公开" in text and len(text) <= 12:
            priority = 4
        elif text == "公开" or text in ("信息公开专栏", "法定主动公开", "主动公开"):
            priority = 4
        elif ("信息公开" in text or "政务公开" in text) and len(text) <= 30 \
                and "：" not in text and "｜" not in text:
            priority = 5
        elif path_xxgk and 0 < len(text) <= 20 and not text.startswith("国务院信息"):
            priority = 5
        elif path_xxgk and not text:
            priority = 6
        elif path_xxgk and len(text) <= 8:
            priority = 6
        if priority is not None:
            if is_article_url(abs_url):
                priority += 20  # 文章详情页降级（除非无其他候选）
            seen.add(key)
            results.append((text, abs_url, priority))
    results.sort(key=lambda x: x[2])
    return results


def find_xxgk_url(html: str, base_url: str) -> str | None:
    """返回页面中最像信息公开专栏的 URL，找不到返回 None。"""
    links = find_xxgk_links(html, base_url)
    if links:
        return links[0][1]
    return None


def probe_xxgk_paths(portal_url: str) -> str | None:
    """常见信息公开专栏路径探测兜底。"""
    base = portal_url.rstrip("/")
    if base.endswith(("index.html", "index.htm", "index.shtml")):
        base = base.rsplit("/", 1)[0]
    candidates = [
        f"{base}/zfxxgk/",
        f"{base}/zfxxgk/index.html",
        f"{base}/zfxxgk/index.htm",
        f"{base}/zfxxgkm/",
        f"{base}/zfxxgkm/index.htm",
        f"{base}/xxgk/",
        f"{base}/zwgk/",
        f"{base}/govinfo/",
        f"{base}/zfxxgkzn/",
        f"{base}/xxgkml/",
        f"{base}/zfgk/",
        f"{base}/zfxxgk/index.shtml",
    ]
    for u in candidates:
        try:
            resp = get_client().get(u, timeout=10.0)
            if resp.status_code == 200 and len(resp.content) > 500:
                return u
        except Exception:
            continue
    return None


def norm_url(url: str) -> str:
    """规范化 URL：去尾部斜杠、去默认 index、http→https（保原文另行记录）。"""
    if not url:
        return ""
    url = url.strip()
    if not url:
        return ""
    return url


def domain_of(url: str) -> str:
    return urlparse(url).netloc.lower().replace("www.", "") or ""


def map_parallel(items, fn, workers=20, batch_label=""):
    """并发执行 fn(item) -> item 更新，返回成功/失败计数。"""
    ok = fail = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(fn, it): it for it in items}
        for i, fut in enumerate(as_completed(futs)):
            it = futs[fut]
            try:
                if fut.result():
                    ok += 1
                else:
                    fail += 1
            except Exception:
                fail += 1
            if batch_label and (i + 1) % 100 == 0:
                print(f"[{batch_label}] {i+1}/{len(items)} ok={ok} fail={fail}", flush=True)
    print(f"[{batch_label}] done ok={ok} fail={fail}", flush=True)
    return ok, fail


# ---------- 页面快照留痕（证据保存，2026-11-03 体系设计确立） ----------

SNAP_ROOT = "snapshots"


def snap_path(board: str, province: str, org: str, page: str,
              day: str = None) -> str:
    """快照路径：snapshots/<板块>/<省>/<机构>/<YYYYMMDD>_<页面>.html。

    板块：renda/zhengxie/jiancha/fayuan/jiwei/minzhu/buwei/tingju/
          shixian/other；省：全名或「中央」；机构：机构简称。
    """
    import datetime
    d = day or datetime.date.today().strftime("%Y%m%d")
    import os
    p = os.path.join(SNAP_ROOT, board, province, org, f"{d}_{page}.html")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    return p


def save_snap(board: str, province: str, org: str, page: str,
              html: str, day: str = None) -> str:
    """保存快照并返回路径。页面名建议：入口页=home、栏目页=栏目名。"""
    import os
    p = snap_path(board, province, org, page, day)
    with open(p, "w", encoding="utf-8") as f:
        f.write(html)
    return p


def save_snap_bin(board: str, province: str, org: str, page: str,
                  raw: bytes, day: str = None) -> str:
    """保存二进制快照（gb18030 等非 UTF-8 页面原始字节）。"""
    p = snap_path(board, province, org, page, day)
    with open(p, "wb") as f:
        f.write(raw)
    return p


# ---------- 网站注册表（条块同源，2026-11-06 架构确立） ----------

def reg_key(cat, name):
    return f"{cat}|{name}"


def load_registry():
    """加载统一网站注册表（采集结果唯一登记处）。"""
    import json, os
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "site_registry.json")
    if os.path.exists(p):
        return json.load(open(p, encoding="utf-8"))
    return {}


def save_registry(reg):
    import json, os
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "site_registry.json")
    json.dump(reg, open(p, "w", encoding="utf-8"),
              ensure_ascii=False, indent=0)
    return p
