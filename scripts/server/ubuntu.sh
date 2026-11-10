#!/data/data/com.termux/files/usr/bin/bash
# 进入 Ubuntu 容器：$HOME/ubuntu.sh <命令>
# 2026-11-10 修复：不绑定 /sdcard、/storage（proot 对软链路径 sanitize 会触发 compare_paths2 断言崩溃 SIGABRT）
ROOT=$(readlink -f "$HOME/ubuntu")
export PROOT_NO_SECCOMP=1
exec proot --kill-on-exit --link2symlink -0 -r "$ROOT" \
  -b /dev -b /proc -b /sys \
  -b /dev/urandom:/dev/random \
  -b /proc/self/fd:/dev/fd \
  -b /proc/self/fd/0:/dev/stdin \
  -b /proc/self/fd/1:/dev/stdout \
  -b /proc/self/fd/2:/dev/stderr \
  -b "$HOME:/hosthome" \
  -w /root \
  /lib/ld-linux-aarch64.so.1 /usr/bin/env -i HOME=/root USER=root LOGNAME=root SHELL=/bin/bash \
  PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
  LANG=C.UTF-8 TERM=xterm-256color TMPDIR=/tmp \
  /bin/bash -lc "$*"
