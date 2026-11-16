#!/system/bin/sh
# haydn 观测摘要生成器（设备 /data/server/bin/soak-summary.sh；只读，供备份归档用）
# 由 device-make-backup.sh 调用：写入 meta/observability/soak-summary-<ts>.txt
# soak 观测摘要生成器（只读；输出供归档/备份证据用）
# 用法：soak-summary.sh [--out DIR]
OUT_DIR="${1:-/data/server/logs}"
[ "$OUT_DIR" = "--out" ] && OUT_DIR="${2:-/data/server/logs}"
mkdir -p "$OUT_DIR" 2>/dev/null
TS=$(date -u +%Y%m%dT%H%M%SZ)
OUT="$OUT_DIR/soak-summary-$TS.txt"
CSV=/data/server/logs/telemetry.csv

{
  echo "# soak summary $TS"
  echo "generated_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "uptime_s=$(cut -d' ' -f1 /proc/uptime)"
  echo "soak_start_utc=$(cat /data/server/logs/soak-start.txt 2>/dev/null)"
  echo "csv_lines=$(wc -l < "$CSV" 2>/dev/null)"
  echo "csv_first=$(head -2 "$CSV" 2>/dev/null | tail -1 | cut -d, -f1)"
  echo "csv_last=$(tail -1 "$CSV" 2>/dev/null | cut -d, -f1)"
  echo
  echo "## last 12 samples (ts, uptime, load1, mem_avail_kb, batt, batt_temp_raw, thermal_max_raw, supervisord, http)"
  tail -12 "$CSV" 2>/dev/null | awk -F, '{printf "%s %s load=%s mem=%s batt=%s(%s) temp=%s sv=%s http=%s\n", $1,$2,$3,$5,$8,$9,$11,$12,$13}'
  echo
  echo "## peaks (whole csv)"
  awk -F, 'NR>1{if($3+0>lmax)lmax=$3+0; if($11+0>tmax)tmax=$11+0; if($9+0>bmax)bmax=$9+0; if($5+0>0 && (mmin=="" || $5+0<mmin))mmin=$5+0; n++} END{printf "samples=%d load1_max=%.2f thermal_max_raw=%d batt_temp_max_raw=%d mem_avail_min_kb=%d\n", n, lmax, tmax, bmax, mmin}' "$CSV" 2>/dev/null
  echo
  echo "## availability (counts of up/up)"
  awk -F, 'NR>1{n++; if($12=="up")s++; if($13=="up")h++} END{printf "supervisord_up=%d/%d chroot_http_up=%d/%d\n", s, n, h, n}' "$CSV" 2>/dev/null
  echo
  echo "## watchdog log tail (last 10)"
  tail -10 /data/server/logs/watchdog.log 2>/dev/null
  echo
  echo "## alerts (last 10)"
  tail -10 /data/server/logs/alerts.log 2>/dev/null
  echo
  echo "## health log (last 5)"
  tail -5 /data/server/rootfs/var/log/haydn/health.log 2>/dev/null
  echo
  echo "## supervisor status"
  /data/server/bin/chroot-enter.sh /usr/bin/supervisorctl -c /etc/supervisor/supervisord.conf status 2>/dev/null
  echo
  echo "## wifi guard tail"
  tail -5 /data/server/logs/wifi-guard.log 2>/dev/null
  echo
  echo "## process instances"
  echo "telemetry_loops=$(pgrep -f 'telemetry-loop\.sh' 2>/dev/null | wc -l)"
  echo "watchdog_loops=$(pgrep -f 'watchdog-loop\.sh --loop' 2>/dev/null | wc -l)"
} > "$OUT" 2>&1

echo "SUMMARY=$OUT"
echo "size_bytes=$(wc -c < "$OUT")"
sha256sum "$OUT"
