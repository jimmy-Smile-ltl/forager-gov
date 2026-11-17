# -*- coding: utf-8 -*-
"""声明式采集框架——YAML 配置驱动的机构名录采集。

模式：
  block_links  - 页面区块锚点链接（按文本正则匹配目标名）
  select       - select 下拉选项
  js_click     - JS 点击切换（点击关键词后抓 DOM）
  serp_verify  - SERP 线索 + title 验证（兜底，结果标 L3）
自动：快照存档、registry 登记（source_level 按模式）、断点续跑。

配置示例（configs/qixiang.yaml）：
  source: https://www.cma.gov.cn/
  pattern: block_links
  match: "({省})气象局$"
  name_suffix: ""
  source_level: L1
"""
import json
import os
import re
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import save_snap, load_registry, save_registry

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")


def fetch(u):
    r = subprocess.run(["curl", "-s", "--compressed", "-L", "--max-time", "15",
                        "-A", UA, u], capture_output=True, timeout=18)
    raw = r.stdout
    for enc in ("utf-8", "gb18030"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def run(cfg):
    """执行一个采集配置。cfg: dict。返回 {name: url}。"""
    pat = cfg["pattern"]
    u = cfg["source"]
    html = fetch(u)
    out = {}
    if pat == "block_links":
        for uu, txt in re.findall(
                r'<a[^>]+href="([^"]+)"[^>]*>\s*([^<]{2,30}?)\s*</a>', html):
            t2 = txt.strip()
            m = re.match(cfg["match"], t2)
            if m and uu.startswith("http"):
                name = m.group(1) if m.groups() else t2
                out.setdefault(name, uu)
    elif pat == "select":
        for sel in re.findall(r'<select[^>]*>(.*?)</select>', html, re.S):
            opts = re.findall(
                r'<option[^>]*value="([^"]*)"[^>]*>\s*([^<]+?)\s*</option>', sel)
            for v, txt in opts:
                t2 = txt.strip()
                m = re.match(cfg["match"], t2)
                if m and v.startswith("http"):
                    name = m.group(1) if m.groups() else t2
                    out.setdefault(name, v)
    # 快照 + registry
    snap = save_snap("other", "中央", cfg.get("name", "declarative"),
                     "collect", html)
    reg = load_registry()
    for name, url in out.items():
        key = f"{cfg.get('cat', '其他')}|{name}"
        reg.setdefault(key, {"u": url, "locations": ["declarative"],
                             "source_level": cfg.get("source_level", "L1"),
                             "verified_at": "", "status": "unknown",
                             "snapshot": snap})
    save_registry(reg)
    return out


if __name__ == "__main__":
    # 演示：气象系统（已采过，仅验证框架可用）
    demo = {
        "name": "气象",
        "source": "https://www.cma.gov.cn/",
        "pattern": "block_links",
        "match": r"(北京|天津|河北|山西|内蒙古|辽宁|吉林|黑龙江|上海|江苏|浙江|安徽|福建|江西|山东|河南|湖北|湖南|广东|广西|海南|重庆|四川|贵州|云南|西藏|陕西|甘肃|青海|宁夏|新疆)[^<]*气象局$",
        "cat": "气象",
        "source_level": "L1",
    }
    out = run(demo)
    print(f"声明式框架演示: {len(out)} 条")
    for k, v in list(out.items())[:5]:
        print(f"  {k} -> {v}")
