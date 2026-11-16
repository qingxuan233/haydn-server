#!/system/bin/sh
# haydn 观测/遥测循环看门狗（宿主侧；只读检查 + 必要时重启既有循环）
# 设备路径：/data/server/bin/watchdog-loop.sh
# 用法：watchdog-loop.sh [--check-once | --loop <interval_sec>]
# 判定：telemetry-loop 进程不在（process_missing）或 telemetry.csv 末行距今 > STALE_SEC（stale_data）
#       → 都视为循环失效 → 重启 telemetry-loop.sh 并写 /data/server/logs/watchdog.log
# 说明：Android toybox awk 无 mktime()，此处用 `date -D <fmt>` 解析 ISO8601 → epoch（真机验证可用）。
# 自启：KernelSU 模块 service.sh（宿主侧 chains，supervisord 在 chroot 内看不到 /data/server/bin）。
# 回滚：从 service.sh 删除 watchdog 段 + kill $(cat /data/server/run/watchdog.pid)
STALE_SEC=900
TELEMETRY=/data/server/logs/telemetry.csv
TELEMETRY_LOOP=/data/server/bin/telemetry-loop.sh
LOG=/data/server/logs/watchdog.log
[ -f "$LOG" ] || touch "$LOG"

log() { echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) $*" >> "$LOG"; }

check_once() {
  alive=0
  pgrep -f "telemetry-loop.sh" >/dev/null 2>&1 && alive=1

  ts_str=$(tail -n 1 "$TELEMETRY" 2>/dev/null | cut -d, -f1)
  ts=$(date -u -D '%Y-%m-%dT%H:%M:%SZ' -d "$ts_str" +%s 2>/dev/null)
  now=$(date -u +%s)
  age="unknown"
  case "$ts" in ''|*[!0-9]*) : ;; *) [ -n "$ts" ] && age=$((now - ts)) ;; esac

  if [ "$alive" = "1" ] && [ "$age" != "unknown" ] && [ "$age" -le "$STALE_SEC" ]; then
    log "OK alive=1 age=${age}s"
    return 0
  fi

  if [ "$alive" = "0" ]; then reason="process_missing"; else reason="stale_data age=${age}s"; fi
  log "STALE alive=$alive age=${age}s reason=${reason} -> restart telemetry-loop"

  pgrep -f "telemetry-loop.sh" 2>/dev/null | while read -r p; do kill "$p" 2>/dev/null; done
  sleep 2
  setsid "$TELEMETRY_LOOP" >/data/server/logs/telemetry-loop.out 2>&1 &
  echo $! > /data/server/run/telemetry.pid
  sleep 8
  if pgrep -f "telemetry-loop.sh" >/dev/null 2>&1; then
    log "RESTARTED pid=$(cat /data/server/run/telemetry.pid 2>/dev/null)"
    return 0
  fi
  log "RESTART_FAILED"
  return 1
}

case "${1:---check-once}" in
  --loop)
    interval="${2:-300}"
    while :; do sleep "$interval"; check_once; done
    ;;
  --check-once|*) check_once ;;
esac
