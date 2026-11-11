#!/bin/bash
# DSH 服务器收尾：原生模块 / 包装器 / supervisor / nginx /app 反代 / server-dsh
# 在 proot Ubuntu 内执行（通过 ubuntu.sh）
set -u

NODE=/opt/node24/bin/node
NPM=/opt/node24/bin/npm
DSHROOT=/opt/dsh/lib/node_modules/@deepseek-ai/dsh
CONF=/root/server/etc/supervisord.conf
SITE=/etc/nginx/sites-available/dsh-tls
UP=/etc/nginx/conf.d/dsh-upstreams.conf
LOG=/root/server/logs/dsh.log

echo "=== 1) 原生模块 ==="
if [ ! -d "$DSHROOT/node_modules/node-addon-require-builtin-linux-arm64-gnu" ]; then
  cd "$DSHROOT"
  "$NPM" install --no-save --no-audit --no-fund node-addon-require-builtin-linux-arm64-gnu@0.1.9 > /tmp/dsh-native.log 2>&1
  echo "native_exit=$?"
  tail -3 /tmp/dsh-native.log
else
  echo "native 已存在"
fi

echo "=== 2) /usr/local/bin/dsh 包装器（显式 Node24） ==="
rm -f /usr/local/bin/dsh
printf '#!/bin/sh\nexec /opt/node24/bin/node /opt/dsh/lib/node_modules/@deepseek-ai/dsh/lib/bin.js "$@"\n' > /usr/local/bin/dsh
chmod 755 /usr/local/bin/dsh
"$NODE" "$DSHROOT/lib/bin.js" --version 2>&1 | head -2
/usr/local/bin/dsh --version 2>&1 | head -2

echo "=== 3) supervisor [program:dsh] ==="
if grep -q '^\[program:dsh\]' "$CONF"; then
  echo "已存在 program:dsh"
else
  cat >> "$CONF" <<'EOF'

; DSH 内核（服务器自托管，2026-11-10 重建）
[program:dsh]
command=/opt/node24/bin/node /opt/dsh/lib/node_modules/@deepseek-ai/dsh/lib/bin.js web --host 127.0.0.1 --port 3081 --no-open --public-url https://47.97.70.99:44904/app/ --trusted-host 47.97.70.99:44904 --trusted-host 192.168.10.165:8443 --trusted-host 192.168.10.143:8443 --trusted-host 47.97.70.99 --trusted-host 192.168.10.165 --trusted-host 192.168.10.143
directory=/root
environment=HOME="/root",PATH="/opt/node24/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",DSH_PROFILE="server",DSH_PROFILE_DIR="/root/.dsh/profiles/server",NODE_OPTIONS="--max-old-space-size=768"
autostart=true
autorestart=true
startsecs=8
startretries=5
stopsignal=TERM
stopasgroup=true
killasgroup=true
stdout_logfile=/root/server/logs/dsh.log
stdout_logfile_maxbytes=3MB
stdout_logfile_backups=2
redirect_stderr=true
EOF
  echo "已写入 program:dsh"
fi
mkdir -p /root/.dsh/profiles/server
chmod 700 /root/.dsh 2>/dev/null || true

echo "=== 4) server-dsh 工具 ==="
cat > /root/server/bin/server-dsh <<'EOF2'
#!/bin/bash
CONF=/root/server/etc/supervisord.conf
LOG=/root/server/logs/dsh.log
case "${1:-url}" in
  status)  supervisorctl -c "$CONF" status dsh ;;
  url)     grep -oE 'http[s]://[^[:space:]]*token=[A-Za-z0-9_-]*' "$LOG" 2>/dev/null | tail -1 ;;
  restart) supervisorctl -c "$CONF" restart dsh ;;
  start)   supervisorctl -c "$CONF" start dsh ;;
  stop)    supervisorctl -c "$CONF" stop dsh ;;
  logs)    tail -n 40 "$LOG" ;;
  *) echo "用法: server-dsh [status|url|restart|start|stop|logs]"; exit 1 ;;
esac
EOF2
chmod 755 /root/server/bin/server-dsh
ln -sf /root/server/bin/server-dsh /usr/local/bin/server-dsh

echo "=== 5) nginx /app/ -> DSH 3081（前缀剥离） ==="
if ! grep -q 'upstream dsh_upstream' "$UP"; then
cat >> "$UP" <<'EOF3'

# DSH 自托管（127.0.0.1:3081），供 /app/ 前缀剥离反代使用
upstream dsh_upstream   { server 127.0.0.1:3081; keepalive 16; keepalive_timeout 60s; keepalive_requests 1000; }
EOF3
fi
python3 - <<'PY'
import re
p='/etc/nginx/sites-available/dsh-tls'
s=open(p).read()
new='''    # --- DSH 自托管：127.0.0.1:3081 的 8443 入口（复用原 /app/ 公网路径） ---
    location = /app-login {
        access_log off;
        absolute_redirect off;
        auth_basic "DSH App";
        auth_basic_user_file /root/server/etc/dsh-web.htpasswd;
        return 302 /app/;
    }

    location /app/ {
        if (-f /sdcard/DSH/dsh-app-public.off) { return 403; }

        access_log off;
        auth_basic "DSH App";
        auth_basic_user_file /root/server/etc/dsh-web.htpasswd;

        proxy_pass http://dsh_upstream/;
        proxy_http_version 1.1;
        proxy_set_header Host $http_host;
        proxy_set_header Origin "";
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header X-Forwarded-Host $http_host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection $dsh_connection_upgrade;
        proxy_cookie_flags ~ secure;

        proxy_request_buffering off;
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
    }

'''
pattern = r'    # --- App 自己的 DSH：.*?    # 项目文件只读挂载'
m = re.search(pattern, s, re.S)
if m:
    s = s[:m.start()] + new + '    # 项目文件只读挂载' + s[m.end():]
    open(p,'w').write(s)
    print('OK: nginx /app 已替换为 dsh_upstream')
else:
    print('WARN: 未找到旧 /app 块（可能已替换过）')
PY
nginx -t 2>&1 | tail -2
nginx -s reload 2>&1 || true

echo "=== 6) 启动 dsh ==="
supervisorctl -c "$CONF" reread >/dev/null 2>&1 || true
supervisorctl -c "$CONF" update >/dev/null 2>&1 || true
supervisorctl -c "$CONF" restart dsh >/dev/null 2>&1 || supervisorctl -c "$CONF" start dsh >/dev/null 2>&1 || true
for i in $(seq 1 20); do
  if grep -q 'token=' "$LOG" 2>/dev/null; then break; fi
  sleep 2
done
echo "--- status ---"
supervisorctl -c "$CONF" status dsh 2>&1 || true
echo "--- url ---"
grep -oE 'http[s]://[^[:space:]]*token=[A-Za-z0-9_-]*' "$LOG" 2>/dev/null | tail -1
echo "--- 本机 HTTP 测试 ---"
URL=$(grep -oE 'https://[^[:space:]]*token=[A-Za-z0-9_-]*' "$LOG" | tail -1)
if [ -n "${URL:-}" ]; then
  curl -k -s -o /dev/null -w "dsh_http=%{http_code}\n" --max-time 10 "$URL" || true
fi
echo DONE
