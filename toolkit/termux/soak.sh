#!/usr/bin/env bash
# toolkit/termux/soak.sh
# 用途：改造成果的**长期稳定性观测**（默认 24h）。周期性只读采样并写 CSV/摘要，
#       用于验收"5 次重启 + 24h soak"，不修改系统、不重启服务。
# 用法：
#   bash toolkit/termux/soak.sh --duration 24h --interval 300 --out soak.csv
#   bash toolkit/termux/soak.sh --duration 1h --interval 60 --dry-run
#   bash toolkit/termux/soak.sh --health-url http://<loopback-or-lan-host>:<port>/health
#   bash toolkit/termux/soak.sh --help
# 参数：
#   --duration <24h|3600s|60m>  观测时长（默认 24h；到点后输出摘要并退出）
#   --interval <sec>            采样间隔（默认 300；>=10）
#   --out <path>                CSV 输出路径（默认 ./soak-<UTC时间>.csv）
#   --health-url <url>          可选：HTTP 健康检查地址（仅允许 loopback/局域网；不写凭据）
#   --max-samples <n>           最多采样数（默认 100000，防跑飞）
#   --dry-run                   只打印将执行的动作与 1 次采样，不写文件
#   --help                      显示本帮助
# 退出码：0=完成；1=观测期间出现失败（仍写完整数据与摘要）；2=用法错误；130=被中断（已落盘摘要）。
# 安全：只读 /proc、/sys 与只读命令；写入仅限 --out 指定的 CSV；可随时 Ctrl-C 安全中断。
# 说明：--health-url 必须由调用方显式提供，脚本不硬编码任何 IP/端口/凭据。

set -u

DURATION="24h"
INTERVAL="300"
OUT=""
HEALTH_URL=""
MAX_SAMPLES="100000"
DRY_RUN=0
FAIL_COUNT=0
SAMPLE_COUNT=0
START_EPOCH=0
SUMMARY_WRITTEN=0

usage() {
    sed -n '2,22p' "$0" | sed 's/^# \{0,1\}//'
}

while [ $# -gt 0 ]; do
    case "$1" in
        --duration) DURATION="${2:-}"; shift 2 || { echo "用法错误：--duration 缺少参数" >&2; exit 2; } ;;
        --interval) INTERVAL="${2:-}"; shift 2 || { echo "用法错误：--interval 缺少参数" >&2; exit 2; } ;;
        --out) OUT="${2:-}"; shift 2 || { echo "用法错误：--out 缺少参数" >&2; exit 2; } ;;
        --health-url) HEALTH_URL="${2:-}"; shift 2 || { echo "用法错误：--health-url 缺少参数" >&2; exit 2; } ;;
        --max-samples) MAX_SAMPLES="${2:-}"; shift 2 || { echo "用法错误：--max-samples 缺少参数" >&2; exit 2; } ;;
        --dry-run) DRY_RUN=1 ;;
        --help|-h) usage; exit 0 ;;
        *) echo "用法错误：未知参数 $1（--help 查看用法）" >&2; exit 2 ;;
    esac
done

# ---------- 参数校验 ----------
case "$INTERVAL" in *[!0-9]*|"") echo "用法错误：--interval 必须是整数秒" >&2; exit 2 ;; esac
[ "$INTERVAL" -ge 10 ] || { echo "用法错误：--interval 不能小于 10 秒" >&2; exit 2; }
case "$MAX_SAMPLES" in *[!0-9]*|"") echo "用法错误：--max-samples 必须是整数" >&2; exit 2 ;; esac

parse_duration_seconds() {
    # 支持 24h / 3600s / 60m / 纯数字（秒）；非法返回空。
    d="$1"
    case "$d" in
        *h) n="${d%h}"; unit=3600 ;;
        *m) n="${d%m}"; unit=60 ;;
        *s) n="${d%s}"; unit=1 ;;
        *) n="$d"; unit=1 ;;
    esac
    case "$n" in ''|*[!0-9]*) echo "" ; return ;; esac
    echo $((n * unit))
}
DURATION_S="$(parse_duration_seconds "$DURATION")"
[ -n "$DURATION_S" ] || { echo "用法错误：--duration 格式应为 24h/60m/3600s 或秒数" >&2; exit 2; }
[ "$DURATION_S" -gt 0 ] || { echo "用法错误：--duration 必须大于 0" >&2; exit 2; }

if [ -n "$HEALTH_URL" ]; then
    case "$HEALTH_URL" in http://*|https://*) : ;; *)
        echo "用法错误：--health-url 必须是 http(s):// 地址" >&2; exit 2 ;;
    esac
    if ! command -v curl >/dev/null 2>&1; then
        echo "警告：未找到 curl，--health-url 检查将记录为 na" >&2
        HEALTH_URL=""
    fi
fi

if [ -z "$OUT" ]; then
    OUT="./soak-$(date -u +%Y%m%dT%H%M%SZ).csv"
fi
case "$OUT" in *..*|/*) echo "用法错误：--out 不能是绝对路径或包含 .." >&2; exit 2 ;; esac

# ---------- 只读采样 ----------
read_first() {
    # $1=文件 $2=awk 表达式；失败输出 null
    [ -r "$1" ] || { echo "null"; return; }
    awk "$2" "$1" 2>/dev/null || echo "null"
}
read_uptime_s() { read_first /proc/uptime '{printf "%d", $1}'; }
read_load1() { read_first /proc/loadavg '{print $1}'; }
read_mem_avail_mb() { read_first /proc/meminfo '/MemAvailable/ {gsub("kB","",$2); printf "%d", $2/1024; exit}'; }
read_disk_avail_mb() { df -k /data 2>/dev/null | awk 'END { if (NF >= 4 && $4 ~ /^[0-9]+$/) printf "%d", $4/1024; else print "null" }'; }
read_boot_id() {
    if [ -r /proc/sys/kernel/random/boot_id ]; then
        head -n 1 /proc/sys/kernel/random/boot_id 2>/dev/null | tr -d '[:space:]' || echo "null"
    else
        echo "null"
    fi
}
read_battery_temp_c() {
    node="/sys/class/power_supply/battery/temp"
    if [ -r "$node" ]; then
        raw="$(head -n 1 "$node" 2>/dev/null | tr -d '[:space:]')"
        case "$raw" in ''|*[!0-9]*) echo "null" ;; *) echo $((raw / 10)) ;; esac
    else
        echo "null"
    fi
}
read_thermal_max_c() {
    if ls /sys/class/thermal/thermal_zone*/temp >/dev/null 2>&1; then
        awk 'BEGIN { max=-999 } { v=$1+0; if (v > 0) { c=(v >= 1000) ? v/1000 : (v >= 100 ? v/10 : v); if (c > max) max=c } } END { if (max == -999) print "null"; else printf "%.1f", max }' \
            /sys/class/thermal/thermal_zone*/temp 2>/dev/null
    else
        echo "null"
    fi
}
read_services() {
    if command -v supervisorctl >/dev/null 2>&1; then
        supervisorctl status 2>/dev/null | awk '
            BEGIN { run=0; total=0 }
            { total++; if ($2 == "RUNNING") run++ }
            END { printf "%d/%d", run, total }'
    else
        echo "na"
    fi
}
read_health() {
    # 返回 HTTP 状态码；无 URL/失败返回 na。
    [ -n "$HEALTH_URL" ] || { echo "na"; return; }
    curl --max-time 5 --silent --output /dev/null --write-out "%{http_code}" "$HEALTH_URL" 2>/dev/null || echo "na"
}

esc() { printf '%s' "$1" | tr ',' ';' | tr -d '\r\n'; }

write_row() {
    ts="$1"; boot="$2"; up="$3"; load="$4"; mem="$5"; disk="$6"; btemp="$7"; tmax="$8"; svc="$9"; health="${10}"
    printf '%s,%s,%s,%s,%s,%s,%s,%s,%s,%s\n' \
        "$ts" "$boot" "$up" "$load" "$mem" "$disk" "$btemp" "$tmax" "$(esc "$svc")" "$health" >> "$OUT"
}

print_summary() {
    [ "$SUMMARY_WRITTEN" -eq 1 ] && return 0
    SUMMARY_WRITTEN=1
    end_epoch="$(date +%s 2>/dev/null || echo 0)"
    elapsed=$((end_epoch - START_EPOCH))
    avail="na"
    if [ "$SAMPLE_COUNT" -gt 0 ]; then
        ok=$((SAMPLE_COUNT - FAIL_COUNT))
        # 百分比（整数）
        avail=$((ok * 100 / SAMPLE_COUNT))
    fi
    printf '\nsoak 摘要：samples=%s failures=%s availability=%s%% elapsed_s=%s out=%s\n' \
        "$SAMPLE_COUNT" "$FAIL_COUNT" "$avail" "$elapsed" "$OUT"
    if [ "$SAMPLE_COUNT" -gt 0 ] && [ "$DRY_RUN" -eq 0 ]; then
        printf '%s\n' "# summary samples=$SAMPLE_COUNT failures=$FAIL_COUNT availability_pct=$avail elapsed_s=$elapsed" >> "$OUT"
    fi
}

trap 'echo "soak 收到中断信号：正在落盘摘要..." >&2; print_summary; exit 130' INT TERM

# ---------- 初始化 ----------
START_EPOCH="$(date +%s 2>/dev/null || echo 0)"
if [ "$DRY_RUN" -eq 1 ]; then
    echo "[dry-run] duration=$DURATION_S interval=$INTERVAL out=$OUT health_url=${HEALTH_URL:-off}"
    echo "[dry-run] 示例采样："
    printf 'timestamp,boot_id,uptime_s,load1,mem_avail_mb,disk_avail_mb,battery_temp_c,thermal_max_c,services,health\n'
    printf '%s,%s,%s,%s,%s,%s,%s,%s,%s,%s\n' \
        "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$(read_boot_id)" "$(read_uptime_s)" "$(read_load1)" \
        "$(read_mem_avail_mb)" "$(read_disk_avail_mb)" "$(read_battery_temp_c)" \
        "$(read_thermal_max_c)" "$(read_services)" "$(read_health)"
    exit 0
fi

if ! printf '# soak 观测开始 %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$OUT" 2>/dev/null; then
    echo "错误：无法写入 --out 文件" >&2; exit 2
fi
printf 'timestamp,boot_id,uptime_s,load1,mem_avail_mb,disk_avail_mb,battery_temp_c,thermal_max_c,services,health\n' >> "$OUT"

# ---------- 主循环 ----------
while :; do
    ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    boot="$(read_boot_id)"
    up="$(read_uptime_s)"
    load="$(read_load1)"
    mem="$(read_mem_avail_mb)"
    disk="$(read_disk_avail_mb)"
    btemp="$(read_battery_temp_c)"
    tmax="$(read_thermal_max_c)"
    svc="$(read_services)"
    health="$(read_health)"

    SAMPLE_COUNT=$((SAMPLE_COUNT + 1))
    # 采样失败判定：关键字段 null 或 health 非 2xx/na 以外的错误。
    sample_fail=0
    case "$up" in ''|null|*[!0-9]*) sample_fail=1 ;; esac
    case "$mem" in ''|null|*[!0-9]*) sample_fail=1 ;; esac
    case "$health" in
        na|2??) : ;;
        *) sample_fail=1 ;;
    esac
    if [ "$sample_fail" -eq 1 ]; then FAIL_COUNT=$((FAIL_COUNT + 1)); fi
    write_row "$ts" "$boot" "$up" "$load" "$mem" "$disk" "$btemp" "$tmax" "$svc" "$health"

    now="$(date +%s 2>/dev/null || echo 0)"
    if [ $((now - START_EPOCH)) -ge "$DURATION_S" ]; then
        print_summary
        break
    fi
    if [ "$SAMPLE_COUNT" -ge "$MAX_SAMPLES" ]; then
        echo "达到 --max-samples 上限，提前结束" >&2
        print_summary
        break
    fi
    sleep "$INTERVAL"
    # sleep 被信号中断时 trap 已接管；正常等待后继续。
done

[ "$FAIL_COUNT" -eq 0 ] && exit 0 || exit 1
