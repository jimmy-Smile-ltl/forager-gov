# -*- coding: utf-8 -*-
"""p1c: WAF 站点多指纹重试 + 本地导航解析，输出命中结果。"""
import json
import sys

sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
from common import find_xxgk_url, norm_url

IMPERSONATES = ["chrome124", "chrome110", "chrome120", "safari17_0", "edge101", "chrome"]

TARGETS = [
    ("国防部", "http://www.mod.gov.cn/"),
    ("国家卫生健康委员会", "http://www.nhc.gov.cn/"),
    ("海关总署", "http://www.customs.gov.cn/"),
    ("国家金融监督管理总局", "https://www.nfra.gov.cn/"),
    ("国家国际发展合作署", "http://www.cidca.gov.cn/"),
    ("国家认证认可监督管理委员会", "http://www.cnca.gov.cn/"),
    ("国家宗教事务局", "https://www.sara.gov.cn/"),
    ("国务院港澳事务办公室", "https://www.hmo.gov.cn/"),
    ("国家互联网信息办公室", "http://www.cac.gov.cn/"),
    ("国务院新闻办公室", "http://www.scio.gov.cn/index.htm"),
    ("中国工程院", "https://www.cae.cn/"),
    ("国家数据局", "https://www.nda.gov.cn/"),
    ("国家航天局", "http://www.cnsa.gov.cn/"),
    ("国家原子能机构", "http://www.caea.gov.cn/"),
    ("国家消防救援局", "https://www.119.gov.cn/"),
    ("国家药品监督管理局", "https://www.nmpa.gov.cn/"),
    ("湖北", "http://www.hubei.gov.cn/"),
    ("甘肃", "http://www.gansu.gov.cn/"),
]


def try_fetch(url):
    from curl_cffi import requests as creq
    for imp in IMPERSONATES:
        try:
            resp = creq.get(url, timeout=15, impersonate=imp, verify=False)
            if resp.status_code == 200 and len(resp.content) > 2000:
                for enc in ("utf-8", "gb18030"):
                    try:
                        return resp.content.decode(enc)
                    except UnicodeDecodeError:
                        continue
                return resp.content.decode("utf-8", errors="replace")
        except Exception:
            continue
    # httpx 兜底
    from common import fetch_text
    return fetch_text(url)


def main():
    results = {}
    for name, url in TARGETS:
        html = try_fetch(url)
        if not html:
            print(f"{name}: FETCH FAIL")
            continue
        found = find_xxgk_url(html, url)
        if found:
            print(f"{name}: {found}")
            results[name] = found
        else:
            print(f"{name}: home ok, no xxgk link")
    json.dump(results, open("p1c_hits.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0)


if __name__ == "__main__":
    main()
