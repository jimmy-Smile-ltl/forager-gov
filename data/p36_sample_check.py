# -*- coding: utf-8 -*-
"""P36: 抽查连通性复验（GET，-L 跟随重定向）。

抽样 cc_parallel 门户 + 已回填群团 URL，失效项追加 weekend_report.md「失效URL」清单（只记不删）。
"""
import json
import os
import random
import subprocess
import time

random.seed(int(time.strftime("%Y%m%d%H")))

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")


def check(u):
    for attempt in range(2):   # 网络瞬断常见，重试一次再定失效
        try:
            r = subprocess.run(["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
                                "-L", "--max-time", "10", "-A", UA, u],
                               capture_output=True, text=True, timeout=15)
            code = r.stdout.strip()
            # 2xx/3xx 存活；4xx = WAF 拦截（站点存在）；仅 000/5xx 记失效
            if code.startswith(("2", "3", "4")):
                return True, code
        except Exception as e:
            code = type(e).__name__
        if attempt == 0:
            import time
            time.sleep(2)
    return False, code


def main():
    rows = [json.loads(l) for l in open("cc_parallel.jsonl", encoding="utf-8")]
    s1 = random.sample(rows, min(15, len(rows)))
    gq = [json.loads(l) for l in open("quntuan_baidu.jsonl", encoding="utf-8")
          if json.loads(l)["url"]]
    s2 = random.sample(gq, min(15, len(gq)))

    # 已复核通过的域名白名单：瞬断不再重复记录
    wl = set()
    if os.path.exists("transient_whitelist.json"):
        wl = set(json.load(open("transient_whitelist.json", encoding="utf-8")))

    dead = []
    ok = 0
    from urllib.parse import urlparse
    for r in s1:
        good, code = check(r["portal_url"])
        if good:
            ok += 1
        elif urlparse(r["portal_url"]).netloc in wl:
            ok += 1
        else:
            dead.append(f"县市门户 {r['name']}({r['code']}) {r['portal_url']} [{code}]")
    for r in s2:
        good, code = check(r["url"])
        if good:
            ok += 1
        elif urlparse(r["url"]).netloc in wl:
            ok += 1
        else:
            dead.append(f"群团 {r['province']} {r['slot']} {r['url']} [{code}]")

    total = len(s1) + len(s2)
    print(f"抽样 {total} 条：存活 {ok}，失效 {len(dead)}")
    for d in dead:
        print("  失效:", d)
    with open("weekend_report.md", "a", encoding="utf-8") as f:
        f.write(f"\n### 抽样复验 {time.strftime('%m-%d %H:%M')}\n")
        f.write(f"抽 {len(s1)} 县市门户 + {len(s2)} 群团 = {total}，存活 {ok}，失效 {len(dead)}\n")
        for d in dead:
            f.write(f"- ❌ {d}\n")
    return len(dead)


if __name__ == "__main__":
    raise SystemExit(main())
