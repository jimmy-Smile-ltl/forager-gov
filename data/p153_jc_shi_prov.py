# -*- coding: utf-8 -*-
"""P153: 17 缺口省的省检察院官网「市州分院」导航提取市级院 URL。"""
import json, re, subprocess

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
need = json.load(open("/tmp/jc_prov_need.json", encoding="utf-8"))

tree = json.load(open("tree.json", encoding="utf-8"))
tiao = next(g for g in tree["ks"] if g["n"].startswith("条"))
jc = next(g for g in tiao["ks"] if g["n"].startswith("检察院系统"))
prov_jc = next(g for g in jc["ks"] if "省级检察院" in g["n"])

def fetch(u):
    try:
        r = subprocess.run(["curl", "-s", "--compressed", "-L", "--max-time", "15",
                            "-A", UA, u], capture_output=True, timeout=18)
        raw = r.stdout
        for enc in ("utf-8", "gb18030"):
            try:
                return raw.decode(enc)
            except UnicodeDecodeError:
                continue
        return raw.decode("utf-8", errors="replace")
    except Exception:
        return ""

results = {}
for pn, u in need.items():
    if not u:
        results[pn] = {}
        continue
    html = fetch(u)
    # 市级院链接：文本含「人民检察院/检察院」+ URL 含 jcy
    hits = {}
    for uu, txt in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>\s*([^<]{3,30}?)\s*</a>', html):
        t2 = txt.strip()
        if re.search(r'(人民检察院|检察)', t2) and uu.startswith("http"):
            m = re.match(r'^(.+?)(?:市|自治州|盟|地区)?(?:人民检察院|检察院)$', t2)
            if m:
                core = m.group(1)
                hits.setdefault(core, uu)
    results[pn] = hits
    print(f"{pn}: {len(hits)} 个市级链接", flush=True)
    for k, v in list(hits.items())[:16]:
        print(f"   {k} -> {v[:60]}", flush=True)

json.dump(results, open("/tmp/jc_prov_hits.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=0)
print(f"\np153 完成: {sum(len(v) for v in results.values())} 条")
