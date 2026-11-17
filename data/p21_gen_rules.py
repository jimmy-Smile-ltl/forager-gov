# -*- coding: utf-8 -*-
"""P21: 生成各省「提取规则」元数据（方法/来源页/样例部门/样例市州）。"""
import json
import re
from urllib.parse import urlparse

METHODS = {
    "北京": ("首页底部「市级政府部门网站」导航模块（m_links_module3，隐藏 ul，悬停展开）",
             ["https://www.beijing.gov.cn/"]),
    "天津": ("首页底部导航容器（隐藏 ul 悬停展开）", ["https://www.tj.gov.cn/"]),
    "河北": ("首页底部导航容器", ["https://www.hebei.gov.cn/"]),
    "山西": ("首页底部导航容器", ["https://www.shanxi.gov.cn/"]),
    "内蒙古": ("首页底部导航容器", ["https://www.nmg.gov.cn/"]),
    "辽宁": ("首页底部导航容器", ["https://www.ln.gov.cn/"]),
    "吉林": ("首页底部导航容器", ["https://www.jl.gov.cn/"]),
    "黑龙江": ("首页底部导航容器", ["https://www.hlj.gov.cn/"]),
    "上海": ("首页底部导航容器（部分部门为门户子路径 www.shanghai.gov.cn/nw…，需按 URL 去重）",
             ["https://www.shanghai.gov.cn/"]),
    "江苏": ("组织机构页（TRS CMS：col/col84420）", ["https://www.jiangsu.gov.cn/col/col84420/"]),
    "浙江": ("门户底部导航（JS 动态渲染，需浏览器）+ 百度 SERP 挖 xxx.zj.gov.cn 子域",
             ["https://www.zj.gov.cn/"]),
    "安徽": ("组织机构页 zwgk/zfjg", ["https://www.ah.gov.cn/zwgk/zfjg/"]),
    "福建": ("首页底部导航容器", ["https://www.fujian.gov.cn/"]),
    "江西": ("首页底部导航容器", ["https://www.jiangxi.gov.cn/"]),
    "山东": ("组织机构页 col/col314107/index.html", ["http://www.shandong.gov.cn/col/col314107/index.html"]),
    "河南": ("首页底部导航容器", ["https://www.henan.gov.cn/"]),
    "湖北": ("门户瑞数 WAF → 百度 SERP 挖 xxx.hubei.gov.cn 子域 + 各子域标题定名",
             ["https://www.hubei.gov.cn/"]),
    "湖南": ("网站导航页 hnszf/fzlm/wzdh/szdw/szdh.html", ["https://www.hunan.gov.cn/hnszf/fzlm/wzdh/szdw/szdh.html"]),
    "广东": ("省直单位网站页 yw/szfjg/index.html", ["https://www.gd.gov.cn/yw/szfjg/index.html"]),
    "广西": ("首页底部导航容器", ["https://www.gxzf.gov.cn/"]),
    "海南": ("政府机构页 hainan/zfjgg/zfjg.shtml", ["https://www.hainan.gov.cn/hainan/zfjgg/zfjg.shtml"]),
    "重庆": ("首页底部「市级部门网站」导航容器", ["https://www.cq.gov.cn/"]),
    "四川": ("首页底部「省级部门网站」悬停弹出容器（xgljuldiv）", ["https://www.sc.gov.cn/"]),
    "贵州": ("首页底部导航容器", ["https://www.guizhou.gov.cn/"]),
    "云南": ("首页底部导航容器", ["https://www.yn.gov.cn/"]),
    "西藏": ("首页底部导航容器", ["https://www.xizang.gov.cn/"]),
    "陕西": ("首页底部导航容器", ["https://www.shaanxi.gov.cn/"]),
    "甘肃": ("首页底部导航容器（WAF 需浏览器渲染）", ["https://www.gansu.gov.cn/"]),
    "青海": ("首页底部导航容器", ["https://www.qinghai.gov.cn/"]),
    "宁夏": ("首页底部导航容器", ["https://www.nx.gov.cn/"]),
    "新疆": ("首页底部导航容器", ["https://www.xinjiang.gov.cn/"]),
}


CODE_TEMPLATE = '# -*- coding: utf-8 -*-\n"""从 {prov}人民政府门户提取「市州政府网站」+「省政府部门网站」完整流程。\n\n提取方法（{prov}）：{method}\n来源页：{sources}\n\n流程：URL 请求(编码自适应) → 定位底部「部门网站」容器 → 提取全部链接\n     → 部门名模式/域名过滤 → 按域名判定归属(防跨省导航) → 保 DOM 原始顺序\n依赖：pip install requests beautifulsoup4 lxml\n"""\nimport re\nfrom urllib.parse import urljoin, urlparse\n\nimport requests\nfrom bs4 import BeautifulSoup\n\nPORTAL = "{portal}"        # 省政府门户\nPROVINCE = "{prov}"\nUA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "\n      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")\n\n\ndef fetch(url: str) -> str:\n    """请求页面（GBK/UTF-8 自适应解码）。"""\n    resp = requests.get(url, headers={{"User-Agent": UA}}, timeout=15, verify=False)\n    if resp.encoding and "gb" in resp.encoding.lower():\n        return resp.content.decode("gb18030", errors="replace")\n    return resp.content.decode("utf-8", errors="replace")\n\n\n# ============ 一、提取市州政府网站 ============\nhtml = fetch(PORTAL)\nsoup = BeautifulSoup(html, "lxml")\n\nCITY_NAMES = {city_names}   # 民政部区划：该省地级市全名\ncities = {{}}\nfor a in soup.find_all("a"):\n    text = re.sub(r"\\s+", "", a.get_text(" ", strip=True))\n    href = a.get("href") or ""\n    if not text or not href.startswith(("http", "/")):\n        continue\n    # 锚文本与区划名匹配：去「政府/门户/网站」后缀，防 长沙县/长沙市 混淆\n    for city in CITY_NAMES:\n        t = re.sub(r"(人民政府|政府|门户网站|门户|网站)$", "", text)\n        if t == city and urlparse(urljoin(PORTAL, href)).netloc.endswith(".gov.cn"):\n            cities[city] = urljoin(PORTAL, href)\nprint("市州政府网站:", len(cities))\nfor k, v in cities.items():\n    print("  ", k, v)\n\n\n# ============ 二、提取省政府部门网站 ============\n# 1) 定位「部门网站」导航容器：标签文本匹配 → 向上找 >=8 个链接的祖先\nCONTAINER_RE = re.compile(r"(部门网站|委办局|厅局网站|政府部门|组成部门|直属机构|政府机构)")\nboxes = set()\nfor text_node in soup.find_all(string=CONTAINER_RE):\n    node = text_node.parent\n    for _ in range(4):\n        if node is None:\n            break\n        if len(node.find_all("a")) >= 8:\n            boxes.add(node)\n            break\n        node = node.parent\n\n# 2) 容器内链接过滤：部门名模式 + 域名\nDEPT_RE = re.compile(\n    r"^(省|市|自治区)?[^，。|、（）]{{1,12}}?"\n    r"(委员会|办公厅|办公室|厅|局|委|办|中心|管委会|执法队|总队)$")\nJUNK_TAIL = re.compile(r"(区|县|市|州|盟|旗)$")           # 排除区县/市州链接\nJUNK_PREFIX = re.compile(r"^(国家|国务院|中央|中国|全国)")  # 排除中央机构链接\n\ndepartments = []        # 保持 DOM 原始顺序（官网顺序，如发改委在前）\nfor box in boxes:\n    for idx, a in enumerate(box.find_all("a")):\n        name = re.sub(r"\\s+", "", (a.get("title") or a.get_text(" ", strip=True)).strip())\n        url = urljoin(PORTAL, a.get("href") or "")\n        host = urlparse(url).netloc.lower().replace("www.", "")\n        if not DEPT_RE.match(name) or JUNK_TAIL.search(name) or JUNK_PREFIX.match(name):\n            continue\n        if not host.endswith(".gov.cn"):\n            continue\n        departments.append((idx, name, url))\n    if departments:       # 取第一个命中容器\n        break\n\n# 3) 归属判定：域名全拼/省域子域 → 剔除跨省链接（如全国文旅系统导航）\nPROV_MARKERS = {{"四川": ["sichuan", "sc"], "北京": ["beijing", "bj"]}}  # 完整映射见 p13\ndef detect_province(url: str):\n    host = urlparse(url).netloc.lower()\n    for prov, keys in PROV_MARKERS.items():\n        if any(k in host for k in keys):\n            return prov\n    return None\n\nfor idx, name, url in departments:\n    owner = detect_province(url)\n    flag = "" if owner in (PROVINCE, None) else f"  <- 归属{{owner}}，剔除"\n    print(f"{{idx:3d}}  {{name:16s}} {{url}} {{flag}}")\n\n# 注：瑞数 WAF 站点（首页 JS 挑战）需浏览器渲染后再提取——\n#     见采集代码归档 p16_browser_footer.py（CloakBrowser CDP + DrissionPage）\n#     与 util/smart_fetch.py（curl_cffi→iv8→nodenv→RsSpider→Drission 五级降级）\n'

def build_code(pname, method, sources, portal, city_names):
    return CODE_TEMPLATE.format(
        prov=pname, method=method,
        sources="、".join(sources),
        portal=portal,
        city_names=repr(city_names),
    )


def main():
    provs = [json.loads(l) for l in open("province.jsonl", encoding="utf-8")]
    depts = [json.loads(l) for l in open("prov_depts.jsonl", encoding="utf-8")]
    cc = [json.loads(l) for l in open("city_county_final.jsonl", encoding="utf-8")]

    rules = {}
    for p in provs:
        pname = p["name"]
        if pname == "新疆生产建设兵团":
            continue
        method, sources = METHODS.get(pname, ("首页底部导航容器", [p["portal_url"]]))
        dlist = sorted([r for r in depts if r["province"] == pname],
                       key=lambda x: (x.get("order", 999), x["name"]))
        cities = [r for r in cc if r["level"] == "市" and r["province"].replace("省", "").replace("市", "")
                  .replace("壮族自治区", "").replace("回族自治区", "").replace("维吾尔自治区", "")
                  .replace("自治区", "") == pname.replace("省", "").replace("市", "")
                  .replace("壮族自治区", "").replace("回族自治区", "").replace("维吾尔自治区", "")
                  .replace("自治区", "")
                  and r.get("portal_url")]
        rules[pname] = {
            "portal": p["portal_url"],
            "method": method,
            "sources": sources,
            "code": build_code(pname, method, sources, p["portal_url"],
                               [c["name"] for c in cities]),
            "depts": [{"n": r["name"], "u": r.get("portal_url", ""), "o": r.get("order", 999)}
                      for r in dlist[:18]],
            "cities": [{"n": r["name"], "u": r["portal_url"]} for r in cities[:18]],
        }
    json.dump(rules, open("extraction_rules.json", "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    print("extraction_rules.json:", len(rules), "省")


if __name__ == "__main__":
    main()
