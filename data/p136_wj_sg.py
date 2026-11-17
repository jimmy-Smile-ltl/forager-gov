# -*- coding: utf-8 -*-
"""P136: 外交部驻外机构全量提取（使馆 6 洲 + 总领馆 6 洲 + 团处）。"""
import json
import re
import subprocess

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")

PAGES = [
    ("驻外使馆", "yz", "https://www.fmprc.gov.cn/web/zwjg_674741/zwsg_674743/yz_674745/", "亚洲"),
    ("驻外使馆", "fz", "https://www.fmprc.gov.cn/web/zwjg_674741/zwsg_674743/fz_674747/", "非洲"),
    ("驻外使馆", "xo", "https://www.fmprc.gov.cn/web/zwjg_674741/zwsg_674743/xo_674749/", "欧洲"),
    ("驻外使馆", "xybf", "https://www.fmprc.gov.cn/web/zwjg_674741/zwsg_674743/xybf_674751/", "北美洲"),
    ("驻外使馆", "dozy", "https://www.fmprc.gov.cn/web/zwjg_674741/zwsg_674743/dozy_674753/", "南美洲"),
    ("驻外使馆", "bmdyz", "https://www.fmprc.gov.cn/web/zwjg_674741/zwsg_674743/bmdyz_674755/", "大洋洲"),
    ("驻外总领馆", "yz", "https://www.fmprc.gov.cn/web/zwjg_674741/zwzlg_674757/yz_674759/", "亚洲"),
    ("驻外总领馆", "fz", "https://www.fmprc.gov.cn/web/zwjg_674741/zwzlg_674757/fz_674761/", "非洲"),
    ("驻外总领馆", "xo", "https://www.fmprc.gov.cn/web/zwjg_674741/zwzlg_674757/xo_674763/", "欧洲"),
    ("驻外总领馆", "xybf", "https://www.fmprc.gov.cn/web/zwjg_674741/zwzlg_674757/xybf_674765/", "北美洲"),
    ("驻外总领馆", "dozy", "https://www.fmprc.gov.cn/web/zwjg_674741/zwzlg_674757/dozy_674767/", "南美洲"),
    ("驻外总领馆", "bmdyz", "https://www.fmprc.gov.cn/web/zwjg_674741/zwzlg_674757/bmdyz_674769/", "大洋洲"),
    ("驻外团处", "tuanchu", "https://www.fmprc.gov.cn/web/zwjg_674741/zwtc_674771/", "全部"),
]

rows = []
for cat, key, u, zhou in PAGES:
    try:
        r = subprocess.run(["curl", "-s", "--compressed", "-L", "--max-time", "15",
                            "-A", UA, u], capture_output=True, timeout=20)
        t = r.stdout.decode("utf-8", errors="replace")
        orgs = {}
        for uu, txt in re.findall(
                r'<a[^>]+href="([^"]+)"[^>]*>\s*([^<]{4,40}?)\s*</a>', t):
            t2 = txt.strip()
            if re.search(r'^(驻.+?(大使馆|总领事馆|领事馆|领事办公室|办事处|代表团|代表处|公署))$', t2) \
                    or re.search(r'^(常驻|中国驻)', t2):
                orgs.setdefault(t2, uu)
        print(f"{cat}/{zhou}: {len(orgs)} 个", flush=True)
        for nm, uu in orgs.items():
            rows.append({"cat": cat, "zhou": zhou, "name": nm, "url": uu})
    except Exception as e:
        print(f"{cat}/{zhou}: 失败 {str(e)[:40]}", flush=True)

with open("wj_zwjg.jsonl", "w", encoding="utf-8") as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
print(f"\np136 完成: {len(rows)} 个驻外机构")
