#!/bin/sh
echo "=== credentials refs (names only) ==="
python3 - <<'PY'
import re
p='/root/.dsh/.credentials.yaml'
try:
    t=open(p).read()
except Exception as e:
    print('ERR',e); raise SystemExit
# 打印键名与值长度，不打印值
inrefs=False
for line in t.splitlines():
    if line.strip()=='refs:':
        inrefs=True; continue
    if inrefs:
        m=re.match(r'^  ([A-Za-z0-9_]+):\s*(.*)$', line)
        if m:
            print(m.group(1), 'len=%d' % len(m.group(2).strip()))
        elif line.strip() and not line.startswith(' '):
            break
PY
echo "=== web profile patch entry ids ==="
grep -n '^- id:' /root/.dsh/profiles/web/cordis.patch.yml 2>/dev/null
echo "=== plugin packages available ==="
D=/opt/dsh/lib/node_modules/@deepseek-ai/dsh/node_modules/@deepseek-ai
for p in dsh-plugin-market dsh-llm-pi-ai dsh-subagent dsh-client-ui-theme dsh-agent-preset-registry dsh-client-ui-settings-account dsh-client-ui-chat dsh-client-ui-settings; do
  [ -e "$D/$p" ] && echo "YES $p" || echo "NO  $p"
done
[ -e /opt/dsh/lib/node_modules/@deepseek-ai/dsh/node_modules/@linxin666 ] && echo "linxin666 present" || echo "linxin666 absent"
echo "=== dump-config 当前是否可用 ==="
cd /root
DSH_HOME=/root/.dsh /usr/local/bin/dsh --profile web --dump-config 2>/tmp/dump.err | head -40
echo "dump_err:"; head -8 /tmp/dump.err
