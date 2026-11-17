# -*- coding: utf-8 -*-
"""P42: 省级高院/检察院门户拼音模式补齐。

模式（实测）：
  法院：{s}fy.gov.cn、{s}court.gov.cn、cqfygzfw.gov.cn（渝）、hshfy.sh.cn（沪）
  检察院：{s}.jcy.gov.cn、{full}.jcy.gov.cn
每个命中做标题验证（法院/检察 + 省名），回填 tree 并列机关成员 + 规则。
"""
import json
import re
import subprocess
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")

# 省级法院/检察院已知例外域名
SPECIAL = {
    ("重庆市", "court"): ["cqfygzfw.gov.cn"],
    ("上海市", "court"): ["hshfy.sh.cn"],
}


def short_of(full):
    return re.sub(r"(维吾尔|壮族|回族)?自治区$|省$|市$", "", full)


def probe(dom):
    for scheme in ("https", "http"):
        u = f"{scheme}://www.{dom}/"
        try:
            r = subprocess.run(["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
                                "-L", "--max-time", "6", "-A", UA, u],
                               capture_output=True, text=True, timeout=10)
            code = r.stdout.strip()
            if code and code != "000":
                return u
        except Exception:
            pass
    return ""


def title_ok(url, pname, kind):
    try:
        import requests
        r = requests.get(url, headers={"User-Agent": UA}, timeout=12, verify=False)
        raw = r.content[:80000]
        m = re.search(rb'charset=["\']?\s*([a-zA-Z0-9_-]+)', raw[:2000])
        enc = (m.group(1).decode("ascii", "ignore") if m else (r.encoding or "")).lower()
        txt = raw.decode("gb18030", errors="replace") if (
            "gb" in enc or "iso-8859-1" in enc or not enc) \
            else raw.decode("utf-8", errors="replace")
        kw = "法院" if kind == "court" else "检察"
        if kw not in txt[:25000]:
            return False
        short = short_of(pname)
        if pname == "新疆生产建设兵团":
            short = "兵团"
        return short in txt[:25000]
    except Exception:
        return False


def main():
    tree = json.load(open("tree.json", encoding="utf-8"))
    prov_g = next(g for g in tree["ks"] if g["n"].startswith("省级"))
    rules = json.load(open("extraction_rules.json", encoding="utf-8"))
    filled = 0
    for p in prov_g["ks"]:
        par = next((k for k in p.get("ks", []) if k.get("c") == "并列机关"), None)
        if not par:
            continue
        pname = p["n"]
        short = short_of(pname)
        from pypinyin import lazy_pinyin
        full = "".join(lazy_pinyin(short))
        for m in par.get("ks", []):
            kind = "court" if "法院" in m["n"] else ("jcy" if "检察院" in m["n"] else "")
            if not kind or m.get("u"):
                continue
            pats = SPECIAL.get((pname, kind), [])
            if kind == "court":
                pats += [f"{short}fy.gov.cn", f"{short}court.gov.cn",
                         f"{full}fy.gov.cn", f"{full}court.gov.cn"]
            else:
                pats += [f"{short}.jcy.gov.cn", f"{full}.jcy.gov.cn",
                         f"{short}jcy.gov.cn"]
            url = ""
            for dom in pats:
                url = probe(dom)
                if url and title_ok(url, pname, kind):
                    break
                url = ""
            if url:
                m["u"] = url
                filled += 1
                # 成员规则同步
                mkey = f"{pname}·{m['n']}"
                if mkey in rules:
                    rules[mkey]["portal"] = url
                    rules[mkey]["sources"] = [url]
                    rules[mkey]["method"] = "独立门户（域名模式探测 + 标题验证）"
                print(f"  {pname} {m['n']} -> {url}", flush=True)
    json.dump(tree, open("tree.json", "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    json.dump(rules, open("extraction_rules.json", "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    print(f"p42 完成：回填 {filled} 个省级法检门户")


if __name__ == "__main__":
    main()
