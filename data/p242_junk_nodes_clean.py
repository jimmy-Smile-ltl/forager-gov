"""p242 —— 清理「市级政府部门」组里的非部门垃圾节点。

p240 全量核查把一批**根本不是本级部门**的节点清空了 URL（身份不符），但节点
本身还挂在树里、在站点「部门」列表里显示为一行空名目。它们全部来自市门户
「部门导航」区的误抓：

  · 两会专题（2026年全国两会 / 全国两会）——中国政府网专题页
  · 中联办——中央人民政府驻香港特别行政区联络办公室
  · 建设部——住房和城乡建设部
  · XX省人民政府网站——省门户被挂在市级部门组（自贡/绵阳/广安/资阳/保山/普洱）
  · 宁远县人民政府网站——县政府门户被挂在永州市部门组

处理：树里删掉这些节点（k=政府部门 且名字命中），registry 同步删除对应键
（只删名字确实属于这批垃圾的键，不碰任何真部门）。写前备份，默认 dry-run。

用法（在 data/ 目录）：
    uv run python p242_junk_nodes_clean.py            # 列出将删除的节点/键
    uv run python p242_junk_nodes_clean.py --apply    # 落库（写前备份）
"""
import datetime
import json
import os
import re
import shutil
import sys
import tempfile

DATA = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(DATA)
TREE_F = os.path.join(DATA, "tree.json")
REG_F = os.path.join(DATA, "site_registry.json")
TODAY = datetime.date.today().isoformat()
APPLY = "--apply" in sys.argv

# 与 p241 同一口径（两会/中联办/省门户冒充部门/建设部）
JUNK = re.compile(r"(两会|中联办|人民政府网站?$|^建设部$)")


def is_junk_node(n):
    return ((n.get("k") or "") == "政府部门"
            and bool(JUNK.search((n.get("n") or "").strip())))


def atomic(obj, path):
    d = os.path.dirname(path)
    fd, tmp = tempfile.mkstemp(dir=d, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=1)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def main():
    tree = json.load(open(TREE_F, encoding="utf-8"))
    reg = json.load(open(REG_F, encoding="utf-8"))
    removed = []

    def walk(n, path):
        keep = []
        for c in n.get("ks") or []:
            nm = (c.get("n") or "").strip()
            if is_junk_node(c):
                removed.append({"path": path + [nm], "u": c.get("u") or "",
                                "s": (c.get("s") or "")[-70:]})
                continue
            walk(c, path + [nm])
            keep.append(c)
        if len(keep) != len(n.get("ks") or []):
            n["ks"] = keep

    for g in tree["ks"]:
        walk(g, [(g.get("n") or "")])
    # walk 里根节点自身的名字已放进 path；重算展示用的路径（去掉根部）
    for r in removed:
        r["path"] = r["path"][1:]

    names = {(r["path"][-1]) for r in removed}
    reg_del = [k for k, v in reg.items()
               if k.split("|")[0].endswith("部门")
               and (v.get("n") or k.split("|")[-1]).strip() in names]

    print(f"垃圾节点 {len(removed)} 个 / registry 键 {len(reg_del)} 个")
    for r in removed:
        print(f"  - {'/'.join(r['path'][-3:]):<30} {r['u'][:50]}")
    for k in reg_del:
        print(f"  reg - {k}")

    if not APPLY:
        print("\n（dry-run，未写库；加 --apply 落库）")
        return
    if not removed and not reg_del:
        return
    d = os.path.join(ROOT, "backups", TODAY)
    os.makedirs(d, exist_ok=True)
    ts = datetime.datetime.now().strftime("%H%M%S")
    shutil.copy2(TREE_F, os.path.join(d, f"tree_before_p242_{ts}.json"))
    shutil.copy2(REG_F, os.path.join(d, f"registry_before_p242_{ts}.json"))
    for k in reg_del:
        reg.pop(k, None)
    atomic(tree, TREE_F)
    atomic(reg, REG_F)
    print(f"\n已落库：删节点 {len(removed)} / 删 registry 键 {len(reg_del)}")


if __name__ == "__main__":
    main()
