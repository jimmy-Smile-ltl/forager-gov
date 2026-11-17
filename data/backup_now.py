# -*- coding: utf-8 -*-
"""数据快照：tree.json / extraction_rules.json / site_registry.json →
backups/<日期>/。p22 拆分前自动调用；也可手动/定时调用。"""
import datetime
import json
import os
import shutil

TODAY = datetime.date.today().strftime("%Y%m%d")
DST = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "backups", TODAY)
os.makedirs(DST, exist_ok=True)
for fn in ("tree.json", "extraction_rules.json", "site_registry.json"):
    src = os.path.join(os.path.dirname(os.path.abspath(__file__)), fn)
    if os.path.exists(src):
        dst = os.path.join(DST, fn)
        if not os.path.exists(dst):   # 当日首次快照；已有则覆盖
            shutil.copy(src, dst)
        else:
            shutil.copy(src, dst)
print(f"快照已存: {DST}")
