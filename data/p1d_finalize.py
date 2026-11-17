# -*- coding: utf-8 -*-
"""P1d: 中央/省级剩余站点最终落定（百度检索路径 + 挂靠母体 + 标准路径推断）。"""
import json

MANUAL = {
    "海关总署": ("http://www.customs.gov.cn/customs/302249/zfxxgk/", "百度检索路径"),
    "国家药品监督管理局": ("https://www.nmpa.gov.cn/zwgk/", "百度检索路径"),
    "国家消防救援局": ("https://www.119.gov.cn/xxgk/", "百度检索路径"),
    "湖北": ("https://www.hubei.gov.cn/zfxxgk/", "百度检索路径"),
    "甘肃": ("https://www.gansu.gov.cn/zfxxgk/", "国办标准路径推断，WAF待复核"),
}
# 加挂牌子/合署 → 母体专栏
PARENT_XXGK = {
    "国家语言文字工作委员会": "教育部",
    "国家航天局": "工业和信息化部",
    "国家原子能机构": "工业和信息化部",
}


def main():
    rows = [json.loads(l) for l in open("central.jsonl", encoding="utf-8")]
    by_name = {r["name"]: r for r in rows}
    # 先取母体 URL
    for child, parent in PARENT_XXGK.items():
        p = by_name.get(parent)
        if p and p.get("xxgk_url"):
            c = by_name[child]
            c["xxgk_url"] = p["xxgk_url"]
            c["xxgk_src"] = f"挂靠母体{parent}"
    for name, (url, src) in MANUAL.items():
        if name in by_name:
            by_name[name]["xxgk_url"] = url
            by_name[name]["xxgk_src"] = src
    with open("central.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # 省文件：湖北/甘肃
    rows = [json.loads(l) for l in open("province.jsonl", encoding="utf-8")]
    for r in rows:
        if r["name"] in MANUAL:
            r["xxgk_url"], r["xxgk_src"] = MANUAL[r["name"]]
    with open("province.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # 报告剩余
    miss = [r["name"] for r in json.loads(open("central.jsonl", encoding="utf-8").read().splitlines()[0] for _ in [0])] if False else []
    for fn in ("central.jsonl", "province.jsonl"):
        miss += [json.loads(l)["name"] for l in open(fn, encoding="utf-8") if not json.loads(l).get("xxgk_url")]
    print("剩余未命中:", miss)


if __name__ == "__main__":
    main()
