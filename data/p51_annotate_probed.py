# -*- coding: utf-8 -*-
"""P51: 存量域名探测数据降级标注（配合「禁止猜测域名」铁律）。

对以下探测来源的规则 method 追加降级标注，待 HTML 名录页重采替换：
  1. 条系统成员规则（税务/邮政/烟草/人行 —— p46 拼音域名探测）
  2. 县级规则中由 p40 拼音探测回填的检察院 URL（在 method 末尾注明）
不删除数据，仅标注来源性质。
"""
import json

TAG = "（来源：域名探测，待官方 HTML 名录页提取替换）"
TIAO_KEYS = ("税务系统", "邮政系统", "烟草系统", "人民银行系统")


def main():
    rules = json.load(open("extraction_rules.json", encoding="utf-8"))
    n = 0
    for k, r in rules.items():
        if k.startswith(TIAO_KEYS):
            # 条系统成员/组规则
            if r.get("url") or r.get("portal"):
                if TAG not in (r.get("method") or ""):
                    r["method"] = (r.get("method") or "") + TAG
                    n += 1
        elif k.isdigit() and len(k) == 6:
            # 县级规则：检察院探测回填标注
            if any(d.get("u") and "检察院" in d["n"] for d in r.get("depts", [])):
                if TAG not in (r.get("method") or ""):
                    r["method"] = (r.get("method") or "") + \
                        "（其中县检察院 URL 部分来自拼音域名探测，待官方名录页替换）"
                    n += 1
    json.dump(rules, open("extraction_rules.json", "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    print(f"p51 完成：标注 {n} 条规则")


if __name__ == "__main__":
    main()
