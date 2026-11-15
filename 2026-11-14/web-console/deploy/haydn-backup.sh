#!/system/bin/sh
# 设备侧夸克加密备份：逐来源快照 -> 加密 -> 自检 -> 上传 -> 保留策略
# 来源：haydn（整机配置/代码）、forgejo（Git 仓库数据）与 vaultwarden（密码库数据），后两者用 SQLite 一致性备份
# 由 backup-loop.sh 每日调用；也可手工执行。密码/令牌只在设备本地，不进日志。
# 2026-11-15 加固：
#   1) 上传前 DNS/TCP 预检，不通即快速失败（不再空转 300+900 秒），密文留在本地待补传；
#   2) 三来源互不阻断，逐来源记录 ok/fail 并输出 SUMMARY，单来源失败不影响其余；
#   3) 支持 SOURCES 环境变量选择来源（如 SOURCES=vaultwarden 手工单来源补备）。
set -u

ROOT=/data/server
LOG=$ROOT/logs/backup.log
LOCK=$ROOT/run/backup.lock
CHROOT=$ROOT/bin/chroot-enter.sh
CRYPT=/opt/haydn/haydn_crypt.py
ENC_DIR=/var/backups/haydn            # chroot 内路径
ENC_DIR_HOST=$ROOT/rootfs/var/backups/haydn
PASS=/root/.haydn-backup-pass          # chroot 内路径
QUARK_CLI=/opt/quark/scripts/quark-drive.cjs
FID_FILE=/root/.quark-drive/deepseek/backup-fid
KEEP=7
PRECHECK_HOST=${PRECHECK_HOST:-open-api-drive.quark.cn}
PRECHECK_TIMEOUT=${PRECHECK_TIMEOUT:-6}
SOURCES=${SOURCES:-haydn forgejo vaultwarden}

log() { echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) $*" >> "$LOG"; }

notify() {
  cmd notification post -S bigtext -t "haydn 备份失败" haydn_backup "$1" >/dev/null 2>&1
}

rotate_log() {
  sz=$(stat -c %s "$LOG" 2>/dev/null || echo 0)
  [ "$sz" -gt 1048576 ] && mv -f "$LOG" "$LOG.1"
}

fail() {
  log "FAIL $1"
  notify "备份失败: $1"
  rm -rf "$LOCK"
  exit 1
}

# 上传前连通性预检：DNS(getaddrinfo) + TCP/443，与 node 上传走同一条解析/连接路径。
# rc=0 通；rc=2 解析失败；rc=3 连接失败。
precheck() {
  "$CHROOT" python3 -c 'import socket,sys
h=sys.argv[1]; t=float(sys.argv[2])
try:
    ips=sorted({a[4][0] for a in socket.getaddrinfo(h,443,proto=socket.IPPROTO_TCP)})
except Exception as e:
    print("dns-fail " + type(e).__name__); sys.exit(2)
try:
    socket.create_connection((h,443),timeout=t).close()
except Exception as e:
    print("tcp-fail " + type(e).__name__ + " " + str(e) + " ips=" + ",".join(ips)); sys.exit(3)
print("ok ips=" + ",".join(ips))' "$1" "$2" 2>&1
}

# 加密 + 解密自检 + 上传；$1=明文归档路径 $2=标签（haydn|forgejo|vaultwarden）
process_archive() {
  ARCHIVE=$1
  LABEL=$2
  NAME=$(basename "$ARCHIVE")
  case "$NAME" in
    "$LABEL"-backup-*) ;;
    *) log "SKIP unexpected archive name $NAME"; return 1 ;;
  esac

  SHA=$(sha256sum "$ARCHIVE" | awk '{print $1}')
  [ -n "$SHA" ] || return 1
  log "snapshot label=$LABEL $NAME sha=$SHA"

  PLAIN_HOST=$ENC_DIR_HOST/incoming-$NAME
  mv -f "$ARCHIVE" "$PLAIN_HOST" || return 1
  CHK=$(sha256sum "$PLAIN_HOST" | awk '{print $1}')
  [ "$CHK" = "$SHA" ] || { rm -f "$PLAIN_HOST"; return 1; }

  ENC_NAME=$NAME.enc
  "$CHROOT" python3 "$CRYPT" encrypt "$ENC_DIR/incoming-$NAME" "$ENC_DIR/$ENC_NAME" "$PASS" >> "$LOG" 2>&1 || return 1
  rm -f "$PLAIN_HOST"

  ENC_HOST=$ENC_DIR_HOST/$ENC_NAME
  [ -f "$ENC_HOST" ] || return 1
  (cd "$ENC_DIR_HOST" && sha256sum "$ENC_NAME" > "$ENC_NAME.sha256") || return 1

  VERIFY=verify-$NAME
  "$CHROOT" python3 "$CRYPT" decrypt "$ENC_DIR/$ENC_NAME" "/var/backups/haydn/$VERIFY" "$PASS" >> "$LOG" 2>&1 || return 1
  VCHK=$(sha256sum "$ENC_DIR_HOST/$VERIFY" | awk '{print $1}')
  rm -f "$ENC_DIR_HOST/$VERIFY"
  [ "$VCHK" = "$SHA" ] || return 1
  log "encrypt+verify ok label=$LABEL enc=$ENC_NAME bytes=$(stat -c %s "$ENC_HOST")"

  # 预检：不通就直接留档退出，不做 300/900 秒退避重试
  PC=$(precheck "$PRECHECK_HOST" "$PRECHECK_TIMEOUT")
  PC_RC=$?
  if [ "$PC_RC" -ne 0 ]; then
    log "upload precheck fail label=$LABEL rc=$PC_RC $PC"
    log "upload skipped label=$LABEL keep=/var/backups/haydn/$ENC_NAME (network down, 待补传)"
    return 1
  fi
  log "upload precheck ok label=$LABEL $PC"

  i=1
  UP_OK=0
  while [ "$i" -le 3 ]; do
    SID="$(date +%s)-$RANDOM"
    UP=$("$CHROOT" env DSH_HOME=/root node "$QUARK_CLI" upload "$ENC_DIR/$ENC_NAME" "$ENC_DIR/$ENC_NAME.sha256" \
          --parent-fid "$(cat "$ROOT/rootfs$FID_FILE")" \
          --session-input "设备侧定时夸克备份" --session-id "$SID" 2>&1)
    RES=$(echo "$UP" | grep '"type":"result"' | tail -1)
    if echo "$RES" | grep -q '"code":0'; then
      UP_OK=1
      log "upload ok label=$LABEL attempt=$i $RES"
      break
    fi
    log "upload fail label=$LABEL attempt=$i $(echo "$RES" | cut -c1-300)"
    [ "$i" -lt 3 ] && sleep $((i == 1 ? 300 : 900))
    i=$((i + 1))
  done
  [ "$UP_OK" = "1" ] || return 1

  # 按来源分别保留最近 KEEP 份
  LC_ALL=C ls -1t "$ENC_DIR_HOST/$LABEL"-backup-*.enc 2>/dev/null | tail -n +$((KEEP + 1)) | while read -r old; do
    rm -f "$old" "$old.sha256"
    log "prune $(basename "$old")"
  done
  return 0
}

# 单来源：快照 -> process_archive；任何一步失败只返回 1，不退出整个备份
run_source() {
  SRC=$1
  case "$SRC" in
    haydn) SCRIPT=/data/server/bin/device-make-backup.sh ;;
    forgejo) SCRIPT=/data/server/bin/backup-forgejo.sh ;;
    vaultwarden) SCRIPT=/data/server/bin/backup-vaultwarden.sh ;;
    *) log "source fail label=$SRC stage=unknown-source"; return 1 ;;
  esac

  OUT=$("$SCRIPT" 2>&1)
  SRC_RC=$?
  if [ "$SRC_RC" -ne 0 ]; then
    log "source fail label=$SRC stage=snapshot rc=$SRC_RC detail=$(echo "$OUT" | tail -2 | tr '\n' ' ' | cut -c1-200)"
    return 1
  fi
  A=$(echo "$OUT" | sed -n 's/^ARCHIVE=//p' | tail -1)
  if [ -z "$A" ]; then
    log "source fail label=$SRC stage=snapshot reason=archive-not-parsed"
    return 1
  fi
  if [ "$SRC" != "haydn" ]; then
    log "$SRC snapshot: $(echo "$OUT" | grep -E '^(sqlite backup|manifest_lines|SIZE=)' | tr '\n' ' ')"
  fi

  process_archive "$A" "$SRC" || { log "source fail label=$SRC stage=pipeline"; return 1; }
  log "source ok label=$SRC"
  return 0
}

mkdir -p "$ROOT/logs" "$ROOT/run" "$ENC_DIR_HOST"
rotate_log
if ! mkdir "$LOCK" 2>/dev/null; then
  log "SKIP another backup running"
  exit 0
fi

log "START device-side backup sources=[$SOURCES]"
OKN=0
FAILN=0
FAILED=""
for SRC in $SOURCES; do
  case "$SRC" in
    haydn|forgejo|vaultwarden) ;;
    *) log "SKIP unknown source $SRC"; continue ;;
  esac
  if run_source "$SRC"; then
    OKN=$((OKN + 1))
  else
    FAILN=$((FAILN + 1))
    FAILED="$FAILED $SRC"
  fi
done

rm -f /data/local/tmp/haydn-backup-*.tar.gz /data/local/tmp/haydn-backup-*.tar 2>/dev/null
rm -f /data/local/tmp/forgejo-backup-*.tar.gz /data/local/tmp/forgejo-backup-*.tar 2>/dev/null
rm -f /data/local/tmp/vaultwarden-backup-*.tar.gz /data/local/tmp/vaultwarden-backup-*.tar 2>/dev/null
rm -rf /data/server/rootfs/srv/haydn/backup-stage 2>/dev/null

if [ "$FAILN" -gt 0 ]; then
  log "SUMMARY ok=$OKN fail=$FAILN failed=[$FAILED ]"
  fail "备份部分失败 ok=$OKN fail=$FAILN:$FAILED"
fi
log "DONE ok sources=$OKN"
rm -rf "$LOCK"
exit 0
