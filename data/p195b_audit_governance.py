# -*- coding: utf-8 -*-
"""P195b: 县级门户不合规存量治理 — 上级政府门户区县导航重提取（禁用搜索引擎）。

背景（2026-11-11 全局核查，优先级高于剩余缺口）：
- 树中县级人民政府有 URL 的节点里，523 个来自搜索引擎（bing搜索(已验证)/
  p3c-bing，p129 时代留痕）+ 4 个拼音探测（s=路径探测，红线）——全部违反
  「只能上级人民政府官网提取」铁律。清单在 /tmp/audit_result.json
  （viol 数组 523 条 = (省, 县名, URL)；unknow 17 条带第 4 元素来源）。
- 治理动作：
  1) 4 个拼音探测 URL 立即清空列名（不设降级标注），然后按上级门户重新提取。
  2) 其余搜索来源条目：在其上级政府门户的区县导航里重新提取——提取到且
     title 验证通过 → 更新 u + s=「来源：XX政府门户区县导航 HTML 提取
     （title 验证）」；上级门户确无该县链接 → 清空列名（宁缺毋滥）。
  3) 已合规条目（现有 s 以「来源：」开头，如 p194 凉山 4 条）仅 title 复验，
     通过保留，失败清除。

流程：按上级门户分组 → 门户首页 + 导航栏目页 + JS 壳渲染兜底 → 全量链接提取
→ 基底名/令牌匹配 → 候选 title 验证 → 落库（树 u/s 更新或清空 + registry）。
断点 state data/p195_audit_state.json；幂等，重复运行跳过已处理条目。
"""
import json, os, re, sys, datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin, urlparse

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, "util"))
os.chdir(BASE)

os.environ["BROWSER_TIERS"] = "on"
from smart_fetch import smart_fetch  # noqa: E402

TREE_F = "data/tree.json"
REG_F = "data/site_registry.json"
STATE_F = "data/p195_audit_state.json"
AUDIT_F = "/tmp/audit_result.json"
today = datetime.date.today().strftime("%Y-%m-%d")

CTYPES = {"县级人民政府", "市辖区（地级行政区划）", "直辖市辖县（县级行政区划）",
          "省直辖县级市/县/林区", "兵团直辖县级市（自治区直辖县级市）"}

# ── 基底名归一 + 提取工具（p195 同款，纯函数复制）──
ETH_PY = re.compile(
    r"(哈萨克族?|维吾尔族?|柯尔克孜族?|蒙古族?|藏族?|回族?|壮族?|苗族?|黎族?"
    r"|侗族?|满族?|白族?|傣族?|彝族?|哈尼族?|拉祜族?|傈僳族?|佤族?|水族?"
    r"|羌族?|布依族?|仡佬族?|仫佬族?|毛南族?|瑶族?|畲族?|土家族?|锡伯族?"
    r"|达斡尔族?|鄂温克族?|鄂伦春族?|赫哲族?|俄罗斯族?|塔塔尔族?|乌孜别克族?"
    r"|塔吉克族?|撒拉族?|保安族?|裕固族?|东乡族?|纳西族?|景颇族?|阿昌族?"
    r"|普米族?|怒族?|德昂族?|独龙族?|基诺族?|门巴族?|珞巴族?|京族?"
    r"|朝鲜族?|各族?|自治)$")


def base(nm):
    t = re.sub(r"(自治州|自治县|自治旗|地区|盟|市|县|区|旗)$", "", nm or "")
    for _ in range(8):
        t2 = ETH_PY.sub("", t)
        if t2 == t:
            break
        t = t2
    return t


COUNTY_RE = re.compile(r"^[一-鿿]{1,10}(自治县|自治旗|县|市|区|旗|林区|矿区)$")
NAV_KW = re.compile(r"(区县|县区|旗县|盟市|网站导航|县市区|区县政府|区县之窗|网站地图|地方网站|政府网站|下属|下级)")
A_RE = re.compile(r'''<a\s[^>]*?href=["']([^"']+)["'][^>]*>\s*([^<>]{1,20}?)\s*</a>''', re.S)
OPT_RE = re.compile(r'''<option\s[^>]*?value=["']([^"']*)["'][^>]*>\s*([^<>]{1,20}?)\s*</option>''', re.S)


def match_token(node_name):
    if "高新技术产业开发区" in node_name or "高新区" in node_name:
        return "高新"
    if "经济技术开发区" in node_name or "经开区" in node_name or "经济开发区" in node_name:
        return "经开"
    if "滨海" in node_name:
        return "滨海"
    m = re.search(r"([一-鿿]+管理区)", node_name)
    if m:
        return m.group(1)
    return None


def county_hit(node_name, cand_text):
    tok = match_token(node_name)
    if tok:
        return tok in cand_text
    return base(node_name) == base(cand_text)


def norm_text(t):
    t = re.sub(r"[\s　]+", "", t or "")
    while True:
        t0 = t
        for suf in ("人民政府", "门户网站", "政府", "网站", "门户", "网"):
            if t.endswith(suf):
                t = t[: -len(suf)]
                break
        if t == t0 or not t:
            break
    return t


def resolve_url(parent_u, href):
    href = (href or "").replace("&amp;", "&").strip()
    if not href or href.startswith("javascript:") or href.startswith("mailto:") \
            or href.startswith("#"):
        return ""
    u = urljoin(parent_u, href)
    p = urlparse(u)
    if p.scheme not in ("http", "https") or not p.netloc:
        return ""
    return u.split("#")[0].rstrip("/")


def extract_candidates(parent_u, html):
    parent_host = urlparse(parent_u).netloc.lower()
    out, seen = [], set()
    for href, txt in A_RE.findall(html):
        out.append((txt.strip(), href))
    for val, txt in OPT_RE.findall(html):
        out.append((txt.strip(), val))
    cands = []
    for txt, href in out:
        t = norm_text(txt)
        if not COUNTY_RE.match(t):
            continue
        u = resolve_url(parent_u, href)
        if not u or "gov.cn" not in urlparse(u).netloc.lower():
            continue
        if urlparse(u).netloc.lower() == parent_host:
            continue
        if u in seen:
            continue
        seen.add(u)
        cands.append((t, u))
    return cands


def extract_nav_pages(parent_u, html):
    exact = re.compile(r"^(区县|旗县|盟市|县市区|区县政府|区县之窗|网站地图|网站导航|地方网站|政府网站|各县市|旗县市|县市区政府|各市区县)$")
    fuzzy = NAV_KW
    pages = []
    for href, txt in A_RE.findall(html):
        t = (txt or "").strip()
        if not exact.search(t):
            continue
        u = resolve_url(parent_u, href)
        if u and u not in pages:
            pages.append(u)
        if len(pages) >= 3:
            break
    if len(pages) < 3:
        for href, txt in A_RE.findall(html):
            t = (txt or "").strip()
            if re.search(r"(动态|专题|新闻|时讯)", t):
                continue
            if not fuzzy.search(t):
                continue
            u = resolve_url(parent_u, href)
            if u and u not in pages:
                pages.append(u)
            if len(pages) >= 3:
                break
    return pages


def render_pass(parent_u, html, _hard_timeout=70):
    """硬超时保护：CloakBrowser 的 goto/content/close 任一卡住（本环境实测
    close 卡死致信号量不释放、整批 as_completed 永久等待），70s 未返回即放弃。
    泄漏的渲染进程由批处理结束后的统一 pkill 清理，超时线程最终自行结束并
    release 信号量（若 close 永久卡住则后续渲染 acquire(90s) 超时放弃，不阻塞）。"""
    import time as _t
    try:
        from smart_fetch import _cloak_sem
        if not _cloak_sem.acquire(timeout=90):
            return None
        try:
            from cloakbrowser import launch
            try:
                _b = launch(headless=False, humanize=True)
            except Exception:
                _b = launch()
            try:
                _p = _b.new_page()
                try:
                    _p.goto(parent_u, timeout=30000, wait_until="domcontentloaded")
                except Exception:
                    pass
                _t.sleep(5)
                try:
                    return _p.content()
                except Exception:
                    return None
            finally:
                try:
                    _b.close()
                except Exception:
                    pass
        except Exception:
            return None
        finally:
            try:
                _cloak_sem.release()
            except Exception:
                pass
    except Exception:
        return None


def verify_title(county, u):
    try:
        h, m = smart_fetch(u, timeout=25)
        if not h:
            return False, f"无响应[{m}]"
        mt = re.search(r"<title>(.*?)</title>", h, re.S | re.I)
        t = (mt.group(1).strip() if mt else "")[:60]
        if not t:
            return False, "title 空"
        if re.search(r"404|无法访问|页面不存在|错误|ERROR", t, re.I):
            return False, f"异常页: {t}"
        b = base(county)
        pre = b[:2] if len(b) >= 2 else b
        ok = ("政府" in t or "人民" in t) and \
             (pre in t or "人民政府" in t or "县" in t or "市" in t or "区" in t
              or "旗" in t or "自治" in t)
        return ok, t
    except Exception as e:
        return False, f"异常: {str(e)[:30]}"


# ── state ──
def load_state():
    if os.path.exists(STATE_F):
        return json.load(open(STATE_F, encoding="utf-8"))
    return {"entries": {}, "parents": {}}


def save_state(st):
    tmp = STATE_F + ".tmp"
    json.dump(st, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    os.replace(tmp, STATE_F)


# ── 1. 载入审计清单并定位树节点 ──
def walk(n, path):
    yield n, path
    for k in n.get("ks", []) or []:
        yield from walk(k, path + [n])


aud = json.load(open(AUDIT_F, encoding="utf-8"))
viol = aud["viol"]          # (省, 县名, URL)
unknow = aud["unknow"]      # (省, 县名, URL, 来源)

tree = json.load(open(TREE_F, encoding="utf-8"))
reg = json.load(open(REG_F, encoding="utf-8"))
st = load_state()

# 按 (省, 名) 定位节点：先按 u==URL 精确匹配（防重名），再按省祖先兜底
nodes_by_key = {}
county_nodes = {}
for n, path in walk(tree, []):
    if n.get("k") != "人民政府" or n.get("c") not in CTYPES:
        continue
    county_nodes.setdefault(n["n"], []).append((n, path))


def prov_of(path):
    """父链中省级节点名：任意祖先 n == 省名即命中（城市名不可能等于省名）。"""
    for p in reversed(path):
        if p.get("n") in PROVINCES:
            return p.get("n")
    return None


# 省级名单（含港澳台/兵团，p195b 只处理大陆县级节点）
PROVINCES = {"北京市", "天津市", "河北省", "山西省", "内蒙古自治区", "辽宁省",
             "吉林省", "黑龙江省", "上海市", "江苏省", "浙江省", "安徽省",
             "福建省", "江西省", "山东省", "河南省", "湖北省", "湖南省",
             "广东省", "广西壮族自治区", "海南省", "重庆市", "四川省",
             "贵州省", "云南省", "西藏自治区", "陕西省", "甘肃省", "青海省",
             "宁夏回族自治区", "新疆维吾尔自治区", "新疆生产建设兵团",
             "香港特别行政区", "澳门特别行政区", "台湾省"}


def find_node(prov, name, url):
    cands = county_nodes.get(name, [])
    # 1) u 精确匹配
    for n, path in cands:
        if n.get("u") == url:
            return n, path
    # 2) 省祖先匹配
    for n, path in cands:
        if prov and prov_of(path) == prov:
            return n, path
    # 3) 未匹配
    return None, None


def find_ancestor(path):
    for p in reversed(path):
        if p.get("k") == "人民政府" and p.get("u"):
            return p.get("n"), p.get("u")
    for p in reversed(path):
        if p.get("k") == "人民政府":
            return p.get("n"), p.get("u") or ""
    return None, None


# 条目统一结构: {key: {prov, name, url, kind}}
# kind: pinyin(4 拼音探测) / search(搜索来源) / ok(现有 s 合规, 仅复验) / unknown
entries = {}
for prov, name, url in viol:
    n, path = find_node(prov, name, url)
    if n is None:
        print(f"⚠️ viol 未定位节点: {prov} {name} {url}", flush=True)
        continue
    s = n.get("s", "")
    if s == "路径探测":
        kind = "pinyin"
    elif s.startswith("来源："):
        kind = "ok"
    else:
        kind = "search"
    entries[f"{prov}|{name}"] = {"prov": prov, "name": name, "url": url,
                                 "kind": kind, "node": n, "path": path}
for prov, name, url, src in unknow:
    n, path = find_node(prov, name, url)
    if n is None:
        print(f"⚠️ unknow 未定位节点: {prov} {name} {url}", flush=True)
        continue
    s = n.get("s", "")
    if s.startswith("来源："):
        kind = "ok"
    else:
        kind = "unknown"
    entries[f"{prov}|{name}"] = {"prov": prov, "name": name, "url": url,
                                 "kind": kind, "node": n, "path": path}

n_pinyin = sum(1 for e in entries.values() if e["kind"] == "pinyin")
n_search = sum(1 for e in entries.values() if e["kind"] == "search")
n_ok = sum(1 for e in entries.values() if e["kind"] == "ok")
n_unknown = sum(1 for e in entries.values() if e["kind"] == "unknown")
print(f"审计条目: 共 {len(entries)} (拼音 {n_pinyin} / 搜索 {n_search} / "
      f"合规复验 {n_ok} / 未知来源 {n_unknown})", flush=True)

# 按上级门户分组（每组一次提取，匹配该组全部条目）
by_parent = {}
no_parent_keys = []
for key, e in entries.items():
    if key in st["entries"]:
        continue
    pn, pu = find_ancestor(e["path"])
    if not pn or not pu:
        # 无上级门户：kind=ok 走现有 URL 复验（apply 阶段处理），其余直接清空
        if e["kind"] != "ok":
            st["entries"][key] = {"status": "no_parent_url", "result": "clear",
                                  "u": ""}
        else:
            no_parent_keys.append(key)
        continue
    by_parent.setdefault(pn, {"u": pu, "items": []})
    by_parent[pn]["items"].append((key, e))
print(f"待处理上级门户 {len(by_parent)} 个, 条目 {sum(len(v['items']) for v in by_parent.values())} 条",
      flush=True)


# ── 2. 每上级门户提取区县导航候选，匹配该组条目 ──
def process_parent(pn):
    info = by_parent[pn]
    pu = info["u"]
    try:
        html, m = smart_fetch(pu, timeout=25)
        if not html or len(html) < 500:
            return pn, {"status": f"fetch_fail[{m}]", "hits": {}}
        cands = extract_candidates(pu, html)
        for npage in extract_nav_pages(pu, html):
            h2, _ = smart_fetch(npage, timeout=25)
            if h2 and len(h2) > 500:
                cands += extract_candidates(npage, h2)
        if len(cands) < len(info["items"]):
            rh = None
            with ThreadPoolExecutor(max_workers=1) as _ex:
                _fut = _ex.submit(render_pass, pu, html)
                try:
                    rh = _fut.result(timeout=75)
                except Exception:
                    rh = None
            if rh and len(rh) > 1000:
                cands += extract_candidates(pu, rh)
        dedup, seen = [], set()
        for t, u in cands:
            if u in seen:
                continue
            seen.add(u)
            dedup.append((t, u))
        cands = dedup
        hits = {}
        for key, e in info["items"]:
            if e["kind"] == "pinyin":
                continue  # 拼音条目：候选集复用 search 逻辑，单独匹配
            hit = None
            for t, u in cands:
                if county_hit(e["name"], t):
                    hit = u
                    break
            if hit:
                hits[key] = hit
        # 拼音条目同样匹配（同候选集）
        for key, e in info["items"]:
            if e["kind"] != "pinyin":
                continue
            hit = None
            for t, u in cands:
                if county_hit(e["name"], t):
                    hit = u
                    break
            if hit:
                hits[key] = hit
        return pn, {"status": "ok", "hits": hits}
    except Exception as e:
        return pn, {"status": f"exception:{str(e)[:40]}", "hits": {}}


WORKERS = int(os.environ.get("P195B_WORKERS", "8"))
parents = [pn for pn in by_parent if pn not in st["parents"]]
if parents:
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(process_parent, p): p for p in parents}
        done_n = 0
        for fut in as_completed(futs):
            pn, res = fut.result()
            st["parents"][pn] = res
            done_n += 1
            if done_n % 10 == 0:
                save_state(st)
                n_hits = sum(1 for r in st["parents"].values() for _ in r["hits"])
                print(f"  门户 {done_n}/{len(parents)}, 命中 {n_hits}", flush=True)
    save_state(st)

# ── 3. title 验证 + 落库/清空 ──
# 先验：拼音条目先清空（铁律），再重提取；其余条目重提取或复验后落库
def apply_one(item):
    key, e = item
    pn, pu = find_ancestor(e["path"])
    if not pn:
        # 无上级门户：kind=ok 走现有 URL 复验，其余清空
        if e["kind"] == "ok" and e["url"]:
            ok, t = verify_title(e["name"], e["url"])
            return key, ("kept_existing" if ok else "verify_fail_existing"), e["url"], t
        return key, "no_parent", e["url"]
    hit_u = st["parents"].get(pn, {}).get("hits", {}).get(key)
    if e["kind"] in ("pinyin", "search", "unknown"):
        # 重提取：命中 → title 验证；未命中 → 清空列名
        if hit_u:
            ok, t = verify_title(e["name"], hit_u)
            if ok:
                return key, "kept", hit_u, t
            return key, "verify_fail", "", t
        return key, "no_nav_clear", "", ""
    # kind=ok：现有 URL title 复验，通过保留（s 已是合规来源），失败清空
    if e["url"]:
        ok, t = verify_title(e["name"], e["url"])
        if ok:
            return key, "kept_existing", e["url"], t
        return key, "verify_fail_existing", "", t
    return key, "no_url", "", ""


def apply_entries(items):
    out = []
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(apply_one, it): it for it in items}
        for fut in as_completed(futs):
            out.append(fut.result())
    return out


todo = [(key, e) for key, e in entries.items() if key not in st["entries"]]
results = []
for i in range(0, len(todo), 20):
    batch = todo[i:i + 20]
    for r in apply_entries(batch):
        key = r[0]
        e = entries[key]
        if r[1] in ("kept", "kept_existing"):
            new_u = r[2]
            pd = urlparse(new_u).netloc
            pn, _ = find_ancestor(e["path"])
            e["node"]["u"] = new_u
            e["node"]["s"] = f"来源：{pn}政府门户({pd})区县导航 HTML 提取（title 验证）"
            c = e["node"].get("c", "县级人民政府")
            rk = f"{c}|{e['name']}"
            if rk in reg and reg[rk].get("u"):
                reg[rk].update({"u": new_u, "source_level": "L2",
                                "verified_at": today, "status": "ok"})
            else:
                reg[rk] = {"u": new_u, "n": e["name"], "locations": ["块"],
                           "source_level": "L2", "verified_at": today,
                           "status": "ok", "snapshot": "", "xxgk": "",
                           "xxgk_src": ""}
            st["entries"][key] = {"status": r[1], "u": new_u, "title": r[3]}
        else:
            # 清空列名
            old = e["node"].get("u", "")
            e["node"]["u"] = ""
            e["node"]["s"] = ""
            c = e["node"].get("c", "县级人民政府")
            rk = f"{c}|{e['name']}"
            if rk in reg:
                reg[rk]["u"] = ""
                reg[rk]["status"] = "dead"
            st["entries"][key] = {"status": r[1], "u": "", "old_u": old}
        results.append((key, r[1]))
    save_state(st)

json.dump(tree, open(TREE_F, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
json.dump(reg, open(REG_F, "w", encoding="utf-8"), ensure_ascii=False, indent=0)

# ── 4. 报告 ──
from collections import Counter
rc = Counter()
for key, status in results:
    e = entries[key]
    rc[f"{e['kind']}:{status}"] += 1
print("\n═══ P195b 治理报告 ═══")
print("治理结果分布:", dict(rc))
for k in sorted(rc):
    print(f"  {k}: {rc[k]}")
n_kept = sum(1 for r in results if r[1] in ("kept", "kept_existing"))
n_clear = sum(1 for r in results if r[1] not in ("kept", "kept_existing"))
print(f"保留 {n_kept} | 清除 {n_clear}")
tree2 = json.load(open(TREE_F, encoding="utf-8"))
tot = sum(1 for n, _ in walk(tree2, [])
          if n.get("k") == "人民政府" and n.get("c") in CTYPES)
cov = sum(1 for n, _ in walk(tree2, [])
          if n.get("k") == "人民政府" and n.get("c") in CTYPES and n.get("u"))
print(f"县级门户覆盖率: {cov}/{tot} ({cov/tot*100:.1f}%)")
print("P195b done")
