#!/bin/bash
# P198+P199 周末循环: 五系统市级补全 + 市级政府部门采集
# 每 3 小时一轮, 轮前等 p195 轮间休眠期（marker 数变化或进程不在）再启动,
# 避免两循环并发写 tree.json。单写者纪律不变。
# 2026-11-17 单例锁: mkdir 原子锁防双实例(曾多次双循环互相覆盖 tree.json)
if ! mkdir /tmp/p198loop.lockdir 2>/dev/null; then
  echo "$(date '+%F %T') 已有 p198_loop 实例运行, 本实例退出" >> /tmp/p198_loop.log
  exit 0
fi
trap 'rmdir /tmp/p198loop.lockdir' EXIT
cd "$(dirname "$0")/.." || exit 1
ROUND=0
while true; do
  ROUND=$((ROUND+1))
  # 等 p195 不在轮内（p195 轮内特征: 无「视图已刷新」新增且进程存在;
  # 简化: 检查 p195_county_portal_fill.py 进程不在跑）
  while pgrep -f "p195_county_portal_fill.py" > /dev/null; do sleep 60; done
  echo "═══ 周末任务 第 $ROUND 轮开始 $(date '+%F %T') ═══"
  (cd data && BROWSER_TIERS=off PYTHONUNBUFFERED=1 uv run python p198_city_tiao_fill.py) >> /tmp/p198.log 2>&1
  # 2026-11-16 P199_LIGHT=1: 部门采集纯 curl 快失败链（反爬区如渝中区曾触发
  # smart_fetch 浏览器层 C 级阻塞, signal.alarm 打不断, 100% CPU 空转 5.5h）
  (cd data && P199_LIGHT=1 BROWSER_TIERS=off PYTHONUNBUFFERED=1 uv run python p199_city_dept_fill.py) >> /tmp/p199.log 2>&1
  # p201 中院补全(轮询重试 fetch 失败的高院) + p202 条→块同步
  (cd data && BROWSER_TIERS=off PYTHONUNBUFFERED=1 uv run python p201_court_zy_fill.py) >> /tmp/p201.log 2>&1
  (cd data && uv run python p202_court_blk_sync.py) >> /tmp/p201.log 2>&1
  # p203 五系统地级市补全(省人大/政协/检察院/纪委官网市级链接区块)
  (cd data && P203_LIGHT=1 BROWSER_TIERS=off PYTHONUNBUFFERED=1 uv run python p203_city_5sys_fill.py) >> /tmp/p203.log 2>&1
  # p204 五系统地级市·市门户导航+SERP严格验证兜底(每轮限量 150)
  (cd data && P204_LIMIT=150 P204_LIGHT=1 BROWSER_TIERS=off PYTHONUNBUFFERED=1 uv run python p204_city_5sys_deep.py) >> /tmp/p204.log 2>&1
  # p206 缺口城市门户导航深挖(组织机构栏目页, smart_fetch)
  (cd data && BROWSER_TIERS=off PYTHONUNBUFFERED=1 uv run python p206_city_portal_nav.py) >> /tmp/p206.log 2>&1
  # p207 法院同级互链(中院官网友情链接区块=权威互链)
  (cd data && BROWSER_TIERS=off PYTHONUNBUFFERED=1 uv run python p207_court_peer_links.py) >> /tmp/p207.log 2>&1
  # p208 五系统同级互链(市政协/人大官网友情链接区块, 按 P208_SYS 轮换)
  (cd data && for s in zx rd jcy jw; do P208_SYS=$s BROWSER_TIERS=off PYTHONUNBUFFERED=1 uv run python p208_city_peer_links.py; done) >> /tmp/p208.log 2>&1
  # p213 医疗系统(卫生健康)条系统: 市级卫健委补全, miss 项轮间重试(每轮限量 100)
  (cd data && P213_LIMIT=100 BROWSER_TIERS=off PYTHONUNBUFFERED=1 uv run python p213_medical_system.py) >> /tmp/p213.log 2>&1
  (cd data && BROWSER_TIERS=off PYTHONUNBUFFERED=1 uv run python p200_func_fill.py) >> /tmp/p200.log 2>&1
  echo "═══ 周末任务 第 $ROUND 轮采集完成 $(date '+%F %T')，重建视图 ═══"
  (cd data && uv run python p22_split_data.py) >> /tmp/p198.log 2>&1
  cp 模板.html 中国政府网站体系.html
  uv run python data/p99_weekend_check.py >> /tmp/p198.log 2>&1 || true
  echo "═══ 周末任务 第 $ROUND 轮结束 $(date '+%F %T')，3 小时后下轮 ═══"
  sleep 10800
done
