#!/bin/sh
echo "===== system ====="
uptime 2>/dev/null
cat /proc/loadavg 2>/dev/null
head -3 /proc/meminfo 2>/dev/null
echo "===== dsh process ====="
for p in /proc/*/cmdline; do
  pid=$(echo "$p" | cut -d/ -f3)
  cmd=$(tr '\0' ' ' < "$p" 2>/dev/null)
  case "$cmd" in
    *bin.js*|*dsh/lib*) echo "PID=$pid"; echo "$cmd" | cut -c1-260; echo "---"; ;;
  esac
done
for pid in $(for p in /proc/*/cmdline; do cmd=$(tr '\0' ' ' < "$p" 2>/dev/null); case "$cmd" in *bin.js*) echo "$p" | cut -d/ -f3;; esac; done); do
  echo "== /proc/$pid/status =="
  grep -E 'Name|VmRSS|VmSwap|Threads|voluntary_ctxt' "/proc/$pid/status" 2>/dev/null
  grep -E '^cpu ' /proc/$pid/stat 2>/dev/null
done
echo "===== node versions ====="
/opt/node24/bin/node -v 2>/dev/null
echo "===== dsh disk/session usage ====="
du -sh /root/.dsh 2>/dev/null
du -sh /root/.dsh/sessions 2>/dev/null
du -sh /root/.dsh/storages 2>/dev/null
du -sh /root/server/logs 2>/dev/null
find /root/.dsh/sessions -type f 2>/dev/null | wc -l
ls -lS /root/server/logs 2>/dev/null | head -8
echo "===== profile package ====="
cat /root/.dsh/profiles/web/package.json 2>/dev/null
echo "===== patch entry ids ====="
grep '^- id:' /root/.dsh/profiles/web/cordis.patch.yml 2>/dev/null
echo "===== supervisor dsh ====="
supervisorctl -c /root/server/etc/supervisord.conf status dsh dsh-login nginx gitea syncthing 2>/dev/null
echo "===== dsh log tail ====="
tail -8 /root/server/logs/dsh.log 2>/dev/null
