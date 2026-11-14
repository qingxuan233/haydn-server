#!/system/bin/sh
# 每日 03:30（设备本地时区）触发一次设备侧备份；按日标记防重复。
# 2026-11-14 修复：pidfile 记录 "pid boot_id"，判活同时校验 cmdline 与 boot_id，
# 避免重启后 PID 复用导致新实例误判“已有实例”而静默退出。
# 2026-11-14 追加：Web 控制台手动触发（轮询 run/backup-trigger，最多延迟 60s）。
MARK=/data/server/run/backup-last-day
PIDF=/data/server/run/backup-loop.pid
TRIG=/data/server/run/backup-trigger
LOG=/data/server/logs/backup.log
BOOTID=$(cat /proc/sys/kernel/random/boot_id 2>/dev/null)

alive() {
  # $1=pid $2=boot_id
  [ -n "$1" ] || return 1
  [ -r "/proc/$1/cmdline" ] || return 1
  tr '\0' ' ' < "/proc/$1/cmdline" 2>/dev/null | grep -q 'backup-loop.sh' || return 1
  [ "$2" = "$BOOTID" ] || return 1
  return 0
}

if [ -f "$PIDF" ]; then
  read -r OPID OBOOT < "$PIDF" 2>/dev/null || true
  [ -n "$OBOOT" ] || OBOOT=""
  if alive "$OPID" "$OBOOT"; then
    exit 0
  fi
fi

echo "$$ $BOOTID" > "$PIDF"
echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) backup-loop start pid=$$ boot_id=$BOOTID" >> "$LOG"

while true; do
  if [ -f "$TRIG" ]; then
    rm -f "$TRIG"
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) manual trigger via console" >> "$LOG"
    /data/server/bin/haydn-backup.sh
  fi
  NOW=$(date +%H:%M)
  TODAY=$(date +%Y-%m-%d)
  if [ "$NOW" = "03:30" ] && [ "$(cat "$MARK" 2>/dev/null)" != "$TODAY" ]; then
    echo "$TODAY" > "$MARK"
    /data/server/bin/haydn-backup.sh
  fi
  sleep 60
done
