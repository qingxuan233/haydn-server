#!/system/bin/sh
# backup-forgejo.sh — Forgejo 数据一致性快照（SQLite 在线 backup，不阻塞写入）
# 供 haydn-backup.sh 调用；输出 /data/local/tmp/forgejo-backup-<TS>.tar.gz
# 只读源数据；策略：db 走 python sqlite3 backup API（含 WAL），仓库与附件目录直接复制。
set -u

STAGE_HOST=/data/server/rootfs/srv/haydn/backup-stage
STAGE_CHROOT=/srv/haydn/backup-stage
SRC_HOST=/data/server/rootfs/srv/haydn/forgejo
SRC_CHROOT=/srv/haydn/forgejo
CFG_HOST=/data/server/rootfs/etc/haydn/forgejo
CHROOT=/data/server/bin/chroot-enter.sh
OUT_DIR=/data/local/tmp

umask 077
rm -rf "$STAGE_HOST"
mkdir -p "$STAGE_HOST/data/server/rootfs/srv/haydn/forgejo/data" \
         "$STAGE_HOST/data/server/rootfs/etc/haydn/forgejo" || exit 1
DST="$STAGE_HOST/data/server/rootfs/srv/haydn/forgejo"

# 1) SQLite 一致性备份（源用只读连接；目标写 stage；含 WAL 已提交内容）
"$CHROOT" /usr/bin/python3 - "$SRC_CHROOT/data/forgejo.db" "$STAGE_CHROOT/data/server/rootfs/srv/haydn/forgejo/data/forgejo.db" <<'PY' || exit 1
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

# 2) 仓库与数据子目录（跳过可重建的 tmp/queues/indexers 与日志）
[ -d "$SRC_HOST/repositories" ] && cp -Rp "$SRC_HOST/repositories" "$DST/repositories"
for d in actions_id_token attachments avatars home jwt packages repo-archive repo-avatars; do
  [ -d "$SRC_HOST/data/$d" ] && cp -Rp "$SRC_HOST/data/$d" "$DST/data/$d"
done

# 3) 配置（含 ROOT_URL/DB_TYPE 等服务端关键项；不含任何外部口令）
[ -f "$CFG_HOST/app.ini" ] && cp -p "$CFG_HOST/app.ini" "$STAGE_HOST/data/server/rootfs/etc/haydn/forgejo/app.ini"

# 4) 清单元数据
{
  echo "source=forgejo"
  echo "snapshot_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "db_mode=sqlite-backup-api"
} > "$STAGE_HOST/meta.txt"

# 5) 清单哈希（相对路径）
( cd "$STAGE_HOST" && find . -type f ! -name MANIFEST.sha256 | sort | while read -r f; do sha256sum "$f"; done ) > "$STAGE_HOST/MANIFEST.sha256"
echo "manifest_lines=$(wc -l < "$STAGE_HOST/MANIFEST.sha256")"

# 6) 打包（toybox tar 无 -z，gzip 分开）
TS=$(date -u +%Y%m%dT%H%M%SZ)
TAR="$OUT_DIR/forgejo-backup-$TS.tar"
tar -cf "$TAR" -C "$STAGE_HOST" . || exit 1
gzip -9 "$TAR" || exit 1
rm -rf "$STAGE_HOST"
echo "ARCHIVE=$TAR.gz"
echo "SIZE=$(stat -c %s "$TAR.gz" 2>/dev/null || wc -c < "$TAR.gz")"
sha256sum "$TAR.gz"
echo DONE
