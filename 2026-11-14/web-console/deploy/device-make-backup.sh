#!/system/bin/sh
# 整机配置/代码快照（不含 Vaultwarden 二进制与 web-vault，避免每日备份膨胀）
STAGE=/data/local/tmp/haydn-backup-stage
OUT_DIR=/data/local/tmp
rm -rf "$STAGE"
mkdir -p "$STAGE/data/server" "$STAGE/data/adb/modules" "$STAGE/meta"

# server config/custom assets (absolute layout preserved)
cp -r /data/server/bin "$STAGE/data/server/bin"
cp -r /data/server/etc "$STAGE/data/server/etc"
mkdir -p "$STAGE/data/server/rootfs/usr/local" "$STAGE/data/server/rootfs/root"
cp -r /data/server/rootfs/etc "$STAGE/data/server/rootfs/etc"
cp -r /data/server/rootfs/usr/local/bin "$STAGE/data/server/rootfs/usr/local/bin"
cp -r /data/server/rootfs/root/.ssh "$STAGE/data/server/rootfs/root/.ssh"
# 代码类工具纳入快照；凭据（/root/.haydn-backup-pass、.quark-drive）绝不入包
mkdir -p "$STAGE/data/server/rootfs/opt/quark" "$STAGE/data/server/rootfs/opt/haydn"
cp -r /data/server/rootfs/opt/haydn/. "$STAGE/data/server/rootfs/opt/haydn/"
# 可重建的大二进制（vaultwarden/forgejo/web-vault，约 313MB）不入每日备份；
# 配置文件、数据与脚本仍完整入包。
rm -rf "$STAGE/data/server/rootfs/opt/haydn/bin/vaultwarden" \
       "$STAGE/data/server/rootfs/opt/haydn/bin/forgejo" \
       "$STAGE/data/server/rootfs/opt/haydn/vaultwarden-web-vault"
cp -r /data/server/rootfs/opt/quark/scripts "$STAGE/data/server/rootfs/opt/quark/scripts"
# Netdata：只备配置；dbengine 历史库（512MiB 上限）可再生，不进每日快照
mkdir -p "$STAGE/data/server/rootfs/opt/netdata"
cp -r /data/server/rootfs/opt/netdata/etc "$STAGE/data/server/rootfs/opt/netdata/etc"
# AList：配置与数据库入包；sqlite 为 WAL 模式，db/wal/shm 三个文件一起拷避免单文件撕裂；
# data/temp、data/log 可再生，不入包；110MB 二进制不入包（可从 release 重下）
mkdir -p "$STAGE/data/server/rootfs/opt/alist/data"
cp -f /data/server/rootfs/opt/alist/data/config.json "$STAGE/data/server/rootfs/opt/alist/data/" 2>/dev/null
cp -f /data/server/rootfs/opt/alist/data/data.db /data/server/rootfs/opt/alist/data/data.db-wal /data/server/rootfs/opt/alist/data/data.db-shm "$STAGE/data/server/rootfs/opt/alist/data/" 2>/dev/null
mkdir -p "$STAGE/data/server/rootfs/var/log"
cp -r /data/server/rootfs/var/log/haydn "$STAGE/data/server/rootfs/var/log/haydn"
cp -r /data/server/logs "$STAGE/data/server/logs"
cp -r /data/adb/modules/server-chroot "$STAGE/data/adb/modules/server-chroot"

# metadata for restore reference (no secrets)
date -u +%Y-%m-%dT%H:%M:%SZ > "$STAGE/meta/backup-time.txt"
getprop ro.build.version.ota > "$STAGE/meta/build-ota.txt"
getprop ro.build.version.release > "$STAGE/meta/build-release.txt"
getprop ro.build.version.security_patch > "$STAGE/meta/build-security-patch.txt"
getprop ro.build.fingerprint > "$STAGE/meta/build-fingerprint.txt"
pm list packages -d > "$STAGE/meta/disabled-packages.txt" 2>/dev/null
pm list packages -e > "$STAGE/meta/enabled-packages.txt" 2>/dev/null
settings list system 2>/dev/null | grep -iE 'charge_protection|regular_charge' > "$STAGE/meta/charge-protection-settings.txt"
iptables -S INPUT > "$STAGE/meta/iptables-input.txt" 2>/dev/null
cat /data/server/logs/soak-start.txt > "$STAGE/meta/soak-start.txt" 2>/dev/null
cat /data/server/logs/soak-baseline.txt > "$STAGE/meta/soak-baseline.txt" 2>/dev/null

# 观测证据归档（2026-11-16）：生成一次 soak 摘要（peaks/可用率/看门狗/告警/健康/服务）随包入库，
# 便于"备份包自身即可证明观测期状态"。脚本缺失只记一行，不阻断备份。
mkdir -p "$STAGE/meta/observability"
if [ -x /data/server/bin/soak-summary.sh ]; then
  /data/server/bin/soak-summary.sh >/dev/null 2>&1
  latest=$(ls -t /data/server/logs/soak-summary-*.txt 2>/dev/null | head -1)
  [ -n "$latest" ] && cp -f "$latest" "$STAGE/meta/observability/"
  cp -f /data/server/logs/watchdog.log "$STAGE/meta/observability/" 2>/dev/null
  cp -f /data/server/logs/alerts.log "$STAGE/meta/observability/" 2>/dev/null
  cp -f /data/server/logs/wifi-guard.log "$STAGE/meta/observability/" 2>/dev/null
  echo "observability=$(ls "$STAGE/meta/observability" | wc -l) 个文件" >> "$STAGE/meta/observability/index.txt"
else
  echo "soak-summary.sh 缺失，跳过观测证据归档" >> "$STAGE/meta/observability/index.txt"
fi

# checksum manifest (relative paths; exclude the manifest itself to avoid a self-referential hash)
cd "$STAGE" || exit 1
(find . -type f ! -name MANIFEST.sha256 | sort | while read -r f; do sha256sum "$f"; done) > /data/local/tmp/manifest.txt
mv /data/local/tmp/manifest.txt "$STAGE/MANIFEST.sha256"
echo "manifest_lines=$(wc -l < MANIFEST.sha256)"

# archive: toybox tar has no -z, gzip separately
TS=$(date -u +%Y%m%dT%H%M%SZ)
TAR="$OUT_DIR/haydn-backup-$TS.tar"
gz="$TAR.gz"
tar -cf "$TAR" -C "$STAGE" . || exit 1
gzip -9 "$TAR" || exit 1
rm -rf "$STAGE"
echo "ARCHIVE=$gz"
echo "SIZE=$(stat -c %s "$gz" 2>/dev/null || wc -c < "$gz")"
sha256sum "$gz"
echo DONE
