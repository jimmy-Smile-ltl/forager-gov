#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""p225 法院条树县级 URL 治理（2026-11-17）。

p197 在 32 高院官网「辖区法院」下拉提取基层法院时有三个系统性缺陷，
导致条树里出现错误/重复/垃圾叶子，进而被 p224 同步进块树：

  1. 垃圾：高院下拉里夹带「最高人民法院」「山西省高级人民法院」等选项，
     被 p197 当成基层法院叶子挂到各中院下（u=court.gov.cn / 省高院域名）。
  2. 特殊法院误挂：大连海事法院、太原铁路中院、怀铁法院等下挂了全省
     普通县区法院（高院页是全省平铺列表，p197 归位时 city_map 冲突）。
  3. 重名县区串市：`city_map[base]` 单值字典，同名县区（新华区=石家庄/
     沧州、鼓楼区=南京/徐州…）后者覆盖前者，出现「沧州新华区法院」挂
     石家庄 URL 的错配。

本脚本只做「清理 + 用高院页重新认领」，不发明任何 URL：

  A 删垃圾叶子（最高法/高院，根域 court.gov.cn）
  B 删特殊法院下的普通县区叶子（海事/铁路/森林/知产/兵团/矿区/林区）
  C 同中院内同名同 URL 的重复节点合并（保留全称「人民法院」那个）
  D 跨中院重复 URL：按省高院页候选名（支持「沧州新华法院」城市前缀
    形态）为每个城市认领各自的 URL；认领不到且 URL 已被他市认领的
    叶子删除；空 URL 且能唯一认领的叶子顺手补全（L1 权威来源）

用法：
  cd data && uv run python p225_court_cleanup.py --dry   # 只看统计
  cd data && uv run python p225_court_cleanup.py         # 写库（自动备份）
"""
import datetime
import json
import os
import re
import shutil
import sys
import base64
from urllib.parse import urljoin

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BASE_DIR)
sys.path.insert(0, BASE_DIR)
from site_contract import base as _base, upsert_registry  # noqa: E402
from p223_county_5sys_fill import unwrap  # noqa: E402

TREE_F = os.path.join(BASE_DIR, "tree.json")
REG_F = os.path.join(BASE_DIR, "site_registry.json")
TODAY = datetime.date.today().isoformat()
DRY = "--dry" in sys.argv

SPECIAL = re.compile(r"铁路|海事|森林|知识产权|知产|兵团|矿区|林区|军事")
JUNK = re.compile(r"高级人民法院|最高人民法院|^高院$")


def b(nm):
    """地名基底（复用 site_contract，剥 高级/中级 等中院前缀）。"""
    x = _base(nm or "")
    for _ in range(4):
        x0 = x
        for suf in ("高级人民", "高级", "中级人民", "中级", "人民", "省", "市"):
            if x.endswith(suf) and len(x) > len(suf):
                x = x[:-len(suf)]
                break
        if x == x0:
            break
    return x


def nu(u):
    u = (u or "").strip().rstrip("/")
    m = re.match(r"(https?://[^/]+)(/.*)?$", u, re.I)
    return (m.group(1).lower() + (m.group(2) or "")) if m else u


# ── 网络：curl_cffi，隧道代理失败自动直连 ──
def _get(u):
    try:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(ROOT, ".env"))
    except Exception:
        pass
    from curl_cffi import requests as creq
    px = os.getenv("TUNNEL_PROXY")
    for p in (px, None):
        try:
            s = creq.Session(impersonate="chrome124")
            kw = {"proxies": {"http": p, "https": p}} if p else {}
            r = s.get(u, timeout=20, verify=False, **kw)
            if r.status_code == 200 and len(r.text) > 500:
                return r.text
        except Exception:
            continue
    return ""


def _dec(h):
    if "elink.chinacourt.cn" in h:
        m = re.search(r"elid=([^&\s\"']+)", h)
        if m:
            e = m.group(1)
            if e.startswith(("http://", "https://")):
                return e
            try:
                return base64.urlsafe_b64decode(e + "==").decode()
            except Exception:
                pass
    return h


def court_links(page_url, html):
    """高院页 → [(名称, URL)]（a + option 双通道，保留重名条目）。"""
    out = []
    for m in re.finditer(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html, re.S):
        t = re.sub(r"<[^>]+>", "", m.group(2))
        t = re.sub(r"\s+", "", t)
        t = re.sub(r"^\|*-+", "", t)
        if not t or len(t) > 20 or "中级" in t or "高级" in t or "最高" in t:
            continue
        if t.endswith(("法院", "法庭")):
            u = _dec(urljoin(page_url, m.group(1)))
            if u.startswith(("http://", "https://")):
                out.append((t, u))
    for m in re.finditer(r'<option[^>]*value\s*=\s*["\']([^"\']+)["\'][^>]*>\s*([^<]{2,24}?)\s*</option>', html):
        t = re.sub(r"\s+", "", m.group(2))
        t = re.sub(r"^\|*-+", "", t)
        if not t.endswith(("人民法院", "法院", "法庭")) or len(t) > 20:
            continue
        if "中级" in t or "高级" in t or "最高" in t:
            continue
        u = _dec(urljoin(page_url, m.group(1)))
        if u.startswith("http"):
            out.append((t, u))
    return out


def collect_city_counties(blk):
    """块树 → {省名: {市基底: {县基底,...}}}。"""
    out = {}
    for prov in blk.get("ks") or []:
        pn = b(prov.get("n", ""))
        d = out.setdefault(pn, {})

        def walk_city(n, city, city_b):
            if n.get("k") == "人民政府" and n.get("l") in ("市", "地级区"):
                city, city_b = n.get("n"), b(n.get("n"))
            counties = set()
            for c in n.get("ks") or []:
                if c.get("k") == "人民政府" and c.get("n") != city:
                    counties.add(b(c.get("n")))
                yield from walk_city(c, city, city_b)
            if city and counties:
                yield (city_b, counties)

        for city_b, cs in walk_city(prov, None, None):
            if city_b:
                d.setdefault(city_b, set()).update(cs)
    return out


def main():
    tree = json.load(open(TREE_F, encoding="utf-8"))
    reg = json.load(open(REG_F, encoding="utf-8"))
    blk = next(g for g in tree["ks"] if g["n"].startswith("省级"))
    tiao = next(g for g in tree["ks"] if g["n"].startswith("条"))
    fy = next(s for s in tiao["ks"] if s["n"].startswith("法院系统"))

    # 市基底 → {县基底}（按省隔离，防同名城市跨省串台）
    county_of_all = collect_city_counties(blk)

    stat = {"junk": 0, "special": 0, "dup_same_mid": 0, "fixed": 0,
            "deleted_bogus": 0, "filled": 0, "urgent": 0}
    samples = []

    for hold in fy.get("ks") or []:
        for prov in (hold.get("ks") or []):
            county_of = county_of_all.get(b(prov.get("n", "")), {})
            mids = [m for m in (prov.get("ks") or [])]
            if not mids:
                continue
            # 全省 URL 使用计数：特殊法院下的县区叶子只在「该 URL 已被普通
            # 中院持有」时才删（防误删唯一副本）
            prov_use = {}
            for m in mids:
                for l in m.get("ks") or []:
                    uu = nu(unwrap((l.get("u") or "").strip()))
                    if uu:
                        prov_use[uu] = prov_use.get(uu, 0) + 1
            # ── A/B/C：单中院内部清理 ──
            for mid in mids:
                kids = mid.get("ks") or []
                if not kids:
                    continue
                new_kids = []
                seen = {}
                for leaf in kids:
                    nm = leaf.get("n", "")
                    u = unwrap((leaf.get("u") or "").strip())
                    # A 垃圾叶子
                    if JUNK.search(nm) or re.match(r"https?://(www\.)?court\.gov\.cn/?$", u, re.I) \
                            or (prov.get("u") and nu(u) == nu(prov.get("u")) and len(b(nm)) <= 4):
                        stat["junk"] += 1
                        if stat["junk"] <= 12:
                            samples.append(f"JUNK {prov.get('n')}/{mid.get('n')}/{nm} {u[:50]}")
                        continue
                    # B 特殊法院下挂普通县区法院（仅当 URL 已被他处持有）
                    if SPECIAL.search(mid.get("n", "")) and not SPECIAL.search(nm) \
                            and (not u or prov_use.get(nu(u), 0) > 1):
                        stat["special"] += 1
                        continue
                    # C 同院同名同 URL 重复
                    key = (b(nm), nu(u))
                    if u and key in seen:
                        keep = seen[key]
                        if len(nm) > len(keep.get("n", "")) and nm.endswith("人民法院"):
                            new_kids[new_kids.index(keep)] = leaf
                            seen[key] = leaf
                        stat["dup_same_mid"] += 1
                        continue
                    if u:
                        seen[key] = leaf
                    new_kids.append(leaf)
                mid["ks"] = new_kids

            # ── D：跨中院重复 URL 认领 ──
            url_owner = {}
            for mid in mids:
                for leaf in mid.get("ks") or []:
                    u = nu(unwrap((leaf.get("u") or "").strip()))
                    if u:
                        url_owner.setdefault(u, []).append((mid, leaf))
            dups = {u: v for u, v in url_owner.items() if len({m["n"] for m, _ in v}) > 1}
            if not dups and not any(not (l.get("u") or "").strip()
                                    for m in mids for l in (m.get("ks") or [])):
                continue

            # 高院页候选 → 认领表 {(市基底, 县基底): url}
            page = _get(prov.get("u") or "") if prov.get("u") else ""
            claim = {}
            if page:
                links = court_links(prov["u"], page)
                # ① 城市前缀候选优先（「沧州新华法院」= 沧州的新华区法院）
                for nm, u in links:
                    cb = b(nm)
                    if not cb:
                        continue
                    for city_b, counties in county_of.items():
                        if cb.startswith(city_b) and cb[len(city_b):] in counties:
                            claim[(city_b, cb[len(city_b):])] = u
                # ② 裸县名候选只认领省内唯一的县基底（重名县不猜）
                cnt = {}
                for city_b, counties in county_of.items():
                    for c in counties:
                        cnt[c] = cnt.get(c, 0) + 1
                for nm, u in links:
                    cb = b(nm)
                    if not cb or cnt.get(cb, 0) != 1:
                        continue
                    for city_b, counties in county_of.items():
                        if cb in counties:
                            claim.setdefault((city_b, cb), u)
            for u, owners in dups.items():
                for mid, leaf in owners:
                    cb = b(mid.get("n"))
                    lb = b(leaf.get("n"))
                    want = claim.get((cb, lb))
                    owner_city = None
                    for other_mid, other_leaf in owners:
                        oc = b(other_mid.get("n"))
                        if claim.get((oc, b(other_leaf.get("n")))) and \
                                nu(claim[(oc, b(other_leaf.get("n")))]) == u:
                            owner_city = oc
                    if want and nu(want) != u:
                        leaf["u"] = want
                        leaf["s"] = "来源：省高院官网辖区法院区块（p225 重认领）"
                        stat["fixed"] += 1
                        if len(samples) < 30:
                            samples.append(f"FIX {prov.get('n')}/{mid.get('n')}/{leaf.get('n')} -> {want[:60]}")
                    elif owner_city and owner_city != cb:
                        stat["deleted_bogus"] += 1
                        if len(samples) < 30:
                            samples.append(f"DEL {prov.get('n')}/{mid.get('n')}/{leaf.get('n')}（URL 属 {owner_city}）")
                        mid["ks"].remove(leaf)
                    else:
                        stat["urgent"] += 1
                        if stat["urgent"] <= 12:
                            samples.append(
                                f"URG {prov.get('n')}/{mid.get('n')}/{leaf.get('n')} {u[-45:]}")

            # 空 URL 唯一认领补全
            for mid in mids:
                cb = b(mid.get("n"))
                for leaf in mid.get("ks") or []:
                    if (leaf.get("u") or "").strip():
                        continue
                    want = claim.get((cb, b(leaf.get("n"))))
                    if not want:
                        continue
                    # 该 URL 不能被本省其他中院认领（防串市）
                    clash = [k for k, v in claim.items() if nu(v) == nu(want) and k[0] != cb]
                    if clash:
                        continue
                    leaf["u"] = want
                    leaf["s"] = "来源：省高院官网辖区法院区块（p225 认领）"
                    stat["filled"] += 1
                    if not DRY:
                        key = f"县级人民法院|{leaf.get('n')}"
                        upsert_registry(reg, key, want, name=leaf.get("n"),
                                        source_level="L1", source=leaf["s"],
                                        verified_at=TODAY, locations=["条"])
                    if len(samples) < 40:
                        samples.append(f"NUE {prov.get('n')}/{mid.get('n')}/{leaf.get('n')} -> {want[:60]}")

    for s in samples:
        print(" ", s)
    print("p225 法院条树治理:", ", ".join(f"{k}={v}" for k, v in stat.items()),
          "（DRY 未写库）" if DRY else "")

    if not DRY and (stat["filled"] or stat["fixed"] or stat["junk"] or stat["special"]
                    or stat["dup_same_mid"] or stat["deleted_bogus"]):
        d = os.path.join(ROOT, "backups", TODAY)
        os.makedirs(d, exist_ok=True)
        ts = datetime.datetime.now().strftime("%H%M%S")
        shutil.copy2(TREE_F, os.path.join(d, f"tree_before_p225_{ts}.json"))
        shutil.copy2(REG_F, os.path.join(d, f"registry_before_p225_{ts}.json"))
        json.dump(tree, open(TREE_F, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        json.dump(reg, open(REG_F, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("  已写 tree.json / site_registry.json")


if __name__ == "__main__":
    main()
