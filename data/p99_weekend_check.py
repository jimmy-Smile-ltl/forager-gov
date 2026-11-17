# -*- coding: utf-8 -*-
"""P99: 周末无人值守自检 / 核查脚本。

检查项：
 1. p29 采集进度（done/todo、按类别命中数、最近 checkpoint）
 2. 规则总量与县级规则覆盖（键=6位区划代码）
 3. cc_parallel 门户命中是否回填进 rules（县法院/县检察院 u 值）
 4. data_js 拆分一致性（rulesFiles 数 == rules 数、文件存在）
 5. 名录 HTML 与 manifest 时间戳
 6. 采样验证：屏山县 511529 deptSwitch URL 完整性
输出：stdout 摘要 + 追加 weekend_report.md
"""
import json
import os
import time
from collections import Counter

DATA = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(DATA)
STAMP = time.strftime("%Y-%m-%d %H:%M:%S")

report = [f"\n## 自检 {STAMP}"]


def line(tag, ok, msg):
    mark = "✅" if ok else "❌"
    report.append(f"- {mark} **{tag}**: {msg}")
    print(f"{mark} {tag}: {msg}")


def main():
    problems = 0

    # ---- 1. p29 进度 ----
    sf = os.path.join(DATA, "weekend_state.json")
    cc_f = os.path.join(DATA, "cc_parallel.jsonl")
    done = rows = 0
    rows_cat = Counter()
    if os.path.exists(sf):
        st = json.load(open(sf, encoding="utf-8"))
        done = len(st.get("cc_parallel_done", []))
        rows = len(st.get("cc_parallel_rows", []))
        rows_cat = Counter(r["org_cat"] for r in st.get("cc_parallel_rows", []))
    cc_total = 0
    if os.path.exists(os.path.join(DATA, "city_county_final.jsonl")):
        cc_total = sum(1 for l in open(os.path.join(DATA, "city_county_final.jsonl"),
                                       encoding="utf-8")
                       if json.loads(l).get("portal_url"))
    todo = max(cc_total - done, 0)
    line("p29 进度", done > 0, f"已完成 {done}/{cc_total} 门户，命中 {rows} 条 "
        f"（{'、'.join(f'{k} {v}' for k, v in sorted(rows_cat.items()))}）")
    if done == 0:
        problems += 1
    # cc_parallel.jsonl 与 state 一致性
    jl_rows = 0
    if os.path.exists(cc_f):
        jl_rows = sum(1 for _ in open(cc_f, encoding="utf-8"))
    line("cc_parallel 一致性", jl_rows == rows, f"jsonl {jl_rows} 行 vs state {rows} 行")

    # ---- 2. 规则覆盖 ----
    rf = os.path.join(DATA, "extraction_rules.json")
    rules = json.load(open(rf, encoding="utf-8"))
    county_keys = [k for k in rules if k.isdigit() and len(k) == 6]
    line("规则总量", len(rules) > 6000, f"共 {len(rules)} 条，其中县级(6位码) {len(county_keys)} 条")

    # ---- 3. 门户回填检查 ----
    filled = 0
    for k in county_keys:
        r = rules[k]
        if any(d.get("u") and "法院" in d["n"] for d in r.get("depts", [])) \
                or any(d.get("u") and "检察院" in d["n"] for d in r.get("depts", [])):
            filled += 1
    line("县级法院/检察院回填", filled > 0,
        f"{filled}/{len(county_keys)} 个县已有法检独立门户 URL（随采集增长）")

    # ---- 4. data_js 一致性 ----
    mf = os.path.join(ROOT, "data_js", "manifest.js")
    src = open(mf, encoding="utf-8").read()
    i = src.find('"rulesFiles"')
    j = src.index("{", i)
    depth = 0
    end = None
    for k in range(j, len(src)):
        if src[k] == "{":
            depth += 1
        elif src[k] == "}":
            depth -= 1
            if depth == 0:
                end = k + 1
                break
    rfm = json.loads(src[j:end])
    missing = [k for k, v in rfm.items() if not os.path.exists(os.path.join(ROOT, "data_js", v))]
    line("data_js 拆分一致性", len(rfm) == len(rules) and not missing,
        f"rulesFiles {len(rfm)} 条（rules {len(rules)} 条），缺失文件 {len(missing)}")

    # ---- 5. HTML 时间戳 ----
    html_f = os.path.join(ROOT, "中国政府网站体系.html")
    if os.path.exists(html_f) and os.path.exists(mf):
        ok = os.path.getmtime(html_f) >= os.path.getmtime(mf)
        line("HTML 构建", ok,
            f"HTML {time.strftime('%m-%d %H:%M', time.localtime(os.path.getmtime(html_f)))}"
            f" >= manifest {time.strftime('%m-%d %H:%M', time.localtime(os.path.getmtime(mf)))}")
        if not ok:
            problems += 1

    # ---- 6. 屏山县采样 ----
    if "511529" in rules:
        r = rules["511529"]
        zw = next((d for d in r["depts"] if "政务服务" in d["n"]), None)
        ok = bool(zw and zw.get("u", "").find("areaCode=511529000000") >= 0)
        line("屏山县 511529 采样", ok,
            f"县直部门 deptSwitch URL: {zw['u'] if zw else '缺失'}")
        if not ok:
            problems += 1
        # 法检 URL 采样
        fj = [d for d in r["depts"] if "法院" in d["n"] or "检察院" in d["n"]]
        fj_filled = sum(1 for d in fj if d.get("u"))
        report.append(f"  - 屏山县法检: {fj_filled}/{len(fj)} 有独立门户 URL")

    # ---- 汇总 ----
    line("总体", problems == 0, f"问题项 {problems} 个")
    with open(os.path.join(DATA, "weekend_report.md"), "a", encoding="utf-8") as f:
        f.write("\n".join(report) + "\n")
    return problems


if __name__ == "__main__":
    raise SystemExit(main())
