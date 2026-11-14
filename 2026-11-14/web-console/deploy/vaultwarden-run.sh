#!/bin/sh
# vaultwarden-run.sh — 加载非敏感配置与管理员 token 后启动 vaultwarden
# 用法（supervisor 调用）：/opt/haydn/bin/vaultwarden-run.sh
# ADMIN_TOKEN 只从 600 的 secrets 文件读入环境，不写日志、不进命令行。
set -eu
umask 077

ENV_FILE=${HAYDN_VAULTWARDEN_ENV:-/etc/haydn/vaultwarden.env}
BIN=${HAYDN_VAULTWARDEN_BIN:-/opt/haydn/bin/vaultwarden}
TOKEN_FILE=${HAYDN_VAULTWARDEN_TOKEN_FILE:-/opt/haydn/secrets/vaultwarden-admin-token}

if [ -r "$ENV_FILE" ]; then
  set -a
  . "$ENV_FILE"
  set +a
fi

if [ -s "$TOKEN_FILE" ]; then
  ADMIN_TOKEN=$(cat "$TOKEN_FILE")
  export ADMIN_TOKEN
fi

# 以 root 读取 600 的配置/token 后，再降权到 vaultwarden 运行
if [ "$(id -u)" = "0" ] && [ -x /usr/bin/setpriv ] && id -u vaultwarden >/dev/null 2>&1; then
  exec /usr/bin/setpriv --reuid "$(id -u vaultwarden)" --regid "$(id -g vaultwarden)" \
    --clear-groups "$BIN"
fi

exec "$BIN"
