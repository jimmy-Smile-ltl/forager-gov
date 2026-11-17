# -*- coding: utf-8 -*-
"""P176: 海关总署官网「直属海关」名录采集。
Cloudflare 521/412 全域防护 → smart_fetch 循环（cloakbrowser 指纹会话,
成功 ~1/3 窗口 8s 内通过）→ cf_clearance 落盘 → curl 快路径复采。"""
import json, os, re, sys, time
sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开")
sys.path.insert(0, "/Users/jimmy/projectBaidu/官网名单-分类/政府信息公开/util")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import save_snap
from smart_fetch import smart_fetch, _cf_cookie_load, _host_of_url

STATE_F = "hg_state.json"
state = json.load(open(STATE_F, encoding="utf-8")) if os.path.exists(STATE_F) \
    else {"tries": 0, "ok": False}

home = None
for rnd in range(10):
    if state.get("ok"):
        break
    state["tries"] += 1
    t0 = time.time()
    html, method = smart_fetch("http://www.customs.gov.cn/", timeout=25)
    print(f"轮{rnd+1}: method={method} 长度={len(html)} 耗时={time.time()-t0:.0f}s", flush=True)
    if html and len(html) > 5000:
        home = html
        state["ok"] = True
        state["method"] = method
        break
    time.sleep(90)  # Cloudflare 连续挑战惩罚: 拉长冷却
json.dump(state, open(STATE_F, "w", encoding="utf-8"), ensure_ascii=False, indent=0)

if not home:
    print("P176: 4 轮均未通过 Cloudflare 挑战")
    sys.exit(0)

save_snap("other", "中央", "海关总署", "home", home)
print(f"✓ 拿到海关总署首页 {len(home)} 字节", flush=True)

# 提取「直属海关」链接（真实 HTML）
seen = {}
for uu, txt in re.findall(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>\s*([^<]{2,24}?)\s*</a>', home):
    t2 = txt.strip()
    if re.search(r"海关$", t2) and uu.startswith("http") and t2 not in seen:
        seen[t2] = uu
print(f"提取到 {len(seen)} 个海关链接", flush=True)
for n, u in sorted(seen.items()):
    print(f"  {n}: {u}")
json.dump(seen, open("hg_customs_links.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)

# cf_clearance 快路径验证
host = _host_of_url("http://www.customs.gov.cn/")
cfd = _cf_cookie_load(host)
if cfd.get("cf_clearance"):
    print(f"cf_clearance 已落盘 ({len(cfd['cf_clearance'])} 字符)", flush=True)
    import subprocess
    r = subprocess.run(["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
                        "--max-time", "12",
                        "-A", cfd.get("ua", ""),
                        "-H", f"Cookie: cf_clearance={cfd['cf_clearance']}",
                        "http://www.customs.gov.cn/"], capture_output=True, text=True)
    print(f"curl 带 cf_clearance 快路径: HTTP {r.stdout}", flush=True)
else:
    print("cf_clearance 未落盘（会话 cookie 读取失败或未通过 CF 挑战页）", flush=True)
