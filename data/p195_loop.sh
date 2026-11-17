#!/bin/bash
# P195 定期重试循环: 每轮全量跑县级门户补全（渲染子进程隔离 + dps 兜底），
# 90 分钟一轮，覆盖 fetch_fail[blocked]（德阳类 IP 封禁）与 no_nav（JS 壳）重试。
# 单写者纪律: 本循环运行期间不得再手工启动 p195_county_portal_fill.py。
# 用法: nohup bash data/p195_loop.sh >> /tmp/p195_loop.log 2>&1 &
cd "$(dirname "$0")/.." || exit 1

ROUND=0
while true; do
  ROUND=$((ROUND+1))
  echo "═══ P195 第 $ROUND 轮开始 $(date '+%F %T') ═══"
  BROWSER_TIERS=off P195_WORKERS=8 uv run python data/p195_county_portal_fill.py \
    || echo "第 $ROUND 轮异常退出（继续下轮）"
  echo "═══ P195 第 $ROUND 轮结束 $(date '+%F %T')，重建视图 ═══"
  # 数据更新后跑 p22 刷新三视图（gov_data.js/data_js/quality.js/gen_viz），
  # 再同步名录 HTML（p99 时间戳检查项）
  (cd data && uv run python p22_split_data.py) || echo "p22 失败"
  cp 模板.html 中国政府网站体系.html
  uv run python data/p99_weekend_check.py || true
  uv run python data/p195_prov_audit.py || true
  # 轮间清理渲染残留（子进程 os._exit 兜底不严时防堆积）
  pkill -9 -f "user-data-dir=/tmp/p195r_" 2>/dev/null
  # 孤儿 Chromium Helper 清扫（ppid=1 的泄漏进程; 在用的浏览器有活父进程不受影响）
  ps -eo pid,ppid,command | awk '/Chromium|chrome-mac/ && $2==1 {print $1}' | xargs kill -9 2>/dev/null
  rm -rf /tmp/p195r_* 2>/dev/null
  echo "═══ 视图已刷新，90 分钟后下轮 ═══"
  sleep 5400
done
