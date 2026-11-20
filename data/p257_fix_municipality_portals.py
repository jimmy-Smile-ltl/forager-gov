# -*- coding: utf-8 -*-
"""P257: 直辖市市辖区门户 URL 修正 + 部门采集记录回炉。

起因（用户 2026-11-20）：「直辖市下面的区县政府部门，需要在块·行政层级合适的地方展示」。
排查中发现 4 个市辖区的门户 URL 不是门户：
  - 天津市和平区 → http://www.syhp.gov.cn/ 是**沈阳**市和平区门户（跨市同名错配），
    p246 已按此采到「机关简介-沈阳市和平区人民政府」，必须弃掉重采。
  - 北京市朝阳区/通州区/延庆区 → 记的是文章页/专题页（政府网站年度报表、
    /ztlm95/ 专题），不是门户首页；按 CLAUDE.md「门户/深文章页是错配高发区」
    归一到同主机的门户根。

修正来源（合规渠道）：
  - 天津和平区：天津市政府门户(www.tj.gov.cn)「区县导航」HTML 锚点
    `http://www.tjhp.gov.cn/`（2026-11-20 smart_fetch 实取）
  - 北京三区：原 URL 的同主机根，smart_fetch 复验 title：
    北京朝阳 / 北京市通州区人民政府 / 北京市延庆区人民政府

同时清掉 zzjg_pages.json 里 和平区/朝阳区 的错误记录与 p246 失败标记，
让 p246 用修正后的门户重采。
"""
import json
import os
import re
from urllib.parse import urlparse

TODAY = "2026-11-20"
HERE = os.path.dirname(os.path.abspath(__file__))

# 部门栏目链接的「不是栏目页」特征：文章/信息页、企事业单位信息公开
BAD_LINK = re.compile(
    r"/20\d{2}/|/t\d{8}_|\d{5,}\.html?$|ggqsyxxgk|ggqsydw|qyxxgk|gqxxgk|sopxxgk|"
    r"/art/|/content_|/doc/|/Item/|/detail", re.I)

# 站点模板错误页（2026-11-20 河东区实锤）：标题带区名照样能过标题校验，
# 但正文是错误提示。按标题剔除。
ERR_TITLE = re.compile(r"通用错误页面|错误页面|页面不存在|页面未找到|页面找不到|"
                       r"(?<!\d)404(?!\d)|not\s*found|出错了|服务器错误|访问出错|系统错误", re.I)

# (区名, 直辖市, 旧主机, 新 URL, 来源说明)
FIXES = [
    ("和平区", "天津市", "www.syhp.gov.cn", "http://www.tjhp.gov.cn/",
     "p257 修正跨市错配（原 syhp.gov.cn 为沈阳市和平区）；源：天津市政府门户区县导航"),
    ("朝阳区", "北京市", "www.bjchy.gov.cn", "http://www.bjchy.gov.cn/",
     "p257 归一门户根（原为政府网站年度报表文章页）"),
    ("通州区", "北京市", "www.bjtzh.gov.cn", "https://www.bjtzh.gov.cn/",
     "p257 归一门户根（原为政府网站工作年度报表文章页）"),
    ("延庆区", "北京市", "www.bjyq.gov.cn", "http://www.bjyq.gov.cn/",
     "p257 归一门户根（原为 /ztlm95/ 专题页）"),
]


def walk(n):
    yield n
    for k in n.get("ks") or []:
        yield from walk(k)


KIND_ORDER = ["机构设置", "内设机构", "直属单位", "事业单位",
              "直属企业", "公积金", "高校"]


def _realign_u(key, rec):
    """顶层 u/title/src 与 links 中优先级最高的一条对齐（幂等）。"""
    links = [l for l in (rec.get("links") or []) if l.get("u")]
    if not links:
        return
    top = min(links, key=lambda l: KIND_ORDER.index(l["kind"])
              if l.get("kind") in KIND_ORDER else 99)
    if rec.get("u") == top["u"]:
        return
    old = rec.get("u") or ""
    rec["u"] = top["u"]
    rec["title"] = top.get("title") or rec.get("title")
    rec["src"] = top.get("src") or rec.get("src")
    rec["method"] = top.get("method") or rec.get("method")
    rec["score"] = top.get("score") or rec.get("score")
    print(f"[u] {key}: {old[:60]} -> {top['u'][:60]}")


def main(dry=False):
    tree = json.load(open(os.path.join(HERE, "tree.json"), encoding="utf-8"))
    reg = json.load(open(os.path.join(HERE, "site_registry.json"), encoding="utf-8"))
    pages_f = os.path.join(HERE, "zzjg_pages.json")
    pages = json.load(open(pages_f, encoding="utf-8"))
    state_f = os.path.join(HERE, "p246_state.json")
    state = json.load(open(state_f, encoding="utf-8")) if os.path.exists(state_f) \
        else {"done": {}, "fail": {}}

    hits = 0
    changed = set()   # 本轮真正改过门户的区 → 采集记录要回炉
    for nm, prov, host, newu, note in FIXES:
        # ---- tree.json：只改该直辖市下的同名地级区节点 ----
        p = next((x for x in next(g for g in tree["ks"]
                                  if g["n"].startswith("省级"))["ks"]
                  if x["n"] == prov), None)
        node = None
        for ch in (p.get("ks") or []) if p else []:
            for d in walk(ch):
                if d.get("n") == nm and d.get("l") == "地级区":
                    node = d
                    break
        if node is None:
            print("!! 树里没找到", prov, nm)
            continue
        old = node.get("u") or ""
        if (urlparse(old).hostname or "") != host:
            print("!! 主机不符，跳过", prov, nm, old)
            continue
        if old == newu:
            print(f"[tree] {prov}{nm} 已是目标 URL，跳过（幂等）")
            continue
        node["u"] = newu
        # 幂等：同一 note 不重复追加（首次修完再跑一次曾把备注叠成两遍）
        if note not in (node.get("m") or ""):
            node["m"] = (node.get("m") + "；" + note) if node.get("m") else note
        node["verified_at"] = TODAY
        hits += 1
        changed.add(nm)
        print(f"[tree] {prov}{nm}: {old[:60]} -> {newu}")

        # ---- registry 同步（市辖区（地级行政区划）|区名）----
        for k, v in reg.items():
            if k.endswith("|" + nm) and k.startswith("市辖区") and \
                    (urlparse(v.get("u") or "").hostname or "") == host:
                v["u"] = newu
                v["verified_at"] = TODAY
                v["status"] = "ok"
                v["source"] = note
                print(f"   [reg] {k} 同步")

    # ---- 采集记录回炉：本轮改了门户的区，旧记录（按旧门户采的）不可信 ----
    # 只回炉真正改过 URL 的：早期版本无条件删朝阳区，重跑时会把刚采好的记录一起删掉
    for nm in sorted(changed):
        key = "地级区|" + nm
        if key in pages:
            pages.pop(key)
            print(f"[pages] 删除记录 {key}")
        for ph in ("static", "render", "deep", "candrender", "click", "homeblock"):
            state.get("fail", {}).pop(f"{ph}:{key}", None)
        state.get("done", {}).pop(key, None)

    # ---- 市辖区记录质量清洗：文章页/企事业单位公开不是「部门栏目」 ----
    # 2026-11-20 渲染阶段把徐汇「涉企收费目录清单」文章页记成了直属单位、
    # 和平区把 ggqsyxxgk 记成了事业单位——一律剔除；剔空的记录删掉让采集重来。
    n_bad = 0
    for key in [k for k in pages if k.startswith("地级区|")]:
        rec = pages[key]
        links = rec.get("links") or []

        def _bad(l):
            return (BAD_LINK.search(l.get("u") or "")
                    or ERR_TITLE.search(l.get("title") or ""))

        keep = [l for l in links if not _bad(l)]
        if len(keep) == len(links):
            continue
        for l in links:
            if _bad(l):
                print(f"[bad] {key} 剔除 {l.get('kind')} {l.get('u')[:70]} "
                      f"({(l.get('title') or l.get('src') or '')[:40]})")
                n_bad += 1
        if keep:
            rec["links"] = keep
        else:
            pages.pop(key)
            for ph in ("static", "render", "deep", "candrender", "click", "homeblock"):
                state.get("fail", {}).pop(f"{ph}:{key}", None)
            state.get("done", {}).pop(key, None)
            print(f"[pages] 记录已无有效链接，删除重采 {key}")
            continue
        _realign_u(key, rec)

    # ---- 主 URL 与 links 对齐 ----
    # p246 的 merge_links 是增量并入：新命中的类别进 links，顶层 u/title/src 却停在
    # 首次写入值（涪陵区 u 还是 ggqsydwxxgk 那页，links 已换成国资国企）→ 按类别
    # 优先级重挑一次，保证分组节点点进去就是最高优先级的栏目页。
    for key, rec in pages.items():
        if key.startswith("地级区|"):
            _realign_u(key, rec)

    print(f"修正 {hits} 个门户 URL；剔除 {n_bad} 条非栏目链接")
    if dry:
        print("--dry 干跑，未写盘")
        return
    with open(os.path.join(HERE, "tree.json"), "w", encoding="utf-8") as f:
        json.dump(tree, f, ensure_ascii=False, indent=1)
        f.write("\n")
    with open(os.path.join(HERE, "site_registry.json"), "w", encoding="utf-8") as f:
        json.dump(reg, f, ensure_ascii=False, indent=1)
        f.write("\n")
    with open(pages_f, "w", encoding="utf-8") as f:
        json.dump(pages, f, ensure_ascii=False, indent=1)
        f.write("\n")
    with open(state_f, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print("已写 tree.json / site_registry.json / zzjg_pages.json / p246_state.json")


if __name__ == "__main__":
    import sys
    main(dry="--dry" in sys.argv)
