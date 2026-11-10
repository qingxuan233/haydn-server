#!/bin/sh
echo "=== dsh web process ==="
ps -ef 2>/dev/null | grep "bin.js web" | grep -v grep
PID=$(ps -ef 2>/dev/null | grep "bin.js web" | grep -v grep | awk '{print $2}' | head -1)
echo "pid=$PID"
if [ -n "$PID" ] && [ -r "/proc/$PID/environ" ]; then
  echo "--- process env (masked) ---"
  tr '\0' '\n' < "/proc/$PID/environ" | grep -E 'OPEN_DESIGN_API_KEY|SILICONFLOW_API_KEY|EASYCLIPROXYAPI_API_KEY|OPENCODE_GO_API_KEY|DEEPSEEK_API_KEY|DSH_PROFILE|DSH_PROFILE_DIR|DSH_HOME' | sed 's/=.*/=SET/'
fi
echo "=== credential file ==="
ls -la /root/.dsh/.credentials.yaml 2>/dev/null
grep -nE '^[A-Za-z_].*:|^  [A-Z_]+:' /root/.dsh/.credentials.yaml 2>/dev/null | head -20
echo "=== where keys might be defined ==="
grep -R -l 'OPEN_DESIGN_API_KEY' /root --include='*.sh' --include='*.conf' --include='*.env' --include='*.yml' --include='*.yaml' --include='*.json' 2>/dev/null | head -15
echo "=== bundles layout ==="
ls /opt/dsh/lib/node_modules/@deepseek-ai/dsh/node_modules 2>/dev/null | head -30
echo "--- dsh package deps ---"
python3 - <<'PY'
import json
p='/opt/dsh/lib/node_modules/@deepseek-ai/dsh/package.json'
try:
    d=json.load(open(p))
except Exception as e:
    print(e); raise SystemExit
print('name',d.get('name'),'version',d.get('version'))
print('deps', list((d.get('dependencies') or {}).keys())[:20])
print('bundles-dir keys', list(d.keys())[:10])
PY
echo "=== dsh CLI help (profile commands) ==="
/usr/local/bin/dsh --help 2>&1 | head -30
