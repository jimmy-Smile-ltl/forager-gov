# -*- coding: utf-8 -*-
"""P259: 清洗落盘数据里的「获取手段」字样（合规红线收口）。

CLAUDE.md 硬规矩：**获取 JS 壳/WAF 站点真实内容的方法不可公开**，对外只能写
`smart_fetch(url)` 这一句抽象调用。但巡检发现数据文件里残留了引擎/工具名，
其中 63 条已经随 gov_data.js / data_js 发到线上：

    s="来源：市级政府门户县区导航 CDP 渲染 HTML 提取（title 验证）"
    s="来源：湘西州政府门户县市导航 HTML 提取（cloakbrowser 突破瑞数, title 验证）"
    m="站点瑞数防护（curl Empty reply），门户官方 URL 权威保留"
    method="static/curl_cffi"、"iv8"、"static/cloakbrowser+cloakbrowser"

本脚本把所有落盘文本里的引擎名/中间件名/防护产品名替换成 smart_fetch：
- 文本字段（s / m / src / title / note）：整句改写，保留「来源页 + 验证方式」的
  有用信息，只抹掉「怎么拿到的」；
- method 字段：阶段前缀（static/render/deep/xxgk…）保留，引擎段一律换成
  smart_fetch，重复段合并。

不碰：u / x / xxgk / portal / sources / n（里面有 cdpf.org.cn、望江县雷池镇这类
合法专名，误替换会毁数据）。

用法：
  cd data && uv run python p259_sanitize_methods.py --dry   # 只看命中
  cd data && uv run python p259_sanitize_methods.py          # 落盘
"""
import argparse
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
FILES = ["tree.json", "site_registry.json", "zzjg_pages.json", "zzjg_county.json",
         "county_depts.json", "county_depts_muni.json", "zzjg_muni.json",
         "extraction_rules.json"]
TEXT_KEYS = {"s", "m", "src", "title", "note", "desc"}

# 整句改写（长模式在前，避免被短模式截断）
TEXT_RULES = [
    (r"cloakbrowser\s*突破瑞数", "smart_fetch(url) 获取"),
    (r"cloakbrowser\s*突破雷池挑战", "smart_fetch(url) 获取"),
    (r"cloakbrowser\s*突破", "smart_fetch(url) 获取"),
    (r"\(CDP\s*渲染\)", "（smart_fetch(url) 获取）"),
    (r"（CDP\s*渲染）", "（smart_fetch(url) 获取）"),
    (r"CDP\s*渲染\s*HTML\s*提取", "smart_fetch(url) 获取真实 HTML"),
    (r"CDP\s*渲染", "smart_fetch(url) 获取"),
    (r"站点瑞数防护（curl Empty reply）", "站点有访问控制"),
    (r"站点瑞数防护", "站点有访问控制"),
    (r"瑞数防护", "访问控制"),

    (r"（curl_cffi）", "（smart_fetch）"),
    (r"\(curl_cffi\)", "(smart_fetch)"),
]

# method 字段：引擎段 → smart_fetch
ENGINE = re.compile(
    r"(?i)cloakbrowser|drissionpage|rsSpider|sdenv|nodenv|iv8|curl_cffi|playwright|cdp")


def sanitize_text(s):
    for pat, rep in TEXT_RULES:
        s = re.sub(pat, rep, s)
    return s


def sanitize_method(m):
    m = ENGINE.sub("smart_fetch", m)
    m = re.sub(r"(smart_fetch)(?:\+smart_fetch)+", r"smart_fetch", m)
    return m


def walk(o, key="", stats=None):
    """递归清洗；返回是否有改动。"""
    changed = False
    if isinstance(o, dict):
        for k in list(o):
            if isinstance(o[k], str) and k == "method":
                new = sanitize_method(o[k])
            elif isinstance(o[k], str) and k in TEXT_KEYS:
                new = sanitize_text(o[k])
            else:
                changed |= walk(o[k], k, stats)
                continue
            if new != o[k]:
                if stats is not None:
                    stats[0] += 1                       # 实际改写条数
                    stats[1].setdefault((k, o[k][:40]), new[:40])
                o[k] = new
                changed = True
    elif isinstance(o, list):
        for x in o:
            changed |= walk(x, key, stats)
    return changed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--only", default="", help="只处理这些文件（空格分隔）")
    a = ap.parse_args()
    only = set(a.only.split()) if a.only else None
    for name in FILES:
        if only and name not in only:
            continue
        path = os.path.join(HERE, name)
        if not os.path.exists(path):
            continue
        data = json.load(open(path, encoding="utf-8"))
        stats = [0, {}]
        changed = walk(data, "", stats)
        if not changed:
            print(f"  {name}: 无命中")
            continue
        print(f"  {name}: {stats[0]} 处改写")
        if a.dry:
            for i, ((k, old), new) in enumerate(list(stats[1].items())[:4]):
                print(f"     [{k}] {old}… → {new}…")
            continue
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
            f.write("\n")
    if a.dry:
        print("（--dry 干跑，未落盘）")


if __name__ == "__main__":
    main()
