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
FILES = ["中国政府网站体系.html", "gov-tree.html", "map_view.js", "tree_view.js", "gov_data.js"]
# 站点数据目录（保持相对路径不变: data_js/... 与 data/geo/...）
DIRS = ["data_js", os.path.join("data", "geo")]

MAX_FILE = 25 * 1024 * 1024      # Cloudflare Pages 单文件 25 MiB
MAX_FILES = 20000                # 单次部署 20000 文件
BAD_EXT = {".py", ".json", ".env", ".log", ".tmp", ".md", ".bak"}


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

    # 动态加载目标: data_js/{manifest,quality} + modules/rules + geo 关键文件
    for p in ("data_js/manifest.js", "data_js/quality.js",
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
