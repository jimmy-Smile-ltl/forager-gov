#!/bin/bash
# 周末采集 supervisor: 进程存活检查 + 挂死重启（2026-11-13）
# 管三个循环: p195_loop.sh(县级90分/轮) / p198_loop.sh(周末A+B 3小时/轮)
#             / p198_start.sh(首轮启动器)
# 每 3 分钟巡检, 事件写 /tmp/weekend_sup.log
# 2026-11-17 单例锁
if ! mkdir /tmp/supervisor.lockdir 2>/dev/null; then
  echo "$(date '+%F %T') 已有 supervisor 运行, 退出" >> /tmp/weekend_sup.log
  exit 0
fi
trap 'rmdir /tmp/supervisor.lockdir' EXIT
cd /Users/jimmy/projectBaidu/官网名单-分类/政府信息公开/data
LOG=/tmp/weekend_sup.log
log(){ echo "$(date '+%F %T') $*" >> $LOG; }

restart_195(){
  if ! pgrep -f "p195_loop.sh" > /dev/null; then
    log "p195_loop 不在, 重启"
    cd /Users/jimmy/projectBaidu/官网名单-分类/政府信息公开
    nohup bash data/p195_loop.sh >> /tmp/p195_loop.log 2>&1 &
    cd data
  fi
}
restart_198(){
  if ! pgrep -f "p198_loop.sh" > /dev/null && ! pgrep -f "p198_start.sh" > /dev/null; then
    # 首轮未完成（start.sh 不在 = 首轮已跑完并已挂 loop）且 loop 不在 = loop 挂了
    if [ "$(grep -c '周末循环已挂' /tmp/p198_start.log 2>/dev/null || echo 0)" -ge 1 ]; then
      log "p198_loop 不在(已过首轮), 重启"
      cd /Users/jimmy/projectBaidu/官网名单-分类/政府信息公开
      nohup bash data/p198_loop.sh >> /tmp/p198_loop.log 2>&1 &
      cd data
    fi
  fi
}
# 卡死检测: p195 marker 2.5 小时不增且轮内在跑 = 疑似卡死
stall_check(){
  # 2026-11-14 根因修复: 「第 . 轮开始」的 . 只匹配单字符, 第 10 轮起
  # (两位数)永不匹配 → last 永久停在第 9 轮时间导致误判; 改用 [0-9]+
  local last=$(grep -E "第 [0-9]+ 轮开始" /tmp/p195_loop.log 2>/dev/null | tail -1 | grep -oE '[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}')
  if [ -z "$last" ]; then return; fi
  local ts=$(date -j -f "%Y-%m-%d %H:%M:%S" "$last" +%s 2>/dev/null)
  local now=$(date +%s)
  if [ $((now-ts)) -gt 9000 ] && pgrep -f "p195_county_portal_fill.py" > /dev/null; then
    # 2026-11-14 误杀事故修正: 只告警不杀轮——loop 自身有异常续跑机制,
    # 杀轮反而把正常跑的轮打断（第10轮被误杀实证）; 真卡死由 loop 内
    # 每请求超时自愈, 轮级超时由 p195 脚本内部处理
    log "⚠️ p195 疑似长轮(轮开始 $last 超 2.5h), 仅告警不杀"
  fi
}
while true; do
  : # 2026-11-16 县级已收敛(97.4%, 剩余为功能区/列名), p195 循环停用
  restart_198
  stall_check
  sleep 180
done
