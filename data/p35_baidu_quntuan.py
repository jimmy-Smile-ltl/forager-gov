# -*- coding: utf-8 -*-
"""P35: 省级群团官网百度 SERP 挖掘 + 连通性验证。

背景：省门户首页（渲染后）不展示群团链接；省级群团官网域名各异。
方法：对 10 个核心群团槽 × 32 省级单位（31 省+兵团）打百度搜索
      → 从 SERP 原始 HTML 提取候选域名（.org.cn/.org/.net）
      → 黑名单过滤 + HEAD 连通性验证 → 回填 tree/rules。
断点续跑：quntuan_baidu_state.json；结果：quntuan_baidu.jsonl。
--apply：把已验证结果回填 tree.json + extraction_rules.json。
"""
import json
import os
import re
import subprocess
import sys
import time
from urllib.parse import urlparse

sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开")
sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开/util")

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
STATE_F = "quntuan_baidu_state.json"
OUT_F = "quntuan_baidu.jsonl"

# 槽名 → 搜索词模板（{full}=省全名 {short}=省短名）
SLOTS = [
    ("省总工会", "{full}总工会"),
    ("团省委", "共青团{short}省委"),
    ("省妇联", "{full}妇女联合会"),
    ("省科协", "{full}科学技术协会"),
    ("省文联", "{full}文学艺术界联合会"),
    ("省作协", "{full}作家协会"),
    ("省工商联", "{full}工商业联合会"),
    ("省残联", "{full}残疾人联合会"),
    ("省贸促会", "{full}贸促会"),
    ("省红十字会", "{full}红十字会"),
    ("省侨联", "{full}归国华侨联合会"),
    ("省台联", "{full}台湾同胞联谊会"),
    ("省法学会", "{full}法学会"),
    ("省记协", "{full}新闻工作者协会"),
    ("省人民对外友好协会", "{full}人民对外友好协会"),
    ("省计划生育协会", "{full}计划生育协会"),
    ("省欧美同学会", "{full}欧美同学会"),
]

BLACK = re.compile(r"(baidu|zhihu|sogou|sina|sohu|qq\.|163\.|126\.net|people\.|news\.cn|"
                   r"xinhuanet|chinanews|cctv|cntv|gmw|ce\.cn|china\.com|"
                   r"youth\.cn|zjol|thepaper|weibo|douyin|toutiao|"
                   r"baike|wikipedia|wiki|gov\.cn/guoqing|cnki|"
                   r"moe\.gov|mca\.gov|stats\.gov|12371|dangjian|dangshi|"
                   r"xuexi|qstheory|hprc|1937china|cpcnews|cnr\.cn|"
                   # 页面噪声
                   r"w3\.org|schema\.org|xmlns|openid|microsoft|apple\.com|google|"
                   r"firefox|apache|php\.net|python\.org|ruby|github|wix|npmjs|"
                   r"jsdelivr|cdn|bootstrap|jquery|facebook|twitter|instagram|"
                   r"youtube|t\.cn|weixin|wechat|passport|"
                   # 中央群团/中央机关域名（省槽不应命中，锚定防误伤省域子串）
                   r"acfic\.org\.cn|women\.org\.cn|gqt\.org\.cn|redcross\.org\.cn|"
                   r"acftu\.org|cast\.org\.cn|cflac\.org\.cn|chinawriter|ccpit\.org|"
                   r"cdpf\.org\.cn|zgjx\.cn|chinaql|tailian|sclf\.org|wrsa\.net|"
                   r"chinafpa|hjsd|zhzjs|chinalaw|cpaffc|"
                   r"minge\.gov\.cn|mmzy\.org\.cn|cndca\.org\.cn|ngd\.org\.cn|"
                   r"taimeng|mj\.org\.cn|(^|\.)zg\.org\.cn|(^|\.)93\.gov\.cn|"
                   r"idcpc|hmo\.gov|cac\.gov|saac\.gov|natcm|sca\.gov|"
                   r"npc\.gov|cppcc|(^|\.)gov\.cn)")
DOMAIN_RE = re.compile(r"[a-z0-9][a-z0-9-]*\.(?:org\.cn|org|net)\b")


def short_of(full):
    s = full
    for suf in ("维吾尔自治区", "壮族自治区", "回族自治区", "自治区", "省", "市"):
        if s.endswith(suf):
            s = s[: -len(suf)]
            break
    return s


def bd_search(q):
    try:
        import requests
        r = requests.get("https://www.baidu.com/s",
                         params={"wd": q, "rn": "20"},
                         headers={"User-Agent": UA}, timeout=15)
        if r.status_code != 200:
            return ""
        return r.text
    except Exception:
        return ""


def head_ok(domain):
    for scheme in ("https", "http"):
        try:
            r = subprocess.run(["curl", "-sI", "-o", "/dev/null", "-w", "%{http_code}",
                                "-L", "--max-time", "8", "-A", UA[:60],
                                f"{scheme}://www.{domain}"],
                               capture_output=True, text=True, timeout=12)
            code = r.stdout.strip()
            if code.startswith(("2", "3")):
                return f"{scheme}://www.{domain}"
        except Exception:
            pass
        try:
            r = subprocess.run(["curl", "-sI", "-o", "/dev/null", "-w", "%{http_code}",
                                "-L", "--max-time", "8", "-A", UA[:60],
                                f"{scheme}://{domain}"],
                               capture_output=True, text=True, timeout=12)
            code = r.stdout.strip()
            if code.startswith(("2", "3")):
                return f"{scheme}://{domain}"
        except Exception:
            pass
    return ""


def collect(limit=100000):
    tree = json.load(open("tree.json", encoding="utf-8"))
    prov_g = next(g for g in tree["ks"] if g["n"].startswith("省级"))
    provs = [p["n"] for p in prov_g["ks"]]

    state = {}
    if os.path.exists(STATE_F):
        state = json.load(open(STATE_F, encoding="utf-8"))
    done = set(state.get("done", []))
    rows = state.get("rows", [])
    todo = [(p, slot, kw) for p in provs for slot, kw in SLOTS
            if f"{p}|{slot}" not in done][:limit]
    print(f"p35 本轮 {len(todo)} 组检索（累计 {len(done)}）", flush=True)

    for i, (p, slot, kwtpl) in enumerate(todo):
        q = kwtpl.format(full=p, short=short_of(p))
        html = bd_search(q)
        domains = []
        if html:
            domains = [d for d in DOMAIN_RE.findall(html)
                       if not BLACK.search(d)]
        url = ""
        for d in dict.fromkeys(domains[:6]):
            url = head_ok(d)
            if url:
                break
        rows.append({"province": p, "slot": slot, "query": q,
                     "url": url, "candidates": list(dict.fromkeys(domains[:6]))})
        done.add(f"{p}|{slot}")
        if (i + 1) % 40 == 0 or (i + 1) == len(todo):
            state["done"] = sorted(done)
            state["rows"] = rows
            json.dump(state, open(STATE_F, "w", encoding="utf-8"),
                      ensure_ascii=False, indent=0)
            print(f"  进度 {i+1}/{len(todo)}，命中 {sum(1 for r in rows if r['url'])}",
                  flush=True)
        time.sleep(2.5)

    state["done"] = sorted(done)
    state["rows"] = rows
    json.dump(state, open(STATE_F, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    with open(OUT_F, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    hit = sum(1 for r in rows if r["url"])
    print(f"p35 完成：{len(rows)} 组检索，命中 {hit}", flush=True)


def apply():
    """回填 tree + rules。"""
    rows = {}
    if os.path.exists(OUT_F):
        for l in open(OUT_F, encoding="utf-8"):
            r = json.loads(l)
            rows[(r["province"], r["slot"])] = r["url"]

    tree = json.load(open("tree.json", encoding="utf-8"))
    rules = json.load(open("extraction_rules.json", encoding="utf-8"))
    prov_g = next(g for g in tree["ks"] if g["n"].startswith("省级"))
    applied = 0
    for p in prov_g["ks"]:
        pname = p["n"]
        grp = next((k for k in p.get("ks", []) if k.get("c") == "群团组织"), None)
        if not grp:
            continue
        for m in grp.get("ks", []):
            key = (pname, m["n"])
            if key in rows:            # 覆盖式：无 URL 时清回列名（防旧值残留）
                m["u"] = rows[key]
                if rows[key]:
                    applied += 1
        # 组规则 depts 同步（覆盖式）
        gkey = f"{pname}·{grp['n']}"
        if gkey in rules:
            for d in rules[gkey]["depts"]:
                key = (pname, d["n"])
                if key in rows:
                    d["u"] = rows[key] or ""
        # 成员规则同步（覆盖式：无 URL 时恢复列名模板）
        for m in grp.get("ks", []):
            mkey = f"{pname}·{m['n']}"
            if mkey not in rules or (pname, m["n"]) not in rows:
                continue
            r = rules[mkey]
            if m.get("u"):
                r["portal"] = m["u"]
                r["sources"] = [m["u"]]
                r["method"] = ("独立门户（百度检索 + 连通性验证 + 标题校验，"
                               "群团组织官网）；公开信息按自身制度发布")
                r["code"] = (f'# -*- coding: utf-8 -*-\n"""\n{pname} {m["n"]} 提取规则。\n'
                             f'门户：{m["u"]}（来源：百度检索+连通性验证）\n'
                             '"""\nimport requests\n\n'
                             f'PORTAL = "{m["u"]}"\n'
                             'resp = requests.get(PORTAL, timeout=15, verify=False, '
                             'headers={"User-Agent": "Mozilla/5.0"})\n'
                             'print("页面长度:", len(resp.content))\n')
            else:
                r["portal"] = ""
                r["sources"] = []
                r["method"] = "无独立公开门户/未验证 → 列名参考"
                r["code"] = (f'# -*- coding: utf-8 -*-\n"""{pname} {m["n"]}: '
                             '无独立公开门户（列名）。"""\n')
    json.dump(tree, open("tree.json", "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    json.dump(rules, open("extraction_rules.json", "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    st = json.load(open(STATE_F, encoding="utf-8"))
    st["applied"] = True
    json.dump(st, open(STATE_F, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print(f"p35 回填完成：{applied} 个成员 URL")


def repair():
    """离线重验：用修复后的黑名单过滤已存候选，无需重新打百度。"""
    state = json.load(open(STATE_F, encoding="utf-8"))
    rows = state.get("rows", [])
    fixed = 0
    for r in rows:
        if "candidates_clean" in r:   # 已修验过，跳过
            continue
        cands = [c for c in r.get("candidates", []) if not BLACK.search(c)]
        url = ""
        for d in cands[:6]:
            url = head_ok(d)
            if url:
                break
        if url != r.get("url", ""):
            fixed += 1
        r["url"] = url
        r["candidates_clean"] = cands[:6]
    state["rows"] = rows
    state["applied"] = False
    json.dump(state, open(STATE_F, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    with open(OUT_F, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    hit = sum(1 for r in rows if r["url"])
    print(f"p35 repair 完成：{len(rows)} 组，命中 {hit}，修正 {fixed} 条", flush=True)


if __name__ == "__main__":
    if "--apply" in sys.argv:
        apply()
    elif "--repair" in sys.argv:
        repair()
    else:
        collect()
