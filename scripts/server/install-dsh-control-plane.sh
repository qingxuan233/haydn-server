#!/bin/bash
# 在手机服务器（proot Ubuntu）内安装 DSH 控制平面 P0（机器本地）
# 用法：把本目录文件放到设备 /root/_tmp_dshcp 后执行本脚本；或直接在设备上运行。
# 不做外部依赖（不透传外部告警/异地备份）。
set -eu
BASE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
CONF=/root/server/etc/supervisord.conf

echo "=== 1) 安装 dsh-guard / server-ops / AGENTS ==="
cp "$BASE/dsh-guard" /root/server/bin/dsh-guard
chmod 755 /root/server/bin/dsh-guard
cp "$BASE/server-ops" /root/server/bin/server-ops
chmod 755 /root/server/bin/server-ops
ln -sf /root/server/bin/server-ops /usr/local/bin/server-ops
mkdir -p /root/server/ops
cp "$BASE/AGENTS.md" /root/AGENTS.md
cp "$BASE/AGENTS.md" /root/server/ops/AGENTS.md
cp "$BASE/dsh-guard.conf" /root/server/etc/conf.d/dsh-guard.conf

echo "=== 2) server-backup 补丁（DSH storages/profiles + ops/bin） ==="
python3 "$BASE/patch-server-backup-dsh.py"
bash -n /root/server/bin/server-backup && echo 'server-backup syntax OK'

echo "=== 3) nginx 限流 ==="
python3 "$BASE/patch-nginx-dsh-ratelimit.py"
nginx -t
nginx -s reload

echo "=== 4) supervisor 加载 dsh-guard ==="
supervisorctl -c "$CONF" reread
supervisorctl -c "$CONF" update
sleep 2
supervisorctl -c "$CONF" status dsh dsh-login dsh-guard

echo "=== 5) server-ops 只读自检 ==="
/root/server/bin/server-ops status | head -10
/root/server/bin/server-ops health
echo "完成。下一步：执行 /root/server/bin/server-backup 5 并验证备份含 .dsh/ 与 bin/server-ops。"
