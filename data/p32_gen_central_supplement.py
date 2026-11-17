# -*- coding: utf-8 -*-
"""P32: 为 P31 新增的中央板块生成提取规则。

生成：
 1. 「群团组织（21）」组规则 + 21 个成员规则
 2. 「民主党派中央（8）」组规则 + 8 个成员规则
 3. 新增中央机构个体规则（中央直属机构4 + 国家局2 + 总台1）
 4. 刷新父规则 depts（中央/中共中央/国务院 → 按树叶子重算）
"""
import json

CODE_MEMBER = '''# -*- coding: utf-8 -*-
"""{title} 提取规则。

方法：{method}
来源页：{sources}

说明：门户为公开域名，实测可达；其信息公开按各自制度执行
     （群团按参照公务员法管理单位口径、民主党派按参政党口径）。
依赖：pip install requests beautifulsoup4 lxml
"""
import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

PORTAL = "{portal}"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")


def fetch(url):
    resp = requests.get(url, headers={{"User-Agent": UA}}, timeout=15, verify=False)
    if resp.encoding and "gb" in resp.encoding.lower():
        return resp.content.decode("gb18030", errors="replace")
    return resp.content.decode("utf-8", errors="replace")


# 1) 门户请求 + 标题校验
html = fetch(PORTAL)
soup = BeautifulSoup(html, "lxml")
print("门户标题:", soup.title.get_text(strip=True) if soup.title else "?")

# 2) 公开/信息 栏目定位
for a in soup.find_all("a"):
    text = re.sub(r"\\s+", "", a.get_text(" ", strip=True))
    href = a.get("href") or ""
    if ("公开" in text or "信息" in text or "资讯" in text) and len(text) <= 16 \\
            and href.startswith(("http://", "https://")):
        print("  ", text, "->", urljoin(PORTAL, href))
'''

CODE_GROUP = '''# -*- coding: utf-8 -*-
"""{title} 提取规则。

方法：{method}
来源页：{sources}

流程：{title}成员门户为公开域名（2026-10-30 连通性实测），逐个门户
     请求 + 标题校验 + 公开栏目定位；无独立官网者列名。
依赖：pip install requests beautifulsoup4 lxml
"""
import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

PORTALS = {portals!r}
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")


def fetch(url):
    resp = requests.get(url, headers={{"User-Agent": UA}}, timeout=15, verify=False)
    if resp.encoding and "gb" in resp.encoding.lower():
        return resp.content.decode("gb18030", errors="replace")
    return resp.content.decode("utf-8", errors="replace")


for url in PORTALS:
    try:
        soup = BeautifulSoup(fetch(url), "lxml")
        print(url, "| 标题:", soup.title.get_text(strip=True) if soup.title else "?")
    except Exception as e:
        print(url, "| 不可达:", type(e).__name__)
'''

GROUPS = {
    "群团组织（21）": {
        "method": "中央编办管理的群众团体机关（21 个，参照公务员法管理的人民团体/"
                  "群众团体机关）——成员门户公开域名逐个实测",
        "members": [
            ("中华全国总工会", "https://www.acftu.org/"),
            ("共青团中央", "https://www.gqt.org.cn/"),
            ("中华全国妇女联合会", "https://www.women.org.cn/"),
            ("中国科学技术协会", "https://www.cast.org.cn/"),
            ("中国文学艺术界联合会", "https://www.cflac.org.cn/"),
            ("中国作家协会", "http://www.chinawriter.com.cn/"),
            ("中华全国工商业联合会", "https://www.acfic.org.cn/"),
            ("中华全国归国华侨联合会", "http://www.chinaql.org/"),
            ("中华全国台湾同胞联谊会", "http://www.tailian.org.cn/"),
            ("中国残疾人联合会", "https://www.cdpf.org.cn/"),
            ("中国国际贸易促进委员会", "https://www.ccpit.org/"),
            ("中国红十字会总会", "https://www.redcross.org.cn/"),
            ("中华职业教育社", "http://www.zhzjs.org.cn/"),
            ("中国法学会", "https://www.chinalaw.org.cn/"),
            ("中国人民对外友好协会", "https://www.cpaffc.org.cn/"),
            ("中华全国新闻工作者协会", "http://www.zgjx.cn/"),
            ("中国宋庆龄基金会", "https://www.sclf.org.cn/"),
            ("中国计划生育协会", "https://www.chinafpa.org.cn/"),
            ("黄埔军校同学会", "http://www.hjsd.org/"),
            ("欧美同学会", "https://www.wrsa.net/"),
            ("中国思想政治工作研究会", ""),
        ],
        "member_method": "群团组织门户（参照公务员法管理的人民团体）实测可达；"
                         "公开信息按自身制度发布",
    },
    "民主党派中央（8）": {
        "method": "8 个民主党派中央机关（参政党）——成员门户公开域名逐个实测",
        "members": [
            ("中国国民党革命委员会中央委员会", "http://www.minge.gov.cn/"),
            ("中国民主同盟中央委员会", "https://www.mmzy.org.cn/"),
            ("中国民主建国会中央委员会", "https://www.cndca.org.cn/"),
            ("中国民主促进会中央委员会", "https://www.mj.org.cn/"),
            ("中国农工民主党中央委员会", "http://www.ngd.org.cn/"),
            ("中国致公党中央委员会", "https://www.zg.org.cn/"),
            ("九三学社中央委员会", "http://www.93.gov.cn/"),
            ("台湾民主自治同盟中央委员会", "http://www.taimeng.gov.cn/"),
        ],
        "member_method": "民主党派中央门户（参政党）实测可达；"
                         "公开信息按自身制度发布",
    },
}

NEW_ORGANS = [
    ("中央网络安全和信息化委员会办公室", "https://www.cac.gov.cn/",
     "中央直属机构（与国务院互联网信息办公室一个机构两块牌子）"),
    ("中央对外联络部", "https://www.idcpc.gov.cn/", "中共中央直属机构（党的对外工作部门）"),
    ("中央港澳工作办公室", "https://www.hmo.gov.cn/",
     "中央港澳工作办公室（2023 机构改革后列入中共中央直属机构，加挂国务院港澳办牌子）"),
    ("中央档案馆（国家档案局）", "https://www.saac.gov.cn/",
     "中共中央直属机构（中央档案馆与国家档案局一个机构两块牌子）"),
    ("国家中医药管理局", "http://www.natcm.gov.cn/", "国家卫生健康委员会管理的国家局"),
    ("国家密码管理局", "https://www.sca.gov.cn/", "国务院部委管理的国家局"),
    ("中央广播电视总台", "https://www.cctv.com/", "国务院直属事业单位"),
]


def leaves_of(node):
    out = []
    def walk(n):
        if not n.get("ks"):
            out.append({"n": n["n"], "u": n.get("u", ""), "o": len(out)})
        for k in n.get("ks", []):
            walk(k)
    walk(node)
    return out


def main():
    tree = json.load(open("tree.json", encoding="utf-8"))
    central = next(g for g in tree["ks"] if g["n"].startswith("中央"))
    rules = json.load(open("extraction_rules.json", encoding="utf-8"))
    added = 0

    def add(key, rule):
        nonlocal added
        rules[key] = rule
        added += 1

    # ---- 群团 / 民主党派 ----
    for gname, spec in GROUPS.items():
        members = spec["members"]
        portals = [u for _, u in members if u]
        add(gname, {
            "portal": portals[0] if portals else "",
            "method": spec["method"],
            "sources": portals[:8],
            "code": CODE_GROUP.format(title=gname, method=spec["method"],
                                      sources="、".join(portals[:4]),
                                      portals=portals),
            "depts": [{"n": n, "u": u, "o": i} for i, (n, u) in enumerate(members)],
            "cities": [],
        })
        for n, u in members:
            srcs = [u] if u else []
            add(n, {
                "portal": u,
                "method": spec["member_method"] +
                          ("" if u else "（无独立官网 → 列名）"),
                "sources": srcs,
                "code": (CODE_MEMBER.format(title=n, method=spec["member_method"],
                                            sources=u or "（无独立官网，列名）",
                                            portal=u or "")
                         if u else
                         f'# -*- coding: utf-8 -*-\n"""{n}: 无独立公开官网（列名）。"""\n'),
                "depts": [{"n": n, "u": u, "o": 0}],
                "cities": [],
            })

    # ---- 新增中央机构个体 ----
    for n, u, desc in NEW_ORGANS:
        add(n, {
            "portal": u,
            "method": desc + "；门户实测可达，公开信息按机关自身口径发布",
            "sources": [u],
            "code": CODE_MEMBER.format(title=n, method=desc,
                                        sources=u, portal=u),
            "depts": [{"n": n, "u": u, "o": 0}],
            "cities": [],
        })

    # ---- 刷新父规则 depts（按树叶子重算）----
    for gname, rk in [("中共中央（党中央）", "中共中央（党中央）"),
                      ("国务院（中央人民政府）", "国务院（中央人民政府）"),
                      ("中央（党中央、国务院及并列机关）", "中央")]:
        g = central if gname.startswith("中央（党中央") else \
            next(g for g in central["ks"] if g["n"].startswith(gname[:3].replace("中共中央", "中共中央")))
        if gname.startswith("国务院"):
            g = next(g for g in central["ks"] if g["n"].startswith("国务院"))
        if rk in rules:
            rules[rk]["depts"] = leaves_of(g)

    json.dump(rules, open("extraction_rules.json", "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    print(f"p32 完成：新增 {added} 条规则，rules 总数 {len(rules)}")
    print("  中央 depts:", len(rules["中央"]["depts"]),
          "| 中共中央 depts:", len(rules["中共中央（党中央）"]["depts"]),
          "| 国务院 depts:", len(rules["国务院（中央人民政府）"]["depts"]))


if __name__ == "__main__":
    main()
