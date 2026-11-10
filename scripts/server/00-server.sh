#!/data/data/com.termux/files/usr/bin/bash
# Termux:Boot 在开机时执行
termux-wake-lock
/data/data/com.termux/files/home/ubuntu.sh 'SERVER_UP_NO_WATCHDOG=1 /root/server/bin/server-up >> /root/server/logs/boot.log 2>&1; exec /root/server/bin/server-watch'
