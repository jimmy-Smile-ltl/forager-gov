# -*- coding: utf-8 -*-
"""P175j: 提取规则脱敏——WAF/JS 壳攻克方法统一抽象为 smart_fetch(url)，
获取真实 HTML 后的提取逻辑保留公开。"""
import json, re

rules = json.load(open("extraction_rules.json", encoding="utf-8"))

REPL = [
    (r"curl_cffi → iv8 → nodenv → RsSpider/sdenv → Drission", "smart_fetch 分级获取"),
    (r"curl_cffi→iv8→nodenv→RsSpider→Drission 五级降级", "smart_fetch 分级获取"),
    (r"iv8 → nodenv → RsSpider/sdenv → D\S*", "smart_fetch 分级获取"),
    (r"iv8→nodenv→RsSpider→Drission 五级降级", "smart_fetch 分级获取"),
    (r"nodenv → RsSpider/sdenv → Drission", "smart_fetch"),
    (r"nodenv→RsSpider→Drission 五级降级", "smart_fetch 分级获取"),
    (r"RsSpider/sdenv → Drission", "smart_fetch"),
    (r"RsSpider→Drission 五级降级", "smart_fetch 分级获取"),
    (r"瑞数 WAF → 百度 SERP 挖 [\w.]+ 子域 \+ 各子域标题定名", "门户有访问控制 → smart_fetch(url) 获取真实 HTML 后提取"),
    (r"瑞数 WAF 站点专栏——百度 SERP 挖路径/CloakBrowser 渲染降级链", "有访问控制的站点专栏——smart_fetch(url) 获取真实 HTML"),
    (r"瑞数 WAF 站点（首页 JS 挑战）需浏览器渲染后再提取——", "有访问控制的站点调用 smart_fetch(url) 获取真实 HTML 后再提取——"),
    (r"瑞数 WAF 站点，如 国防部/卫健委/海关总署等", "有访问控制的站点（如部分中央部委）"),
    (r"瑞数 WAF 页面", "有访问控制的页面"),
    (r"SERP 挖 [\w.]+ 子域", "smart_fetch(url) 获取真实 HTML"),
    (r"SERP 挖路径 / CloakBrowser 渲染降级链", "smart_fetch(url) 获取真实 HTML"),
    (r"SERP 挖路径/CloakBrowser 渲染降级链", "smart_fetch(url) 获取真实 HTML"),
    (r"SERP 挖路径 / 浏览器渲染，见文末降级链", "smart_fetch(url) 获取真实 HTML，见文末获取说明"),
    (r"CloakBrowser CDP \+ DrissionPage 方案", "smart_fetch 方案"),
    (r"CloakBrowser CDP \+ DrissionPage", "smart_fetch 渲染提取"),
    (r"CloakBrowser CDP 方案", "smart_fetch 方案"),
    (r"CloakBrowser 渲染降级链", "smart_fetch 获取链"),
    (r"CloakBrowser 独立 Chromium \+ DrissionPage 直连 CDP 渲染", "smart_fetch(url) 渲染提取"),
    (r"DrissionPage 直连 CDP 渲染", "smart_fetch 渲染提取"),
    (r"DrissionPage 方案", "smart_fetch 方案"),
    (r"DrissionPage", "smart_fetch"),
    (r"p16_browser_footer\.py CloakBrowser CDP 方案", "采集代码归档中的浏览器获取方案"),
    (r"p16_browser_footer\.py 与 util/smart_fetch\.py", "util/smart_fetch.py"),
    (r"p16_browser_footer\.py（CloakBrowser CDP \+ DrissionPage）", "采集代码归档"),
    (r"见文末降级链", "见文末获取说明"),
]

changed = 0
for k, r in rules.items():
    if not isinstance(r, dict): continue
    for f in ("code", "method", "sources"):
        blob = r.get(f)
        if not isinstance(blob, str): continue
        orig = blob
        for pat, rep in REPL:
            blob = re.sub(pat, rep, blob)
        if blob != orig:
            r[f] = blob
            changed += 1

json.dump(rules, open("extraction_rules.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print(f"p175j: 脱敏规则 {changed} 条")
