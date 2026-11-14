#!/system/bin/sh
# 进入 Ubuntu chroot：确保 /proc /sys /dev 绑定挂载，然后以 bash 登录 shell 执行命令。
# 2026-11-14：追加 /srv/haydn/{logs,run} 绑定（控制台读宿主日志/写备份触发），幂等。
# 2026-11-14 修复：同文件系统上的 bind mount 用 mountpoint -q 会误判“未挂载”，
# 导致每次进入都重复 mount，最终耗尽内核 mount 上限（mount 返回 ENOSPC、df 卡死）。
# 改为比较源/目标的设备+inode，已挂载则跳过。
ROOTFS=/data/server/rootfs

mounted() {
  # bind mount 成功后目标是源的别名（同设备+同 inode）。mountpoint -q 对同文件系统
  # 的 bind 会误判；grep /proc/mounts 在 mount 表很大时又太慢，故用 stat 比较。
  a=$(stat -c '%d:%i' "$1" 2>/dev/null)
  b=$(stat -c '%d:%i' "$2" 2>/dev/null)
  [ -n "$a" ] && [ "$a" = "$b" ]
}

for p in proc sys dev; do
  if ! mountpoint -q "$ROOTFS/$p"; then
    mount -o bind "/$p" "$ROOTFS/$p" || { echo "mount /$p failed" >&2; exit 1; }
  fi
done
if ! mountpoint -q "$ROOTFS/dev/pts"; then
  mount -o bind /dev/pts "$ROOTFS/dev/pts" || true
fi

# Web 控制台数据面：宿主 logs/run 只读/写触发绑定进 chroot
for d in logs run; do
  src="/data/server/$d"
  dst="$ROOTFS/srv/haydn/$d"
  mkdir -p "$src" "$dst" 2>/dev/null
  if ! mounted "$src" "$dst"; then
    mount -o bind "$src" "$dst" || echo "mount $dst failed" >&2
  fi
done

[ $# -gt 0 ] || set -- /bin/bash -l
exec chroot "$ROOTFS" /usr/bin/env -i \
  HOME=/root \
  PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
  TERM=dumb \
  "$@"
