#!/data/data/com.termux/files/usr/bin/bash
# Termux:Boot 在开机时执行
termux-wake-lock

# 系统指标采集（proot 内读不到 /proc/stat、/proc/uptime，由 Termux 侧采集给 API 用）
setsid "$HOME/termux-metrics.sh" >> "$HOME/server-metrics.log" 2>&1 < /dev/null &

/data/data/com.termux/files/home/ubuntu.sh 'SERVER_UP_NO_WATCHDOG=1 /root/server/bin/server-up >> /root/server/logs/boot.log 2>&1; exec /root/server/bin/server-watch'
