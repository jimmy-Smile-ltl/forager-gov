#!/usr/bin/env python
# p216 五系统审计裁决回灌 registry（2026-11-17）
# 背景: p210-p212 已把审计裁决落进 tree.json（82 个市节点替换/根化/清除），
#   但 site_registry.json 仍持有旧值（registry 是主数据，块条共用引用），
#   不同步会导致后续按 registry 回填时把已裁决的错误 URL 重新带回。
# 做法:
#   ① 用 p210 前快照 vs 当前 tree 抽取五系统市级节点 URL 差异
#   ② 按「旧 URL」在 registry 中定位条目（URL 归一匹配，忽略 scheme/尾斜杠）
#      替换 → u=新值 status=ok source_level 按来源；清除 → u="" status=cleared
#   ③ 已清除节点在 p204/p206 状态里种 cleared 标记，防止下轮循环重新采入
# 写前备份 registry 与 state。
import json, os, re, sys, shutil, time, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, "data")
TREE_F = os.path.join(D, "tree.json")
REG_F = os.path.join(D, "site_registry.json")
PRE_F = os.path.join(ROOT, "backups", "2026-11-17", "tree_before_p210_132830.json")
BAK_DIR = os.path.join(ROOT, "backups", "2026-11-17")
DRY = "--dry" in sys.argv
SYS = {"市人大", "市政协", "市中级人民法院", "市人民检察院", "市监委"}

# 旧 URL 不在 registry 的条目（键值形态不一致/无条目），按 key 定点修
# (key, 旧值需含的子串或 None, 新值或 "" 清空, 说明)
MANUAL = [
    ("人大|廊坊市人大", None, "",
     "mzfzw.net=民主法制网（媒体站，非人大官网）"),
    ("法院|市政协|长治市", "m.czszx.gov.cn", "https://www.czszx.gov.cn/",
     "同页 m 站 → 站点根, title=中国人民政治协商会议长治市委员会"),
    ("人大|塔城地区监委", None, "",
     "ccdi.gov.cn=中央纪委国家监委（上级域名，非塔城监委官网）"),
]
# 无条目但 tree 已有权威值 → 补登（类别沿用 p204 的五系统键约定）
INSERT = [
    ("法院|市监委|铜陵市",
     {"u": "http://www.tljw.gov.cn/", "n": "铜陵市市监委", "locations": ["块"],
      "source_level": "L1", "verified_at": "2026-11-17", "status": "ok", "snapshot": ""}),
]


def unorm(u):
    """URL 归一: 去空白/#、统一 scheme/host 小写、去尾斜杠"""
    u = (u or "").strip()
    if not u:
        return ""
    u = u.split("#")[0]
    m = re.match(r"^(https?)://([^/]+)(/.*)?$", u, re.I)
    if not m:
        return u.lower()
    sch, host, path = m.group(1).lower(), m.group(2).lower(), m.group(3) or "/"
    if path != "/" and path.endswith("/"):
        path = path[:-1]
    return f"{sch}://{host}{path}"


def ukey(u):
    """跨 scheme 匹配键: host+path"""
    x = unorm(u)
    return re.sub(r"^https?://", "", x) if x else ""


def walk(path):
    t = json.load(open(path, encoding="utf-8"))
    blk = next(g for g in t["ks"] if g.get("n", "").startswith("省级"))
    d = {}
    for p in blk.get("ks") or []:
        pn = p.get("n", "")
        for c in p.get("ks") or []:
            if c.get("c") not in ("地级市人民政府", "市辖区（地级行政区划）"):
                continue
            for jg in c.get("ks") or []:
                if jg.get("c") != "并列机关":
                    continue
                for o in jg.get("ks") or []:
                    if o.get("n") in SYS:
                        d[(pn, c.get("n"), o.get("n"))] = {
                            "u": (o.get("u") or "").strip(), "s": o.get("s") or ""}
    return d


def atomic(obj, path):
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
    with os.fdopen(fd, "w") as f:
        json.dump(obj, f, ensure_ascii=False)
    os.replace(tmp, path)


def level_of(s, old):
    if "来源:L1" in s:
        return "L1"
    if "SERP" in s:
        return "L3"
    if "L2" in s or "门户" in s:
        return "L2"
    return old or "L2"


def main():
    old = walk(PRE_F)
    new = walk(TREE_F)
    diffs = [(k, old[k], new[k]) for k in new
             if old.get(k, {}).get("u", "") != new[k]["u"]]
    print(f"树差异节点: {len(diffs)}")

    reg = json.load(open(REG_F, encoding="utf-8"))
    idx = {}
    for k, v in reg.items():
        x = ukey(v.get("u"))
        if x:
            idx.setdefault(x, []).append(k)

    stats = {"replace": 0, "clear": 0, "unmatched": 0}
    cleared_keys = []
    for key, ov, nv in diffs:
        ou, nu = ov["u"], nv["u"]
        hits = idx.get(ukey(ou), []) if ou else []
        if not hits:
            print(f"UNMATCHED {key[0]}|{key[1]}|{key[2]}\n    old: {ou or '(空)'}")
            stats["unmatched"] += 1
            continue
        for k in hits:
            e = reg[k]
            if nu:
                e["u"] = nu
                e["status"] = "ok"
                e["source_level"] = level_of(nv["s"], e.get("source_level"))
                e["verified_at"] = "2026-11-17"
                print(f"REPLACE [{k}] {ou[:60]} -> {nu[:60]}")
                stats["replace"] += 1
            else:
                e["u"] = ""
                e["status"] = "cleared"
                e["verified_at"] = "2026-11-17"
                print(f"CLEAR   [{k}] {ou[:70]}")
                stats["clear"] += 1
        if not nu:
            cleared_keys.append("|".join(key))

    # 定点修 + 补登
    for k, need, newv, note in MANUAL:
        e = reg.get(k)
        if not e:
            print(f"MANUAL-MISS [{k}] 条目不存在"); continue
        if need and need not in (e.get("u") or ""):
            print(f"MANUAL-SKIP [{k}] 当前值 {e.get('u','')[:60]} 不含 {need}"); continue
        oldv = e.get("u") or ""
        e["u"] = newv
        e["status"] = "ok" if newv else "cleared"
        e["verified_at"] = "2026-11-17"
        print(f"MANUAL  [{k}] {oldv[:60] or '(空)'} -> {newv or '(空)'}  ({note})")
        stats["replace" if newv else "clear"] += 1
    for k, e in INSERT:
        if k in reg and (reg[k].get("u") or "").strip():
            print(f"INSERT-SKIP [{k}] 已存在 {reg[k]['u'][:60]}"); continue
        reg[k] = e
        print(f"INSERT  [{k}] -> {e['u']}")
        stats["replace"] += 1

    print("\n统计:", stats)
    print("清除节点:", len(cleared_keys))
    if DRY:
        return

    os.makedirs(BAK_DIR, exist_ok=True)
    ts = time.strftime("%H%M%S")
    shutil.copy2(REG_F, os.path.join(BAK_DIR, f"registry_before_p216_{ts}.json"))
    atomic(reg, REG_F)
    print("registry 已同步")

    # ③ 已清除节点种 cleared 标记（p204/p206 的 done 键 = prov|city|system）
    for sf in ("p204_state.json", "p206_state.json"):
        f = os.path.join(D, sf)
        if not os.path.exists(f):
            continue
        st = json.load(open(f, encoding="utf-8"))
        done = st.setdefault("done", {})
        added = 0
        for k in cleared_keys:
            if not done.get(k):
                done[k] = "cleared:2026-11-17"
                added += 1
        if added:
            shutil.copy2(f, os.path.join(BAK_DIR, f"{sf[:-5]}_before_p216_{ts}.json"))
            atomic(st, f)
        print(f"{sf}: +{added} cleared 标记")


if __name__ == "__main__":
    main()
