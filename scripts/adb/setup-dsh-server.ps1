<#
.SYNOPSIS
    在手机服务器（proot Ubuntu arm64）中安装 DSH（@deepseek-ai/dsh），并做 Linux 环境优化。
.DESCRIPTION
    步骤：Node 24（arm64）→ npm 全局安装 DSH → 写入 supervisord [program:dsh]（127.0.0.1:3081）
          → 生成 /root/server/bin/server-dsh 工具 → apt 缓存清理/nginx gzip 等环境优化。
    幂等：已安装的步骤会跳过；可重复执行。
.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\adb\setup-dsh-server.ps1
#>
[CmdletBinding()]
param(
    [string]$KeyPath = '',
    [string]$SshHost = '192.168.10.143',
    [int]$SshPort = 2222,
    [string]$SshUser = 'root',
    [string]$NodeVersion = 'v24.22.2',
    [string]$DshVersion = '0.2.2-rc.1',
    [switch]$SkipLinuxOptimize
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
if (-not $KeyPath) { $KeyPath = Join-Path $repoRoot 'backup\ssh\id_haydn' }
if (-not (Test-Path -LiteralPath $KeyPath)) { throw "找不到 SSH 私钥：$KeyPath" }

$bash = @'
#!/bin/bash
set -eu
NODE_VER="__NODE_VER__"
DSH_VER="__DSH_VER__"
NODE_DIR=/opt/node24
DSH_PREFIX=/opt/dsh
CONF=/root/server/etc/supervisord.conf
LOG=/root/server/logs/dsh.log
URLPORT=3081

echo "============================================================"
echo "[1/6] Node.js $NODE_VER (linux-arm64)"
if [ ! -x "$NODE_DIR/bin/node" ]; then
  curl -fsSL --retry 3 -o /tmp/node.tar.xz "https://nodejs.org/dist/$NODE_VER/node-$NODE_VER-linux-arm64.tar.xz"
  tar -xJf /tmp/node.tar.xz -C /opt
  rm -rf "$NODE_DIR"
  mv "/opt/node-$NODE_VER-linux-arm64" "$NODE_DIR"
  rm -f /tmp/node.tar.xz
fi
"$NODE_DIR/bin/node" -v
export PATH="$NODE_DIR/bin:$PATH"

echo "============================================================"
echo "[2/6] npm 全局安装 @deepseek-ai/dsh@$DSH_VER -> $DSH_PREFIX"
if [ ! -f "$DSH_PREFIX/lib/node_modules/@deepseek-ai/dsh/package.json" ]; then
  mkdir -p "$DSH_PREFIX"
  "$NODE_DIR/bin/npm" install -g --prefix "$DSH_PREFIX" "@deepseek-ai/dsh@$DSH_VER" --no-audit --no-fund
  "$NODE_DIR/bin/npm" cache clean --force >/dev/null 2>&1 || true
else
  echo "已安装，跳过"
fi
"$DSH_PREFIX/bin/dsh" --version 2>&1 | head -3 || true
mkdir -p /root/.dsh/profiles/server

echo "============================================================"
echo "[3/6] 探测 dsh web 支持的参数"
OPENFLAG=""
if "$DSH_PREFIX/bin/dsh" web --help 2>&1 | grep -q -- '--no-open'; then OPENFLAG="--no-open"; fi
HOSTFLAG=""
if "$DSH_PREFIX/bin/dsh" web --help 2>&1 | grep -q -- '--host'; then HOSTFLAG="--host 127.0.0.1"; else HOSTFLAG=""; fi
PORTFLAG=""
if "$DSH_PREFIX/bin/dsh" web --help 2>&1 | grep -q -- '--port'; then PORTFLAG="--port $URLPORT"; else PORTFLAG=""; fi
echo "flags: host='$HOSTFLAG' port='$PORTFLAG' open='$OPENFLAG'"

echo "============================================================"
echo "[4/6] 写入 supervisord [program:dsh]"
if grep -q '^\[program:dsh\]' "$CONF"; then
  echo "已存在 program:dsh，跳过"
else
  cat >> "$CONF" <<EOF

; DSH 内核（服务器自托管，2026-11-10 安装）
[program:dsh]
command=$DSH_PREFIX/bin/dsh web $HOSTFLAG $PORTFLAG $OPENFLAG
directory=/root
environment=HOME="/root",PATH="$NODE_DIR/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",DSH_PROFILE="server",DSH_PROFILE_DIR="/root/.dsh/profiles/server",NODE_OPTIONS="--max-old-space-size=768"
autostart=true
autorestart=true
startsecs=8
startretries=5
stopsignal=TERM
stopasgroup=true
killasgroup=true
stdout_logfile=$LOG
stdout_logfile_maxbytes=3MB
stdout_logfile_backups=2
redirect_stderr=true
EOF
fi

echo "============================================================"
echo "[5/6] 生成 server-dsh 工具"
cat > /root/server/bin/server-dsh <<'EOF'
#!/bin/bash
CONF=/root/server/etc/supervisord.conf
LOG=/root/server/logs/dsh.log
case "${1:-url}" in
  status)  supervisorctl -c "$CONF" status dsh ;;
  url)     grep -o 'http://127.0.0.1:3081/?token=[A-Za-z0-9_-]*' "$LOG" 2>/dev/null | tail -1 ;;
  restart) supervisorctl -c "$CONF" restart dsh ;;
  start)   supervisorctl -c "$CONF" start dsh ;;
  stop)    supervisorctl -c "$CONF" stop dsh ;;
  logs)    tail -n 40 "$LOG" ;;
  *) echo "用法: server-dsh [status|url|restart|start|stop|logs]"; exit 1 ;;
esac
EOF
chmod 755 /root/server/bin/server-dsh
ln -sf /root/server/bin/server-dsh /usr/local/bin/server-dsh
ln -sf "$DSH_PREFIX/bin/dsh" /usr/local/bin/dsh

echo "============================================================"
echo "[6/6] supervisor 重载并启动"
supervisorctl -c "$CONF" reread >/dev/null 2>&1 || true
supervisorctl -c "$CONF" update >/dev/null 2>&1 || true
supervisorctl -c "$CONF" restart dsh >/dev/null 2>&1 || supervisorctl -c "$CONF" start dsh >/dev/null 2>&1 || true
for i in $(seq 1 20); do
  if grep -q 'token=' "$LOG" 2>/dev/null; then break; fi
  sleep 2
done
supervisorctl -c "$CONF" status dsh 2>&1 || true
echo "--- token url ---"
server-dsh url 2>&1 || true
echo "--- log tail ---"
tail -n 8 "$LOG" 2>/dev/null || true

echo "============================================================"
echo "[+] Linux 环境优化"
__LINUX_OPT__
df -h / | tail -1
free -m | head -3
'@

$linuxOpt = @'
apt-get -y clean >/dev/null 2>&1 || true
apt-get -y autoremove >/dev/null 2>&1 || true
rm -rf /var/cache/apt/archives/*.deb /var/cache/apt/*.bin 2>/dev/null || true
if ! grep -Rqs 'gzip on' /etc/nginx/nginx.conf /etc/nginx/conf.d/*.conf 2>/dev/null; then
  cat > /etc/nginx/conf.d/zz-optimize.conf <<'EOF2'
# 2026-11-10 Lead：开启 gzip（公网经 frp 访问，减小传输体积）
gzip on;
gzip_comp_level 5;
gzip_min_length 256;
gzip_proxied any;
gzip_vary on;
gzip_types text/plain text/css application/json application/javascript application/xml text/xml image/svg+xml;
EOF2
  nginx -t >/dev/null 2>&1 && nginx -s reload >/dev/null 2>&1 || echo "nginx gzip 配置未生效（已保留文件待查）"
  echo "nginx gzip: 已启用"
else
  echo "nginx gzip: 已存在，跳过"
fi
rm -f /tmp/node.tar.xz 2>/dev/null || true
'@

$bash = $bash.Replace('__NODE_VER__', $NodeVersion).Replace('__DSH_VER__', $DshVersion).Replace('__LINUX_OPT__', $linuxOpt)
if ($SkipLinuxOptimize) { $bash = $bash.Replace($linuxOpt, 'echo "[跳过] Linux 优化"') }
$bash = $bash -replace "`r`n", "`n"

$tmp = Join-Path $env:TEMP 'setup-dsh-server.sh'
[System.IO.File]::WriteAllText($tmp, $bash, $utf8NoBom)

Write-Host '=== 推送安装脚本到服务器 ==='
& scp -i $KeyPath -P $SshPort -o BatchMode=yes -o StrictHostKeyChecking=accept-new $tmp "${SshUser}@${SshHost}:/root/setup-dsh-server.sh" 2>&1 | Select-Object -Last 2
if ($LASTEXITCODE -ne 0) { throw 'scp 失败' }

Write-Host '=== 在服务器执行（安装可能需数分钟）==='
& ssh -i $KeyPath -p $SshPort -o BatchMode=yes -o ConnectTimeout=15 -o StrictHostKeyChecking=accept-new "${SshUser}@${SshHost}" 'bash /root/setup-dsh-server.sh' 2>&1
$sshExit = $LASTEXITCODE
Write-Host ''
Write-Host ("EXIT=" + $sshExit)
if ($sshExit -ne 0) { Write-Host '[WARN] 脚本返回非 0，请检查上方输出' -ForegroundColor Yellow }
