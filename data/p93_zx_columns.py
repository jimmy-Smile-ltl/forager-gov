# -*- coding: utf-8 -*-
"""P93: 抓省政协官网「市县政协」栏目页。"""
import json, subprocess
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
COLUMNS = {
    "吉林省": ("http://www.jlzx.gov.cn/", "./sxzx/"),
    "天津市": ("http://www.tjszx.gov.cn/", "https://www.tjszx.gov.cn/qxzx/index.shtml"),
    "宁夏回族自治区": ("http://www.nxzx.gov.cn/", "http://www.nxzx.gov.cn/sxzx"),
    "山东省": ("http://www.sdzx.gov.cn/", "/channels/ch03167/"),
    "江苏省": ("http://www.jszx.gov.cn/", "./sxzx/"),
    "江西省": ("http://jxzx.jxnews.com.cn/", "//jxzx.jxnews.com.cn/gdhc/index.shtml"),
    "河北省": ("http://www.hebzx.gov.cn/", "/zxgz/sxzx"),
    "河南省": ("http://www.hnzx.gov.cn/", "/sxzx/"),
    "浙江省": ("http://www.zjzx.gov.cn/", "/sxdt"),
    "海南省": ("http://www.hainanzx.gov.cn/", "https://www.hainanzx.gov.cn/sxzx/"),
    "湖南省": ("http://www.hunanzx.gov.cn/", "/hnzx/wzsyszx/szzx/index.html"),
    "辽宁省": ("http://www.lnzx.gov.cn/", "/lnzx/sxzx/index.shtml"),
}
import urllib.parse
for pn, (base, col) in COLUMNS.items():
    u = urllib.parse.urljoin(base, col)
    fn = f"/tmp/zxcol_{pn}.html"
    try:
        r = subprocess.run(["curl", "-s", "--compressed", "-L", "--max-time", "18",
                            "-A", UA, u, "-o", fn], capture_output=True, timeout=25)
        import os
        print(f"{pn}: {os.path.getsize(fn)} 字节 ({u[:70]})")
    except Exception as e:
        print(f"{pn}: 失败 {str(e)[:50]}")
