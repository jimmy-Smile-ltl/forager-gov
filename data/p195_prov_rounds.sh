#!/bin/bash
# P195 逐省补全: 按缺口数从大到小逐省跑（P195_PROV 过滤 + 单写者）。
# 用法: nohup bash data/p195_prov_rounds.sh >> /tmp/p195_prov.log 2>&1 &
cd "$(dirname "$0")/.." || exit 1

PROVS="河北省 广东省 湖南省 安徽省 山东省 河南省 江苏省 内蒙古自治区 湖北省 浙江省 吉林省 云南省 甘肃省 海南省 山西省 辽宁省 四川省 福建省 江西省 上海市 黑龙江省 重庆市 青海省 新疆维吾尔自治区 西藏自治区"
for prov in $PROVS; do
  echo "═══ P195 逐省: $prov 开始 $(date '+%F %T') ═══"
  P195_PROV="$prov" BROWSER_TIERS=off P195_WORKERS=8 uv run python data/p195_county_portal_fill.py \
    || echo "$prov 异常退出（继续下一省）"
  echo "═══ P195 逐省: $prov 结束 $(date '+%F %T') ═══"
done
echo "═══ 逐省轮全部完成 $(date '+%F %T')，重建视图 ═══"
(cd data && uv run python p22_split_data.py) || echo "p22 失败"
cp 模板.html 中国政府网站体系.html
uv run python data/p99_weekend_check.py || true
uv run python data/p195_prov_audit.py || true
echo "═══ 视图已刷新 ═══"
