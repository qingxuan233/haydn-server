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
