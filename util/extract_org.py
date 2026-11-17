# -*- coding: utf-8 -*-
"""通用机构导航提取器 — 从任意网页 DOM 提取「机构名 → URL」映射。

设计原则（2026-11-09 用户指令：每省市网站结构不同，没有统一规则，
强化提取能力、灵活适配不同网页结构才是根本）：

1. 全量提取文本-URL 对（<a> 与 <option> 双通道, 不分形态）
2. 文本归一化 + 与「机构名库」匹配（区划名及其后缀变体:
   「长安区」「长安区人民检察院」「长安检察院」「长安区院」）
3. 结构感知: <select> 分块内首项=父机构名(市), 后续=子机构(县);
   纯地名文本靠上下文归属
4. URL 过滤与置信评分: 排除 javascript/新闻文章路径;
   域特征(检/政/府)加权; 精确全名匹配 > 纯地名匹配 > 推断
"""
import re
from urllib.parse import urljoin

# 新闻/文章路径特征（非官网导航）
NEWS_PAT = re.compile(
    r"/(content|art_\d+|t\d{8}_\d+|article_\d+|Item/\d+|index\.(s?html?|aspx?)?\?"
    r"(?:articleId|newsid|id)=)", re.I)
BAD_HREF = ("javascript", "#", "mailto:")

def _norm(t: str) -> str:
    return re.sub(r"\s+", "", t or "")

def _clean_url(u: str, base: str) -> str:
    if not u or any(u.strip().lower().startswith(b) for b in BAD_HREF):
        return ""
    if u.startswith("//"):
        u = "http:" + u
    if not u.startswith("http"):
        u = urljoin(base, u)
    return u.strip()

def _conf(u: str, text: str, full_name: str, org_kw: tuple) -> float:
    """置信评分: 0-1"""
    if NEWS_PAT.search(u):
        return 0.0
    s = 0.3  # 基础分: 有 URL 且非新闻
    if text == full_name:
        s += 0.5          # 锚文本=完整机构名
    elif text.endswith(tuple(k for k in org_kw if k)):
        s += 0.35         # 锚文本含机构关键词(XX人民检察院/XX政协)
    # 域特征
    if re.search(r"jcy\.gov\.cn|jiancha|spp\.gov", u):
        s += 0.15
    elif re.search(r"\.gov\.cn", u):
        s += 0.1
    return min(s, 1.0)

def extract(html: str, base: str, org_names: dict,
            org_kw: tuple = ("人民检察院", "检察院", "政协")) -> dict:
    """org_names: {全名: None} 或 {全名: 节点}——键为机构全名（如
    「长安区人民检察院」），值任意（原样返回）。
    返回 {全名: (URL, 置信度, 值)}"""
    results = {}
    # 1) 全量文本-URL 对
    pairs = []
    for uu, tt in re.findall(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>\s*([^<]{1,40}?)\s*</a>', html, re.S):
        pairs.append((_norm(tt), uu))
    # 2) select 分块: (块首文本, [(文本, url), ...])
    for sel in re.findall(r'<select[^>]*>(.*?)</select>', html, re.S):
        opts = [(_norm(t), u) for u, t in
                re.findall(r'<option[^>]+value=["\']([^"\']+)["\'][^>]*>\s*([^<]{1,20}?)\s*</option>', sel, re.S)]
        if not opts:
            continue
        first = opts[0][0]
        for i, (t, u) in enumerate(opts):
            if t in ("", "———", "---", "—"):
                continue
            # 块首项做市上下文: 全名尝试「t+人民检察院」; 县名带市前缀「first+t」
            pairs.append((t, u))
            if i > 0 and first and len(first) <= 5:
                pairs.append((first + t, u))
    # 3) 匹配
    for full_name, val in org_names.items():
        for t, u in pairs:
            cu = _clean_url(u, base)
            if not cu:
                continue
            # 变体匹配: 逐层剥离机构关键词后缀(人大/政协/检察院/监委/法院)
            # + 区划后缀(市/县/区/旗/盟) → 全名/机构短名/区划名/裸地名 全覆盖
            stem = full_name
            for _k in org_kw:
                if stem.endswith(_k):
                    stem = stem[: -len(_k)]
                    break
            stem2 = re.sub(r"人民?$", "", stem)   # 「XX市人民」→「XX市」
            bare = re.sub(r"(市|县|区|旗|盟|自治州)$", "", stem2)
            variants = {full_name, stem, stem2, bare,
                        re.sub(r"(人民)?检察院$", "", full_name)}
            if t in variants or t == stem:
                c = _conf(cu, t, full_name, org_kw)
                if c > 0 and c >= results.get(full_name, (None, 0))[1]:
                    results[full_name] = (cu, c, val)
    return results
