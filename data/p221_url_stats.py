#!/usr/bin/env python
# p221 URL 缺失率统计（省 / 市 / 县 × 系统）
"""按块视图统计机构官网 URL 缺失率，供文档与网站「数据健康」面板共用。

口径:
  - 范围: 块视图「省级」子树（31 省区市 + 新疆兵团 = 32 个省级单位）及其
    下辖市/县/直辖市辖区；民主党派省级组织挂在中央子树，单独补充统计。
  - 统计对象: 机构节点（不含「分组」容器）；缺失 = 树节点 u 为空（列名，
    不代表死链——死链状态由 registry 巡检 status 字段承载）。
  - 层级: l=省→省；l=市/地级区→市；l=县→县；l 缺失的「市级部门」按市计。
  - 系统: 政府门户(人民政府) / 政府部门(厅局·市局) / 人大 / 政协 /
    监委·纪委 / 法院 / 检察院 / 党委 / 群团 / 民主党派 / 其他。

产物:
  - data/url_stats.json   机器可读（p22 嵌入 data_js/quality.js 供面板消费）
  - data/URL_STATS.md     文档（随管线自动刷新，勿手工改数字）
用法: (cd data && uv run python p221_url_stats.py)
"""
import collections
import datetime
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
TREE_F = os.path.join(DATA, "tree.json")
OUT_JSON = os.path.join(DATA, "url_stats.json")
OUT_MD = os.path.join(DATA, "URL_STATS.md")

LEVELS = ["省", "市", "县"]
SYS_ORDER = [
    ("gov", "政府门户"),
    ("dept", "政府部门"),
    ("rd", "人大"),
    ("zx", "政协"),
    ("jw", "监委/纪委"),
    ("fy", "法院"),
    ("jcy", "检察院"),
    ("party", "党委"),
    ("qt", "群团"),
    ("mzdp", "民主党派"),
    ("other", "其他"),
]
SCOPE = ("块视图「省级」子树（31 省区市 + 新疆兵团 = 32 个单位）及其下辖市/县/"
         "直辖市辖区；民主党派省级组织取自中央子树。统计对象为机构节点"
         "（不含分组容器）；缺失 = 树中 u 为空（列名）。")


def _blank():
    return {"total": 0, "with_url": 0}


def level_of(n):
    lv = n.get("l")
    if lv == "省":
        return "省"
    if lv in ("市", "地级区"):
        return "市"
    if lv == "县":
        return "县"
    # 个别节点缺 l（如清远「市级部门」组下的部门）——按市级部门归到市
    if lv is None and n.get("k") == "市级部门":
        return "市"
    return None


def sys_of(n):
    k = n.get("k")
    name = n.get("n") or ""
    if k == "分组":
        return None
    if k in ("人民政府", "功能区"):
        return "gov"
    if k in ("部门", "政府部门", "市级部门"):
        return "dept"
    if k == "并列机关":
        if "人大" in name:
            return "rd"
        if "政协" in name:
            return "zx"
        if "监委" in name or "纪委" in name or "纪检" in name:
            return "jw"
        if "法院" in name:
            return "fy"
        if "检察院" in name:
            return "jcy"
        if "党委" in name or name in ("省委", "市委", "县委", "区委"):
            return "party"
        return "other"
    if k == "群团组织":
        return "qt"
    if k == "民主党派":
        return "mzdp"
    return None


def _finalize(rec):
    rec["missing"] = rec["total"] - rec["with_url"]
    rec["missing_rate"] = round(rec["missing"] / rec["total"] * 100, 2) if rec["total"] else 0.0
    return rec


def collect(tree):
    """返回统计字典（不落盘）。"""
    prov = next((g for g in tree.get("ks") or []
                 if (g.get("n") or "").startswith("省级")), None)
    raw = collections.defaultdict(_blank)

    def walk(n):
        lv, sy = level_of(n), sys_of(n)
        if lv and sy:
            rec = raw[(lv, sy)]
            rec["total"] += 1
            if (n.get("u") or "").strip():
                rec["with_url"] += 1
        for c in n.get("ks") or []:
            walk(c)

    if prov:
        walk(prov)

    # 民主党派省级组织（k=民主党派, l=省）挂在中央子树，单独补计
    def walk_mzdp(n):
        if n.get("k") == "民主党派" and n.get("l") == "省":
            rec = raw[("省", "mzdp")]
            rec["total"] += 1
            if (n.get("u") or "").strip():
                rec["with_url"] += 1
        for c in n.get("ks") or []:
            walk_mzdp(c)

    walk_mzdp(tree)

    levels = {}
    for lv in LEVELS:
        systems = {}
        for key, _label in SYS_ORDER:
            systems[key] = _finalize(dict(raw[(lv, key)]))
        total = {"total": sum(s["total"] for s in systems.values()),
                 "with_url": sum(s["with_url"] for s in systems.values())}
        total = _finalize(total)
        total["systems"] = systems
        levels[lv] = total

    systems_out = []
    for key, label in SYS_ORDER:
        per = {lv: levels[lv]["systems"][key] for lv in LEVELS}
        agg = {"total": sum(per[lv]["total"] for lv in LEVELS),
               "with_url": sum(per[lv]["with_url"] for lv in LEVELS)}
        agg = _finalize(agg)
        systems_out.append({"key": key, "label": label, "levels": per, "total": agg})

    overall = {"total": sum(levels[lv]["total"] for lv in LEVELS),
               "with_url": sum(levels[lv]["with_url"] for lv in LEVELS)}
    overall = _finalize(overall)

    return {
        "generated": datetime.date.today().isoformat(),
        "scope": SCOPE,
        "levels": levels,
        "systems": systems_out,
        "total": overall,
    }


def _num(n):
    return f"{n:,}"


def _pct(x):
    return f"{x:.2f}%"


def render_md(s):
    head = [
        "# URL 缺失率统计（省 / 市 / 县 × 系统）",
        "",
        f"> 自动生成：`data/p221_url_stats.py`（p22 管线调用） · 生成日期 {s['generated']}",
        f"> 口径：{s['scope']}",
        "> 缺失率 = 缺失数 ÷ 机构数；缺失仅表示树中无官网（u 为空，列名），",
        "> 不代表该官网已失效（死链状态见 registry 巡检 status）。",
        "",
        "## 一、分等级汇总",
        "",
        "| 等级 | 机构数 | 有官网 | 缺失 | 缺失率 |",
        "|---|---:|---:|---:|---:|",
    ]
    for lv in LEVELS:
        d = s["levels"][lv]
        head.append(f"| {lv}级 | {_num(d['total'])} | {_num(d['with_url'])} | "
                    f"{_num(d['missing'])} | **{_pct(d['missing_rate'])}** |")
    t = s["total"]
    head.append(f"| **合计** | **{_num(t['total'])}** | **{_num(t['with_url'])}** | "
                f"**{_num(t['missing'])}** | **{_pct(t['missing_rate'])}** |")

    lines = head + [
        "",
        "## 二、分系统 × 等级 缺失率矩阵",
        "",
        "| 系统 | 省级 | 市级 | 县级 | 合计 |",
        "|---|---:|---:|---:|---:|",
    ]

    def cell(d):
        return f"{_pct(d['missing_rate'])}（{_num(d['missing'])}/{_num(d['total'])}）" if d["total"] else "—"

    for row in s["systems"]:
        if not row["total"]["total"]:
            continue
        lines.append(f"| {row['label']} | {cell(row['levels']['省'])} | "
                     f"{cell(row['levels']['市'])} | {cell(row['levels']['县'])} | "
                     f"{cell(row['total'])} |")

    for i, lv in enumerate(LEVELS, start=3):
        lines += ["", f"## {('三','四','五')[i - 3]}、{lv}级明细", "",
                  "| 系统 | 机构数 | 有官网 | 缺失 | 缺失率 |",
                  "|---|---:|---:|---:|---:|"]
        for key, label in SYS_ORDER:
            d = s["levels"][lv]["systems"][key]
            if not d["total"]:
                continue
            lines.append(f"| {label} | {_num(d['total'])} | {_num(d['with_url'])} | "
                         f"{_num(d['missing'])} | {_pct(d['missing_rate'])} |")
        d = s["levels"][lv]
        lines.append(f"| **合计** | **{_num(d['total'])}** | **{_num(d['with_url'])}** | "
                     f"**{_num(d['missing'])}** | **{_pct(d['missing_rate'])}** |")

    lines += [
        "",
        "## 四、口径备注",
        "",
        "- **党委**：树中省委/市委/县委（区委）节点均未收录独立官网，缺失率 100%——",
        "  党委系统通常不单独设政府门户类网站，属于数据真相而非漏采。",
        "- **县级人大/政协/监委**：区县一级建站率天然偏低（多数无独立官网），",
        "  缺失以列名呈现，符合「无官网列名、零猜测」的采集纪律。",
        "- **政府部门**：省级为省政府组成部门/直属机构，市级为市级政府部门；",
        "  市级含直辖市辖区（地级区）的下设部门。",
        "- **民主党派**：省级组织（8 党派 × 各省）挂在中央子树，本统计单独补计；",
        "  市级民主党派组织不在省/市/县统计口径内。",
        "- **功能区/开发区**：按县级人民政府计入「政府门户」。",
        "",
        "---",
        "",
        "重新生成：`cd data && uv run python p221_url_stats.py`（p22 拆分管线会自动调用）。",
    ]
    return "\n".join(lines) + "\n"


def build_and_write(tree=None):
    """计算并落盘 json + md，返回统计字典（供 p22 嵌入 quality.js）。"""
    if tree is None:
        with open(TREE_F, encoding="utf-8") as f:
            tree = json.load(f)
    stats = collect(tree)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=1)
    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write(render_md(stats))
    return stats


def main():
    stats = build_and_write()
    print("URL 缺失率统计:")
    for lv in LEVELS:
        d = stats["levels"][lv]
        print(f"  {lv}: {d['with_url']}/{d['total']} 有官网, 缺失 {d['missing']} "
              f"({d['missing_rate']}%)")
    t = stats["total"]
    print(f"  合计: {t['with_url']}/{t['total']} 有官网, 缺失 {t['missing']} "
          f"({t['missing_rate']}%)")
    print(f"已写入: {OUT_JSON}")
    print(f"已写入: {OUT_MD}")


if __name__ == "__main__":
    main()
