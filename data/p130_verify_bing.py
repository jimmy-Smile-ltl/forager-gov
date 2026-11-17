# -*- coding: utf-8 -*-
"""P130: 702 条 bing 类市县门户合规重验。

SERP 直接采信的历史存量，现在回官方页面 HTML 验证 title 身份
（权威源第 4 档兜底）。通过者保留并留痕 how=bing搜索(已验证)；
不通过者列名。并发 8。
"""
import json
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")

rows = [json.loads(l) for l in open("city_county_final.jsonl", encoding="utf-8")]
to_verify = [r for r in rows if "bing" in r.get("how", "").lower() and r.get("portal_url")]
print(f"待验证: {len(to_verify)} 条")

def verify(r):
    u = r["portal_url"]
    name = r["name"]
    core = re.sub(r"(自治州|自治县|地区|盟|市|区|县)$", "", name)
    # 民族名清理
    core = re.sub(r"(维吾尔|壮族|回族|蒙古族|藏族|土家族|苗族|彝族|朝鲜族|满族|白族|侗族|瑶族|布依族|哈尼族|傣族|黎族|傈僳族|佤族|畲族|拉祜族|水族|东乡族|纳西族|景颇族|柯尔克孜族|土族|达斡尔族|仫佬族|羌族|布朗族|撒拉族|毛南族|仡佬族|锡伯族|阿昌族|普米族|塔吉克族|怒族|乌孜别克族|俄罗斯族|鄂温克族|德昂族|保安族|裕固族|京族|塔塔尔族|独龙族|鄂伦春族|赫哲族|门巴族|珞巴族|基诺族|哈萨克族)+$", "", core)
    if len(core) < 2:
        core = name[:2]
    try:
        r2 = subprocess.run(["curl", "-s", "--compressed", "-L", "--max-time", "10",
                             "-A", UA, u], capture_output=True, timeout=14)
        raw = r2.stdout
        t = None
        for enc in ("utf-8", "gb18030"):
            try:
                t = raw.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        if t is None:
            t = raw.decode("utf-8", errors="replace")
        m = re.search(r"<title>([^<]*)</title>", t)
        title = m.group(1).strip() if m else ""
        ok = (core in title and ("政府" in title or "人民政府" in title)) \
             or name in title
        return r, ok, title[:40]
    except Exception as e:
        return r, None, str(e)[:30]

ok_list, fail_list, unknown = [], [], []
with ThreadPoolExecutor(max_workers=8) as ex:
    futs = {ex.submit(verify, r): r for r in to_verify}
    for f in as_completed(futs):
        r, ok, title = f.result()
        if ok is True:
            r["how"] = r.get("how", "") + "(已验证)"
            ok_list.append(r)
        elif ok is False:
            r["portal_url"] = ""
            r["how"] = r.get("how", "") + "(验证失败已列名)"
            fail_list.append(r)
        else:
            unknown.append(r)

# 写回
by_code = {r["code"]: r for r in rows}
for r in ok_list + fail_list + unknown:
    by_code[r["code"]] = r
with open("city_county_final.jsonl", "w", encoding="utf-8") as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
print(f"验证通过: {len(ok_list)}，失败列名: {len(fail_list)}，无法验证: {len(unknown)}")

# 树同步
tree = json.load(open("tree.json", encoding="utf-8"))
prov = next(g for g in tree["ks"] if g["n"].startswith("省级"))
fail_names = {(r["province"], r["name"]) for r in fail_list + unknown}
cleared = 0
for p in prov["ks"]:
    pn = p["n"]
    for top in p.get("ks", []):
        def walk(n):
            global cleared
            if n.get("k") == "人民政府" and n.get("l") in ("市", "县", "地级区") \
                    and (pn, n["n"]) in fail_names and n.get("u"):
                n["u"] = ""
                cleared += 1
            for k in n.get("ks", []):
                walk(k)
        walk(top)
json.dump(tree, open("tree.json", "w", encoding="utf-8"),
          ensure_ascii=False, separators=(",", ":"))
print(f"树清除: {cleared}")
