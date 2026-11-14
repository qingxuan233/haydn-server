#!/system/bin/sh
# backup-vaultwarden.sh — Vaultwarden 数据一致性快照（SQLite 在线 backup，不阻塞写入）
# 供 haydn-backup.sh 调用；输出 /data/local/tmp/vaultwarden-backup-<TS>.tar.gz
# 只读源数据；策略：db 走 python sqlite3 backup API（含 WAL），其余文件直接复制。
set -u

STAGE_HOST=/data/server/rootfs/srv/haydn/backup-stage
STAGE_CHROOT=/srv/haydn/backup-stage
SRC_HOST=/data/server/rootfs/srv/haydn/vaultwarden
SRC_CHROOT=/srv/haydn/vaultwarden
CHROOT=/data/server/bin/chroot-enter.sh
OUT_DIR=/data/local/tmp

umask 077
rm -rf "$STAGE_HOST"
mkdir -p "$STAGE_HOST/data/server/rootfs/srv/haydn/vaultwarden" || exit 1
DST="$STAGE_HOST/data/server/rootfs/srv/haydn/vaultwarden"

# 1) SQLite 一致性备份（源用只读连接；目标写 stage；含 WAL 已提交内容）
"$CHROOT" /usr/bin/python3 - "$SRC_CHROOT/db.sqlite3" "$STAGE_CHROOT/data/server/rootfs/srv/haydn/vaultwarden/db.sqlite3" <<'PY' || exit 1
import sqlite3, sys
src = sqlite3.connect("file:%s?mode=ro" % sys.argv[1], uri=True)
dst = sqlite3.connect(sys.argv[2])
src.backup(dst)
dst.execute("PRAGMA wal_checkpoint(TRUNCATE)")
dst.commit()
ok = dst.execute("PRAGMA integrity_check").fetchone()[0]
dst.close(); src.close()
print("sqlite backup integrity_check=%s" % ok)
raise SystemExit(0 if ok == "ok" else 1)
PY

# 2) 密钥与附件（若有）
for f in rsa_key.pem config.json; do
  [ -f "$SRC_HOST/$f" ] && cp -p "$SRC_HOST/$f" "$DST/$f"
done
for d in attachments sends; do
  [ -d "$SRC_HOST/$d" ] && cp -Rp "$SRC_HOST/$d" "$DST/$d"
done

# 3) 清单元数据（不含任何密钥内容）
{
  echo "source=vaultwarden"
  echo "snapshot_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "db_mode=sqlite-backup-api"
} > "$STAGE_HOST/meta.txt"

# 4) 清单哈希（相对路径）
( cd "$STAGE_HOST" && find . -type f ! -name MANIFEST.sha256 | sort | while read -r f; do sha256sum "$f"; done ) > "$STAGE_HOST/MANIFEST.sha256"
echo "manifest_lines=$(wc -l < "$STAGE_HOST/MANIFEST.sha256")"

# 5) 打包
TS=$(date -u +%Y%m%dT%H%M%SZ)
TAR="$OUT_DIR/vaultwarden-backup-$TS.tar"
tar -cf "$TAR" -C "$STAGE_HOST" . || exit 1
gzip -9 "$TAR" || exit 1
rm -rf "$STAGE_HOST"
echo "ARCHIVE=$TAR.gz"
echo "SIZE=$(stat -c %s "$TAR.gz" 2>/dev/null || wc -c < "$TAR.gz")"
sha256sum "$TAR.gz"
echo DONE
