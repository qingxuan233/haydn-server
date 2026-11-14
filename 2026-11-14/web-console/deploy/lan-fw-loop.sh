#!/system/bin/sh
# 局域网入口防火墙同步（宿主侧 root）。
# 读取网关写入的网段文件（探测得到的 CIDR），幂等维护：
#   iptables -I INPUT 1 -p tcp --dport 18090 -s <CIDR> -m comment --comment haydnlab_allow_lan18090 -j ACCEPT
# 文件缺失/内容非法/前缀过宽时删除放行规则（fail closed）。只动这一条规则，不碰其他链。
# 回滚：kill $(cat /data/server/run/lan-fw.pid) 后
#       iptables -S INPUT | grep haydnlab_allow_lan18090 逐条 -D；并从 KSU service.sh 删除本段。
PORT=18090
TAG=haydnlab_allow_lan18090
CIDRF=/data/server/run/lan-subnet
PIDF=/data/server/run/lan-fw.pid
LOG=/data/server/logs/lan-fw.log
INTERVAL=${1:-15}
BOOTID=$(cat /proc/sys/kernel/random/boot_id 2>/dev/null)

alive() {
  [ -n "$1" ] || return 1
  [ -r "/proc/$1/cmdline" ] || return 1
  tr '\0' ' ' < "/proc/$1/cmdline" 2>/dev/null | grep -q 'lan-fw-loop.sh' || return 1
  [ "$2" = "$BOOTID" ] || return 1
  return 0
}

if [ -f "$PIDF" ]; then
  read -r OPID OBOOT < "$PIDF" 2>/dev/null || true
  if alive "$OPID" "$OBOOT"; then
    exit 0
  fi
fi
echo "$$ $BOOTID" > "$PIDF"

log() { echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) $*" >> "$LOG"; }

cur_src() {
  iptables -S INPUT 2>/dev/null | grep -- "$TAG" | awk '{for (i = 1; i <= NF; i++) if ($i == "-s") {print $(i + 1); exit}}' | head -1
}

drop_tagged() {
  n=0
  while iptables -S INPUT 2>/dev/null | grep -q -- "$TAG"; do
    spec=$(iptables -S INPUT 2>/dev/null | grep -- "$TAG" | head -1 | sed 's/^-A INPUT //')
    [ -n "$spec" ] || break
    # shellcheck disable=SC2086
    iptables -D INPUT $spec || break
    n=$((n + 1))
    [ "$n" -ge 5 ] && break
  done
  [ "$n" -gt 0 ] && log "removed $n rule(s) tagged $TAG"
}

valid_cidr() {
  case "$1" in
    *[!0-9./]*) return 1 ;;
  esac
  echo "$1" | grep -Eq '^[0-9]{1,3}(\.[0-9]{1,3}){3}/[0-9]{1,2}$' || return 1
  pfx=${1#*/}
  [ "$pfx" -ge 8 ] && [ "$pfx" -le 32 ] || return 1
  return 0
}

log "lan-fw-loop start pid=$$ boot_id=$BOOTID interval=${INTERVAL}s"
while true; do
  want=""
  if [ -r "$CIDRF" ]; then
    want=$(head -1 "$CIDRF" | tr -d ' \r\n')
  fi
  if [ -z "$want" ] || ! valid_cidr "$want"; then
    if [ -n "$(cur_src)" ]; then
      drop_tagged
      log "subnet file missing/invalid ('$want') -> lan rule removed (fail closed)"
    fi
  else
    have=$(cur_src)
    if [ "$have" != "$want" ]; then
      drop_tagged
      if iptables -I INPUT 1 -p tcp --dport "$PORT" -s "$want" \
           -m comment --comment "$TAG" -j ACCEPT 2>>"$LOG"; then
        log "lan rule set: $want -> tcp/$PORT"
      else
        log "FAILED to set lan rule for $want"
      fi
    fi
  fi
  sleep "$INTERVAL"
done
