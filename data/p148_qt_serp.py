# -*- coding: utf-8 -*-
"""P148: 科协/记协/台联/计生协/欧美同学会 省级组织——SERP+title 验证。"""
import json
import re
import subprocess
import time

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")

SHORTS = ["北京", "天津", "河北", "山西", "内蒙古", "辽宁", "吉林", "黑龙江",
          "上海", "江苏", "浙江", "安徽", "福建", "江西", "山东", "河南",
          "湖北", "湖南", "广东", "广西", "海南", "重庆", "四川", "贵州",
          "云南", "西藏", "陕西", "甘肃", "青海", "宁夏", "新疆"]
SHORT2FULL = {"北京": "北京市", "天津": "天津市", "河北": "河北省",
              "山西": "山西省", "内蒙古": "内蒙古自治区", "辽宁": "辽宁省",
              "吉林": "吉林省", "黑龙江": "黑龙江省", "上海": "上海市",
              "江苏": "江苏省", "浙江": "浙江省", "安徽": "安徽省",
              "福建": "福建省", "江西": "江西省", "山东": "山东省",
              "河南": "河南省", "湖北": "湖北省", "湖南": "湖南省",
              "广东": "广东省", "广西": "广西壮族自治区", "海南": "海南省",
              "重庆": "重庆市", "四川": "四川省", "贵州": "贵州省",
              "云南": "云南省", "西藏": "西藏自治区", "陕西": "陕西省",
              "甘肃": "甘肃省", "青海": "青海省", "宁夏": "宁夏回族自治区",
              "新疆": "新疆维吾尔自治区"}
ORG_QUERY = {
    "科协": ("科学技术协会", "科协"),
    "记协": ("新闻工作者协会", "记协"),
    "台联": ("台湾同胞联谊会", "台联"),
    "计生协": ("计划生育协会", "计生协"),
    "欧美同学会": ("欧美同学会", "欧美同学会"),
}

results = {}
for org, (full_name, short_name) in ORG_QUERY.items():
    results[org] = {}
    for short in SHORTS:
        q = f"{short}{full_name}"
        try:
            r = subprocess.run(["curl", "-s", "--compressed", "--max-time", "12",
                                "-A", UA, "https://www.baidu.com/s?wd=" + q],
                               capture_output=True, timeout=15)
            t = r.stdout.decode("utf-8", errors="replace")
            cands = re.findall(r'mu="([^"]+)"', t)
            hit = None
            for u in cands[:6]:
                if not u or not u.startswith("http") or "baidu" in u or "baike" in u or "weibo" in u:
                    continue
                try:
                    r2 = subprocess.run(["curl", "-s", "--compressed", "-L", "--max-time", "9",
                                         "-A", UA, u], capture_output=True, timeout=13)
                    raw = r2.stdout
                    tt = None
                    for enc in ("utf-8", "gb18030"):
                        try:
                            tt = raw.decode(enc)
                            break
                        except UnicodeDecodeError:
                            continue
                    if tt is None:
                        tt = raw.decode("utf-8", errors="replace")
                    m = re.search(r"<title>([^<]*)</title>", tt)
                    title = m.group(1).strip() if m else ""
                    if short in title and (short_name in title or full_name[:2] in title):
                        hit = u
                        break
                except Exception:
                    pass
                time.sleep(0.35)
            results[org][SHORT2FULL[short]] = hit or ""
            if hit:
                print(f"✓ {org} {short}", flush=True)
        except Exception:
            results[org][SHORT2FULL[short]] = ""
        time.sleep(0.9)

json.dump(results, open("/tmp/qt_serp.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=0)
for org, d in results.items():
    n = sum(1 for v in d.values() if v)
    print(f"{org}: {n}/31")
