#!/bin/sh
# haydn P1 周期健康检查（cron 每 5 分钟）
# 只读为主；唯一的写动作是：对“非人工停止”的异常服务执行一次 supervisorctl start。
# 控制台主动 stop 会写 /srv/haydn/run/.stopped-<svc>，据此跳过自动拉起。
# 2026-11-14 修复：df 在 mount 表异常时会卡死并堆积进程，改用 stat -f 直接取容量
STAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)
LOG=/var/log/haydn/health.log
SUP="/usr/bin/supervisorctl -c /etc/supervisor/supervisord.conf"
FAIL=""
RECOVER=""

st=$($SUP status 2>&1)
for svc in $(echo "$st" | awk '$2 ~ /^(STOPPED|FATAL|BACKOFF|EXITED)$/ {print $1}'); do
  [ -f "/srv/haydn/run/.stopped-$svc" ] && continue
  $SUP start "$svc" >/dev/null 2>&1 && RECOVER="$RECOVER $svc"
done
if [ -n "$RECOVER" ]; then
  echo "$STAMP RECOVER$RECOVER" >> "$LOG"
  st=$($SUP status 2>&1)
fi

echo "$st" | grep -qE 'FATAL|BACKOFF|STOPPED|EXITED' && FAIL="$FAIL supervisor"
curl -fsS -m 5 http://127.0.0.1:18080/ >/dev/null 2>&1 || FAIL="$FAIL http"
curl -fsS -m 5 http://127.0.0.1:9100/metrics >/dev/null 2>&1 || FAIL="$FAIL node_exporter"
ss -ltn 2>/dev/null | grep -q '127.0.0.1:22' || FAIL="$FAIL sshd"

USED=$(stat -f / 2>/dev/null | awk '/^Blocks:/{for(i=1;i<=NF;i++){if($i=="Total:")t=$(i+1); if($i=="Available:")a=$(i+1)}} END{if(t>0) print int((t-a)*100/t)}')
if [ -n "$USED" ] && [ "$USED" -ge 90 ]; then FAIL="$FAIL disk_${USED}pct"; fi

# 内存水位：MemAvailable 占 MemTotal 的比例（阈值 10%，与磁盘 90% 使用对齐）
MEM=$(awk '/MemAvailable/{a=$2} /MemTotal/{t=$2} END{if(t>0) print int(a*100/t)}' /proc/meminfo 2>/dev/null)
if [ -n "$MEM" ] && [ "$MEM" -lt 10 ]; then FAIL="$FAIL mem_${MEM}pct"; fi

if [ -z "$FAIL" ]; then
  echo "$STAMP OK" >> "$LOG"
else
  echo "$STAMP FAIL$FAIL" >> "$LOG"
fi
