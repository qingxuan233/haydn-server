#!/system/bin/sh
# Web 控制台安装脚本（在设备上以 root 执行；不重启服务、不改 stunnel/frpc）
# 用法：adb push 后在设备上执行  su -c "sh /data/local/tmp/web-console/install.sh"
# 幂等：重复执行只覆盖文件；配置/口令已存在时不覆盖。
set -eu

STAGE=${1:-/data/local/tmp/web-console}
ROOTFS=/data/server/rootfs
BACKUP=/data/server/backups/console-20261114
TS=$(date -u +%Y%m%dT%H%M%SZ)

echo "[1/7] 备份现有配置到 $BACKUP"
mkdir -p "$BACKUP"
cp -f "$ROOTFS/etc/supervisor/conf.d/haydn.conf" "$BACKUP/haydn.conf.$TS" 2>/dev/null || true
cp -f /data/server/bin/chroot-enter.sh "$BACKUP/chroot-enter.sh.$TS" 2>/dev/null || true
cp -f /data/server/bin/backup-loop.sh "$BACKUP/backup-loop.sh.$TS" 2>/dev/null || true
cp -f "$ROOTFS/etc/stunnel/haydn-tls.conf" "$BACKUP/haydn-tls.conf.$TS" 2>/dev/null || true
echo "backup files:"; ls -1 "$BACKUP" | tail -8

echo "[2/7] 安装控制台源码到 $ROOTFS/opt/haydn/console"
mkdir -p "$ROOTFS/opt/haydn/console"
cp -f "$STAGE"/console/*.py "$ROOTFS/opt/haydn/console/"
chmod 755 "$ROOTFS/opt/haydn/console"
chmod 644 "$ROOTFS/opt/haydn/console"/*.py

echo "[3/7] 安装配置（已存在则不覆盖）"
mkdir -p "$ROOTFS/etc/haydn-console" "$ROOTFS/srv/haydn/logs" "$ROOTFS/srv/haydn/run"
if [ -f "$ROOTFS/etc/haydn-console/gateway.json" ]; then
  echo "keep existing gateway.json"
else
  cp -f "$STAGE/console/config.example.json" "$ROOTFS/etc/haydn-console/gateway.json"
  chmod 644 "$ROOTFS/etc/haydn-console/gateway.json"
fi

echo "[4/7] 安装 supervisor 程序定义 haydn-console-gateway"
cp -f "$STAGE/deploy/haydn-console.conf" "$ROOTFS/etc/supervisor/conf.d/haydn-console.conf"
chmod 644 "$ROOTFS/etc/supervisor/conf.d/haydn-console.conf"

echo "[5/7] 静态站后移 18080 -> 18081（保持 stunnel 指向 18080）"
if grep -q 'http.server 18080' "$ROOTFS/etc/supervisor/conf.d/haydn.conf"; then
  sed -i 's/-m http\.server 18080/-m http.server 18081/' "$ROOTFS/etc/supervisor/conf.d/haydn.conf"
  echo "patched haydn-local-http -> 18081"
else
  echo "haydn-local-http already patched"
fi

echo "[6/7] 更新宿主脚本（chroot-enter / backup-loop，含回滚备份）"
cp -f "$STAGE/deploy/chroot-enter.sh" /data/server/bin/chroot-enter.sh
cp -f "$STAGE/deploy/backup-loop.sh" /data/server/bin/backup-loop.sh
chmod 755 /data/server/bin/chroot-enter.sh /data/server/bin/backup-loop.sh
sh -n /data/server/bin/chroot-enter.sh
sh -n /data/server/bin/backup-loop.sh

echo "[7/7] 完成。下一步（人工执行，见 README）:"
echo "  - 初始化口令: chroot-enter.sh /usr/bin/python3 /opt/haydn/console/gateway.py --config /etc/haydn-console/gateway.json --init-admin"
echo "  - 应用 supervisor: chroot-enter.sh /usr/bin/supervisorctl -c /etc/supervisor/supervisord.conf reread"
echo "                    chroot-enter.sh /usr/bin/supervisorctl -c /etc/supervisor/supervisord.conf update"
echo "  - 回滚: $BACKUP/ 内文件覆盖回原路径后 supervisorctl reread/update"
