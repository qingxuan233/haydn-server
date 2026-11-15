#!/bin/sh
# haydn 24h 观察采样（每小时一行：host 汇总 + 每个 supervisor 程序一行）
# 由 /etc/cron.d/haydn-observe 调用；输出 /var/log/haydn/observe.csv（logrotate.d/haydn-csv 覆盖）
OUT=/var/log/haydn/observe.csv
TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
LOAD=$(cut -d' ' -f1-3 /proc/loadavg | tr ' ' '/')
MA=$(awk '/^MemAvailable/{print $2}' /proc/meminfo)
MT=$(awk '/^MemTotal/{print $2}' /proc/meminfo)
DISK=$(df -P / | awk 'NR==2{print $5}')
UPT=$(cut -d. -f1 /proc/uptime)

[ -f "$OUT" ] || echo "ts_utc,kind,name,rss_kb,load1/5/15,mem_avail_kb,mem_total_kb,disk_used,uptime_s" >> "$OUT"
echo "$TS,host,-,-,$LOAD,$MA,$MT,$DISK,$UPT" >> "$OUT"

supervisorctl status 2>/dev/null | awk '{gsub(",","",$4); print $1"|"$2"|"$4}' | while IFS='|' read -r name state pid; do
  rss=0
  if [ "$state" = "RUNNING" ] && [ -n "$pid" ]; then
    r=$(awk '/^VmRSS/{print $2}' "/proc/$pid/status" 2>/dev/null)
    [ -n "$r" ] && rss=$r
  fi
  echo "$TS,svc,$name,$rss,-,-,-,-,-" >> "$OUT"
done
