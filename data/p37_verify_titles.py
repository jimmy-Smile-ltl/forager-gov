# -*- coding: utf-8 -*-
"""P37: 群团命中 URL 标题验证 —— 防 SERP 挖掘误配。

对 quntuan_baidu.jsonl 每条带 url 的行：GET 抓标题+正文前 2000 字，
按槽位关键词校验（防 统战部域名混入台联、新华网混入友协 等）。
校验失败 → url 清空回列名，记录到 quntuan_verify_report.md。
200 校验通过 / 非200(网络或WAF) 保留并标记 unverified。
"""
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开")
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")

SLOT_KW = {
    "省总工会": r"工会",
    "团省委": r"共青团|团委|青年",
    "省妇联": r"妇联|妇女联合会",
    "省科协": r"科协|科学技术协会",
    "省文联": r"文联|文学艺术界",
    "省作协": r"作协|作家协会",
    "省工商联": r"工商联|总商会",
    "省残联": r"残联|残疾人",
    "省贸促会": r"贸促|国际贸易促进",
    "省红十字会": r"红十字",
    "省侨联": r"侨联|归国华侨",
    "省台联": r"台联|台湾同胞联谊",
    "省法学会": r"法学会",
    "省记协": r"记协|新闻工作者协会",
    "省人民对外友好协会": r"友协|对外友好",
    "省计划生育协会": r"计划生育协会|计生协",
    "省欧美同学会": r"欧美同学会|留学人员",
}

# 确凿错误证据：标题含异类组织词 → 清除；无证据（JS渲染无标题）→ 保留待核
WRONG_RE = re.compile(
    r"(统战部|人民政府|人民网|新华网|凤凰|腾讯|新浪|搜狐|网易|百度|百科|"
    r"医院|学校|大学|学院|银行|保险|证券|公司|集团|商城|购物|旅游|招聘|人才网|"
    r"纪检监察|纪委|法院|检察院|公安|财政局|教育局|卫健委)")


def judge(text, kw):
    if kw.search(text):
        return "pass"
    if WRONG_RE.search(text):
        return "fail"
    return "uncertain"


def fetch(u):
    import requests
    try:
        r = requests.get(u, headers={"User-Agent": UA}, timeout=12, verify=False)
        if r.status_code != 200:
            return None, r.status_code
        raw = r.content
        enc = (r.encoding or "").lower()
        # 编码嗅探：meta charset 优先；未声明时中文站按 gb18030 解码
        m = re.search(rb'charset=["\']?\s*([a-zA-Z0-9_-]+)', raw[:2000])
        meta = m.group(1).decode("ascii", "ignore").lower() if m else ""
        if meta and "gb" in meta:
            text = raw.decode("gb18030", errors="replace")
        elif meta and "utf" in meta:
            text = raw.decode("utf-8", errors="replace")
        elif "gb" in enc or "iso-8859-1" in enc or enc == "":
            try:
                text = raw.decode("gb18030")
            except Exception:
                text = raw.decode("utf-8", errors="replace")
        else:
            text = raw.decode("utf-8", errors="replace")
        m = re.search(r"<title[^>]*>(.*?)</title>", text, re.S | re.I)
        title = re.sub(r"\s+", " ", m.group(1)).strip() if m else ""
        return (title + " " + re.sub(r"<[^>]+>", " ", text[:4000])), r.status_code
    except Exception:
        return None, None


def verify(row):
    u = row.get("url", "")
    if row.get("verify") == "pass":
        return row, "skip"          # 已验证通过，不重复抓取
    if not u:
        # 已清除行：从候选重新挑选（judge：通过/不确定均可保留，优先通过）
        if row.get("verify") != "title_mismatch":
            return row, "skip"
        kw = re.compile(SLOT_KW[row["slot"]])
        best = None
        for cand in row.get("candidates_clean", []):
            for scheme in ("https://", "http://"):
                try:
                    import subprocess
                    r = subprocess.run(
                        ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
                         "-L", "--max-time", "8", "-A", UA[:60], scheme + "www." + cand],
                        capture_output=True, text=True, timeout=12)
                    if r.stdout.strip().startswith(("2", "3")):
                        cand_url = scheme + "www." + cand
                    else:
                        r2 = subprocess.run(
                            ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
                             "-L", "--max-time", "8", "-A", UA[:60], scheme + cand],
                            capture_output=True, text=True, timeout=12)
                        if not r2.stdout.strip().startswith(("2", "3")):
                            continue
                        cand_url = scheme + cand
                    text, code = fetch(cand_url)
                    if text is None:
                        continue
                    v = judge(text, kw)
                    if v == "pass":
                        row["url"] = cand_url
                        row["verify"] = "pass_repick"
                        return row, "pass"
                    if v == "uncertain" and best is None:
                        best = cand_url
                except Exception:
                    continue
        if best:
            row["url"] = best
            row["verify"] = "uncertain_repick"
            return row, "uncertain"
        row["verify"] = "title_mismatch"
        return row, "fail"
    text, code = fetch(u)
    if text is None:
        row["verify"] = f"不可达[{code}]"
        return row, "unverified"      # 保留（网络/WAF），报告标记
    kw = re.compile(SLOT_KW[row["slot"]])
    v = judge(text, kw)
    row["verify"] = {"pass": "pass", "fail": "title_mismatch",
                     "uncertain": "uncertain"}[v]
    return row, v


def main():
    rows = [json.loads(l) for l in open("quntuan_baidu.jsonl", encoding="utf-8")]
    with ThreadPoolExecutor(10) as ex:
        results = list(ex.map(verify, rows))
    fails = [r for r, st in results if st == "fail"]
    unv = [r for r, st in results if st == "unverified"]
    unc = [r for r, st in results if st == "uncertain"]
    # 确凿错误者清空 url
    fail_keys = {r["province"] + "|" + r["slot"] for r in fails}
    cleared = 0
    for r in rows:
        if r["province"] + "|" + r["slot"] in fail_keys:
            r["url"] = ""
            cleared += 1
    with open("quntuan_baidu.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    st = json.load(open("quntuan_baidu_state.json", encoding="utf-8"))
    st["rows"] = rows
    st["applied"] = False
    json.dump(st, open("quntuan_baidu_state.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=0)

    with open("quntuan_verify_report.md", "w", encoding="utf-8") as f:
        f.write(f"# 群团 URL 验证报告 {time.strftime('%Y-%m-%d %H:%M')}\n\n")
        f.write(f"- 总数 {len(rows)}，确凿错误清除 {len(fails)}，"
                f"不可达保留 {len(unv)}，标题无证据待核 {len(unc)}\n\n")
        f.write("## 确凿错误（已清空回列名）\n")
        for r in fails:
            f.write(f"- {r['province']} {r['slot']} 候选 {r.get('candidates_clean')}\n")
        f.write("\n## 不可达（保留待复查）\n")
        for r in unv:
            f.write(f"- {r['province']} {r['slot']} {r.get('url')} [{r['verify']}]\n")
        f.write("\n## 标题无证据（保留待核，多为 JS 渲染站）\n")
        for r in unc:
            f.write(f"- {r['province']} {r['slot']} {r.get('url')}\n")
    hit = sum(1 for r in rows if r["url"])
    print(f"p37 完成：{len(rows)} 行，确凿错误清除 {len(fails)}，"
          f"不可达 {len(unv)}，待核 {len(unc)}，现命中 {hit}")


if __name__ == "__main__":
    main()
