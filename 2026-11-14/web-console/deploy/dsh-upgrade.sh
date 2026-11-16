#!/system/bin/sh
# DSH 升级脚本（更新 /opt/dsh 的 @deepseek-ai/dsh 版本并回归）
#
# 为什么需要它：健康检查每 5 分钟会把「非人工停止」的服务拉起；若直接
# `supervisorctl stop haydn-dsh` 后跑 npm install，健康检查会在安装中途把
# 服务拉起来 —— 半更新状态会让插件版本判定混乱（2026-11-16 rc.1→rc.3 升级
# 实测出现过 "disabling profile plugin row … incompatible" 中间态日志）。
# 本脚本先写 /srv/haydn/run/.stopped-haydn-dsh 标记（健康检查据此跳过自动拉起
# 与探针），升级完成并回归通过后再删除标记。
#
# 用法（设备侧，root）：
#   /data/server/bin/dsh-upgrade.sh 0.2.2-rc.3          # 升级到指定版本
#   /data/server/bin/dsh-upgrade.sh 0.2.2-rc.3 --dry-run
#
# 退出码：0=成功且已回归；1=升级/回归失败（已尝试回滚到升级前版本）；2=用法错误。
# 证据：/data/server/logs/dsh-upgrade.log（每次一行时间戳 + 关键状态，不含 token）。
set -u

TARGET=""
DRY=0
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY=1 ;;
    -h|--help) sed -n '3,18p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) TARGET="$arg" ;;
  esac
done
[ -n "$TARGET" ] || { echo "用法：dsh-upgrade.sh <版本，如 0.2.2-rc.3> [--dry-run]" >&2; exit 2; }
case "$TARGET" in *[!a-zA-Z0-9._-]*) echo "版本号不合法：$TARGET" >&2; exit 2 ;; esac

ROOT=/data/server
CHROOT=$ROOT/bin/chroot-enter.sh
SUP="$CHROOT /usr/bin/supervisorctl -c /etc/supervisor/supervisord.conf"
MARKSTOP=$ROOT/rootfs/srv/haydn/run/.stopped-haydn-dsh
LOG=$ROOT/logs/dsh-upgrade.log
NODE=/opt/node24/bin/node
BIN=/opt/dsh/lib/node_modules/@deepseek-ai/dsh/lib/bin.js

log() { echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) $*" >> "$LOG"; }
dsh_version() {
  $CHROOT sh -c "PATH=/opt/node24/bin:\$PATH $NODE $BIN --version" 2>/dev/null | tail -1
}
probe_live() {
  code=$($CHROOT sh -c "curl -s -o /dev/null -w '%{http_code}' -m 5 http://127.0.0.1:3080/" 2>/dev/null)
  case "$code" in 200|401) return 0 ;; *) return 1 ;; esac
}

PREV=$(dsh_version)
log "upgrade start target=$TARGET prev=$PREV dry_run=$DRY"
echo "prev=$PREV target=$TARGET"

if [ "$DRY" = "1" ]; then
  echo "dry-run：将写标记 $MARKSTOP、stop haydn-dsh、npm install -g --prefix /opt/dsh @deepseek-ai/dsh@$TARGET、回归后删标记"
  exit 0
fi

mkdir -p "$(dirname "$MARKSTOP")" 2>/dev/null
: > "$MARKSTOP" || { echo "无法写标记（需 root）" >&2; exit 1; }
$SUP stop haydn-dsh >/dev/null 2>&1
log "service stopped (marker written)"

$CHROOT sh -c "export PATH=/opt/node24/bin:\$PATH HOME=/root
  /opt/node24/bin/npm install -g --prefix /opt/dsh @deepseek-ai/dsh@$TARGET" >> "$LOG" 2>&1
rc=$?
if [ "$rc" -ne 0 ]; then
  log "install failed rc=$rc; rollback to $PREV"
  if [ -n "$PREV" ]; then
    $CHROOT sh -c "export PATH=/opt/node24/bin:\$PATH HOME=/root
      /opt/node24/bin/npm install -g --prefix /opt/dsh @deepseek-ai/dsh@$PREV" >> "$LOG" 2>&1
  fi
  rm -f "$MARKSTOP"
  $SUP start haydn-dsh >/dev/null 2>&1
  echo "FAILED：安装失败，已回滚到 $PREV"
  exit 1
fi

GOT=$(dsh_version)
if [ "$GOT" != "$TARGET" ]; then
  log "version mismatch got=$GOT expected=$TARGET; rollback"
  $CHROOT sh -c "export PATH=/opt/node24/bin:\$PATH HOME=/root
    /opt/node24/bin/npm install -g --prefix /opt/dsh @deepseek-ai/dsh@$PREV" >> "$LOG" 2>&1
  rm -f "$MARKSTOP"
  $SUP start haydn-dsh >/dev/null 2>&1
  echo "FAILED：版本回读 $GOT 与目标 $TARGET 不符，已回滚"
  exit 1
fi
log "installed version=$GOT"

rm -f "$MARKSTOP"
$SUP start haydn-dsh >/dev/null 2>&1
# rc.3 冷启动约 20–40s：轮询最长 120s，避免把"还没监听"误判为失败
ready=0
i=0
while [ "$i" -lt 24 ]; do
  sleep 5
  i=$((i + 1))
  if probe_live; then ready=1; break; fi
done
if [ "$ready" = "1" ] && $SUP status 2>/dev/null | grep -q 'haydn-dsh.*RUNNING'; then
  log "regression ok port=alive version=$GOT"
  echo "OK：$PREV → $GOT，服务 RUNNING，127.0.0.1:3080 存活"
  echo "提示：如插件提示 incompatible，请在插件管理器更新插件版本或按提示授予精确版本豁免。"
  exit 0
fi
log "regression FAILED version=$GOT"
echo "FAILED：服务启动或探针失败，保留新版本但请人工检查 /srv/haydn/logs/dsh.log" >&2
exit 1
