#!/system/bin/sh
# Wi-Fi 守护：省电态纠正 + 掉线告警/计数 + 重连后复查省电态。
# 由 telemetry-loop.sh 每 300 秒调用；也可手工执行。
# 2026-11-15 加固：掉线（无 IPv4）时落 alerts.log 并发通知、累计掉线次数，
#   重连（down/missing -> up）后立刻复查并把省电态纠正回 off；状态存 run/wifi-guard.state。
# 演练开关（仅验证用，不参与常规运行）：WIFI_DEV 换探测网卡，WIFI_FORCE_DOWN=1 模拟无 IPv4。
LOG=/data/server/logs/wifi-guard.log
ALERT=/data/server/logs/alerts.log
STATE=/data/server/run/wifi-guard.state
DEV=${WIFI_DEV:-wlan0}
TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)

sz=$(stat -c %s "$LOG" 2>/dev/null || echo 0)
[ "$sz" -gt 262144 ] && mv -f "$LOG" "$LOG.1"

LAST=up
DOWNS=0
if [ -r "$STATE" ]; then
  read -r LAST DOWNS < "$STATE" 2>/dev/null || true
  [ -n "$LAST" ] || LAST=up
  case "$DOWNS" in ''|*[!0-9]*) DOWNS=0 ;; esac
fi

save_state() { echo "$1 $2" > "$STATE" 2>/dev/null; }

# 省电态：0=已纠正 1=本来就是 off 2=读取/写入失败
fix_power_save() {
  PS=$(iw dev "$DEV" get power_save 2>&1)
  case "$PS" in
    *"Power save: off"*) return 1 ;;
    *"Power save: on"*)
      if iw dev "$DEV" set power_save off >/dev/null 2>&1; then
        echo "$TS CORRECTED power_save on->off" >> "$LOG"
        return 0
      fi
      echo "$TS FAIL set power_save off rc=$?" >> "$LOG"
      echo "$TS ALERT_NOTIFY wifi power_save correction failed" >> "$ALERT"
      return 2
      ;;
    *)
      echo "$TS FAIL iw read: $PS" >> "$LOG"
      echo "$TS ALERT_NOTIFY wifi power_save read failed" >> "$ALERT"
      return 2
      ;;
  esac
}

if ! ip link show "$DEV" >/dev/null 2>&1; then
  if [ "$LAST" != "missing" ]; then
    echo "$TS FAIL $DEV missing" >> "$LOG"
    echo "$TS ALERT_NOTIFY wifi $DEV missing" >> "$ALERT"
    cmd notification post -S bigtext -t "haydn Wi-Fi 异常" haydn_wifi "$DEV 网卡不存在" >/dev/null 2>&1
  fi
  save_state missing "$DOWNS"
  exit 1
fi

IP4=$(ip -4 addr show "$DEV" 2>/dev/null | grep -c 'inet ')
[ "${WIFI_FORCE_DOWN:-0}" = "1" ] && IP4=0

if [ "$IP4" -eq 0 ]; then
  DOWNS=$((DOWNS + 1))
  echo "$TS FAIL $DEV down no-ipv4 downs=$DOWNS" >> "$LOG"
  # 首次掉线或每 12 次（约 1 小时）告警一次，避免刷屏
  if [ "$LAST" != "down" ] || [ $((DOWNS % 12)) -eq 0 ]; then
    echo "$TS ALERT_NOTIFY wifi link down dev=$DEV downs=$DOWNS" >> "$ALERT"
    cmd notification post -S bigtext -t "haydn Wi-Fi 掉线" haydn_wifi "$DEV 无 IPv4，累计掉线 ${DOWNS} 次" >/dev/null 2>&1
  fi
  save_state down "$DOWNS"
  exit 1
fi

if [ "$LAST" = "down" ] || [ "$LAST" = "missing" ]; then
  echo "$TS RECOVER $DEV link up after downs=$DOWNS" >> "$LOG"
  fix_power_save
  save_state up "$DOWNS"
  exit 0
fi

fix_power_save
save_state up "$DOWNS"
exit 0
