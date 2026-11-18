# -*- coding: utf-8 -*-
"""p245 县级人民政府门户回填 + 连带修正（2026-11-18）。

背景：p240 全量 URL 身份核查判出 4 个县级人民政府门户为**跨地区串站**
（标题实测分别是张家口桥西区 / 阜新海州区 / 阳泉郊区 / 玉树州），已清除留名。
用户人工核实给出 4 个正确域名，本脚本按「块树 + registry」双写回填：

  河北省 石家庄市桥西区   http://www.sjzqx.gov.cn/   L2（石家庄市政府门户「县（市、区）
                                                    政府信息公开」真实 HTML + title「桥西区政府」）
  江苏省 连云港市海州区   http://www.lyghz.gov.cn/   L3（用户人工核实 + title「连云港海州区人民政府」）
  安徽省 铜陵市郊区       https://www.tljq.gov.cn/   L2（铜陵市政府门户首页「郊区」链接 +
                                                    title「郊区人民政府」/主办「铜陵市郊区人民政府办公室」）
  青海省 黄南州同仁市     http://www.hntongren.gov.cn L2（青海省政府门户 / 青海政务服务网 /
                                                    尖扎县门户 区县导航指向 + 用户人工核实）
      注：2026-11-18 实测该域名返回玉树藏族自治州站点内容（与 www.yushuzhou.gov.cn 同页、
      同备案 青ICP备2021000923号-1），疑平台域名路由异常；按用户人工核实登记，m 字段留痕待复核。

连带修正（同一批错配的孪生问题）：
- registry 三个裸地名键（县级人民政府|桥西区 / 郊区 / 海州区）存的是**另一城市的同名区**
  （张家口桥西区 / 阳泉郊区 / 阜新海州区），改名加城市前缀消歧，避免与本次回填互相覆盖；
- 连云港市海州区「县人民法院」= https://fxhz.lncourt.gov.cn 是**阜新海州区法院**（跨省错挂，
  p240 漏检），清除留名；
- extraction_rules 海州区（区划码 320706）portal 与 sources 误用阜新站，改为连云港海州区门户。

写前自动备份（backups/<日期>/），幂等可重跑。
"""
import datetime
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TODAY = datetime.date.today().isoformat()

sys.path.insert(0, HERE)
from site_contract import upsert_registry  # noqa: E402

FILLS = [
    dict(
        prov="河北省", city="石家庄市", county="桥西区",
        url="http://www.sjzqx.gov.cn/", level="L2", status="ok",
        src=("p245 回填: 石家庄市政府门户「县（市、区）政府信息公开」真实 HTML 提取 "
             "(L2) + title 实测「桥西区政府」+ 用户人工核实"),
    ),
    dict(
        prov="江苏省", city="连云港市", county="海州区",
        url="http://www.lyghz.gov.cn/", level="L3", status="ok",
        src="p245 回填: 用户人工核实 + title 实测「连云港海州区人民政府」(L3)",
    ),
    dict(
        prov="安徽省", city="铜陵市", county="郊区",
        url="https://www.tljq.gov.cn/", level="L2", status="ok",
        src=("p245 回填: 铜陵市政府门户首页「郊区」链接真实 HTML 提取 (L2) + "
             "title 实测「郊区人民政府」/主办「铜陵市郊区人民政府办公室」+ 用户人工核实"),
    ),
    dict(
        prov="青海省", city="黄南藏族自治州", county="同仁市",
        url="http://www.hntongren.gov.cn", level="L2", status="unknown",
        src=("p245 回填: 青海省政府门户 / 青海政务服务网 / 尖扎县门户 区县导航指向 (L2) "
             "+ 用户人工核实"),
        m=("2026-11-18 实测 www.hntongren.gov.cn 返回玉树藏族自治州站点内容"
           "（与 www.yushuzhou.gov.cn 同页、同备案 青ICP备2021000923号-1），"
           "疑平台域名路由异常；按用户人工核实登记，待复核。"),
    ),
]

# registry 裸地名键消歧：键 → (城市前缀)
RENAMES = {
    "县级人民政府|桥西区": "县级人民政府|张家口市桥西区",
    "县级人民政府|郊区": "县级人民政府|阳泉市郊区",
    "县级人民政府|海州区": "县级人民政府|阜新市海州区",
}

# 跨省错挂法院（阜新海州区法院挂到连云港海州区）
COURT_CLEAR = dict(prov="江苏省", city="连云港市", county="海州区")

RULE_FIX = {
    "code": "320706",
    "portal": "http://www.lyghz.gov.cn/",
    "bad": "https://www.fxhz.gov.cn/",
}


def find_county(tree, prov, city, county):
    """按路径后缀（省/市/县）定位块树节点，返回 (node, path_names)。"""
    def walk(node, path):
        for ch in node.get("ks") or []:
            p = path + [ch.get("n")]
            yield p, ch
            yield from walk(ch, p)
    for path, node in walk(tree, [tree.get("n")]):
        if len(path) >= 3 and path[-3:] == [prov, city, county]:
            return node, path
    return None, None


def find_child(node, keyword, exclude=()):
    """在节点子树里找名称含 keyword 的叶子（跨分组层）。"""
    def walk(n):
        for ch in n.get("ks") or []:
            yield ch
            yield from walk(ch)
    for ch in walk(node):
        n = ch.get("n") or ""
        if keyword in n and not any(x in n for x in exclude):
            return ch
    return None


def main():
    db = os.path.join(HERE, "backup_now.py")
    if os.path.exists(db) and "--no-backup" not in sys.argv:
        import subprocess
        subprocess.run([sys.executable, db], cwd=HERE, check=False)

    tree_path = os.path.join(HERE, "tree.json")
    reg_path = os.path.join(HERE, "site_registry.json")
    rules_path = os.path.join(HERE, "extraction_rules.json")

    tree = json.load(open(tree_path, encoding="utf-8"))
    reg = json.load(open(reg_path, encoding="utf-8"))
    rules = json.load(open(rules_path, encoding="utf-8"))

    # ---- 1. registry 裸地名键消歧（保住另一城市同名区的正确记录） ----
    for old, new in RENAMES.items():
        if old in reg and new not in reg:
            e = reg.pop(old)
            note = e.get("note") or ""
            e["note"] = (note + " | p245 同名区县键消歧: 本键原为裸地名，实为" +
                         new.split("|")[1].replace("县级人民政府|", "") +
                         "记录，改名加城市前缀").strip(" |")
            reg[new] = e
            print(f"[rename] {old} -> {new}")

    # ---- 2. 回填 4 个县级人民政府门户 ----
    for f in FILLS:
        key = f"县级人民政府|{f['county']}"
        # 优先用带城市前缀的严格键（裸键已消歧指向别的城市同名区）
        strict = f"县级人民政府|{f['city']}{f['county']}"
        use_key = strict if (strict in reg or key not in reg) else key
        node, path = find_county(tree, f["prov"], f["city"], f["county"])
        if node is None:
            print(f"[ERR] 树中未找到 {f['prov']}/{f['city']}/{f['county']}")
            continue
        node["u"] = f["url"]
        s = node.get("s") or ""
        if "p245 回填" not in s:
            node["s"] = (s + " | " if s else "") + f["src"]
        if f.get("m"):
            m = node.get("m") or ""
            if "hntongren.gov.cn 返回玉树" not in m:
                node["m"] = (m + " | " if m else "") + f["m"]
        upsert_registry(
            reg, use_key, f["url"], name=f["county"], source_level=f["level"],
            source=f["src"], verified_at=TODAY, status=f.get("status", "ok"),
            locations=("块",), note=f.get("m", ""),
        )
        print(f"[fill] {' / '.join(path)} -> {f['url']}  ({use_key})")

    # ---- 3. 错误法院清除（阜新海州区法院挂连云港海州区） ----
    node, path = find_county(tree, **COURT_CLEAR)
    if node is not None:
        court = find_child(node, "人民法院", exclude=("中级", "高级", "最高"))
        if court is not None and (court.get("u") or "").find("fxhz") >= 0:
            old = court["u"]
            court["u"] = ""
            s = court.get("s") or ""
            court["s"] = (s + " | " if s else "") + (
                f"p245 清除: {old} 为阜新市海州区法院（跨省错挂，p240 漏检），"
                "连云港海州区法院正确入口待补")
            print(f"[court] {court.get('n')} 清除 {old}")
    rk = "县级人民法院|江苏省海州区"
    if rk in reg and "fxhz" in (reg[rk].get("u") or ""):
        reg[rk]["u"] = ""
        reg[rk]["status"] = "cleared"
        reg[rk]["verified_at"] = TODAY
        reg[rk]["note"] = (reg[rk].get("note") or "") + \
            " | p245 清除: fxhz.lncourt.gov.cn 为阜新市海州区法院（跨省错挂）"
        print(f"[court-registry] {rk} 清除")

    # ---- 4. extraction_rules 海州区（320706）portal 修正 ----
    fixed = 0
    for k, v in rules.items():
        if not isinstance(v, dict):
            continue
        is_320706 = (k == RULE_FIX["code"] or k.startswith(RULE_FIX["code"] + "·")
                     or k.startswith("海州区·"))
        if not is_320706:
            continue
        if v.get("portal") == RULE_FIX["bad"]:
            v["portal"] = RULE_FIX["portal"]
            fixed += 1
        if isinstance(v.get("sources"), list):
            v["sources"] = [RULE_FIX["portal"] if x == RULE_FIX["bad"] else x
                            for x in v["sources"]]
        if isinstance(v.get("method"), str) and "海州区" in k:
            v["method"] = v["method"].replace(RULE_FIX["bad"], RULE_FIX["portal"])
        if isinstance(v.get("code"), str):
            v["code"] = v["code"].replace(RULE_FIX["bad"], RULE_FIX["portal"])
        print(f"[rule] {k} portal -> {v.get('portal')}")
    print(f"[rule] 修正 {fixed} 条 portal")

    json.dump(tree, open(tree_path, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    json.dump(reg, open(reg_path, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    json.dump(rules, open(rules_path, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("写入完成: tree.json / site_registry.json / extraction_rules.json")


if __name__ == "__main__":
    main()
