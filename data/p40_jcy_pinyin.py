# -*- coding: utf-8 -*-
"""P40: 市县检察院 pinyin.jcy.gov.cn 域名探测回填。

背景：检察系统全国统一域名体系 www.{拼音}.jcy.gov.cn（辽宁 14 市实测成立，
绵阳 mianyang.jcy.gov.cn 200；部分城市例外如成都）。
方法：333 市 + 2980 县/地级区 拼音探测（GET，任意 HTTP 响应=存在）
      → 标题含「检察」验证 → 回填 tree 并列机关成员 + 规则 depts。
拼音例外表沿用 p7（旗县缩写）；多音字低风险=DNS miss。
运行：uv run --with pypinyin python p40_jcy_pinyin.py
断点续跑：p40_state.json。
"""
import json
import os
import re
import socket
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
STATE_F = "p40_state.json"

PY_EXCEPT = {
    "达尔罕茂明安联合旗": "dmlh", "阿拉善右旗": "alsyq", "科尔沁左翼中旗": "kzzq",
    "科尔沁左翼后旗": "kzhq", "科尔沁右翼前旗": "kyqq", "察哈尔右翼前旗": "cyqq",
    "察哈尔右翼中旗": "cyzq", "察哈尔右翼后旗": "cyhq", "正蓝旗": "zlq",
    "恩施土家族苗族自治州": "enshi", "湘西土家族苗族自治州": "xiangxi",
    "黔南布依族苗族自治州": "qiannan", "西双版纳傣族自治州": "xsbn",
    "德宏傣族景颇族自治州": "dehong", "迪庆藏族自治州": "diqing",
    "黄南藏族自治州": "huangnan", "果洛藏族自治州": "guoluo",
    "玉树藏族自治州": "yushu", "海西蒙古族藏族自治州": "haixi",
    "重庆": "chongqing", "厦门": "xiamen", "六安": "luan", "丽水": "lishui",
    "长治": "changzhi", "乐清": "yueqing", "蚌埠": "bengbu", "亳州": "bozhou",
    "番禺": "panyu", "台州": "taizhou", "涪陵": "fuling", "尉氏": "weishi",
    "尉犁": "yuli", "泌阳": "biyang", "荥阳": "xingyang", "单县": "shanxian",
}


ETHNIC = ("维吾尔|哈萨克|柯尔克孜|乌孜别克|塔吉克|塔塔尔|锡伯|俄罗斯|达斡尔|"
          "鄂温克|鄂伦春|赫哲|蒙古|回|藏|苗|彝|壮|布依|朝鲜|满|侗|瑶|白|"
          "土家|哈尼|傣|黎|傈僳|佤|畲|拉祜|水|东乡|纳西|景颇|仫佬|羌|"
          "布朗|撒拉|毛南|仡佬|阿昌|普米|怒|德昂|保安|裕固|京|基诺|门巴|珞巴|独龙|土")
STRIP_RE = re.compile(
    rf"(({ETHNIC})族)?(自治州|自治县|自治旗|地区|盟|市|县|区|旗|林区|特区|联合旗)$")


def pinyin_of(name):
    if name in PY_EXCEPT:
        return PY_EXCEPT[name]
    from pypinyin import lazy_pinyin
    core = STRIP_RE.sub("", name) or name
    return "".join(lazy_pinyin(core))


def probe(py):
    """返回 (exists: bool, url: str)"""
    for scheme in ("https", "http"):
        u = f"{scheme}://www.{py}.jcy.gov.cn/"
        try:
            r = subprocess.run(["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
                                "-L", "--max-time", "8", "-A", UA, u],
                               capture_output=True, text=True, timeout=12)
            code = r.stdout.strip()
            if code and code != "000":
                return True, u
        except Exception:
            pass
    return False, ""


def title_check(url, name):
    """标题/正文含「检察」+ 尽量含地名 → 置信度。"""
    try:
        import requests
        r = requests.get(url, headers={"User-Agent": UA}, timeout=12, verify=False)
        raw = r.content[:60000]
        m = re.search(rb'charset=["\']?\s*([a-zA-Z0-9_-]+)', raw[:2000])
        enc = (m.group(1).decode("ascii", "ignore") if m else (r.encoding or "")).lower()
        if "gb" in enc or "iso-8859-1" in enc or not enc:
            txt = raw.decode("gb18030", errors="replace")
        else:
            txt = raw.decode("utf-8", errors="replace")
        if "检察" not in txt[:20000]:
            return False
        short = re.sub(r"(维吾尔|壮族|回族)?(自治州|自治县|地区|盟|市|区|县|旗)$", "", name)
        return short in txt[:20000]
    except Exception:
        return False


def main():
    tree = json.load(open("tree.json", encoding="utf-8"))
    prov_g = next(g for g in tree["ks"] if g["n"].startswith("省级"))

    targets = []
    for p in prov_g["ks"]:
        for top in p.get("ks", []):
            def walk(n):
                if n.get("l") in ("市", "县", "地级区") and n.get("k") == "人民政府" \
                        and n.get("cd"):
                    targets.append({"province": p["n"], "name": n["n"],
                                    "cd": n["cd"], "level": n["l"]})
                for k in n.get("ks", []):
                    walk(k)
            walk(top)

    state = {}
    if os.path.exists(STATE_F):
        state = json.load(open(STATE_F, encoding="utf-8"))
    done = set(state.get("done", []))
    hits = state.get("hits", [])
    todo = [t for t in targets if t["cd"] not in done]
    print(f"p40 本轮 {len(todo)} 个市县（累计 {len(done)}，命中 {len(hits)}）", flush=True)

    def work(t):
        py = pinyin_of(t["name"])
        ok, url = probe(py)
        conf = None
        if ok:
            conf = title_check(url, t["name"])
        return t, py, url, conf

    with ThreadPoolExecutor(12) as ex:
        for i, (t, py, url, conf) in enumerate(ex.map(work, todo)):
            if url:
                hits.append({"province": t["province"], "name": t["name"],
                             "cd": t["cd"], "level": t["level"], "py": py,
                             "url": url, "verified": conf})
            done.add(t["cd"])
            if (i + 1) % 200 == 0:
                state["done"] = sorted(done)
                state["hits"] = hits
                json.dump(state, open(STATE_F, "w", encoding="utf-8"),
                          ensure_ascii=False, indent=0)
                print(f"  进度 {i+1}/{len(todo)}，命中 {len(hits)}", flush=True)

    state["done"] = sorted(done)
    state["hits"] = hits
    json.dump(state, open(STATE_F, "w", encoding="utf-8"), ensure_ascii=False, indent=0)

    # ---- 回填 tree + rules ----
    by_cd = {h["cd"]: h for h in hits}
    rules = json.load(open("extraction_rules.json", encoding="utf-8"))
    filled = 0
    for p in prov_g["ks"]:
        for top in p.get("ks", []):
            def walk(n):
                nonlocal filled
                if n.get("l") in ("市", "县", "地级区") and n.get("cd") in by_cd:
                    h = by_cd[n["cd"]]
                    if not h["verified"]:
                        # 标题不含地名（同名拼音冲突风险）→ 跳过，仅记录
                        return
                    par = next((g for g in n.get("ks", []) if g.get("c") == "并列机关"), None)
                    if par:
                        for m in par.get("ks", []):
                            if "检察院" in m["n"]:
                                m["u"] = h["url"]
                                filled += 1
                    rkeys = [n["cd"]] + [f"{n['n']}·{g['n']}" for g in n.get("ks", [])
                                          if g.get("c") == "并列机关"]
                    for rkey in rkeys:
                        if rkey in rules:
                            for d in rules[rkey]["depts"]:
                                if "检察院" in d["n"]:
                                    d["u"] = h["url"]
                for k in n.get("ks", []):
                    walk(k)
            walk(top)
    json.dump(tree, open("tree.json", "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    json.dump(rules, open("extraction_rules.json", "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    ver = sum(1 for h in hits if h["verified"])
    print(f"p40 完成：探测命中 {len(hits)}（标题验证 {ver}），回填 {filled} 个成员",
          flush=True)


if __name__ == "__main__":
    main()
