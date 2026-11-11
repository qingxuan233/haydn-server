#!/usr/bin/env bash
# toolkit/termux/healthcheck.sh
# 用途：Termux 侧**只读**健康检查（CPU 负载/内存/磁盘/电池/温度/服务状态）。
# 特性：不写设备、不改配置、不需要 Root；任何一行失败都不中断后续检查。
# 用法：
#   bash toolkit/termux/healthcheck.sh --once          # 单次检查（默认）
#   bash toolkit/termux/healthcheck.sh --json          # 单次检查并以 JSON 输出
#   bash toolkit/termux/healthcheck.sh --interval 300  # 每 300 秒重复检查
#   bash toolkit/termux/healthcheck.sh --help
# 参数：
#   --once              执行一次后退出（默认行为，与 --interval 互斥）
#   --interval <sec>    循环检查间隔（秒，>=10）
#   --json              输出机器可读 JSON（字段值缺失时为 null）
#   --quiet             仅在有 WARN 时输出
#   --max-load <n>      1 分钟负载阈值，默认 8.0
#   --min-free-mb <n>   可用内存阈值（MB），默认 256
#   --min-disk-mb <n>   /data 可用空间阈值（MB），默认 1024
#   --max-temp-c <n>    最高温度阈值（°C），默认 70
#   --help              显示本帮助
# 退出码：0=全部正常；1=有 WARN；2=用法错误；130=被 Ctrl-C 中断。
# 安全：只读取 /proc、/sys 与只读命令；不包含任何凭据、IP、端口常量。

set -u

MAX_LOAD="8.0"
MIN_FREE_MB="256"
MIN_DISK_MB="1024"
MAX_TEMP_C="70"
INTERVAL="0"
MODE="once"
JSON=0
QUIET=0

usage() {
    sed -n '2,24p' "$0" | sed 's/^# \{0,1\}//'
}

while [ $# -gt 0 ]; do
    case "$1" in
        --once) MODE="once" ;;
        --interval) INTERVAL="${2:-}"; shift 2 || { echo "用法错误：--interval 缺少参数" >&2; exit 2; } ;;
        --json) JSON=1 ;;
        --quiet) QUIET=1 ;;
        --max-load) MAX_LOAD="${2:-}"; shift 2 || { echo "用法错误：--max-load 缺少参数" >&2; exit 2; } ;;
        --min-free-mb) MIN_FREE_MB="${2:-}"; shift 2 || { echo "用法错误：--min-free-mb 缺少参数" >&2; exit 2; } ;;
        --min-disk-mb) MIN_DISK_MB="${2:-}"; shift 2 || { echo "用法错误：--min-disk-mb 缺少参数" >&2; exit 2; } ;;
        --max-temp-c) MAX_TEMP_C="${2:-}"; shift 2 || { echo "用法错误：--max-temp-c 缺少参数" >&2; exit 2; } ;;
        --help|-h) usage; exit 0 ;;
        *) echo "用法错误：未知参数 $1（--help 查看用法）" >&2; exit 2 ;;
    esac
done

# 数值参数只接受整数（负载/温度允许小数），避免命令注入与误用。
case "$MAX_LOAD" in *[!0-9.]*|"") echo "用法错误：--max-load 必须是数字" >&2; exit 2 ;; esac
case "$MIN_FREE_MB$MIN_DISK_MB$MAX_TEMP_C" in *[!0-9]*|"") echo "用法错误：阈值必须是整数" >&2; exit 2 ;; esac
if [ "$MODE" = "loop" ] || [ "$INTERVAL" != "0" ]; then
    case "$INTERVAL" in *[!0-9]*|"") echo "用法错误：--interval 必须是整数秒" >&2; exit 2 ;; esac
    if [ "$INTERVAL" -lt 10 ]; then echo "用法错误：--interval 不能小于 10 秒" >&2; exit 2; fi
fi

# ---------- 只读采样函数 ----------
read_uptime_s() {
    if [ -r /proc/uptime ]; then
        awk '{printf "%d", $1}' /proc/uptime 2>/dev/null || echo "null"
    else
        echo "null"
    fi
}

read_load1() {
    if [ -r /proc/loadavg ]; then
        awk '{print $1}' /proc/loadavg 2>/dev/null || echo "null"
    else
        echo "null"
    fi
}

read_mem_available_kb() {
    if [ -r /proc/meminfo ]; then
        awk '/MemAvailable/ {gsub("kB","",$2); print $2; exit}' /proc/meminfo 2>/dev/null || echo "null"
    else
        echo "null"
    fi
}

read_mem_total_kb() {
    if [ -r /proc/meminfo ]; then
        awk '/MemTotal/ {gsub("kB","",$2); print $2; exit}' /proc/meminfo 2>/dev/null || echo "null"
    else
        echo "null"
    fi
}

read_data_avail_kb() {
    df -k /data 2>/dev/null | awk 'END { if (NF >= 4 && $4 ~ /^[0-9]+$/) print $4; else print "null" }'
}

read_battery_value() {
    # $1=节点名；只读，权限不足时返回 null。
    node="/sys/class/power_supply/battery/$1"
    if [ -r "$node" ]; then
        head -n 1 "$node" 2>/dev/null | tr -d '[:space:]' || echo "null"
    else
        echo "null"
    fi
}

read_thermal_max_c() {
    # 输出最高有效温度（°C，一位小数）；无可用节点时 null。
    if ls /sys/class/thermal/thermal_zone*/temp >/dev/null 2>&1; then
        awk 'BEGIN { max=-999 } { v=$1+0; if (v > 0) { c=(v >= 1000) ? v/1000 : (v >= 100 ? v/10 : v); if (c > max) max=c } } END { if (max == -999) print "null"; else printf "%.1f", max }' \
            /sys/class/thermal/thermal_zone*/temp 2>/dev/null
    else
        echo "null"
    fi
}

read_supervisor() {
    if command -v supervisorctl >/dev/null 2>&1; then
        supervisorctl status 2>/dev/null | awk '
            BEGIN { run=0; total=0 }
            { total++; if ($2 == "RUNNING") run++ }
            END { printf "%d/%d", run, total }'
    else
        echo "na"
    fi
}

service_count() { read_supervisor | cut -d'/' -f2; }
service_running() { read_supervisor | cut -d'/' -f1; }

# 简单数值比较：awk 输出 1/0；null 当作不比较。
num_ge() { awk -v a="$1" -v b="$2" 'BEGIN { if (a == "null" || a == "na") exit 1; exit !(a+0 >= b+0) }' 2>/dev/null; }
num_lt() { awk -v a="$1" -v b="$2" 'BEGIN { if (a == "null" || a == "na") exit 1; exit !(a+0 < b+0) }' 2>/dev/null; }

collect_once() {
    uptime_s="$(read_uptime_s)"
    load1="$(read_load1)"
    mem_avail="$(read_mem_available_kb)"
    mem_total="$(read_mem_total_kb)"
    disk_avail="$(read_data_avail_kb)"
    battery_level="$(read_battery_value capacity)"
    battery_temp="$(read_battery_value temp)"
    thermal_max="$(read_thermal_max_c)"
    svc="$(read_supervisor)"

    # 电池温度单位是 0.1°C；转换为整数 °C。
    battery_temp_c="null"
    case "$battery_temp" in
        ''|null|*[!0-9]*) battery_temp_c="null" ;;
        *) battery_temp_c=$((battery_temp / 10)) ;;
    esac
    mem_avail_mb="null"
    case "$mem_avail" in ''|null|*[!0-9]*) ;; *) mem_avail_mb=$((mem_avail / 1024)) ;; esac
    disk_avail_mb="null"
    case "$disk_avail" in ''|null|*[!0-9]*) ;; *) disk_avail_mb=$((disk_avail / 1024)) ;; esac

    status="OK"
    warn=""
    if num_lt "$load1" "$MAX_LOAD"; then :; else
        # 负载 >= 阈值
        case "$load1" in ''|null) ;; *) status="WARN"; warn="${warn}load1=${load1}>${MAX_LOAD};" ;; esac
    fi
    if num_lt "$mem_avail_mb" "$MIN_FREE_MB"; then
        status="WARN"; warn="${warn}mem_avail=${mem_avail_mb}MB<${MIN_FREE_MB}MB;"
    fi
    if num_lt "$disk_avail_mb" "$MIN_DISK_MB"; then
        status="WARN"; warn="${warn}disk_avail=${disk_avail_mb}MB<${MIN_DISK_MB}MB;"
    fi
    if num_ge "$thermal_max" "$MAX_TEMP_C"; then
        status="WARN"; warn="${warn}thermal=${thermal_max}C>=${MAX_TEMP_C}C;"
    fi
    if num_lt "$battery_temp_c" "45"; then :; else
        case "$battery_temp_c" in ''|null) ;; *) status="WARN"; warn="${warn}battery=${battery_temp_c}C>=45C;" ;; esac
    fi

    if [ "$JSON" -eq 1 ]; then
        printf '{"status":"%s","uptime_s":%s,"load1":%s,"mem_available_kb":%s,"mem_total_kb":%s,"disk_avail_kb":%s,"battery_level":%s,"battery_temp_c":%s,"thermal_max_c":%s,"services":"%s","warnings":"%s"}\n' \
            "$status" "$uptime_s" "$load1" "$mem_avail" "$mem_total" "$disk_avail" \
            "$battery_level" "$battery_temp_c" "$thermal_max" "$svc" "$warn"
    else
        if [ "$QUIET" -eq 1 ] && [ "$status" = "OK" ]; then
            return 0
        fi
        printf 'status=%s uptime_s=%s load1=%s mem_avail=%sMB disk_avail=%sMB battery=%s%% battery_temp=%sC thermal_max=%sC services=%s\n' \
            "$status" "$uptime_s" "$load1" "$mem_avail_mb" "$disk_avail_mb" "$battery_level" "$battery_temp_c" "$thermal_max" "$svc"
        [ -n "$warn" ] && printf 'WARN: %s\n' "$warn"
    fi
    [ "$status" = "OK" ] && return 0 || return 1
}

trap 'echo "healthcheck 已中断（只读检查，无副作用）" >&2; exit 130' INT TERM

# 默认单次；--interval 大于 0 进入循环（由 --once 覆盖）。
if [ "$MODE" = "loop" ] || [ "$INTERVAL" != "0" ]; then
    while :; do
        collect_once
        sleep "$INTERVAL"
    done
else
    collect_once
fi
