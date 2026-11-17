# -*- coding: utf-8 -*-
"""P1b: 修复 P1 未命中的信息公开 URL（v2 链接识别 + 多路径探测 + 多指纹重试）。"""
import json
import sys
from urllib.parse import urlparse

sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
from common import fetch, curl_fetch_text, find_xxgk_url, probe_xxgk_paths, norm_url

# 已知站点直接路径（探测均失败时的手工兜底，来自公开网站导航）
MANUAL = {
    "公安部": "https://app.mps.gov.cn/gdnps/pc/content.jsp?id=7477058",
    "国家卫生健康委员会": "http://www.nhc.gov.cn/wjw/xxgk/xxgk.shtml",
    "海关总署": "http://www.customs.gov.cn/customs/302249/302310/index.html",
    "国家金融监督管理总局": "https://www.nfra.gov.cn/cn/view/pages/zhengfuxinxi.html",
    "国家药品监督管理局": "https://www.nmpa.gov.cn/zwgk/zfxxgkzq/index.html",
    "国务院新闻办公室": "http://www.scio.gov.cn/zfxxgk/",
    "国家消防救援局": "https://www.119.gov.cn/zfxxgk/",
    "国家数据局": "https://www.nda.gov.cn/zfxxgk/",
    "湖北省人民政府": "https://www.hubei.gov.cn/zfxxgk/",
    "甘肃省人民政府": "https://www.gansu.gov.cn/zfxxgk/",
    "湖北": "https://www.hubei.gov.cn/zfxxgk/",
    "甘肃": "https://www.gansu.gov.cn/zfxxgk/",
}


def verify(url: str) -> bool:
    """验证 URL 可达且非错误页。"""
    html = fetch(url, timeout=12)
    return bool(html)


def main():
    recs = []
    for fn in ("central.jsonl", "province.jsonl"):
        for line in open(fn, encoding="utf-8"):
            r = json.loads(line)
            if not r.get("xxgk_url"):
                recs.append(r)
    print(f"待修复 {len(recs)} 个")

    for r in recs:
        name, portal = r["name"], r["portal_url"]
        found = None
        # 1) 重新抓首页，v2 识别（含 URL 路径特征）
        html = fetch(portal)
        if html:
            found = find_xxgk_url(html, portal)
        # 2) 路径探测（含 /xxgk/ /zwgk/ 等扩展列表）
        if not found:
            found = probe_xxgk_paths(portal)
        # 3) 手工兜底表 + 验证
        if not found:
            cand = MANUAL.get(name)
            if cand and verify(cand):
                found = cand
        if found:
            r["xxgk_url"] = norm_url(found)
            r["xxgk_src"] = r.get("xxgk_src", "修复")
        else:
            r["xxgk_src"] = "未命中"
        print(f"{name}: {found or 'MISS'}", flush=True)

    for fn in ("central.jsonl", "province.jsonl"):
        rows = [json.loads(l) for l in open(fn, encoding="utf-8")]
        for r in recs:
            for row in rows:
                if row["name"] == r["name"]:
                    row.update(r)
        with open(fn, "w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    miss = [r["name"] for r in recs if not r.get("xxgk_url")]
    print("剩余未命中:", miss)


if __name__ == "__main__":
    main()
