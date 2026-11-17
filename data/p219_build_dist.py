#!/usr/bin/env python
# p219 站点发布包构建（Cloudflare Pages 部署用，2026-11-17 用户指令「就用 Cloudflare Pages，帮我准备 dist」）
# 只拷站点运行所需资产（HTML/视图脚本 + 统一数据 + data_js 模块/规则 + geo 边界），
# 不含采集脚本、state、快照、备份等——避免把中间数据和路径暴露到公网。
# 校验三道:
#   1) 引用完整性: 两 HTML 里出现的本地资源 + manifest/geo 关键文件必须在 dist 内
#   2) Pages 限额: 单文件 <= 25 MiB、单次部署 <= 20000 文件
#   3) 泄漏检查: dist 内不得出现 .py/.json/.env 等非站点文件
# 只用标准库（无第三方依赖）——Cloudflare Pages Git 构建可直接调用:
#   构建命令 python3 data/p219_build_dist.py / 输出目录 dist / 根目录 /
# 用法: (cd data && uv run python p219_build_dist.py)
# 直传兜底: npx wrangler pages deploy dist --project-name=<项目名>
import os
import re
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(ROOT, "dist")

# 站点根文件（与 HTML/JS 引用一一对应）
FILES = ["中国政府网站体系.html", "gov-tree.html", "map_view.js", "tree_view.js",
         "gov_data.js", "gov_data_records.js"]
# 站点数据目录（保持相对路径不变: data_js/... 与 data/geo/...）
DIRS = ["data_js", os.path.join("data", "geo")]

# 静态资源缓存策略（Cloudflare Pages `_headers`）: 网络到 pages.dev 的 RTT 较高
# （实测 geo 文件 TTFB 1-2.5s），重复访问必须命中浏览器缓存; 版本通过 HTML/JS
# 里的 ?v= 戳控制——geo 改动时同步改 map_view.js 的 GEO_VER。
HEADERS = """/data/geo/*
  Cache-Control: public, max-age=31536000, immutable
/data_js/*
  Cache-Control: public, max-age=3600
/gov_data.js
  Cache-Control: public, max-age=86400
/gov_data_records.js
  Cache-Control: public, max-age=86400
/map_view.js
  Cache-Control: public, max-age=86400
/tree_view.js
  Cache-Control: public, max-age=86400
"""

MAX_FILE = 25 * 1024 * 1024      # Cloudflare Pages 单文件 25 MiB
MAX_FILES = 20000                # 单次部署 20000 文件
BAD_EXT = {".py", ".json", ".env", ".log", ".tmp", ".md", ".bak"}

# 站点根入口: Pages 默认去 .html 后缀（/中国政府网站体系.html 会 308 到
# /中国政府网站体系），根路径 "/" 需 index.html 才有响应——做一个跳转页。
INDEX_HTML = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>中国政府网站体系</title>
<meta http-equiv="refresh" content="0; url=./中国政府网站体系.html">
<script>location.replace("./中国政府网站体系.html" + location.hash);</script>
</head>
<body>
<p>正在进入 <a href="./中国政府网站体系.html">中国政府网站体系</a> …</p>
<p>树图 / 地图：<a href="./gov-tree.html">gov-tree</a></p>
</body>
</html>
"""


def build_geo_bundles(geo_dir):
    """省级「县级边界包」: dist/data/geo/geo_bundle_{省码}.js =
    {市级adcode: FeatureCollection}。省图打开后空闲预取该包 → 点任意市零请求
    （线上 pages.dev 单文件 TTFB 1-2.5s，这是省→市下钻等待的根治手段）。
    只在发布包生成（原始体积 +约22MB，与单文件内容重复，不进仓库）;
    本地 file:// 没有 bundle → map_view.js 自动回退逐文件加载。"""
    import glob
    import json as _json
    bundles = {}
    for path in glob.glob(os.path.join(geo_dir, "geo_*.js")):
        name = os.path.basename(path)
        if name.startswith("geo_bundle_"):
            continue
        m = re.fullmatch(r"geo_(\d{6})\.js", name)
        if not m:
            continue
        code = m.group(1)
        if code.endswith("0000"):
            continue                      # 省级文件自身（其内容=市级边界）
        if not code.endswith("00"):
            continue                      # 非市级文件（不存在, 防御）
        try:
            txt = open(path, encoding="utf-8").read()
            mm = re.search(r"window\.__GEO_" + code + r"__\s*=\s*(\{.*\})\s*;?\s*$",
                           txt, re.S)
            if not mm:
                continue
            obj = _json.loads(mm.group(1))
        except Exception as e:
            print("  [bundle] 解析失败", name, e)
            continue
        prov = code[:2] + "0000"
        bundles.setdefault(prov, {})[code] = obj
    n = 0
    total = 0
    for prov, mp in sorted(bundles.items()):
        out = os.path.join(geo_dir, "geo_bundle_%s.js" % prov)
        js = ("window.__GEO_BUNDLE__=window.__GEO_BUNDLE__||{};"
              "window.__GEO_BUNDLE__[%s]=%s;\n"
              % (_json.dumps(prov), _json.dumps(mp, ensure_ascii=False,
                                                separators=(",", ":"))))
        with open(out, "w", encoding="utf-8") as f:
            f.write(js)
        n += 1
        total += os.path.getsize(out)
    print(f"geo 县界包: {n} 个省, {total / 1048576:.1f} MB（点市零请求）")


def main():
    # 1) 清空并重建 dist
    if os.path.isdir(DIST):
        shutil.rmtree(DIST)
    os.makedirs(DIST)

    missing = []
    for f in FILES:
        src = os.path.join(ROOT, f)
        if not os.path.isfile(src):
            missing.append(f)
            continue
        shutil.copy2(src, os.path.join(DIST, f))
    for d in DIRS:
        src = os.path.join(ROOT, d)
        if not os.path.isdir(src):
            missing.append(d + "/")
            continue
        shutil.copytree(src, os.path.join(DIST, d))
    if missing:
        print("❌ 缺少站点资产:", ", ".join(missing))
        sys.exit(1)

    # 站点根入口（根路径 "/" → 主查看器）
    with open(os.path.join(DIST, "index.html"), "w", encoding="utf-8") as f:
        f.write(INDEX_HTML)

    # 2) 引用完整性: HTML/JS 静态引用
    refs = set()
    for f in ("中国政府网站体系.html", "gov-tree.html"):
        html = open(os.path.join(DIST, f), encoding="utf-8").read()
        for m in re.finditer(r'(?:src|href)="([^"]+\.(?:js|css))(?:\?[^"]*)?"', html):
            refs.add(m.group(1))
    absent = [r for r in sorted(refs) if not os.path.isfile(os.path.join(DIST, r))]
    if absent:
        print("❌ HTML 引用缺失:", ", ".join(absent))
        sys.exit(1)

    # `_headers`（缓存策略）+ 省级县界包（点市零请求）
    with open(os.path.join(DIST, "_headers"), "w", encoding="utf-8") as f:
        f.write(HEADERS)
    build_geo_bundles(os.path.join(DIST, "data", "geo"))

    # 动态加载目标: data_js/{manifest,quality} + modules/rules + geo 关键文件
    for p in ("index.html", "gov_data_records.js", "data_js/manifest.js", "data_js/quality.js",
              "data/geo/adcode.js", "data/geo/china.js", "data/geo/geo_index.js"):
        if not os.path.isfile(os.path.join(DIST, p)):
            print("❌ 动态数据缺失:", p)
            sys.exit(1)
    for p in ("data_js/modules", "data_js/rules", "data/geo"):
        if not os.path.isdir(os.path.join(DIST, p)):
            print("❌ 数据目录缺失:", p)
            sys.exit(1)

    # 3) 限额 + 泄漏检查 + 统计
    n_files, n_bytes, largest, bad = 0, 0, [], []
    for dirpath, _dirnames, filenames in os.walk(DIST):
        for name in filenames:
            p = os.path.join(dirpath, name)
            rel = os.path.relpath(p, DIST)
            size = os.path.getsize(p)
            n_files += 1
            n_bytes += size
            if size > MAX_FILE:
                bad.append(f"{rel} ({size / 1048576:.1f}MB > 25MiB)")
            if os.path.splitext(name)[1].lower() in BAD_EXT:
                bad.append(f"{rel} (非站点文件)")
            largest.append((size, rel))
    largest.sort(reverse=True)

    print(f"dist 文件数: {n_files:,} / {MAX_FILES:,}   总体积: {n_bytes / 1048576:.1f} MB")
    print("最大文件 top5:")
    for size, rel in largest[:5]:
        print(f"  {size / 1048576:6.1f} MB  {rel}")
    if n_files > MAX_FILES:
        bad.append(f"文件数 {n_files} 超过 {MAX_FILES}")
    if bad:
        print("❌ 限额/泄漏问题:")
        for b in bad[:20]:
            print("  ", b)
        sys.exit(1)

    print(f"✅ dist 就绪: {DIST}")
    print("   部署: npx wrangler pages deploy dist --project-name=<项目名>")


if __name__ == "__main__":
    main()
