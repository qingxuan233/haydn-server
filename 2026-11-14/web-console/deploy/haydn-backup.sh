#!/system/bin/sh
# 设备侧夸克加密备份：逐来源快照 -> 加密 -> 自检 -> 上传 -> 保留策略
# 来源：haydn（整机配置/代码）、forgejo（Git 仓库数据）与 vaultwarden（密码库数据），后两者用 SQLite 一致性备份
# 由 backup-loop.sh 每日调用；也可手工执行。密码/令牌只在设备本地，不进日志。
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

# 加密 + 解密自检 + 上传；$1=明文归档路径 $2=标签（haydn|vaultwarden）
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

  i=1
  UP_OK=0
  while [ "$i" -le 3 ]; do
    SID="$(date +%s)-$RANDOM"
    UP=$("$CHROOT" env DSH_HOME=/root node "$QUARK_CLI" upload "/var/backups/haydn/$ENC_NAME" "/var/backups/haydn/$ENC_NAME.sha256" \
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

mkdir -p "$ROOT/logs" "$ROOT/run" "$ENC_DIR_HOST"
rotate_log
if ! mkdir "$LOCK" 2>/dev/null; then
  log "SKIP another backup running"
  exit 0
fi

log "START device-side backup"
OUT=$(/data/server/bin/device-make-backup.sh 2>&1) || fail "haydn snapshot failed"
A1=$(echo "$OUT" | sed -n 's/^ARCHIVE=//p' | tail -1)
[ -n "$A1" ] || fail "haydn archive not parsed"
process_archive "$A1" "haydn" || fail "haydn backup pipeline failed"

OUTF=$(/data/server/bin/backup-forgejo.sh 2>&1) || fail "forgejo snapshot failed"
A3=$(echo "$OUTF" | sed -n 's/^ARCHIVE=//p' | tail -1)
[ -n "$A3" ] || fail "forgejo archive not parsed"
log "forgejo snapshot: $(echo "$OUTF" | grep -E '^(sqlite backup|manifest_lines|SIZE=)' | tr '\n' ' ')"
process_archive "$A3" "forgejo" || fail "forgejo backup pipeline failed"

OUT2=$(/data/server/bin/backup-vaultwarden.sh 2>&1) || fail "vaultwarden snapshot failed"
A2=$(echo "$OUT2" | sed -n 's/^ARCHIVE=//p' | tail -1)
[ -n "$A2" ] || fail "vaultwarden archive not parsed"
log "vaultwarden snapshot: $(echo "$OUT2" | grep -E '^(sqlite backup|manifest_lines|SIZE=)' | tr '\n' ' ')"
process_archive "$A2" "vaultwarden" || fail "vaultwarden backup pipeline failed"

rm -f /data/local/tmp/haydn-backup-*.tar.gz /data/local/tmp/haydn-backup-*.tar 2>/dev/null
rm -f /data/local/tmp/forgejo-backup-*.tar.gz /data/local/tmp/forgejo-backup-*.tar 2>/dev/null
rm -f /data/local/tmp/vaultwarden-backup-*.tar.gz /data/local/tmp/vaultwarden-backup-*.tar 2>/dev/null
rm -rf /data/server/rootfs/srv/haydn/backup-stage 2>/dev/null

log "DONE ok"
rm -rf "$LOCK"
exit 0
