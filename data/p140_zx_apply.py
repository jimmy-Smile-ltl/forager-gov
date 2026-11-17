# -*- coding: utf-8 -*-
"""P140: p139 提取结果落库（rd_zx.jsonl 更新 + 挂载 + rules）。"""
import json

def main():
    rows = [json.loads(l) for l in open("zx_all.jsonl", encoding="utf-8")]
    old = [json.loads(l) for l in open("rd_zx.jsonl", encoding="utf-8")]
    by_prov = {r["province"]: r["hits"] for r in rows}
    added = updated = 0
    for r in old:
        pn = r["province"]
        if pn in by_prov and r["name"] in by_prov[pn]:
            u = by_prov[pn][r["name"]]
            if not r["url"] and u:
                r["url"] = u
                r["listed"] = True
                added += 1
            elif r["url"] and u and r["url"] != u:
                r["url"] = u
                updated += 1
    with open("rd_zx.jsonl", "w", encoding="utf-8") as f:
        for r in old:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    n_u = sum(1 for r in old if r["listed"])
    print(f"p140: 新增 {added}，更新 {updated}，rd_zx 共 {len(old)} 条（{n_u} 有官网）")

if __name__ == "__main__":
    main()
