#!/data/data/com.termux/files/usr/bin/bash
# Termux 侧综合状态采集器（每 10s）
# 输出 key=value 到 $HOME/termux-status.txt，proot 内 Console 通过 /hosthome 读取。
export HOME=/data/data/com.termux/files/home
export PREFIX=/data/data/com.termux/files/usr
export PATH="$PREFIX/bin:$PATH"
export LD_LIBRARY_PATH="$PREFIX/lib"
OUT="$HOME/termux-status.txt"
OLD="$HOME/server-metrics.txt"
TMP="$OUT.tmp"

while true; do
  UP=$(/system/bin/uptime 2>/dev/null | head -1)
  TOP=$(/system/bin/top -b -n1 2>/dev/null)
  CPU=$(printf '%s\n' "$TOP" | grep -m1 '%cpu')
  TASK=$(printf '%s\n' "$TOP" | grep -m1 'Tasks:')
  MEM=$(cat /proc/meminfo 2>/dev/null)

  BAT=$(timeout 8 termux-battery-status 2>/dev/null)
  WIFI=$(timeout 8 termux-wifi-connectioninfo 2>/dev/null)

  MEM_TOTAL=$(printf '%s\n' "$MEM" | awk '/^MemTotal:/{print $2}')
  MEM_AVAIL=$(printf '%s\n' "$MEM" | awk '/^MemAvailable:/{print $2}')
  SWAP_TOTAL=$(printf '%s\n' "$MEM" | awk '/^SwapTotal:/{print $2}')
  SWAP_FREE=$(printf '%s\n' "$MEM" | awk '/^SwapFree:/{print $2}')

  DISK=$(/system/bin/df -kP /data 2>/dev/null | tail -1)
  DISK_TOTAL=$(printf '%s\n' "$DISK" | awk '{print $2}')
  DISK_USED=$(printf '%s\n' "$DISK" | awk '{print $3}')
  DISK_FREE=$(printf '%s\n' "$DISK" | awk '{print $4}')
  DISK_PCT=$(printf '%s\n' "$DISK" | awk '{print $5}' | tr -d '%')

  THERMAL_MAX=0
  THERMAL_BATTERY=0
  THERMAL_CPU=0
  for z in /sys/class/thermal/thermal_zone*; do
    [ -r "$z/temp" ] || continue
    raw=$(cat "$z/temp" 2>/dev/null) || continue
    val=$(awk -v v="$raw" 'BEGIN{ if (v > 1500) printf "%.1f", v/1000; else printf "%.1f", v }')
    type=$(cat "$z/type" 2>/dev/null)
    max=$(awk -v a="$THERMAL_MAX" -v b="$val" 'BEGIN{print (b>a?b:a)}')
    THERMAL_MAX=$max
    case "$type" in
      *battery*) THERMAL_BATTERY=$val ;;
      *cpu*|*gpu*) THERMAL_CPU=$(awk -v a="$THERMAL_CPU" -v b="$val" 'BEGIN{print (b>a?b:a)}') ;;
    esac
  done

  {
    printf 'ts=%s\n' "$(date +%s)"
    printf 'model=%s\n' "$(/system/bin/getprop ro.product.model)"
    printf 'device=%s\n' "$(/system/bin/getprop ro.product.device)"
    printf 'android=%s\n' "$(/system/bin/getprop ro.build.version.release)"
    printf 'sdk=%s\n' "$(/system/bin/getprop ro.build.version.sdk)"
    printf 'build=%s\n' "$(/system/bin/getprop ro.build.version.incremental)"
    printf 'miui=%s\n' "$(/system/bin/getprop ro.miui.build.version)"
    printf 'uptime_line=%s\n' "$UP"
    printf 'cpu_line=%s\n' "$CPU"
    printf 'task_line=%s\n' "$TASK"
    printf 'mem_total_kb=%s\n' "$MEM_TOTAL"
    printf 'mem_available_kb=%s\n' "$MEM_AVAIL"
    printf 'swap_total_kb=%s\n' "$SWAP_TOTAL"
    printf 'swap_free_kb=%s\n' "$SWAP_FREE"
    printf 'disk_total_kb=%s\n' "$DISK_TOTAL"
    printf 'disk_used_kb=%s\n' "$DISK_USED"
    printf 'disk_free_kb=%s\n' "$DISK_FREE"
    printf 'disk_used_pct=%s\n' "$DISK_PCT"
    printf 'package_count=%s\n' "$(/system/bin/pm list packages 2>/dev/null | wc -l | tr -d ' ')"
    printf 'thermal_max_c=%s\n' "$THERMAL_MAX"
    printf 'thermal_battery_c=%s\n' "$THERMAL_BATTERY"
    printf 'thermal_cpu_c=%s\n' "$THERMAL_CPU"
    if [ -n "$BAT" ]; then
      printf 'battery_level=%s\n' "$(printf '%s' "$BAT" | jq -r '.level // .percentage // empty' 2>/dev/null)"
      printf 'battery_status=%s\n' "$(printf '%s' "$BAT" | jq -r '.status // empty' 2>/dev/null)"
      printf 'battery_health=%s\n' "$(printf '%s' "$BAT" | jq -r '.health // empty' 2>/dev/null)"
      printf 'battery_plugged=%s\n' "$(printf '%s' "$BAT" | jq -r '.plugged // empty' 2>/dev/null)"
      printf 'battery_temp_c=%s\n' "$(printf '%s' "$BAT" | jq -r '.temperature // empty' 2>/dev/null)"
      printf 'battery_voltage_mv=%s\n' "$(printf '%s' "$BAT" | jq -r '.voltage // empty' 2>/dev/null)"
      printf 'battery_current_ma=%s\n' "$(printf '%s' "$BAT" | jq -r '.current // empty' 2>/dev/null)"
      printf 'battery_cycle=%s\n' "$(printf '%s' "$BAT" | jq -r '.cycle // empty' 2>/dev/null)"
    fi
    if [ -n "$WIFI" ]; then
      printf 'wifi_ssid=%s\n' "$(printf '%s' "$WIFI" | jq -r '.ssid // empty' 2>/dev/null)"
      printf 'wifi_bssid=%s\n' "$(printf '%s' "$WIFI" | jq -r '.bssid // empty' 2>/dev/null)"
      printf 'wifi_ip=%s\n' "$(printf '%s' "$WIFI" | jq -r '.ip // empty' 2>/dev/null)"
      printf 'wifi_rssi=%s\n' "$(printf '%s' "$WIFI" | jq -r '.rssi // empty' 2>/dev/null)"
      printf 'wifi_link_speed_mbps=%s\n' "$(printf '%s' "$WIFI" | jq -r '.link_speed_mbps // empty' 2>/dev/null)"
      printf 'wifi_frequency_mhz=%s\n' "$(printf '%s' "$WIFI" | jq -r '.frequency_mhz // empty' 2>/dev/null)"
    fi
  } > "$TMP" 2>/dev/null && mv "$TMP" "$OUT" 2>/dev/null

  { printf 'ts=%s\n' "$(date +%s)"; printf 'uptime_line=%s\n' "$UP"; printf 'cpu_line=%s\n' "$CPU"; } > "$OLD.tmp" 2>/dev/null && mv "$OLD.tmp" "$OLD" 2>/dev/null

  sleep 10
done
