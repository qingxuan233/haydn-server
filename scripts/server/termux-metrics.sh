#!/data/data/com.termux/files/usr/bin/bash
# Termux 侧系统指标采集器：proot 内无法读取 /proc/stat、/proc/uptime，
# 所以由 Termux 每 10 秒用 /system/bin/top + /system/bin/uptime 采集，
# 写到 $HOME/server-metrics.txt，proot 内 API 通过 /hosthome 读取。
OUT="$HOME/server-metrics.txt"
while true; do
  UP=$(/system/bin/uptime 2>/dev/null | head -1)
  TOP=$(/system/bin/top -b -n1 2>/dev/null)
  CPU=$(printf '%s\n' "$TOP" | grep -m1 '%cpu')
  {
    printf 'ts=%s\n' "$(date +%s)"
    printf 'uptime_line=%s\n' "$UP"
    printf 'cpu_line=%s\n' "$CPU"
  } > "$OUT.tmp" 2>/dev/null && mv "$OUT.tmp" "$OUT" 2>/dev/null
  sleep 10
done
